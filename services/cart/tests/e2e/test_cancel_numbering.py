# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""A cancellation is numbered from the terminal's series (issue #170).

Before this, `POST /carts/{cart_id}/cancel` took no finalize context, so a
cancelled sale drew its numbers from the server-side counters. Those share the
(business_counter, transaction_no) key space with the carried per-open seq, so a
cancellation could take an identity a sale in the same open session had used —
rejected by the unique index where it exists, silently duplicated where it does
not.
"""

import os

import pytest
import pytest_asyncio
from fastapi import status

RECEIPT_NO_START = 111111
# Per-open seq values these tests carry; kept above the suite's own numbering and
# removed afterwards (see _remove_synthetic_transactions).
SYNTHETIC_SEQ_BASE = 8800


@pytest.fixture
def api_header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


@pytest_asyncio.fixture(autouse=True)
async def _remove_synthetic_transactions(http_client):
    """Take the synthetic numbering rows back out of the shared terminal.

    These tests deliberately carry per-open seq values far above the ones the
    rest of the suite produces, because a carried seq has to be unique inside the
    open session. The transaction list defaults to `sort=transaction_no:-1`
    (`api/v1/tran.py:207`), so leaving them behind pushes other tests' rows off
    page 1 — a test that asserts on `limit=10` then fails for no reason of its
    own. Cleaning up keeps the shared session as we found it.
    """
    yield
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    await db["log_tran"].delete_many({"transaction_no": {"$gte": SYNTHETIC_SEQ_BASE}})


async def _cart_with_item(http_client, terminal_id, header):
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "Cancel Numbering"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    cart_id = response.json()["data"]["cartId"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return cart_id, response.json()["data"]["signedSnapshot"]


@pytest.mark.asyncio
async def test_carried_cancel_uses_the_terminals_numbering(http_client, api_header, opened_terminal_id):
    cart_id, snapshot = await _cart_with_item(http_client, opened_terminal_id, api_header)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel?terminal_id={opened_terminal_id}",
        json={
            "signedSnapshot": snapshot,
            "payload": {
                "seq": 8801,
                "receiptCounter": 3,
                "transactionDatetime": "2026-08-20T13:00:00",
            },
        },
        headers=api_header,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["cartStatus"] == "Cancelled"
    # Numbered from what the terminal carried, not from a server counter.
    assert data["transactionNo"] == 8801
    assert data["receiptNo"] == RECEIPT_NO_START + 2


@pytest.mark.asyncio
async def test_carried_cancel_does_not_collide_with_a_sale(http_client, api_header, opened_terminal_id):
    """The point of the issue: two transactions in one open session, two identities."""
    # A sale on the carried path.
    cart_id, snapshot = await _cart_with_item(http_client, opened_terminal_id, api_header)
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={opened_terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=api_header,
    )
    data = response.json()["data"]
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={opened_terminal_id}",
        json={
            "signedSnapshot": data["signedSnapshot"],
            "payload": [{"paymentCode": "01", "amount": int(data["balanceAmount"])}],
        },
        headers=api_header,
    )
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={opened_terminal_id}",
        json={
            "signedSnapshot": response.json()["data"]["signedSnapshot"],
            "payload": {"seq": 8810, "receiptCounter": 10, "transactionDatetime": "2026-08-20T13:10:00"},
        },
        headers=api_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    sale = response.json()["data"]

    # A cancellation in the same open session, carrying the next numbers.
    cancel_cart_id, cancel_snapshot = await _cart_with_item(http_client, opened_terminal_id, api_header)
    response = await http_client.post(
        f"/api/v1/carts/{cancel_cart_id}/cancel?terminal_id={opened_terminal_id}",
        json={
            "signedSnapshot": cancel_snapshot,
            "payload": {"seq": 8811, "receiptCounter": 11, "transactionDatetime": "2026-08-20T13:11:00"},
        },
        headers=api_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    cancelled = response.json()["data"]

    assert sale["transactionNo"] != cancelled["transactionNo"]
    assert sale["receiptNo"] != cancelled["receiptNo"]
    assert cancelled["receiptNo"] == RECEIPT_NO_START + 10


@pytest.mark.asyncio
async def test_legacy_cancel_is_unaffected(http_client, api_header, opened_terminal_id):
    """A phase 1 client cancels with no snapshot and no context, as before."""
    cart_id, _ = await _cart_with_item(http_client, opened_terminal_id, api_header)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel?terminal_id={opened_terminal_id}",
        headers=api_header,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["cartStatus"] == "Cancelled"
    assert data["receiptNo"] is not None
