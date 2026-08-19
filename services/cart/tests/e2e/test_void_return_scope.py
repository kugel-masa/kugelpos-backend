# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""E2E coverage for what void and return may reach (issue #156).

The two operations deliberately have different reach:

- **void** reverses a sale at the register while the drawer and the day's totals
  are still open, so it is confined to this terminal, this business date, and
  this open session.
- **return** books its own transaction, so it may reference an original from any
  store or terminal of the tenant and from any past session — the customer walks
  in with a receipt from wherever and whenever.

Both are also affected by transaction_no becoming the per-open seq: it repeats
every session, so the original is only pinned down together with
``business_counter``. These tests drive the live stack for each of those.
"""

import os

import pytest
from fastapi import status

from app.config.settings import settings


OTHER_STORE = "7777"
OTHER_TERMINAL = 4
PAST_EPOCH_OFFSET = 5


def _api_header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


def _tenant_id():
    return os.environ.get("TENANT_ID")


async def _cart_db():
    from kugel_common.database import database as db_helper

    return await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{_tenant_id()}")


async def _terminal_state():
    """The terminal's current business date and open epoch, from its own record."""
    from httpx import AsyncClient

    terminal_id = os.environ.get("TERMINAL_ID")
    async with AsyncClient(base_url=os.environ.get("BASE_URL_TERMINAL")) as client:
        response = await client.get(f"/terminals/{terminal_id}", headers=_api_header())
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    return data["businessDate"], data["businessCounter"]


async def _insert_sale(
    *, store_code, terminal_no, business_date, business_counter, transaction_no, cart_id, purge_first=True
):
    """Persist a completed sale directly, to stage originals this session cannot make.

    ``purge_first`` clears same-numbered leftovers; the ambiguity test turns it off
    because it deliberately wants two rows sharing one transaction_no.
    """
    db = await _cart_db()
    collection = db[settings.DB_COLLECTION_NAME_TRAN_LOG]
    if purge_first:
        await collection.delete_many({"transaction_no": transaction_no, "store_code": store_code})
    await collection.insert_one(
        {
            "tenant_id": _tenant_id(),
            "store_code": store_code,
            "store_name": f"Store {store_code}",
            "terminal_no": terminal_no,
            "business_date": business_date,
            "business_counter": business_counter,
            "open_counter": 1,
            "transaction_no": transaction_no,
            "transaction_type": 101,
            "receipt_no": transaction_no,
            "generate_date_time": "2026-01-01T10:00:00",
            "cart_id": cart_id,
            "staff": {"id": "S001", "name": "Staff1"},
            "line_items": [],
            # A void/return reverses the original's tender, so the payment code
            # presented must exist on the original.
            "payments": [
                {"payment_no": 1, "payment_code": "01", "description": "Cash", "amount": 550.0,
                 "deposit_amount": 550.0}
            ],
            "taxes": [],
            "subtotal_discounts": [],
            "sales": {"total_amount_with_tax": 550.0, "total_amount": 500.0},
        }
    )


async def _cleanup(transaction_no, store_code, cart_id):
    db = await _cart_db()
    await db[settings.DB_COLLECTION_NAME_TRAN_LOG].delete_many({"transaction_no": transaction_no})
    await db[settings.DB_COLLECTION_NAME_TRAN_LOG].delete_many({"origin.cart_id": cart_id})
    await db[settings.DB_COLLECTION_NAME_TRAN_LOG].delete_many({"origin.transaction_no": transaction_no})
    await db[settings.DB_COLLECTION_NAME_STATUS_TRAN].delete_many({"store_code": store_code})


def _url(store_code, terminal_no, transaction_no, action, business_counter=None):
    terminal_id = os.environ.get("TERMINAL_ID")
    url = (
        f"/api/v1/tenants/{_tenant_id()}/stores/{store_code}/terminals/{terminal_no}"
        f"/transactions/{transaction_no}/{action}?terminal_id={terminal_id}"
    )
    if business_counter is not None:
        url += f"&business_counter={business_counter}"
    return url


# =========================================================================
# void: this terminal, this business date, this open session
# =========================================================================


@pytest.mark.asyncio
async def test_void_rejects_a_past_open_session(http_client, opened_terminal_id):
    """A sale from an earlier session is settled; void must refuse it.

    Before this rule the only thing standing between a caller and an old sale was
    whether its number happened to be ambiguous, which is not a rule at all.
    """
    business_date, business_counter = await _terminal_state()
    store_code = os.environ.get("STORE_CODE")
    terminal_no = int(os.environ.get("TERMINAL_ID").split("-")[-1])
    transaction_no = 7101
    cart_id = "e2e-scope-past-session"

    await _insert_sale(
        store_code=store_code,
        terminal_no=terminal_no,
        business_date=business_date,
        business_counter=business_counter - PAST_EPOCH_OFFSET,
        transaction_no=transaction_no,
        cart_id=cart_id,
    )
    try:
        response = await http_client.post(
            _url(store_code, terminal_no, transaction_no, "void",
                 business_counter=business_counter - PAST_EPOCH_OFFSET),
            json=[{"paymentCode": "01", "amount": 550.0}],
            headers=_api_header(),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert "401514" in response.text, response.text
    finally:
        await _cleanup(transaction_no, store_code, cart_id)


@pytest.mark.asyncio
async def test_void_rejects_a_past_business_date(http_client, opened_terminal_id):
    """Yesterday's sale would edit a closed day's totals."""
    _, business_counter = await _terminal_state()
    store_code = os.environ.get("STORE_CODE")
    terminal_no = int(os.environ.get("TERMINAL_ID").split("-")[-1])
    transaction_no = 7102
    cart_id = "e2e-scope-past-date"

    await _insert_sale(
        store_code=store_code,
        terminal_no=terminal_no,
        business_date="20200101",
        business_counter=business_counter,
        transaction_no=transaction_no,
        cart_id=cart_id,
    )
    try:
        response = await http_client.post(
            _url(store_code, terminal_no, transaction_no, "void", business_counter=business_counter),
            json=[{"paymentCode": "01", "amount": 550.0}],
            headers=_api_header(),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert "401514" in response.text, response.text
    finally:
        await _cleanup(transaction_no, store_code, cart_id)


@pytest.mark.asyncio
async def test_void_rejects_another_terminal(http_client, opened_terminal_id):
    """Void is this terminal's own drawer only."""
    business_date, business_counter = await _terminal_state()
    store_code = os.environ.get("STORE_CODE")
    transaction_no = 7103
    cart_id = "e2e-scope-other-terminal"

    await _insert_sale(
        store_code=store_code,
        terminal_no=OTHER_TERMINAL,
        business_date=business_date,
        business_counter=business_counter,
        transaction_no=transaction_no,
        cart_id=cart_id,
    )
    try:
        response = await http_client.post(
            _url(store_code, OTHER_TERMINAL, transaction_no, "void", business_counter=business_counter),
            json=[{"paymentCode": "01", "amount": 550.0}],
            headers=_api_header(),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    finally:
        await _cleanup(transaction_no, store_code, cart_id)


@pytest.mark.asyncio
async def test_void_accepts_the_current_session_with_a_carried_epoch(http_client, opened_terminal_id):
    """The permitted side of the same boundary, addressed by its epoch."""
    business_date, business_counter = await _terminal_state()
    store_code = os.environ.get("STORE_CODE")
    terminal_no = int(os.environ.get("TERMINAL_ID").split("-")[-1])
    transaction_no = 7104
    cart_id = "e2e-scope-current-session"

    await _insert_sale(
        store_code=store_code,
        terminal_no=terminal_no,
        business_date=business_date,
        business_counter=business_counter,
        transaction_no=transaction_no,
        cart_id=cart_id,
    )
    try:
        response = await http_client.post(
            _url(store_code, terminal_no, transaction_no, "void", business_counter=business_counter),
            json=[{"paymentCode": "01", "amount": 550.0}],
            headers=_api_header(),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["data"]["transactionType"] == 201  # VoidSales
    finally:
        await _cleanup(transaction_no, store_code, cart_id)


# =========================================================================
# return: any store, any terminal, any past session
# =========================================================================


@pytest.mark.asyncio
async def test_return_accepts_another_store_and_a_past_session(http_client, opened_terminal_id):
    """The customer brings a receipt from another store, rung up long ago.

    The return is still booked against THIS terminal — inheriting the original's
    store while carrying this terminal's counters would write a numbering tuple
    belonging to neither.
    """
    _, business_counter = await _terminal_state()
    transaction_no = 7201
    cart_id = "e2e-scope-cross-store"
    past_epoch = max(business_counter - PAST_EPOCH_OFFSET, 1)

    await _insert_sale(
        store_code=OTHER_STORE,
        terminal_no=OTHER_TERMINAL,
        business_date="20200101",
        business_counter=past_epoch,
        transaction_no=transaction_no,
        cart_id=cart_id,
    )
    try:
        response = await http_client.post(
            _url(OTHER_STORE, OTHER_TERMINAL, transaction_no, "return", business_counter=past_epoch),
            json=[{"paymentCode": "01", "amount": 550.0}],
            headers=_api_header(),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()["data"]
        assert data["transactionType"] == 102  # ReturnSales
        assert data["storeCode"] == os.environ.get("STORE_CODE"), data
        assert data["terminalNo"] == int(os.environ.get("TERMINAL_ID").split("-")[-1]), data

        db = await _cart_db()
        saved = await db[settings.DB_COLLECTION_NAME_TRAN_LOG].find_one(
            {"origin.transaction_no": transaction_no}
        )
        assert saved is not None
        # The origin pins the original by store + terminal + epoch + number.
        assert saved["origin"]["store_code"] == OTHER_STORE
        assert saved["origin"]["terminal_no"] == OTHER_TERMINAL
        assert saved["origin"]["business_counter"] == past_epoch

        # The refund is recorded against the ORIGINAL's identity, epoch included.
        recorded = await db[settings.DB_COLLECTION_NAME_STATUS_TRAN].find_one(
            {"store_code": OTHER_STORE, "transaction_no": transaction_no}
        )
        assert recorded is not None
        assert recorded["business_counter"] == past_epoch
        assert recorded["is_refunded"] is True
    finally:
        await _cleanup(transaction_no, OTHER_STORE, cart_id)


@pytest.mark.asyncio
async def test_return_still_refuses_another_tenant(http_client, opened_terminal_id):
    """Widening the store scope must not have widened the tenant boundary."""
    response = await http_client.post(
        _url(OTHER_STORE, OTHER_TERMINAL, 7202, "return").replace(
            f"/tenants/{_tenant_id()}/", "/tenants/T0000/"
        ),
        json=[{"paymentCode": "01", "amount": 550.0}],
        headers=_api_header(),
    )

    assert response.status_code != status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_ambiguous_transaction_no_is_refused(http_client, opened_terminal_id):
    """Two sessions share a seq; without an epoch the request must not guess.

    Guessing would void or refund a different sale than the one on the receipt.
    Both epochs are fixed values rather than offsets from the terminal's own, so
    the test does not change meaning depending on how many sessions ran before it.
    """
    store_code = os.environ.get("STORE_CODE")
    terminal_no = int(os.environ.get("TERMINAL_ID").split("-")[-1])
    transaction_no = 7301

    for epoch, cart_id in ((8801, "e2e-amb-a"), (8802, "e2e-amb-b")):
        await _insert_sale(
            store_code=store_code,
            terminal_no=terminal_no,
            business_date="20200101",
            business_counter=epoch,
            transaction_no=transaction_no,
            cart_id=cart_id,
            purge_first=False,
        )
    try:
        response = await http_client.get(
            f"/api/v1/tenants/{_tenant_id()}/stores/{store_code}/terminals/{terminal_no}"
            f"/transactions/{transaction_no}?terminal_id={os.environ.get('TERMINAL_ID')}",
            headers=_api_header(),
        )
        assert response.status_code == status.HTTP_409_CONFLICT, response.text
        assert "401513" in response.text, response.text

        # Naming the epoch resolves it — the refusal is about ambiguity, not access.
        response = await http_client.get(
            f"/api/v1/tenants/{_tenant_id()}/stores/{store_code}/terminals/{terminal_no}"
            f"/transactions/{transaction_no}?terminal_id={os.environ.get('TERMINAL_ID')}"
            f"&business_counter=8802",
            headers=_api_header(),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
    finally:
        await _cleanup(transaction_no, store_code, "e2e-amb-a")
