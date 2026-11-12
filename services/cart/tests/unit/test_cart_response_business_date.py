"""A cart response carries the business date the cart was opened on.

cart_repository stamps ``business_date`` from terminal_info when it creates a
cart, and BaseCart inherits the field from BaseTran. transform_cart, which every
cart-shaped response goes through, was the one place that left it out, so all of
them answered ``businessDate: null``. transform_tran always passed it.
"""

from app.api.v1.schemas_transformer import SchemasTransformerV1
from tests.unit.test_tran_total_amount import _external_tax_cart


def test_cart_response_carries_business_date():
    cart = SchemasTransformerV1().transform_cart(_external_tax_cart())

    assert cart.business_date == "20261030"
    assert cart.model_dump(by_alias=True)["businessDate"] == "20261030"


def test_cart_and_tran_agree_on_business_date():
    cart_doc = _external_tax_cart()
    transformer = SchemasTransformerV1()

    assert transformer.transform_cart(cart_doc).business_date == transformer.transform_tran(cart_doc).business_date


def test_cart_without_business_date_still_answers_null():
    cart_doc = _external_tax_cart()
    cart_doc.business_date = None

    assert SchemasTransformerV1().transform_cart(cart_doc).business_date is None
