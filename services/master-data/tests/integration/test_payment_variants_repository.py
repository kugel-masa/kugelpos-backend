"""Payment variants are kept on their payment method's document (issue #311).

Uniqueness within a payment method is held by one conditional update, not an
index (a unique index does not stop duplicates inside one document's array), so
the concurrent case is run with asyncio.gather.
"""

import asyncio
import os

import pytest
import pytest_asyncio

from app.config.settings import settings
from app.models.documents.payment_master_document import PaymentMasterDocument, PaymentVariant
from app.models.repositories.payment_master_repository import PaymentMasterRepository

pytestmark = pytest.mark.asyncio

_TENANT_ID = "PVAR1"
_DB_NAME = f"{settings.DB_NAME_PREFIX}_{_TENANT_ID}"


async def _repo() -> PaymentMasterRepository:
    from kugel_common.database import database as db_helper

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    return PaymentMasterRepository(await db_helper.get_db_async(_DB_NAME), _TENANT_ID)


@pytest_asyncio.fixture
async def tenant_db():
    from kugel_common.database import database as db_helper
    from app.database import database_setup

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    client = await db_helper.get_client_async()
    await client.drop_database(_DB_NAME)
    try:
        await database_setup.create_collections(_TENANT_ID)
        for code, description in (("11", "Cashless"), ("12", "Others")):
            repo = await _repo()
            await repo.create_payment_async(
                PaymentMasterDocument(
                    payment_code=code,
                    description=description,
                    limit_amount=0.0,
                    can_refund=True,
                    can_deposit_over=False,
                    can_change=False,
                    is_active=True,
                )
            )
        yield
    finally:
        await client.drop_database(_DB_NAME)


async def _variants(payment_code: str) -> list[PaymentVariant]:
    payment = await (await _repo()).get_payment_by_code(payment_code)
    return payment.variants


async def test_a_variant_is_added(tenant_db):
    added = await (await _repo()).add_variant_async("11", PaymentVariant(variant_code="VISA", name="VISA"))

    assert added is True
    variants = await _variants("11")
    assert [(v.variant_code, v.name, v.is_active) for v in variants] == [("VISA", "VISA", True)]
    assert variants[0].created_at is not None
    assert variants[0].updated_at is None


async def test_the_same_code_is_not_added_twice(tenant_db):
    repo = await _repo()
    await repo.add_variant_async("11", PaymentVariant(variant_code="VISA", name="VISA"))

    again = await repo.add_variant_async("11", PaymentVariant(variant_code="VISA", name="VISA again"))

    assert again is False
    assert [v.name for v in await _variants("11")] == ["VISA"]


async def test_concurrent_additions_of_one_code_land_once(tenant_db):
    repos = [await _repo() for _ in range(5)]

    results = await asyncio.gather(
        *[repo.add_variant_async("11", PaymentVariant(variant_code="VISA", name=f"VISA {i}")) for i, repo in enumerate(repos)]
    )

    assert sorted(results) == [False, False, False, False, True]
    assert len(await _variants("11")) == 1


async def test_another_method_may_use_the_same_code(tenant_db):
    repo = await _repo()
    await repo.add_variant_async("11", PaymentVariant(variant_code="GIFT", name="Gift"))

    assert await repo.add_variant_async("12", PaymentVariant(variant_code="GIFT", name="Gift")) is True


async def test_adding_under_an_unknown_method_matches_nothing(tenant_db):
    assert await (await _repo()).add_variant_async("99", PaymentVariant(variant_code="VISA", name="VISA")) is False


async def test_a_variant_is_changed_and_stamped(tenant_db):
    repo = await _repo()
    await repo.add_variant_async("11", PaymentVariant(variant_code="VISA", name="VISA"))
    await repo.add_variant_async("11", PaymentVariant(variant_code="JCB", name="JCB"))

    changed = await repo.update_variant_async("11", "VISA", "VISA card", False)

    assert changed is True
    payment = await repo.get_payment_by_code("11")
    visa = next(v for v in payment.variants if v.variant_code == "VISA")
    jcb = next(v for v in payment.variants if v.variant_code == "JCB")
    assert (visa.name, visa.is_active) == ("VISA card", False)
    assert visa.updated_at is not None
    assert (jcb.name, jcb.is_active, jcb.updated_at) == ("JCB", True, None)
    assert payment.updated_at is not None


async def test_changing_an_unknown_variant_matches_nothing(tenant_db):
    assert await (await _repo()).update_variant_async("11", "VISA", "VISA", True) is False


async def test_updating_the_payment_method_keeps_its_variants(tenant_db):
    repo = await _repo()
    await repo.add_variant_async("11", PaymentVariant(variant_code="VISA", name="VISA"))

    await repo.update_payment_async(
        "11",
        {
            "description": "Cards",
            "limit_amount": 100.0,
            "can_refund": True,
            "can_deposit_over": False,
            "can_change": False,
            "is_active": True,
        },
    )

    payment = await repo.get_payment_by_code("11")
    assert payment.description == "Cards"
    assert [v.variant_code for v in payment.variants] == ["VISA"]


async def test_deleting_the_payment_method_takes_its_variants(tenant_db):
    repo = await _repo()
    await repo.add_variant_async("11", PaymentVariant(variant_code="VISA", name="VISA"))

    await repo.delete_payment_async("11")

    assert await repo.get_payment_by_code("11") is None
    await repo.create_payment_async(
        PaymentMasterDocument(payment_code="11", description="Cashless", limit_amount=0.0, is_active=True)
    )
    assert await _variants("11") == []
