"""A discount rounding method the discount logic cannot act on is refused.

The discount paths match ROUND_METHOD_FOR_DISCOUNT exactly against RoundMethod.
Any other value - ``round`` in lower case is enough - matched nothing and fell
through to the un-rounded amount: 33.3% off 100 became a 33.3 discount and a
66.7 line, carried into totals, the tax base and the tranlog with nothing in the
logs.
"""

from decimal import Decimal

import pytest
from kugel_common.enums import RoundMethod
from pydantic import ValidationError

from app.config.settings import Settings, settings
from app.models.documents.cart_document import CartDocument
from app.services.logics import add_discount_to_cart_logic, calc_line_item_logic
from app.services.logics.calc_line_item_logic import calc_line_item_async

MISTYPED = ["round", "ROUND", "floor", "HalfUp", ""]


@pytest.mark.parametrize("value", [m.value for m in RoundMethod])
def test_settings_accept_every_round_method(value):
    assert Settings(ROUND_METHOD_FOR_DISCOUNT=value).ROUND_METHOD_FOR_DISCOUNT == value


@pytest.mark.parametrize("value", MISTYPED)
def test_settings_refuse_a_mistyped_round_method(value):
    with pytest.raises(ValidationError) as excinfo:
        Settings(ROUND_METHOD_FOR_DISCOUNT=value)
    assert "ROUND_METHOD_FOR_DISCOUNT" in str(excinfo.value)


@pytest.mark.parametrize(
    "module", [add_discount_to_cart_logic, calc_line_item_logic], ids=["subtotal-discount", "line-discount"]
)
@pytest.mark.parametrize("value", ["round", "HalfUp"])
def test_rounding_refuses_an_unknown_method_instead_of_passing_through(monkeypatch, module, value):
    # Assigning skips validation, which is how a value could still get here.
    monkeypatch.setattr(settings, "ROUND_METHOD_FOR_DISCOUNT", value)

    with pytest.raises(ValueError, match="ROUND_METHOD_FOR_DISCOUNT"):
        getattr(module, "__round")(Decimal("33.3"))


@pytest.mark.asyncio
async def test_line_discount_is_still_rounded_with_the_default(monkeypatch):
    monkeypatch.setattr(settings, "ROUND_METHOD_FOR_DISCOUNT", RoundMethod.Round.value)
    line_item = CartDocument.CartLineItem(
        line_no=1,
        item_code="X",
        unit_price=100,
        quantity=1,
        amount=100,
        discounts=[
            CartDocument.DiscountInfo(
                seq_no=1, discount_type="DiscountPercentage", discount_value=33.3, discount_amount=0, discount_detail=""
            )
        ],
    )

    line_item = await calc_line_item_async(line_item)

    assert line_item.discounts[0].discount_amount == 33.0
    assert line_item.amount == 67.0
