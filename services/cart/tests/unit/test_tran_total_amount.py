"""
A transaction response carries the same totalAmount as the cart it came from:
the total after discounts, without the external tax. The tax-inclusive figure
is totalAmountWithTax on both.
"""

from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.models.documents.cart_document import CartDocument
from kugel_common.models.documents.base_tranlog import BaseTransaction


def _external_tax_cart() -> CartDocument:
    cart = CartDocument(
        tenant_id="T0001",
        store_code="S001",
        terminal_no=1,
        transaction_no=1,
        receipt_no=1,
        transaction_type=101,
        business_date="20261030",
        generate_date_time="2026-10-30T00:00:00",
    )
    cart.cart_id = "cart-1"
    cart.status = "completed"
    cart.staff = BaseTransaction.Staff(id="ST01", name="staff")
    cart.subtotal_amount = 1000.0
    cart.sales = BaseTransaction.SalesInfo(
        total_amount=1000.0,
        total_amount_with_tax=1100.0,
        tax_amount=100.0,
        total_quantity=1,
    )
    cart.line_items = []
    cart.payments = []
    cart.taxes = []
    cart.subtotal_discounts = []
    return cart


def test_tran_total_amount_excludes_external_tax():
    tran = SchemasTransformerV1().transform_tran(_external_tax_cart())

    assert tran.total_amount == 1000.0
    assert tran.total_amount_with_tax == 1100.0


def test_tran_and_cart_agree_on_total_amount():
    cart_doc = _external_tax_cart()
    transformer = SchemasTransformerV1()

    cart = transformer.transform_cart(cart_doc)
    tran = transformer.transform_tran(cart_doc)

    assert tran.total_amount == cart.total_amount
    assert tran.total_amount_with_tax == cart.total_amount_with_tax


def test_tran_response_serialises_both_totals():
    body = SchemasTransformerV1().transform_tran(_external_tax_cart()).model_dump(by_alias=True)

    assert body["totalAmount"] == 1000.0
    assert body["totalAmountWithTax"] == 1100.0
