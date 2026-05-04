# Copyright 2026 masa@kugel
"""Unit tests for tax calculation.

`calc_tax_async` walks the cart's line items, groups them by tax_code,
and computes per-tax target_amount + tax_amount applying tax type
(External/Internal/Exempt) and rounding method (Floor/Round/Ceil).

Bugs in this logic ripple directly into customer receipts (incorrect
tax displayed) and reports (wrong tax-collected totals). Calculation
edge cases — rounding boundaries, mixed-tax carts, cancelled items,
allocated discounts — are tractable as table-driven unit tests but
hard to reproduce reliably end-to-end.
"""
from unittest.mock import AsyncMock

import pytest

from app.models.documents.cart_document import CartDocument
from app.models.documents.tax_master_document import TaxMasterDocument
from app.services.logics.calc_tax_logic import calc_tax_async


def _line(amount: float, tax_code: str = "01", quantity: int = 1,
          discounts_allocated: list = None, is_cancelled: bool = False) -> CartDocument.CartLineItem:
    li = CartDocument.CartLineItem()
    li.amount = amount
    li.tax_code = tax_code
    li.quantity = quantity
    li.discounts_allocated = discounts_allocated or []
    li.is_cancelled = is_cancelled
    return li


def _allocated(amount: float):
    """Build a discount-allocated entry with the given amount."""
    d = CartDocument.DiscountInfo()
    d.discount_amount = amount
    return d


def _tax_master(code: str, tax_type: str, rate: float = 10.0,
                round_method: str = "Floor", round_digit: int = -1,
                tax_name: str = None) -> TaxMasterDocument:
    return TaxMasterDocument(
        tax_code=code, tax_type=tax_type, rate=rate,
        round_method=round_method, round_digit=round_digit,
        tax_name=tax_name or f"{tax_type} {rate}%",
    )


def _cart(*line_items) -> CartDocument:
    cart = CartDocument()
    cart.line_items = list(line_items)
    cart.taxes = []
    return cart


def _mock_repo(*tax_masters) -> AsyncMock:
    by_code = {tm.tax_code: tm for tm in tax_masters}
    repo = AsyncMock()
    async def _lookup(code):
        return by_code[code]
    repo.get_tax_by_code = AsyncMock(side_effect=_lookup)
    return repo


# ---------------------------------------------------------------------------
# External tax (additive)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_external_tax_simple_percentage():
    """External 10% on 1000 yen → 100 yen tax."""
    cart = _cart(_line(amount=1000.0, tax_code="01"))
    repo = _mock_repo(_tax_master("01", "External", rate=10.0))

    result = await calc_tax_async(cart, repo)

    assert len(result.taxes) == 1
    tax = result.taxes[0]
    assert tax.tax_code == "01"
    assert tax.target_amount == 1000.0
    assert tax.tax_amount == 100.0
    assert tax.tax_type == "External"


@pytest.mark.asyncio
async def test_external_tax_floor_rounding():
    """External 10% on 158 yen with Floor rounding → 15 yen (15.8 floored)."""
    cart = _cart(_line(amount=158.0, tax_code="01"))
    repo = _mock_repo(_tax_master("01", "External", rate=10.0,
                                  round_method="Floor", round_digit=-1))

    result = await calc_tax_async(cart, repo)
    assert result.taxes[0].tax_amount == 15.0


@pytest.mark.asyncio
async def test_external_tax_ceil_rounding():
    """External 10% on 158 yen with Ceil rounding → 16 yen (15.8 ceil'd)."""
    cart = _cart(_line(amount=158.0, tax_code="01"))
    repo = _mock_repo(_tax_master("01", "External", rate=10.0,
                                  round_method="Ceil", round_digit=-1))

    result = await calc_tax_async(cart, repo)
    assert result.taxes[0].tax_amount == 16.0


@pytest.mark.asyncio
async def test_external_tax_round_half_up():
    """External 10% on 155 yen with Round (half-up) → 16 yen (15.5)."""
    cart = _cart(_line(amount=155.0, tax_code="01"))
    repo = _mock_repo(_tax_master("01", "External", rate=10.0,
                                  round_method="Round", round_digit=-1))

    result = await calc_tax_async(cart, repo)
    assert result.taxes[0].tax_amount == 16.0


# ---------------------------------------------------------------------------
# Internal tax (extracted from inclusive total)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_internal_tax_extracted_from_inclusive():
    """Internal 10% on 1100 yen (tax-incl) → 100 yen tax extracted."""
    cart = _cart(_line(amount=1100.0, tax_code="02"))
    repo = _mock_repo(_tax_master("02", "Internal", rate=10.0,
                                  round_method="Round", round_digit=-1))

    result = await calc_tax_async(cart, repo)
    # 1100 / 1.1 = 1000, then 1000 * 0.1 = 100
    assert result.taxes[0].tax_amount == 100.0
    assert result.taxes[0].tax_type == "Internal"


# ---------------------------------------------------------------------------
# Exempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exempt_tax_yields_zero():
    """Exempt tax_code → tax_amount=0 regardless of target."""
    cart = _cart(_line(amount=5000.0, tax_code="00"))
    repo = _mock_repo(_tax_master("00", "Exempt", rate=0.0,
                                  round_method="Floor", round_digit=-1))

    result = await calc_tax_async(cart, repo)
    assert result.taxes[0].tax_amount == 0.0
    assert result.taxes[0].tax_type == "Exempt"


# ---------------------------------------------------------------------------
# Multiple tax codes in one cart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_tax_codes_grouped_separately():
    """Two line items with different tax_codes → two tax entries with
    independent target_amount and tax_amount."""
    cart = _cart(
        _line(amount=1000.0, tax_code="01"),  # external 10%
        _line(amount=500.0, tax_code="11"),   # external 8%
    )
    repo = _mock_repo(
        _tax_master("01", "External", rate=10.0),
        _tax_master("11", "External", rate=8.0),
    )

    result = await calc_tax_async(cart, repo)
    assert len(result.taxes) == 2
    by_code = {t.tax_code: t for t in result.taxes}
    assert by_code["01"].tax_amount == 100.0
    assert by_code["11"].tax_amount == 40.0


@pytest.mark.asyncio
async def test_same_tax_code_aggregates_target_amount():
    """Two line items with the SAME tax_code → single tax entry whose
    target_amount is the sum and target_quantity is the sum of quantities."""
    cart = _cart(
        _line(amount=1000.0, tax_code="01", quantity=2),
        _line(amount=500.0, tax_code="01", quantity=3),
    )
    repo = _mock_repo(_tax_master("01", "External", rate=10.0))

    result = await calc_tax_async(cart, repo)
    assert len(result.taxes) == 1
    assert result.taxes[0].target_amount == 1500.0
    assert result.taxes[0].target_quantity == 5
    assert result.taxes[0].tax_amount == 150.0


# ---------------------------------------------------------------------------
# Edge cases that bit us in production
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancelled_line_items_excluded_from_target():
    """A cancelled line item must NOT contribute to target_amount.
    This was the root cause of issue #107 (cancelled-item discount
    aggregation included cancelled items, inflating discounts)."""
    cart = _cart(
        _line(amount=1000.0, tax_code="01"),
        _line(amount=500.0, tax_code="01", is_cancelled=True),
    )
    repo = _mock_repo(_tax_master("01", "External", rate=10.0))

    result = await calc_tax_async(cart, repo)
    assert result.taxes[0].target_amount == 1000.0
    assert result.taxes[0].tax_amount == 100.0


@pytest.mark.asyncio
async def test_allocated_discounts_reduce_target_amount():
    """A discount_allocated of 200 yen on a 1000 yen line reduces the
    target_amount to 800 yen for tax purposes."""
    cart = _cart(_line(
        amount=1000.0,
        tax_code="01",
        discounts_allocated=[_allocated(200.0)],
    ))
    repo = _mock_repo(_tax_master("01", "External", rate=10.0))

    result = await calc_tax_async(cart, repo)
    assert result.taxes[0].target_amount == 800.0
    assert result.taxes[0].tax_amount == 80.0
