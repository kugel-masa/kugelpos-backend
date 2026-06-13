# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for the cart restore API happy path (issue #148, T020).

Simulates "a backend that has never seen the cart" by deleting the cart's
MongoDB fallback copy (the integration environment has no Dapr sidecar, so
the cache lives in cache_cart), then restores from the snapshot and drives
the transaction to completion.
"""

import base64
import os

import pytest
from fastapi import status

from app.config.settings import settings
from app.services import snapshot_service

KEY_SPEC = "it-v1:" + base64.b64encode(b"integration-test-key-32-bytes!!!").decode()


@pytest.fixture
def snapshot_keys(monkeypatch):
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", KEY_SPEC)
    snapshot_service.init_snapshot_signer(force=True)
    yield KEY_SPEC
    snapshot_service.init_snapshot_signer(force=True)


def _api_headers():
    return {
        "X-API-KEY": "test-api-key-12345",
        "Content-Type": "application/json",
    }


def _terminal_id():
    return f"{os.environ.get('TENANT_ID')}-5678-9"


async def _delete_cart_everywhere(cart_id: str):
    """Remove the cart's server-side copy to simulate a backend that never saw it."""
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"db_cart_{tenant_id}")
    result = await db[settings.DB_COLLECTION_NAME_CACHE_CART].delete_many({"cart_id": cart_id})
    assert result.deleted_count >= 1, f"expected cached cart {cart_id} to exist before deletion"


async def _get_restore_log(cart_id: str) -> list[dict]:
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"db_cart_{tenant_id}")
    cursor = db[settings.DB_COLLECTION_NAME_LOG_CART_RESTORE].find({"cart_id": cart_id})
    return [doc async for doc in cursor]


async def _create_cart_with_items(http_client, items=None):
    """Create a cart, add items, and return (cart_id, snapshot_after_items)."""
    terminal_id = _terminal_id()
    headers = _api_headers()
    r = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={
            "tenant_id": os.environ.get("TENANT_ID"),
            "terminal_id": terminal_id,
            "operator_code": "9999",
            "operator_name": "Test Operator",
        },
        headers=headers,
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text
    cart_id = r.json()["data"]["cartId"]

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=items or [{"itemCode": "49-01", "quantity": 2}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    return cart_id, r.json()["data"]["signedSnapshot"]


@pytest.mark.asyncio
async def test_restore_into_empty_backend_and_continue_to_bill(http_client, snapshot_keys):
    """Snapshot -> wipe server copy -> restore -> add item -> subtotal -> pay -> bill."""
    terminal_id = _terminal_id()
    headers = _api_headers()
    cart_id, snapshot = await _create_cart_with_items(http_client)
    assert snapshot is not None

    await _delete_cart_everywhere(cart_id)

    # The backend no longer knows the cart
    r = await http_client.get(f"/api/v1/carts/{cart_id}?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text

    # Restore from the client-held snapshot
    r = await http_client.post(
        f"/api/v1/carts/restore?terminal_id={terminal_id}",
        json=snapshot,
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    assert data["restored"] is True
    assert data["diverged"] is False
    assert data["cartId"] == cart_id
    assert data["cartStatus"] == "EnteringItem"
    assert len(data["lineItems"]) == 1
    assert data["lineItems"][0]["quantity"] == 2
    # The restore response itself carries a fresh snapshot
    assert data["signedSnapshot"] is not None
    assert data["signedSnapshot"]["cartDocument"]["cart_id"] == cart_id

    # The restored cart behaves like any other cart: continue to completion
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-02", "quantity": 1}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    r = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = r.json()["data"]["balanceAmount"]

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": int(balance)}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    r = await http_client.post(f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    bill_data = r.json()["data"]
    assert bill_data["cartStatus"] == "Completed"
    assert bill_data["transactionNo"] > 0

    # Audit trail records the restore
    logs = await _get_restore_log(cart_id)
    assert [log["result"] for log in logs] == ["restored"]
    assert logs[0]["snapshot_kid"] == "it-v1"
    assert logs[0]["terminal_no"] == 9


@pytest.mark.asyncio
async def test_restore_when_cart_exists_returns_existing(http_client, snapshot_keys):
    """The existing server-side cart wins; identical content -> diverged=false."""
    terminal_id = _terminal_id()
    cart_id, snapshot = await _create_cart_with_items(http_client)

    r = await http_client.post(
        f"/api/v1/carts/restore?terminal_id={terminal_id}",
        json=snapshot,
        headers=_api_headers(),
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    assert data["restored"] is False
    assert data["diverged"] is False
    assert data["cartId"] == cart_id
    # No overwrite happened: the cart still has its single line item
    assert len(data["lineItems"]) == 1

    logs = await _get_restore_log(cart_id)
    assert [log["result"] for log in logs] == ["existing_returned"]
    assert logs[0]["diverged"] is False


@pytest.mark.asyncio
async def test_restore_paying_state_snapshot(http_client, snapshot_keys):
    """A Paying-state snapshot restores and the transaction can be finalized."""
    terminal_id = _terminal_id()
    headers = _api_headers()
    cart_id, _ = await _create_cart_with_items(http_client)

    r = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    paying_snapshot = r.json()["data"]["signedSnapshot"]
    assert paying_snapshot["cartDocument"]["status"] == "Paying"

    await _delete_cart_everywhere(cart_id)

    r = await http_client.post(
        f"/api/v1/carts/restore?terminal_id={terminal_id}",
        json=paying_snapshot,
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    assert data["restored"] is True
    assert data["cartStatus"] == "Paying"

    balance = data["balanceAmount"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": int(balance)}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    r = await http_client.post(f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["data"]["cartStatus"] == "Completed"


@pytest.mark.asyncio
async def test_restored_cart_keeps_snapshot_master_context(http_client, snapshot_keys, monkeypatch):
    """Master-data price changes after the snapshot must not leak into the
    restored transaction (the carried masters are the authority, #146)."""
    from tests.integration import conftest as it_conftest

    terminal_id = _terminal_id()
    headers = _api_headers()
    cart_id, snapshot = await _create_cart_with_items(http_client)
    original_price = snapshot["cartDocument"]["masters"]["items"][0]["unit_price"]

    await _delete_cart_everywhere(cart_id)

    # Master-data now serves a different price for the same item
    monkeypatch.setitem(it_conftest.SYNTHETIC_ITEMS["49-01"], "price", 999.0)

    r = await http_client.post(
        f"/api/v1/carts/restore?terminal_id={terminal_id}",
        json=snapshot,
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["data"]["restored"] is True

    # Adding the same item again uses the snapshot's master, not the new price
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    line_items = r.json()["data"]["lineItems"]
    assert all(item["unitPrice"] == original_price for item in line_items)
