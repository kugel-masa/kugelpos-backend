# Copyright 2026 masa@kugel
"""Unit tests for the restore divergence comparison (issue #148).

`staff` is re-injected from the current terminal info on every cache read,
so a staff difference between the presented snapshot and the existing cart
must not count as divergence; transaction content differences must.
"""

from app.models.documents.cart_document import CartDocument
from app.services.cart_service import CartService


def _comparable(cart: CartDocument) -> bytes:
    return CartService._CartService__comparable_cart_bytes(cart)


def _make_cart(**overrides) -> CartDocument:
    cart = CartDocument()
    cart.tenant_id = "T001"
    cart.store_code = "S001"
    cart.terminal_no = 1
    cart.cart_id = "cart-0001"
    cart.status = "EnteringItem"
    cart.balance_amount = 100.0
    cart.staff = CartDocument.Staff(id="S001", name="Staff One")
    for key, value in overrides.items():
        setattr(cart, key, value)
    return cart


class TestComparableCartBytes:
    def test_identical_carts_compare_equal(self):
        assert _comparable(_make_cart()) == _comparable(_make_cart())

    def test_staff_difference_is_not_divergence(self):
        a = _make_cart()
        b = _make_cart(staff=CartDocument.Staff(id="S002", name="Staff Two"))
        assert _comparable(a) == _comparable(b)

    def test_bookkeeping_fields_are_not_divergence(self):
        from datetime import datetime

        a = _make_cart()
        b = _make_cart()
        b.created_at = datetime(2026, 6, 12, 1, 2, 3)
        b.updated_at = datetime(2026, 6, 12, 1, 2, 4)
        b.etag = "different"
        assert _comparable(a) == _comparable(b)

    def test_transaction_content_difference_is_divergence(self):
        a = _make_cart()
        b = _make_cart(balance_amount=200.0)
        assert _comparable(a) != _comparable(b)
