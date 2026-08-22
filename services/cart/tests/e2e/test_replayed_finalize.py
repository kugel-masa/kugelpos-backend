# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Replaying a pre-bill snapshot of a transaction that is already finalized (issue #152).

The double-count path #148 left open, in full: a terminal holds a snapshot taken
while the cart was still `paying`, the cart is billed, the cart leaves the cache
— and the old snapshot is presented again. Its signature is valid, it is not
itself a terminal-state cart, and the server it reaches has no cart to compare
it against. Before `cart_id` became the transaction identity, the second bill
issued a fresh `transaction_no` and the same sale was recorded twice.

Distinct from #172, which races two finalizes at once and is about the loser of
a commit. This is the sequential case, and it is the one the issue names: the
replay arrives long after the first has been written and acknowledged.

End-to-end because what is being asserted is the row count in the transaction
log — the dedupe lives in a partial-unique index, and an index is not something
a mock has.
"""

import os

import pytest
import pytest_asyncio
from fastapi import status

# Kept above the numbering the rest of the suite produces, and removed
# afterwards; a carried seq has to be unique inside the open session.
SYNTHETIC_SEQ_BASE = 9600


@pytest.fixture
def api_header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


@pytest_asyncio.fixture(autouse=True)
async def _tenant_is_set_up(http_client):
    """The dedupe is a unique index, so the tenant has to be set up.

    Without it both writes land and the count below measures an unconfigured
    database rather than the behaviour (same reason as the #172 suite).
    """
    from tests.e2e.test_cart import create_tenant, get_authentication_token

    await create_tenant(http_client, await get_authentication_token())


@pytest_asyncio.fixture(autouse=True)
async def carts_created():
    """Collect this suite's carts, and take only those back out afterwards.

    Deleting by a `transaction_no >= base` floor is how the neighbouring suites
    do it, and it reaches across them: the bases are 9000, 9500 and 9600, so the
    lowest floor deletes everything above it. Harmless while the suites run one
    after another, and not something to leave for whoever runs them in parallel.
    """
    created = []
    yield created

    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    if created:
        await db["log_tran"].delete_many({"cart_id": {"$in": created}})


async def _cart_ready_to_bill(http_client, terminal_id, header, created=None):
    """Take a cart to `paying` and return its cart_id with the snapshot from there."""
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "Replayed finalize"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    cart_id = response.json()["data"]["cartId"]
    if created is not None:
        created.append(cart_id)

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
    data = response.json()["data"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={
            "signedSnapshot": data["signedSnapshot"],
            "payload": [{"paymentCode": "01", "amount": int(data["balanceAmount"])}],
        },
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return cart_id, response.json()["data"]["signedSnapshot"]


async def _tranlogs_for(cart_id):
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    return await db["log_tran"].find({"cart_id": cart_id}).to_list(length=10)


def _finalize(snapshot, seq, counter):
    return {
        "signedSnapshot": snapshot,
        "payload": {
            "seq": seq,
            "receiptCounter": counter,
            "transactionDatetime": "2026-08-22T09:00:00",
        },
    }


@pytest.mark.asyncio
async def test_the_sale_is_recorded_once(http_client, api_header, opened_terminal_id, carts_created):
    """SC-004 of #148: exactly one recorded transaction per cart_id."""
    cart_id, paying = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header, carts_created)
    url = f"/api/v1/carts/{cart_id}/bill?terminal_id={opened_terminal_id}"
    request = _finalize(paying, SYNTHETIC_SEQ_BASE + 1, 61)

    first = await http_client.post(url, json=request, headers=api_header)
    assert first.status_code == status.HTTP_200_OK, first.text

    # The same pre-bill snapshot, presented again after the cart is finalized and
    # gone from the cache. Nothing about the envelope says it is stale.
    replayed = await http_client.post(url, json=request, headers=api_header)

    assert replayed.status_code == status.HTTP_200_OK, replayed.text
    assert len(await _tranlogs_for(cart_id)) == 1, "the replayed snapshot was recorded as a second sale"


@pytest.mark.asyncio
async def test_the_replay_is_answered_with_the_transaction_that_exists(
    http_client, api_header, opened_terminal_id, carts_created
):
    """Idempotent, not merely refused.

    A terminal replays because it did not hear the first answer; telling it the
    request is invalid leaves it with a sale it cannot account for. It gets the
    numbers that were actually recorded.
    """
    cart_id, paying = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header, carts_created)
    url = f"/api/v1/carts/{cart_id}/bill?terminal_id={opened_terminal_id}"
    request = _finalize(paying, SYNTHETIC_SEQ_BASE + 2, 62)

    first = await http_client.post(url, json=request, headers=api_header)
    replayed = await http_client.post(url, json=request, headers=api_header)

    assert first.status_code == status.HTTP_200_OK, first.text
    assert replayed.status_code == status.HTTP_200_OK, (
        f"the replay was refused rather than answered idempotently: {replayed.text}"
    )
    assert replayed.json()["data"]["transactionNo"] == first.json()["data"]["transactionNo"]
    assert replayed.json()["data"]["receiptNo"] == first.json()["data"]["receiptNo"]


@pytest.mark.asyncio
async def test_a_replay_claiming_other_numbers_still_records_one_sale(
    http_client, api_header, opened_terminal_id, carts_created
):
    """The identity is the cart, not the numbers carried with it.

    `__is_same_finalize` compares (transaction_type, is_cancelled), so a replay
    that claims a different seq and counter for the same cart is still the same
    finalize. It is answered with what was recorded rather than what it asked
    for - which is the honest answer: recording it would be the double-count,
    and refusing it would leave a terminal holding a sale it cannot account for.

    The terminal can see the difference, because the numbers it gets back are
    not the ones it sent. Nothing on the server distinguishes this from an
    identical retry, which is worth knowing when reading the log.
    """
    cart_id, paying = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header, carts_created)
    url = f"/api/v1/carts/{cart_id}/bill?terminal_id={opened_terminal_id}"

    first = await http_client.post(url, json=_finalize(paying, SYNTHETIC_SEQ_BASE + 3, 63), headers=api_header)
    assert first.status_code == status.HTTP_200_OK, first.text

    divergent = await http_client.post(url, json=_finalize(paying, SYNTHETIC_SEQ_BASE + 4, 64), headers=api_header)

    assert divergent.status_code == status.HTTP_200_OK, divergent.text
    assert len(await _tranlogs_for(cart_id)) == 1, "a replay with other numbers was recorded as a second sale"
    # What came back is the recorded transaction, not the one that was claimed.
    assert divergent.json()["data"]["transactionNo"] == SYNTHETIC_SEQ_BASE + 3
    assert divergent.json()["data"]["transactionNo"] == first.json()["data"]["transactionNo"]


@pytest.mark.asyncio
async def test_a_different_operation_on_the_same_cart_is_refused(
    http_client, api_header, opened_terminal_id, carts_created
):
    """A cancel is not a retry of a sale, whatever cart it names.

    Answering that idempotently would tell a terminal its cancellation
    succeeded while a completed sale stands.
    """
    cart_id, paying = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header, carts_created)

    billed = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={opened_terminal_id}",
        json=_finalize(paying, SYNTHETIC_SEQ_BASE + 6, 66),
        headers=api_header,
    )
    assert billed.status_code == status.HTTP_200_OK, billed.text

    cancelled = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel?terminal_id={opened_terminal_id}",
        json=_finalize(paying, SYNTHETIC_SEQ_BASE + 7, 67),
        headers=api_header,
    )

    # The specific refusal, not merely a non-200: with the dedupe gone the unique
    # index refuses the insert too, and a 500 from that would satisfy `!= 200`
    # while saying the opposite about the code under test.
    assert cancelled.status_code == status.HTTP_409_CONFLICT, (
        f"expected the deliberate finalize conflict, got {cancelled.status_code}: {cancelled.text}"
    )
    assert "401511" in cancelled.text, f"not the finalize-conflict error code: {cancelled.text}"
    assert len(await _tranlogs_for(cart_id)) == 1


@pytest.mark.asyncio
async def test_the_recorded_transaction_names_its_cart(http_client, api_header, opened_terminal_id, carts_created):
    """What the dedupe is keyed on has to actually be in the row.

    Historical transactions have no cart_id and the index is partial for that
    reason - so an absent one is not an error anywhere, and nothing else would
    notice if new rows stopped carrying it.
    """
    cart_id, paying = await _cart_ready_to_bill(http_client, opened_terminal_id, api_header, carts_created)

    await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={opened_terminal_id}",
        json=_finalize(paying, SYNTHETIC_SEQ_BASE + 5, 65),
        headers=api_header,
    )

    rows = await _tranlogs_for(cart_id)
    assert len(rows) == 1
    assert rows[0]["cart_id"] == cart_id
