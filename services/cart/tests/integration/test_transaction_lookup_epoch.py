# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for transaction lookup by open epoch (issue #156).

Client-carried cart phase 2 made transaction_no the per-open ``seq``, so it
repeats every open session and no longer names one transaction on its own. The
identity is ``(business_counter, transaction_no)`` — the same tuple the unique
index uses. These tests drive the API with two same-numbered transactions from
different open sessions and assert that:

- supplying business_counter selects the right one,
- omitting it is rejected as ambiguous rather than silently guessing (which
  would void or refund a different sale than the one on the receipt), and
- a return may name an original from another store (the customer brings the
  receipt to whichever store they choose).
"""

import os

import pytest
import pytest_asyncio
from fastapi import status

from app.config.settings import settings


TRANSACTION_NO = 4242
EPOCH_A = 71
EPOCH_B = 72
OTHER_STORE = "9999"


def _api_headers():
    return {"X-API-KEY": "test-api-key-12345", "Content-Type": "application/json"}


def _tenant_id():
    return os.environ.get("TENANT_ID")


def _terminal_id():
    return f"{_tenant_id()}-5678-9"


def _tranlog(business_counter: int, total: float, store_code: str = "5678"):
    """A minimal persisted tranlog: only the fields the lookup and merge touch."""
    return {
        "tenant_id": _tenant_id(),
        "store_code": store_code,
        "store_name": "Test Store",
        "terminal_no": 9,
        "business_counter": business_counter,
        "open_counter": 1,
        "transaction_no": TRANSACTION_NO,
        "transaction_type": 101,
        "business_date": "20260101",
        "receipt_no": business_counter,
        "generate_date_time": "2026-01-01T10:00:00",
        "cart_id": f"epoch-test-{business_counter}",
        "staff": {"id": "S001", "name": "Test Staff"},
        "line_items": [],
        "payments": [],
        "taxes": [],
        "subtotal_discounts": [],
        "sales": {"total_amount_with_tax": total},
    }


@pytest_asyncio.fixture
async def two_epochs():
    """Persist the same transaction_no under two different open epochs."""
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"db_cart_{_tenant_id()}")
    collection = db[settings.DB_COLLECTION_NAME_TRAN_LOG]
    await collection.delete_many({"transaction_no": TRANSACTION_NO})
    await collection.insert_many([_tranlog(EPOCH_A, 100.0), _tranlog(EPOCH_B, 200.0)])
    yield
    await collection.delete_many({"transaction_no": TRANSACTION_NO})


def _transaction_url(store_code: str = "5678", suffix: str = "") -> str:
    return (
        f"/api/v1/tenants/{_tenant_id()}/stores/{store_code}/terminals/9"
        f"/transactions/{TRANSACTION_NO}{suffix}?terminal_id={_terminal_id()}"
    )


@pytest.mark.asyncio
async def test_epoch_selects_the_right_transaction(http_client, two_epochs):
    """business_counter picks out one of two same-numbered transactions."""
    for epoch, expected_total in ((EPOCH_A, 100.0), (EPOCH_B, 200.0)):
        r = await http_client.get(
            _transaction_url() + f"&business_counter={epoch}",
            headers=_api_headers(),
        )
        assert r.status_code == status.HTTP_200_OK, r.text
        data = r.json()["data"]
        assert data["totalAmountWithTax"] == expected_total, (epoch, data)


@pytest.mark.asyncio
async def test_missing_epoch_is_rejected_as_ambiguous(http_client, two_epochs):
    """Without the epoch the number matches both sessions — refuse, don't guess."""
    r = await http_client.get(_transaction_url(), headers=_api_headers())

    assert r.status_code == status.HTTP_409_CONFLICT, r.text
    assert "401513" in r.text, r.text


@pytest.mark.asyncio
async def test_missing_epoch_is_fine_when_unambiguous(http_client):
    """A single match still resolves without an epoch, so legacy clients keep working."""
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"db_cart_{_tenant_id()}")
    collection = db[settings.DB_COLLECTION_NAME_TRAN_LOG]
    await collection.delete_many({"transaction_no": TRANSACTION_NO})
    await collection.insert_one(_tranlog(EPOCH_A, 100.0))
    try:
        r = await http_client.get(_transaction_url(), headers=_api_headers())
        assert r.status_code == status.HTTP_200_OK, r.text
        assert r.json()["data"]["totalAmountWithTax"] == 100.0
    finally:
        await collection.delete_many({"transaction_no": TRANSACTION_NO})


@pytest.mark.asyncio
async def test_return_accepts_an_original_from_another_store(http_client):
    """A return may name an original rung up in a different store of the tenant.

    The path store_code names where the ORIGINAL was rung up, so it is no longer
    required to match the authenticated terminal's store. Reaching "transaction
    not found" proves the store restriction is gone — the request got as far as
    the lookup instead of being rejected up front.
    """
    r = await http_client.post(
        _transaction_url(store_code=OTHER_STORE, suffix="/return"),
        json=[{"paymentCode": "01", "amount": 100.0}],
        headers=_api_headers(),
    )

    assert r.status_code != status.HTTP_400_BAD_REQUEST, (
        f"the cross-store guard should be gone, got: {r.text}"
    )
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text
