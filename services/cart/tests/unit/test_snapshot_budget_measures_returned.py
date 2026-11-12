"""The snapshot budget is measured against what is actually returned.

The size check runs before the save, and the save is what moves the item
masters scanned by this request into the document. So the check measured a
document without them, while the envelope sent back carried them: the measured
size was short by exactly the masters scanned in that request, and a ceiling
measured against something smaller than what is returned does not bound it.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import CartSizeBudgetExceededException
from tests.unit.test_cart_service import _build_service, _make_cart_doc

BYTES_PER_MASTER = 1000
BUDGET = 1500


def _measure_by_carried_masters(cart_doc, terminal_info):
    """A stand-in envelope size that grows with the masters the document carries."""
    return BYTES_PER_MASTER * len(cart_doc.masters.items)


def _service_holding(masters):
    svc = _build_service()
    svc.item_master_repo.item_master_documents = masters
    return svc


def _cart_carrying(masters):
    cart = _make_cart_doc(status="EnteringItem")
    cart.masters.items = list(masters)
    return cart


def _check(svc, cart):
    with (
        patch("app.services.cart_service.snapshot_service.measure_envelope_bytes", _measure_by_carried_masters),
        patch("app.services.cart_service.snapshot_service.snapshot_size_refuse_bytes", return_value=BUDGET),
    ):
        svc._CartService__check_snapshot_size_budget(cart)


def test_masters_scanned_in_this_request_count_against_the_budget():
    # One master came back in the snapshot; this request scanned a second.
    restored, scanned = MagicMock(name="restored"), MagicMock(name="scanned")
    svc = _service_holding([restored, scanned])
    cart = _cart_carrying([restored])

    with pytest.raises(CartSizeBudgetExceededException):
        _check(svc, cart)


def test_a_cart_within_budget_with_its_scanned_masters_is_accepted():
    master = MagicMock(name="only")
    svc = _service_holding([master])
    cart = _cart_carrying([])

    _check(svc, cart)

    assert cart.masters.items == [master], "the measured document is the one that will be returned"
