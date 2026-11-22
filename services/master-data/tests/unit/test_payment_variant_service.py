"""PaymentMasterService's handling of payment variants (issue #311)."""

from unittest.mock import AsyncMock

import pytest

from kugel_common.exceptions import DocumentAlreadyExistsException, DocumentNotFoundException

from app.models.documents.payment_master_document import PaymentMasterDocument, PaymentVariant
from app.services.payment_master_service import PaymentMasterService

pytestmark = pytest.mark.asyncio


def _payment(*variants: PaymentVariant) -> PaymentMasterDocument:
    return PaymentMasterDocument(payment_code="11", description="Cashless", variants=list(variants))


def _service(repo: AsyncMock) -> PaymentMasterService:
    return PaymentMasterService(repo)


async def test_adding_a_variant_returns_it():
    repo = AsyncMock()
    repo.add_variant_async.return_value = True
    repo.get_payment_by_code.return_value = _payment(PaymentVariant(variant_code="VISA", name="VISA"))

    variant = await _service(repo).add_variant_async("11", "VISA", "VISA")

    assert variant.variant_code == "VISA"
    added = repo.add_variant_async.call_args.args[1]
    assert (added.variant_code, added.name, added.is_active) == ("VISA", "VISA", True)


async def test_adding_under_an_unknown_payment_method_is_not_found():
    repo = AsyncMock()
    repo.add_variant_async.return_value = False
    repo.get_payment_by_code.return_value = None

    with pytest.raises(DocumentNotFoundException):
        await _service(repo).add_variant_async("99", "VISA", "VISA")


async def test_adding_a_code_the_method_has_is_a_duplicate():
    repo = AsyncMock()
    repo.add_variant_async.return_value = False
    repo.get_payment_by_code.return_value = _payment(PaymentVariant(variant_code="VISA", name="VISA"))

    with pytest.raises(DocumentAlreadyExistsException):
        await _service(repo).add_variant_async("11", "VISA", "VISA")


async def test_the_list_is_in_code_order_and_keeps_stopped_variants():
    repo = AsyncMock()
    repo.get_payment_by_code.return_value = _payment(
        PaymentVariant(variant_code="VISA", name="VISA"),
        PaymentVariant(variant_code="AMEX", name="AMEX", is_active=False),
        PaymentVariant(variant_code="JCB", name="JCB"),
    )

    variants = await _service(repo).get_variants_async("11")

    assert [v.variant_code for v in variants] == ["AMEX", "JCB", "VISA"]


async def test_listing_an_unknown_payment_method_is_not_found():
    repo = AsyncMock()
    repo.get_payment_by_code.return_value = None

    with pytest.raises(DocumentNotFoundException):
        await _service(repo).get_variants_async("99")


async def test_getting_an_unknown_variant_is_not_found():
    repo = AsyncMock()
    repo.get_payment_by_code.return_value = _payment(PaymentVariant(variant_code="VISA", name="VISA"))

    with pytest.raises(DocumentNotFoundException):
        await _service(repo).get_variant_async("11", "JCB")


async def test_updating_returns_the_changed_variant():
    repo = AsyncMock()
    repo.update_variant_async.return_value = True
    repo.get_payment_by_code.return_value = _payment(PaymentVariant(variant_code="VISA", name="VISA card", is_active=False))

    variant = await _service(repo).update_variant_async("11", "VISA", "VISA card", False)

    assert (variant.name, variant.is_active) == ("VISA card", False)
    repo.update_variant_async.assert_awaited_once_with("11", "VISA", "VISA card", False)


@pytest.mark.parametrize("payment", [None, _payment()])
async def test_updating_an_unknown_variant_is_not_found(payment):
    repo = AsyncMock()
    repo.update_variant_async.return_value = False
    repo.get_payment_by_code.return_value = payment

    with pytest.raises(DocumentNotFoundException):
        await _service(repo).update_variant_async("11", "VISA", "VISA", True)
