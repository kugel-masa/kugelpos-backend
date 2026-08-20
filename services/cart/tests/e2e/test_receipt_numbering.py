# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""E2E coverage for carried receipt numbering against the live stack (issue #166).

Unit tests pin the arithmetic; only the running stack proves that the configured
range actually reaches the finalize path — the range comes from the master-data
settings hierarchy, which the in-process suites do not have.

Before #166 the carried path recorded whatever number the terminal sent, so a
terminal that had counted 1, 2, 3 printed 1, 2, 3 and the configured range was
inert.
"""

import os

import pytest
import pytest_asyncio
from fastapi import status

# What a tenant gets when nobody overrides the range. Asserted as the expected
# seeding, not used as a fallback: a lookup that does not answer is the very
# regression #174 fixed, so it has to fail the suite rather than be papered over.
SHIPPED_START, SHIPPED_END = 111111, 999999
# Per-open seq values these tests carry; kept above the suite's own numbering and
# removed afterwards (see _remove_synthetic_transactions).
SYNTHETIC_SEQ_BASE = 9000


@pytest.fixture
def api_header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


@pytest.fixture(scope="module")
def receipt_range():
    """The range master-data reports — what a client would read (#174).

    Asserting against this rather than a constant makes the suite check the
    thing that matters: cart numbers with the same range the client can see. It
    also keeps the suite honest on a tenant that overrides the range.
    """
    import httpx

    base = os.environ.get("BASE_URL_MASTER_DATA")
    tenant_id = os.environ.get("TENANT_ID")
    header = {"X-API-KEY": os.environ.get("API_KEY")}

    terminal_id = os.environ.get("TERMINAL_ID")

    def value(name):
        # terminal_id is what the API-key credential is checked against; without
        # it the endpoint answers 401 rather than the value.
        response = httpx.get(
            f"{base}/tenants/{tenant_id}/settings/{name}/value?store_code=5678&terminal_no=9&terminal_id={terminal_id}",
            headers=header,
            timeout=10.0,
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"{name} is not readable from master-data ({response.status_code}). "
            "A client derives the printed receipt number from this range, so a lookup "
            "that does not answer is the defect #174 fixed - not a reason to fall back."
        )
        return int(response.json()["data"]["value"])

    start, end = value("RECEIPT_NO_START_VALUE"), value("RECEIPT_NO_END_VALUE")
    # The e2e tenant does not override the range; a deployment that does will see
    # these tests follow its values.
    assert (start, end) == (SHIPPED_START, SHIPPED_END) or start < end
    return start, end, end - start + 1


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


async def _cart_ready_to_bill(http_client, terminal_id, header):
    """Create a cart, add a line, pay it off, and return (cart_id, snapshot)."""
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "Receipt Numbering"},
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
    snapshot = response.json()["data"]["signedSnapshot"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    balance = data["balanceAmount"]
    snapshot = data["signedSnapshot"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"paymentCode": "01", "amount": int(balance)}]},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return cart_id, response.json()["data"]["signedSnapshot"]


async def _bill(http_client, terminal_id, header, cart_id, snapshot, **finalize):
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": finalize},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_carried_counter_prints_inside_the_configured_range(
    http_client, api_header, opened_terminal_id, receipt_range
):
    """Counter 1 prints the configured start value, not 1."""
    start, _, _ = receipt_range
    cart_id, snapshot = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header)

    data = await _bill(
        http_client,
        opened_terminal_id,
        api_header,
        cart_id,
        snapshot,
        seq=9001,
        receiptCounter=1,
        transactionDatetime="2026-08-20T10:00:00",
    )

    assert data["receiptNo"] == start
    assert data["transactionNo"] == 9001  # per-open seq, untouched


@pytest.mark.asyncio
async def test_counter_advances_within_the_range(http_client, api_header, opened_terminal_id, receipt_range):
    start, _, _ = receipt_range
    cart_id, snapshot = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header)

    data = await _bill(
        http_client,
        opened_terminal_id,
        api_header,
        cart_id,
        snapshot,
        seq=9002,
        receiptCounter=5,
        transactionDatetime="2026-08-20T10:01:00",
    )

    assert data["receiptNo"] == start + 4


@pytest.mark.asyncio
async def test_counter_wraps_at_the_end_of_the_range(http_client, api_header, opened_terminal_id, receipt_range):
    """The whole point of the issue: the range must actually cycle."""
    start, _, width = receipt_range
    cart_id, snapshot = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header)

    data = await _bill(
        http_client,
        opened_terminal_id,
        api_header,
        cart_id,
        snapshot,
        seq=9003,
        receiptCounter=width + 1,  # first number of the second cycle
        transactionDatetime="2026-08-20T10:02:00",
    )

    assert data["receiptNo"] == start


@pytest.mark.asyncio
async def test_last_number_of_a_cycle(http_client, api_header, opened_terminal_id, receipt_range):
    _, end, width = receipt_range
    cart_id, snapshot = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header)

    data = await _bill(
        http_client,
        opened_terminal_id,
        api_header,
        cart_id,
        snapshot,
        seq=9004,
        receiptCounter=width,
        transactionDatetime="2026-08-20T10:03:00",
    )

    assert data["receiptNo"] == end


@pytest.mark.asyncio
async def test_pre_166_client_without_a_counter_is_unaffected(http_client, api_header, opened_terminal_id):
    """A terminal that carries only receipt_no keeps working as before."""
    cart_id, snapshot = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header)

    data = await _bill(
        http_client,
        opened_terminal_id,
        api_header,
        cart_id,
        snapshot,
        seq=9005,
        receiptNo=4242,
        transactionDatetime="2026-08-20T10:04:00",
    )

    assert data["receiptNo"] == 4242
