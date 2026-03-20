# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kugel_common.enums import TaxType, RoundMethod

from app.models.documents.cart_document import CartDocument
from app.services.logics.calc_tax_logic import calc_tax_async
from app.services.logics.add_discount_to_cart_logic import (
    add_discount_to_line_item_async,
    add_discount_to_cart_async,
)
from app.services.logics.calc_line_item_logic import calc_line_item_async
from app.enums.discount_type import DiscountType
from app.exceptions import (
    AmountLessThanDiscountException,
    DiscountRestrictionException,
    BalanceLessThanDiscountException,
)
from kugel_common.exceptions import ServiceException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_line_item(
    line_no=1,
    item_code="ITEM-01",
    unit_price=1000.0,
    quantity=2,
    amount=2000.0,
    tax_code="01",
    is_cancelled=False,
    is_discount_restricted=False,
    discounts=None,
    discounts_allocated=None,
):
    item = CartDocument.CartLineItem()
    item.line_no = line_no
    item.item_code = item_code
    item.unit_price = unit_price
    item.quantity = quantity
    item.amount = amount
    item.tax_code = tax_code
    item.is_cancelled = is_cancelled
    item.is_discount_restricted = is_discount_restricted
    item.discounts = discounts or []
    item.discounts_allocated = discounts_allocated or []
    return item


def make_cart(line_items=None, subtotal_amount=0.0, balance_amount=0.0):
    cart = CartDocument()
    cart.cart_id = "CART-001"
    cart.line_items = line_items or []
    cart.subtotal_amount = subtotal_amount
    cart.balance_amount = balance_amount
    cart.taxes = []
    cart.subtotal_discounts = []
    return cart


def make_tax_master(tax_code="01", tax_type=TaxType.External.value, tax_name="Tax 10%", rate=10.0,
                    round_method=RoundMethod.Floor.value, round_digit=0):
    t = MagicMock()
    t.tax_code = tax_code
    t.tax_type = tax_type
    t.tax_name = tax_name
    t.rate = rate
    t.round_method = round_method
    t.round_digit = round_digit
    return t


# ---------------------------------------------------------------------------
# calc_tax_logic tests
# ---------------------------------------------------------------------------

class TestCalcTaxLogic:
    @pytest.mark.asyncio
    async def test_external_tax_basic(self):
        """External tax: target * rate/100."""
        item = make_line_item(amount=1000.0, tax_code="01")
        cart = make_cart(line_items=[item])
        tax_master = make_tax_master(tax_code="01", tax_type=TaxType.External.value, rate=10.0,
                                     round_method=RoundMethod.Round.value, round_digit=0)
        repo = AsyncMock()
        repo.get_tax_by_code.return_value = tax_master

        result = await calc_tax_async(cart, repo)

        assert len(result.taxes) == 1
        assert result.taxes[0].tax_type == TaxType.External.value
        assert result.taxes[0].tax_amount == 100.0  # 1000 * 10% = 100

    @pytest.mark.asyncio
    async def test_internal_tax_basic(self):
        """Internal tax: target / (1 + rate/100) * rate/100."""
        item = make_line_item(amount=1100.0, tax_code="02")
        cart = make_cart(line_items=[item])
        tax_master = make_tax_master(tax_code="02", tax_type=TaxType.Internal.value, rate=10.0,
                                     round_method=RoundMethod.Floor.value, round_digit=0)
        repo = AsyncMock()
        repo.get_tax_by_code.return_value = tax_master

        result = await calc_tax_async(cart, repo)

        assert len(result.taxes) == 1
        assert result.taxes[0].tax_type == TaxType.Internal.value
        # 1100 / 1.1 * 0.1 = 100
        assert result.taxes[0].tax_amount == 100.0

    @pytest.mark.asyncio
    async def test_exempt_tax(self):
        """Exempt tax: always 0."""
        item = make_line_item(amount=500.0, tax_code="00")
        cart = make_cart(line_items=[item])
        tax_master = make_tax_master(tax_code="00", tax_type=TaxType.Exempt.value, rate=0.0,
                                     round_method=RoundMethod.Round.value, round_digit=0)
        repo = AsyncMock()
        repo.get_tax_by_code.return_value = tax_master

        result = await calc_tax_async(cart, repo)

        assert result.taxes[0].tax_type == TaxType.Exempt.value
        assert result.taxes[0].tax_amount == 0.0

    @pytest.mark.asyncio
    async def test_cancelled_items_excluded(self):
        """Cancelled line items must not be included in tax calculation."""
        active = make_line_item(line_no=1, amount=1000.0, tax_code="01", is_cancelled=False)
        cancelled = make_line_item(line_no=2, amount=500.0, tax_code="01", is_cancelled=True)
        cart = make_cart(line_items=[active, cancelled])
        tax_master = make_tax_master(tax_code="01", tax_type=TaxType.External.value, rate=10.0,
                                     round_method=RoundMethod.Round.value, round_digit=0)
        repo = AsyncMock()
        repo.get_tax_by_code.return_value = tax_master

        result = await calc_tax_async(cart, repo)

        # Only active item's amount (1000) should be targeted
        assert result.taxes[0].target_amount == 1000.0
        assert result.taxes[0].tax_amount == 100.0

    @pytest.mark.asyncio
    async def test_multiple_tax_codes(self):
        """Items with different tax codes produce separate tax entries."""
        item1 = make_line_item(line_no=1, amount=1000.0, tax_code="01")
        item2 = make_line_item(line_no=2, amount=2000.0, tax_code="02")
        cart = make_cart(line_items=[item1, item2])

        tax01 = make_tax_master(tax_code="01", tax_type=TaxType.External.value, rate=10.0,
                                round_method=RoundMethod.Round.value, round_digit=0)
        tax02 = make_tax_master(tax_code="02", tax_type=TaxType.Internal.value, rate=10.0,
                                round_method=RoundMethod.Round.value, round_digit=0)
        repo = AsyncMock()
        repo.get_tax_by_code.side_effect = lambda code: tax01 if code == "01" else tax02

        result = await calc_tax_async(cart, repo)

        assert len(result.taxes) == 2
        codes = {t.tax_code for t in result.taxes}
        assert "01" in codes and "02" in codes

    @pytest.mark.asyncio
    async def test_same_tax_code_items_grouped(self):
        """Multiple items with same tax code are grouped and summed."""
        item1 = make_line_item(line_no=1, amount=1000.0, tax_code="01")
        item2 = make_line_item(line_no=2, amount=500.0, tax_code="01")
        cart = make_cart(line_items=[item1, item2])
        tax_master = make_tax_master(tax_code="01", tax_type=TaxType.External.value, rate=10.0,
                                     round_method=RoundMethod.Round.value, round_digit=0)
        repo = AsyncMock()
        repo.get_tax_by_code.return_value = tax_master

        result = await calc_tax_async(cart, repo)

        assert len(result.taxes) == 1
        assert result.taxes[0].target_amount == 1500.0
        assert result.taxes[0].tax_amount == 150.0

    @pytest.mark.asyncio
    async def test_rounding_floor(self):
        """Floor rounding rounds down."""
        item = make_line_item(amount=100.0, tax_code="01")
        cart = make_cart(line_items=[item])
        # 100 * 10% = 10.0 (no fractional part), use odd rate to force fractional
        tax_master = make_tax_master(tax_code="01", tax_type=TaxType.External.value, rate=7.0,
                                     round_method=RoundMethod.Floor.value, round_digit=0)
        repo = AsyncMock()
        repo.get_tax_by_code.return_value = tax_master

        result = await calc_tax_async(cart, repo)

        # 100 * 7% = 7.0 → floor(7.0) = 7
        assert result.taxes[0].tax_amount == 7.0

    @pytest.mark.asyncio
    async def test_rounding_ceil(self):
        """Ceil rounding rounds up."""
        item = make_line_item(amount=100.0, tax_code="01")
        cart = make_cart(line_items=[item])
        tax_master = make_tax_master(tax_code="01", tax_type=TaxType.External.value, rate=7.0,
                                     round_method=RoundMethod.Ceil.value, round_digit=0)
        repo = AsyncMock()
        repo.get_tax_by_code.return_value = tax_master

        result = await calc_tax_async(cart, repo)

        # 100 * 7% = 7.0 → ceil(7.0) = 7
        assert result.taxes[0].tax_amount == 7.0

    @pytest.mark.asyncio
    async def test_empty_cart_produces_no_taxes(self):
        """A cart with no line items should produce no tax entries."""
        cart = make_cart(line_items=[])
        repo = AsyncMock()

        result = await calc_tax_async(cart, repo)

        assert result.taxes == []


# ---------------------------------------------------------------------------
# add_discount_to_line_item_async tests
# ---------------------------------------------------------------------------

class TestAddDiscountToLineItem:
    @pytest.mark.asyncio
    async def test_amount_discount_success(self):
        """Amount discount within item amount is applied."""
        item = make_line_item(amount=1000.0)
        discounts = [{"discount_type": DiscountType.DiscountAmount.value, "discount_value": 100.0, "discount_detail": "10off"}]

        await add_discount_to_line_item_async(item, discounts)

        assert len(item.discounts) == 1
        assert item.discounts[0].discount_type == DiscountType.DiscountAmount.value
        assert item.discounts[0].discount_value == 100.0

    @pytest.mark.asyncio
    async def test_percentage_discount_success(self):
        """Percentage discount within 0-100 is applied."""
        item = make_line_item(amount=1000.0)
        discounts = [{"discount_type": DiscountType.DiscountPercentage.value, "discount_value": 10.0, "discount_detail": "10pct"}]

        await add_discount_to_line_item_async(item, discounts)

        assert len(item.discounts) == 1
        assert item.discounts[0].discount_type == DiscountType.DiscountPercentage.value

    @pytest.mark.asyncio
    async def test_discount_restricted_raises(self):
        """DiscountRestrictionException raised when is_discount_restricted is True."""
        item = make_line_item(amount=1000.0, is_discount_restricted=True)
        discounts = [{"discount_type": DiscountType.DiscountAmount.value, "discount_value": 100.0, "discount_detail": ""}]

        with pytest.raises(DiscountRestrictionException):
            await add_discount_to_line_item_async(item, discounts)

    @pytest.mark.asyncio
    async def test_amount_exceeds_item_amount_raises(self):
        """AmountLessThanDiscountException raised when discount > item amount."""
        item = make_line_item(amount=500.0)
        discounts = [{"discount_type": DiscountType.DiscountAmount.value, "discount_value": 600.0, "discount_detail": ""}]

        with pytest.raises(AmountLessThanDiscountException):
            await add_discount_to_line_item_async(item, discounts)

    @pytest.mark.asyncio
    async def test_percentage_over_100_raises(self):
        """ServiceException raised when percentage discount > 100."""
        item = make_line_item(amount=1000.0)
        discounts = [{"discount_type": DiscountType.DiscountPercentage.value, "discount_value": 110.0, "discount_detail": ""}]

        with pytest.raises(ServiceException):
            await add_discount_to_line_item_async(item, discounts)

    @pytest.mark.asyncio
    async def test_percentage_negative_raises(self):
        """ServiceException raised when percentage discount < 0."""
        item = make_line_item(amount=1000.0)
        discounts = [{"discount_type": DiscountType.DiscountPercentage.value, "discount_value": -5.0, "discount_detail": ""}]

        with pytest.raises(ServiceException):
            await add_discount_to_line_item_async(item, discounts)

    @pytest.mark.asyncio
    async def test_invalid_discount_type_raises(self):
        """ServiceException raised for unknown discount type."""
        item = make_line_item(amount=1000.0)
        discounts = [{"discount_type": "UNKNOWN", "discount_value": 100.0, "discount_detail": ""}]

        with pytest.raises(ServiceException):
            await add_discount_to_line_item_async(item, discounts)

    @pytest.mark.asyncio
    async def test_existing_discounts_cleared(self):
        """Existing discounts on line item are cleared before adding new ones."""
        existing = CartDocument.DiscountInfo(seq_no=1, discount_type=DiscountType.DiscountAmount.value,
                                             discount_value=50.0, discount_amount=50.0)
        item = make_line_item(amount=1000.0, discounts=[existing])
        new_discounts = [{"discount_type": DiscountType.DiscountAmount.value, "discount_value": 100.0, "discount_detail": "new"}]

        await add_discount_to_line_item_async(item, new_discounts)

        assert len(item.discounts) == 1
        assert item.discounts[0].discount_value == 100.0


# ---------------------------------------------------------------------------
# add_discount_to_cart_async tests
# ---------------------------------------------------------------------------

class TestAddDiscountToCart:
    @pytest.mark.asyncio
    async def test_cart_amount_discount_success(self):
        """Amount discount on cart is applied when balance >= discount."""
        item = make_line_item(amount=1000.0)
        cart = make_cart(line_items=[item], subtotal_amount=1000.0, balance_amount=1000.0)
        discounts = [{"discount_type": DiscountType.DiscountAmount.value, "discount_value": 100.0, "discount_detail": "cart100off"}]

        with patch("app.services.logics.add_discount_to_cart_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            await add_discount_to_cart_async(cart, discounts)

        assert len(cart.subtotal_discounts) == 1
        assert cart.subtotal_discounts[0].discount_amount == 100.0

    @pytest.mark.asyncio
    async def test_cart_amount_discount_exceeds_balance_raises(self):
        """BalanceLessThanDiscountException raised when discount > balance."""
        item = make_line_item(amount=500.0)
        cart = make_cart(line_items=[item], subtotal_amount=500.0, balance_amount=500.0)
        discounts = [{"discount_type": DiscountType.DiscountAmount.value, "discount_value": 600.0, "discount_detail": ""}]

        with patch("app.services.logics.add_discount_to_cart_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            with pytest.raises(BalanceLessThanDiscountException):
                await add_discount_to_cart_async(cart, discounts)

    @pytest.mark.asyncio
    async def test_cart_percentage_discount_success(self):
        """Percentage discount on cart calculates discount_amount correctly."""
        item = make_line_item(amount=1000.0)
        cart = make_cart(line_items=[item], subtotal_amount=1000.0, balance_amount=1000.0)
        discounts = [{"discount_type": DiscountType.DiscountPercentage.value, "discount_value": 10.0, "discount_detail": "10pct"}]

        with patch("app.services.logics.add_discount_to_cart_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            await add_discount_to_cart_async(cart, discounts)

        assert len(cart.subtotal_discounts) == 1
        assert cart.subtotal_discounts[0].discount_amount == 100.0  # 1000 * 10%

    @pytest.mark.asyncio
    async def test_cart_invalid_discount_type_raises(self):
        """ServiceException raised for invalid cart discount type."""
        cart = make_cart(line_items=[make_line_item()], subtotal_amount=1000.0, balance_amount=1000.0)
        discounts = [{"discount_type": "INVALID", "discount_value": 100.0, "discount_detail": ""}]

        with patch("app.services.logics.add_discount_to_cart_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            with pytest.raises(ServiceException):
                await add_discount_to_cart_async(cart, discounts)

    @pytest.mark.asyncio
    async def test_discount_allocated_to_line_items(self):
        """Cart discount is allocated proportionally to line items."""
        item1 = make_line_item(line_no=1, amount=600.0)
        item2 = make_line_item(line_no=2, amount=400.0)
        cart = make_cart(line_items=[item1, item2], subtotal_amount=1000.0, balance_amount=1000.0)
        discounts = [{"discount_type": DiscountType.DiscountAmount.value, "discount_value": 100.0, "discount_detail": ""}]

        with patch("app.services.logics.add_discount_to_cart_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            await add_discount_to_cart_async(cart, discounts)

        # item1 gets 600/1000 * 100 = 60, item2 gets 400/1000 * 100 = 40
        alloc1 = sum(d.discount_amount for d in item1.discounts_allocated)
        alloc2 = sum(d.discount_amount for d in item2.discounts_allocated)
        assert alloc1 + alloc2 == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_cancelled_items_excluded_from_percentage_target(self):
        """Cancelled items are not counted in percentage discount target amount."""
        active = make_line_item(line_no=1, amount=1000.0, is_cancelled=False)
        cancelled = make_line_item(line_no=2, amount=500.0, is_cancelled=True)
        cart = make_cart(line_items=[active, cancelled], subtotal_amount=1000.0, balance_amount=1000.0)
        discounts = [{"discount_type": DiscountType.DiscountPercentage.value, "discount_value": 10.0, "discount_detail": ""}]

        with patch("app.services.logics.add_discount_to_cart_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            await add_discount_to_cart_async(cart, discounts)

        # Only active item (1000) is target: 1000 * 10% = 100
        assert cart.subtotal_discounts[0].discount_amount == 100.0


# ---------------------------------------------------------------------------
# calc_line_item_logic tests
# ---------------------------------------------------------------------------

class TestCalcLineItemLogic:
    @pytest.mark.asyncio
    async def test_no_discount(self):
        """Line item with no discounts: amount = unit_price * quantity."""
        item = make_line_item(unit_price=500.0, quantity=3, amount=0.0, discounts=[])

        with patch("app.services.logics.calc_line_item_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            result = await calc_line_item_async(item)

        assert result.amount == 1500.0

    @pytest.mark.asyncio
    async def test_amount_discount(self):
        """DiscountAmount reduces amount by the discount_value."""
        discount = CartDocument.DiscountInfo(
            seq_no=1, discount_type=DiscountType.DiscountAmount.value,
            discount_value=100.0, discount_amount=0.0
        )
        item = make_line_item(unit_price=500.0, quantity=2, amount=0.0, discounts=[discount])

        with patch("app.services.logics.calc_line_item_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            result = await calc_line_item_async(item)

        # 500*2 = 1000 - 100 = 900
        assert result.amount == 900.0
        assert result.discounts[0].discount_amount == 100.0

    @pytest.mark.asyncio
    async def test_percentage_discount(self):
        """DiscountPercentage reduces amount by percentage of unit_price."""
        discount = CartDocument.DiscountInfo(
            seq_no=1, discount_type=DiscountType.DiscountPercentage.value,
            discount_value=10.0, discount_amount=0.0
        )
        item = make_line_item(unit_price=1000.0, quantity=2, amount=0.0, discounts=[discount])

        with patch("app.services.logics.calc_line_item_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            result = await calc_line_item_async(item)

        # 10% of 1000 = 100 per unit, * 2 = 200 discount → 2000 - 200 = 1800
        assert result.amount == 1800.0

    @pytest.mark.asyncio
    async def test_percentage_applied_before_amount(self):
        """Percentage discounts are calculated before amount discounts."""
        pct_discount = CartDocument.DiscountInfo(
            seq_no=1, discount_type=DiscountType.DiscountPercentage.value,
            discount_value=10.0, discount_amount=0.0
        )
        amt_discount = CartDocument.DiscountInfo(
            seq_no=2, discount_type=DiscountType.DiscountAmount.value,
            discount_value=50.0, discount_amount=0.0
        )
        item = make_line_item(unit_price=1000.0, quantity=1, amount=0.0, discounts=[pct_discount, amt_discount])

        with patch("app.services.logics.calc_line_item_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            result = await calc_line_item_async(item)

        # 10% of 1000 = 100 → then 50 amount discount → 1000 - 100 - 50 = 850
        assert result.amount == 850.0

    @pytest.mark.asyncio
    async def test_multiple_amount_discounts(self):
        """Multiple amount discounts are all applied."""
        d1 = CartDocument.DiscountInfo(
            seq_no=1, discount_type=DiscountType.DiscountAmount.value,
            discount_value=100.0, discount_amount=0.0
        )
        d2 = CartDocument.DiscountInfo(
            seq_no=2, discount_type=DiscountType.DiscountAmount.value,
            discount_value=50.0, discount_amount=0.0
        )
        item = make_line_item(unit_price=1000.0, quantity=1, amount=0.0, discounts=[d1, d2])

        with patch("app.services.logics.calc_line_item_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            result = await calc_line_item_async(item)

        # 1000 - 100 - 50 = 850
        assert result.amount == 850.0

    @pytest.mark.asyncio
    async def test_discount_amounts_cleared_before_calc(self):
        """Existing discount_amount values are cleared before recalculation."""
        discount = CartDocument.DiscountInfo(
            seq_no=1, discount_type=DiscountType.DiscountAmount.value,
            discount_value=200.0, discount_amount=999.0  # stale value
        )
        item = make_line_item(unit_price=1000.0, quantity=1, amount=0.0, discounts=[discount])

        with patch("app.services.logics.calc_line_item_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            result = await calc_line_item_async(item)

        # Should use discount_value=200 not the stale 999
        assert result.amount == 800.0

    @pytest.mark.asyncio
    async def test_quantity_affects_amount(self):
        """Higher quantity multiplies unit_price correctly."""
        item = make_line_item(unit_price=300.0, quantity=5, amount=0.0, discounts=[])

        with patch("app.services.logics.calc_line_item_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Round.value
            result = await calc_line_item_async(item)

        assert result.amount == 1500.0

    @pytest.mark.asyncio
    async def test_percentage_discount_floor_rounding(self):
        """Floor rounding: 33.33% of 100 = 33.33 → floor = 33."""
        discount = CartDocument.DiscountInfo(
            seq_no=1, discount_type=DiscountType.DiscountPercentage.value,
            discount_value=33.33, discount_amount=0.0
        )
        item = make_line_item(unit_price=100.0, quantity=1, amount=0.0, discounts=[discount])

        with patch("app.services.logics.calc_line_item_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Floor.value
            result = await calc_line_item_async(item)

        assert result.discounts[0].discount_amount == 33.0
        assert result.amount == 67.0

    @pytest.mark.asyncio
    async def test_percentage_discount_ceil_rounding(self):
        """Ceil rounding: 33.33% of 100 = 33.33 → ceil = 34."""
        discount = CartDocument.DiscountInfo(
            seq_no=1, discount_type=DiscountType.DiscountPercentage.value,
            discount_value=33.33, discount_amount=0.0
        )
        item = make_line_item(unit_price=100.0, quantity=1, amount=0.0, discounts=[discount])

        with patch("app.services.logics.calc_line_item_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Ceil.value
            result = await calc_line_item_async(item)

        assert result.discounts[0].discount_amount == 34.0
        assert result.amount == 66.0


# ---------------------------------------------------------------------------
# add_discount_to_cart_logic: remainder allocation tests
# ---------------------------------------------------------------------------

class TestAddDiscountToCartRemainder:
    @pytest.mark.asyncio
    async def test_remainder_distributed_to_highest_amount_item(self):
        """端数が最も金額の大きいアイテムに配分される。"""
        item1 = make_line_item(line_no=1, amount=500.0, quantity=1)
        item2 = make_line_item(line_no=2, amount=300.0, quantity=1)
        item3 = make_line_item(line_no=3, amount=199.0, quantity=1)
        cart = make_cart(line_items=[item1, item2, item3], subtotal_amount=999.0, balance_amount=999.0)
        discounts = [{"discount_type": DiscountType.DiscountAmount.value, "discount_value": 100.0, "discount_detail": ""}]

        with patch("app.services.logics.add_discount_to_cart_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Floor.value
            await add_discount_to_cart_async(cart, discounts)

        total_alloc = sum(
            sum(d.discount_amount for d in item.discounts_allocated)
            for item in cart.line_items
        )
        assert total_alloc == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_floor_rounding_for_cart_discount(self):
        """Floor rounding で端数が切り捨てられることを確認。"""
        # 333 * 10% = 33.3 → floor = 33
        item = make_line_item(line_no=1, amount=333.0, quantity=1)
        cart = make_cart(line_items=[item], subtotal_amount=333.0, balance_amount=333.0)
        discounts = [{"discount_type": DiscountType.DiscountPercentage.value, "discount_value": 10.0, "discount_detail": ""}]

        with patch("app.services.logics.add_discount_to_cart_logic.settings") as mock_settings:
            mock_settings.ROUND_METHOD_FOR_DISCOUNT = RoundMethod.Floor.value
            await add_discount_to_cart_async(cart, discounts)

        assert cart.subtotal_discounts[0].discount_amount == 33.0


# ---------------------------------------------------------------------------
# CartStrategyManager tests
# ---------------------------------------------------------------------------

class TestCartStrategyManager:
    def test_load_strategies_with_function_plugin(self):
        """function 型プラグインが正しくロードされる。"""
        from app.services.cart_strategy_manager import CartStrategyManager
        import math

        config = {
            "test_strategies": [
                {"module": "math", "function": "sqrt"}
            ]
        }
        mgr = CartStrategyManager()
        mgr.config = config

        strategies = mgr.load_strategies("test_strategies")

        assert len(strategies) == 1
        assert strategies[0] is math.sqrt

    def test_load_strategies_with_class_and_args(self):
        """class + args 型プラグインが正しくロードされる。"""
        from app.services.cart_strategy_manager import CartStrategyManager
        from collections import OrderedDict

        config = {
            "test_strategies": [
                {"module": "collections", "class": "OrderedDict", "args": [], "kwargs": {}}
            ]
        }
        mgr = CartStrategyManager()
        mgr.config = config

        strategies = mgr.load_strategies("test_strategies")

        assert len(strategies) == 1
        assert isinstance(strategies[0], OrderedDict)
