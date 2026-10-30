"""
A line item can no longer be given a quantity below 1, a negative unit price,
or a discount that raises the price, and a quantity or price change that would
leave a fixed discount larger than its line is refused.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums.cart_status import CartStatus
from app.enums.discount_type import DiscountType
from app.exceptions import (
    AmountLessThanDiscountException,
    BalanceLessThanDiscountException,
    InvalidDiscountValueException,
    QuantityBelowMinimumException,
    UnitPriceNegativeException,
)
from app.models.documents.cart_document import CartDocument
from app.services.logics import add_discount_to_cart_logic
from app.services.logics.calc_line_item_logic import calc_line_item_async
from app.services.logics.line_amount_guard import assert_line_amounts_not_negative
from tests.unit.test_cart_service import _build_service, _make_cart_doc

AMOUNT = DiscountType.DiscountAmount.value
PERCENTAGE = DiscountType.DiscountPercentage.value


def _line(unit_price: float, quantity: int, discounts=(), line_no: int = 1) -> CartDocument.CartLineItem:
    line = CartDocument.CartLineItem(line_no=line_no, item_code="A", unit_price=unit_price, quantity=quantity)
    line.discounts = [
        CartDocument.DiscountInfo(seq_no=i + 1, discount_type=t, discount_value=v) for i, (t, v) in enumerate(discounts)
    ]
    return line


async def _recalc(cart, *args, **kwargs):
    for line in cart.line_items:
        await calc_line_item_async(line)
    return cart


@pytest.fixture
def service_for():
    """A service over the given lines whose subtotal recalculates every line for real."""
    patches = []

    def build(*lines):
        cart = _make_cart_doc(status="EnteringItem", line_items=list(lines))
        svc = _build_service(cart_doc=cart)
        svc._subtotal_patcher.stop()
        p = patch("app.services.cart_service.calc_subtotal_logic")
        mock_logic = p.start()
        mock_logic.calc_subtotal_async = AsyncMock(side_effect=_recalc)
        patches.append(p)
        svc.state_manager.set_state(CartStatus.EnteringItem.value)
        return svc

    yield build
    for p in patches:
        p.stop()


def _master_item(unit_price: float) -> MagicMock:
    item = MagicMock()
    item.item_code = "A"
    item.category_code = "001"
    item.description = "Item A"
    item.description_short = "A"
    item.store_price = None
    item.unit_price = unit_price
    item.tax_code = "01"
    item.is_discount_restricted = False
    return item


class TestCalcLineItemWithoutQuantity:
    @pytest.mark.asyncio
    async def test_percentage_discount_on_zero_quantity_does_not_divide_by_zero(self):
        line = await calc_line_item_async(_line(100.0, 0, [(PERCENTAGE, 10.0)]))
        assert line.amount == 0.0
        assert line.discounts[0].discount_amount == 0.0

    @pytest.mark.asyncio
    async def test_fixed_discount_on_zero_quantity_is_not_a_negative_amount(self):
        line = await calc_line_item_async(_line(100.0, 0, [(AMOUNT, 30.0)]))
        assert line.amount == 0.0
        assert line.discounts[0].discount_amount == 0.0

    @pytest.mark.asyncio
    async def test_negative_quantity_is_a_zero_amount(self):
        line = await calc_line_item_async(_line(100.0, -2))
        assert line.amount == 0.0

    @pytest.mark.asyncio
    async def test_positive_quantity_is_calculated_as_before(self):
        line = await calc_line_item_async(_line(100.0, 2, [(AMOUNT, 30.0)]))
        assert line.amount == 170.0


class TestAddItemQuantityAndPrice:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("quantity", [0, -1])
    async def test_quantity_below_one_is_refused_before_the_cart_is_read(self, service_for, quantity):
        svc = service_for()
        with pytest.raises(QuantityBelowMinimumException) as exc:
            await svc.add_item_to_cart_async([{"item_code": "A", "quantity": quantity, "unit_price": None}])
        assert exc.value.error_code == "402007"
        assert exc.value.status_code == 400
        svc.cart_repo.get_cached_cart_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_negative_unit_price_is_refused_before_the_cart_is_read(self, service_for):
        svc = service_for()
        with pytest.raises(UnitPriceNegativeException) as exc:
            await svc.add_item_to_cart_async([{"item_code": "A", "quantity": 1, "unit_price": -100.0}])
        assert exc.value.error_code == "402008"
        assert exc.value.status_code == 400
        svc.cart_repo.get_cached_cart_async.assert_not_awaited()


    @pytest.mark.asyncio
    async def test_a_negative_master_price_is_refused(self, service_for):
        svc = service_for()
        svc.item_master_repo.get_item_by_code_async = AsyncMock(return_value=_master_item(unit_price=-100.0))
        with pytest.raises(UnitPriceNegativeException):
            await svc.add_item_to_cart_async([{"item_code": "A", "quantity": 1, "unit_price": None}])
        svc.cart_repo.cache_cart_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_not_a_number_unit_price_is_refused(self, service_for):
        svc = service_for()
        with pytest.raises(UnitPriceNegativeException):
            await svc.add_item_to_cart_async([{"item_code": "A", "quantity": 1, "unit_price": float("nan")}])

    @pytest.mark.asyncio
    async def test_a_line_left_negative_by_the_subtotal_is_refused(self, service_for):
        # A promotion rate over 100% is not refused where it is registered.
        svc = service_for()
        svc.item_master_repo.get_item_by_code_async = AsyncMock(return_value=_master_item(unit_price=100.0))

        async def over_discounted(cart, *args, **kwargs):
            await _recalc(cart)
            cart.line_items[-1].amount = -20.0
            return cart

        with patch("app.services.cart_service.calc_subtotal_logic") as mock_logic:
            mock_logic.calc_subtotal_async = AsyncMock(side_effect=over_discounted)
            with pytest.raises(AmountLessThanDiscountException):
                await svc.add_item_to_cart_async([{"item_code": "A", "quantity": 1, "unit_price": None}])
        svc.cart_repo.cache_cart_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_positive_master_price_is_added(self, service_for):
        svc = service_for()
        svc.item_master_repo.get_item_by_code_async = AsyncMock(return_value=_master_item(unit_price=100.0))
        cart = await svc.add_item_to_cart_async([{"item_code": "A", "quantity": 2, "unit_price": None}])
        assert cart.line_items[0].amount == 200.0
        svc.cart_repo.cache_cart_async.assert_awaited_once()


class TestQuantityChange:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("quantity", [0, -3])
    async def test_quantity_below_one_is_refused(self, service_for, quantity):
        svc = service_for(_line(100.0, 2))
        with pytest.raises(QuantityBelowMinimumException):
            await svc.update_line_item_quantity_in_cart_async(line_no=1, quantity=quantity)
        svc.cart_repo.cache_cart_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fewer_units_than_a_fixed_discount_covers_is_refused(self, service_for):
        # 689 x 2 with 1,000 off was accepted (1,378 >= 1,000); at 1 unit it is -311.
        svc = service_for(_line(689.0, 2, [(AMOUNT, 1000.0)]))
        with pytest.raises(AmountLessThanDiscountException) as exc:
            await svc.update_line_item_quantity_in_cart_async(line_no=1, quantity=1)
        assert exc.value.error_code == "402002"
        svc.cart_repo.cache_cart_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fewer_units_still_covering_the_discount_is_accepted(self, service_for):
        svc = service_for(_line(689.0, 3, [(AMOUNT, 1000.0)]))
        cart = await svc.update_line_item_quantity_in_cart_async(line_no=1, quantity=2)
        assert cart.line_items[0].amount == 378.0
        svc.cart_repo.cache_cart_async.assert_awaited_once()


class TestUnitPriceChange:
    @pytest.mark.asyncio
    async def test_negative_unit_price_is_refused(self, service_for):
        svc = service_for(_line(100.0, 1))
        with pytest.raises(UnitPriceNegativeException):
            await svc.update_line_item_unit_price_in_cart_async(line_no=1, unit_price=-1.0)
        svc.cart_repo.cache_cart_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_zero_unit_price_is_accepted(self, service_for):
        svc = service_for(_line(100.0, 1))
        cart = await svc.update_line_item_unit_price_in_cart_async(line_no=1, unit_price=0.0)
        assert cart.line_items[0].amount == 0.0

    @pytest.mark.asyncio
    async def test_a_price_below_a_fixed_discount_is_refused(self, service_for):
        # 689 with 600 off, then repriced to 500: 500 - 600 = -100.
        svc = service_for(_line(689.0, 1, [(AMOUNT, 600.0)]))
        with pytest.raises(AmountLessThanDiscountException):
            await svc.update_line_item_unit_price_in_cart_async(line_no=1, unit_price=500.0)
        svc.cart_repo.cache_cart_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_percentage_discount_is_measured_after_recalculation(self, service_for):
        # 1,000 with 50% (500) and 400 off. Repriced to 800 the old 500 would give
        # 800 - 900 = -100, but recalculated it is 800 - 400 - 400 = 0.
        line = _line(1000.0, 1, [(PERCENTAGE, 50.0), (AMOUNT, 400.0)])
        await calc_line_item_async(line)
        svc = service_for(line)
        cart = await svc.update_line_item_unit_price_in_cart_async(line_no=1, unit_price=800.0)
        assert cart.line_items[0].amount == 0.0


class TestLineDiscount:
    @pytest.mark.asyncio
    async def test_fixed_discounts_together_larger_than_the_line_are_refused(self, service_for):
        line = _line(100.0, 1)
        await calc_line_item_async(line)
        svc = service_for(line)
        with pytest.raises(AmountLessThanDiscountException):
            await svc.add_discount_to_line_item_in_cart_async(
                line_no=1, add_discount_list=[_discount(AMOUNT, 60.0), _discount(AMOUNT, 60.0)]
            )
        svc.cart_repo.cache_cart_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fixed_discounts_together_within_the_line_are_accepted(self, service_for):
        line = _line(100.0, 1)
        await calc_line_item_async(line)
        svc = service_for(line)
        cart = await svc.add_discount_to_line_item_in_cart_async(
            line_no=1, add_discount_list=[_discount(AMOUNT, 60.0), _discount(AMOUNT, 40.0)]
        )
        assert cart.line_items[0].amount == 0.0


class TestSubtotalDiscount:
    @pytest.mark.asyncio
    async def test_fixed_discounts_together_larger_than_the_balance_are_refused(self):
        line = _line(1000.0, 1)
        await calc_line_item_async(line)
        cart = _make_cart_doc(balance=1000.0, line_items=[line])
        with pytest.raises(BalanceLessThanDiscountException):
            await add_discount_to_cart_logic.add_discount_to_cart_async(
                cart, [_discount(AMOUNT, 600.0), _discount(AMOUNT, 600.0)]
            )

    @pytest.mark.asyncio
    async def test_a_percentage_and_a_fixed_discount_together_larger_than_the_balance_are_refused(self):
        line = _line(1000.0, 1)
        await calc_line_item_async(line)
        cart = _make_cart_doc(balance=1000.0, line_items=[line])
        with pytest.raises(BalanceLessThanDiscountException):
            await add_discount_to_cart_logic.add_discount_to_cart_async(
                cart, [_discount(PERCENTAGE, 100.0), _discount(AMOUNT, 1.0)]
            )

    @pytest.mark.asyncio
    async def test_replacing_a_subtotal_discount_measures_against_the_balance_before_it(self):
        # 1,000 with 500 off leaves a balance of 500; replacing it with 800 off is valid.
        line = _line(1000.0, 1)
        await calc_line_item_async(line)
        cart = _make_cart_doc(balance=500.0, line_items=[line])
        cart.subtotal_discounts = [
            CartDocument.DiscountInfo(seq_no=1, discount_type=AMOUNT, discount_value=500.0, discount_amount=500.0)
        ]
        await add_discount_to_cart_logic.add_discount_to_cart_async(cart, [_discount(AMOUNT, 800.0)])
        assert [d.discount_amount for d in cart.subtotal_discounts] == [800.0]

    @pytest.mark.asyncio
    async def test_decimal_discounts_adding_up_to_the_balance_are_accepted(self):
        # 0.1 + 0.2 is 0.30000000000000004 as floats.
        line = _line(0.3, 1)
        await calc_line_item_async(line)
        cart = _make_cart_doc(balance=0.3, line_items=[line])
        await add_discount_to_cart_logic.add_discount_to_cart_async(cart, [_discount(AMOUNT, 0.1), _discount(AMOUNT, 0.2)])
        assert len(cart.subtotal_discounts) == 2

    @pytest.mark.asyncio
    async def test_fixed_discounts_together_within_the_balance_are_accepted(self):
        line = _line(1000.0, 1)
        await calc_line_item_async(line)
        cart = _make_cart_doc(balance=1000.0, line_items=[line])
        await add_discount_to_cart_logic.add_discount_to_cart_async(
            cart, [_discount(AMOUNT, 600.0), _discount(AMOUNT, 400.0)]
        )
        assert sum(d.discount_amount for d in cart.subtotal_discounts) == 1000.0


class TestGuard:
    def test_a_cancelled_line_is_not_checked(self):
        cancelled = _line(100.0, 1)
        cancelled.amount = -50.0
        cancelled.is_cancelled = True
        cart = _make_cart_doc(line_items=[cancelled])
        assert_line_amounts_not_negative(cart, context="test")


def _discount(discount_type: str, value: float) -> dict:
    return {"discount_type": discount_type, "discount_value": value, "discount_detail": None}


class TestDiscountValue:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "discount_type, value",
        [(AMOUNT, -500.0), (PERCENTAGE, -10.0), (PERCENTAGE, 150.0), (AMOUNT, float("nan")), (PERCENTAGE, float("nan"))],
    )
    async def test_line_discount_out_of_range_is_refused(self, discount_type, value):
        line = _line(100.0, 1)
        line.amount = 100.0
        with pytest.raises(InvalidDiscountValueException) as exc:
            await add_discount_to_cart_logic.add_discount_to_line_item_async(line, [_discount(discount_type, value)])
        assert exc.value.error_code == "402009"
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "discount_type, value", [(AMOUNT, -500.0), (PERCENTAGE, -10.0), (PERCENTAGE, 150.0)]
    )
    async def test_subtotal_discount_out_of_range_is_refused(self, discount_type, value):
        cart = _make_cart_doc(line_items=[_line(100.0, 1)])
        with pytest.raises(InvalidDiscountValueException):
            await add_discount_to_cart_logic.add_discount_to_cart_async(cart, [_discount(discount_type, value)])

    @pytest.mark.asyncio
    @pytest.mark.parametrize("discount_type, value", [(AMOUNT, 0.0), (AMOUNT, 100.0), (PERCENTAGE, 0.0), (PERCENTAGE, 100.0)])
    async def test_line_discount_at_the_bounds_is_accepted(self, discount_type, value):
        line = _line(100.0, 1)
        line.amount = 100.0
        await add_discount_to_cart_logic.add_discount_to_line_item_async(line, [_discount(discount_type, value)])
        assert line.discounts[0].discount_value == value
