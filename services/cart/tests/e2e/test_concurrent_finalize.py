# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Two identical finalizes in flight at once (issue #172).

The cart_id dedupe makes a *sequential* lost-ACK retry converge, and that is
covered elsewhere. A client with a short timeout produces the concurrent version
instead, where the loser's insert is rejected at commit. That used to answer 500
- describing a cleanup error, not the real one - for a transaction the database
had recorded exactly once.
"""

import asyncio
import os

import pytest
import pytest_asyncio
from fastapi import status

SYNTHETIC_SEQ_BASE = 9500


@pytest.fixture
def api_header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


@pytest_asyncio.fixture(autouse=True)
async def _tenant_is_set_up(http_client):
    """Make sure the tenant's indexes exist before racing two finalizes.

    The session fixture drops the tenant database, and the unique index on
    (tenant_id, store_code, cart_id) is what actually stops a second insert -
    without it both concurrent writes land and the count assertion below is
    measuring an unconfigured database rather than the fix.
    """
    from tests.e2e.test_cart import create_tenant, get_authentication_token

    await create_tenant(http_client, await get_authentication_token())


@pytest_asyncio.fixture(autouse=True)
async def _remove_synthetic_transactions(http_client):
    """Leave the shared terminal's numbering as we found it (see #166 tests)."""
    yield
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    await db["log_tran"].delete_many({"transaction_no": {"$gte": SYNTHETIC_SEQ_BASE}})


async def _cart_ready_to_bill(http_client, terminal_id, header):
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={
            # Opened for the carried path (issue #192): every request below
            # carries the snapshot, so nothing is cached to serve a plain one.
            "carrySnapshot": True,
            "transaction_type": 101,
            "user_id": "99",
            "user_name": "Concurrent finalize",
        },
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    created = response.json()["data"]
    cart_id = created["cartId"]
    snapshot = created["signedSnapshot"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=header,
    )
    snapshot = response.json()["data"]["signedSnapshot"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=header,
    )
    data = response.json()["data"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={
            "signedSnapshot": data["signedSnapshot"],
            "payload": [{"paymentCode": "01", "amount": int(data["balanceAmount"])}],
        },
        headers=header,
    )
    return cart_id, response.json()["data"]["signedSnapshot"]


async def _tranlog_count(cart_id):
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    return await db["log_tran"].count_documents({"cart_id": cart_id})


@pytest.mark.asyncio
async def test_concurrent_identical_bills_both_succeed(http_client, api_header, opened_terminal_id):
    cart_id, snapshot = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header)
    request = {
        "signedSnapshot": snapshot,
        "payload": {
            "seq": SYNTHETIC_SEQ_BASE + 1,
            "receiptCounter": 41,
            "transactionDatetime": "2026-08-20T09:00:00",
        },
    }
    url = f"/api/v1/carts/{cart_id}/bill?terminal_id={opened_terminal_id}"

    first, second = await asyncio.gather(
        http_client.post(url, json=request, headers=api_header),
        http_client.post(url, json=request, headers=api_header),
    )

    assert first.status_code == status.HTTP_200_OK, first.text
    assert second.status_code == status.HTTP_200_OK, second.text
    # Both callers see the transaction that was written, with its numbers.
    assert first.json()["data"]["transactionNo"] == second.json()["data"]["transactionNo"]
    assert first.json()["data"]["receiptNo"] == second.json()["data"]["receiptNo"]
    assert await _tranlog_count(cart_id) == 1


@pytest.mark.asyncio
async def test_concurrent_identical_cancels_both_succeed(http_client, api_header, opened_terminal_id):
    """A cancellation takes the same finalize path since #170."""
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={opened_terminal_id}",
        json={
            # Opened for the carried path (issue #192): every request below
            # carries the snapshot, so nothing is cached to serve a plain one.
            "carrySnapshot": True,
            "transaction_type": 101,
            "user_id": "99",
            "user_name": "Concurrent cancel",
        },
        headers=api_header,
    )
    created = response.json()["data"]
    cart_id = created["cartId"]
    snapshot = created["signedSnapshot"]
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={opened_terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=api_header,
    )
    request = {
        "signedSnapshot": response.json()["data"]["signedSnapshot"],
        "payload": {
            "seq": SYNTHETIC_SEQ_BASE + 2,
            "receiptCounter": 42,
            "transactionDatetime": "2026-08-20T09:01:00",
        },
    }
    url = f"/api/v1/carts/{cart_id}/cancel?terminal_id={opened_terminal_id}"

    first, second = await asyncio.gather(
        http_client.post(url, json=request, headers=api_header),
        http_client.post(url, json=request, headers=api_header),
    )

    assert first.status_code == status.HTTP_200_OK, first.text
    assert second.status_code == status.HTTP_200_OK, second.text
    assert first.json()["data"]["receiptNo"] == second.json()["data"]["receiptNo"]
    assert await _tranlog_count(cart_id) == 1
