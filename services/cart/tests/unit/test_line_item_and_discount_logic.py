# Copyright 2026 masa@kugel
"""Unit tests for line-item and discount logic.

  * `calc_line_item_async`             : amount = qty × unit_price − discounts
  * `add_discount_to_line_item_async`  : line-level discount validation
  * `add_discount_to_cart_async`       : subtotal-level discount validation

These functions decide how much money each customer pays. Bugs here
mean either undercharging (revenue loss) or overcharging (legal /
trust impact). Pure-function logic with branching on discount type +
restriction flags — perfect candidates for unit tests.
"""
import pytest

from app.enums.discount_type import DiscountType
from app.exceptions import (
    AmountLessThanDiscountException,
    BalanceLessThanDiscountException,
    DiscountRestrictionException,
)
from app.models.documents.cart_document import CartDocument
from app.services.logics.add_discount_to_cart_logic import (
    add_discount_to_cart_async,
    add_discount_to_line_item_async,
)
from app.services.logics.calc_line_item_logic import calc_line_item_async
from kugel_common.exceptions import ServiceException


def _line(unit_price=100.0, quantity=1, discounts=None,
          is_discount_restricted=False, line_no=1, amount=None):
    li = CartDocument.CartLineItem()
    li.line_no = line_no
    li.unit_price = unit_price
    li.quantity = quantity
    li.discounts = discounts or []
    li.is_discount_restricted = is_discount_restricted
    li.amount = amount if amount is not None else unit_price * quantity
    return li


def _discount(d_type, d_value, d_amount=0.0):
    d = CartDocument.DiscountInfo()
    d.discount_type = d_type
    d.discount_value = d_value
    d.discount_amount = d_amount
    return d


# ===========================================================================
# calc_line_item_async — amount = qty × unit_price − discounts
# ===========================================================================


class TestCalcLineItem:
    @pytest.mark.asyncio
    async def test_no_discount_simple_amount(self):
        """100 × 3 = 300 with no discounts."""
        li = _line(unit_price=100.0, quantity=3)
        result = await calc_line_item_async(li)
        assert result.amount == 300.0

    @pytest.mark.asyncio
    async def test_amount_discount_subtracts_directly(self):
        """100 × 2 − 50 = 150 for a flat 50-yen discount."""
        li = _line(unit_price=100.0, quantity=2,
                   discounts=[_discount(DiscountType.DiscountAmount.value, 50.0)])
        result = await calc_line_item_async(li)
        assert result.amount == 150.0
        assert result.discounts[0].discount_amount == 50.0

    @pytest.mark.asyncio
    async def test_percentage_discount_applies_to_unit_price_per_item(self):
        """100 × 2 with 10% discount → discount = 100*0.10 *2 = 20, final = 180."""
        li = _line(unit_price=100.0, quantity=2,
                   discounts=[_discount(DiscountType.DiscountPercentage.value, 10.0)])
        result = await calc_line_item_async(li)
        assert result.discounts[0].discount_amount == 20.0
        assert result.amount == 180.0

    @pytest.mark.asyncio
    async def test_percentage_then_amount_combined(self):
        """When both discount types present, percentage runs first, then amount.
        100×2=200 → -10% (20) → -fixed 30 → final 150."""
        li = _line(unit_price=100.0, quantity=2, discounts=[
            _discount(DiscountType.DiscountPercentage.value, 10.0),
            _discount(DiscountType.DiscountAmount.value, 30.0),
        ])
        result = await calc_line_item_async(li)
        # Percentage discount is computed first and the fixed-amount discount
        # is applied on top.
        assert result.amount == 150.0


# ===========================================================================
# add_discount_to_line_item_async — line-level discount validation
# ===========================================================================


class TestLineItemDiscountValidation:
    @pytest.mark.asyncio
    async def test_restricted_line_rejects_any_discount(self):
        """is_discount_restricted=True → DiscountRestrictionException.
        Used for items like cigarettes where discounts are illegal."""
        li = _line(amount=100.0, is_discount_restricted=True)
        with pytest.raises(DiscountRestrictionException):
            await add_discount_to_line_item_async(li, [
                {"discount_type": DiscountType.DiscountAmount.value,
                 "discount_value": 10.0, "discount_detail": ""},
            ])

    @pytest.mark.asyncio
    async def test_amount_exceeding_line_total_rejected(self):
        """Discount amount > line amount → AmountLessThanDiscountException.
        Prevents negative-amount line items."""
        li = _line(amount=100.0)
        with pytest.raises(AmountLessThanDiscountException):
            await add_discount_to_line_item_async(li, [
                {"discount_type": DiscountType.DiscountAmount.value,
                 "discount_value": 200.0, "discount_detail": "too big"},
            ])

    @pytest.mark.asyncio
    async def test_percentage_over_100_rejected(self):
        """Percentage > 100 (or < 0) is a domain error."""
        li = _line(amount=100.0)
        with pytest.raises(ServiceException):
            await add_discount_to_line_item_async(li, [
                {"discount_type": DiscountType.DiscountPercentage.value,
                 "discount_value": 150.0, "discount_detail": ""},
            ])

    @pytest.mark.asyncio
    async def test_negative_percentage_rejected(self):
        """Percentage < 0 is a domain error (negative discount = price hike)."""
        li = _line(amount=100.0)
        with pytest.raises(ServiceException):
            await add_discount_to_line_item_async(li, [
                {"discount_type": DiscountType.DiscountPercentage.value,
                 "discount_value": -5.0, "discount_detail": ""},
            ])

    @pytest.mark.asyncio
    async def test_unknown_discount_type_rejected(self):
        """Discount type that's neither Amount nor Percentage → reject.
        Prevents typos / forged client requests from creating arbitrary discounts."""
        li = _line(amount=100.0)
        with pytest.raises(ServiceException):
            await add_discount_to_line_item_async(li, [
                {"discount_type": "FreeFood",
                 "discount_value": 100.0, "discount_detail": ""},
            ])

    @pytest.mark.asyncio
    async def test_valid_discount_replaces_existing_discounts(self):
        """Calling add_discount with a new list REPLACES the line's existing
        discounts (this is the contract — POS UI flow re-sends the full list)."""
        li = _line(amount=100.0,
                   discounts=[_discount(DiscountType.DiscountPercentage.value, 5.0, 5.0)])
        await add_discount_to_line_item_async(li, [
            {"discount_type": DiscountType.DiscountAmount.value,
             "discount_value": 10.0, "discount_detail": ""},
        ])
        assert len(li.discounts) == 1
        assert li.discounts[0].discount_value == 10.0


# ===========================================================================
# add_discount_to_cart_async — subtotal-level discount validation
# ===========================================================================


def _cart_for_subtotal(balance: float = 200.0) -> CartDocument:
    cart = CartDocument()
    cart.cart_id = "test-cart"
    cart.balance_amount = balance
    cart.subtotal_amount = balance
    cart.subtotal_discounts = []
    cart.line_items = [
        _line(unit_price=100.0, quantity=2, line_no=1, amount=200.0),
    ]
    return cart


class TestCartLevelDiscountValidation:
    @pytest.mark.asyncio
    async def test_amount_exceeding_balance_rejected(self):
        """Subtotal-level discount must NOT exceed cart balance.
        Without this check, customer would owe a negative amount."""
        cart = _cart_for_subtotal(balance=100.0)
        with pytest.raises(BalanceLessThanDiscountException):
            await add_discount_to_cart_async(cart, [
                {"discount_type": DiscountType.DiscountAmount.value,
                 "discount_value": 200.0, "discount_detail": "too big"},
            ])
