# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for the phase 2 per-request snapshot path (issue #156, US1).

A mutating request that carries the last snapshot in a wrapped body
({signedSnapshot, payload}) is processed statelessly: the peel middleware
lifts the snapshot, the DI reconstructs the cart from it WITHOUT reading the
server-side cache, applies the operation, and returns a fresh snapshot. This
mirrors "continue the transaction on a backend that no longer has the cart
cached" without calling the restore API.
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
    return {"X-API-KEY": "test-api-key-12345", "Content-Type": "application/json"}


def _terminal_id():
    return f"{os.environ.get('TENANT_ID')}-5678-9"


async def _delete_cart_everywhere(cart_id: str):
    """Remove the server-side copy to simulate a backend that no longer has it."""
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"db_cart_{tenant_id}")
    await db[settings.DB_COLLECTION_NAME_CACHE_CART].delete_many({"cart_id": cart_id})


async def _create_cart_with_items(http_client):
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
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    return cart_id, data["signedSnapshot"], len(data["lineItems"])


@pytest.mark.asyncio
async def test_wrapped_request_continues_after_cache_wipe(http_client, snapshot_keys):
    """Snapshot -> wipe server copy -> wrapped add-item request -> succeeds statelessly."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, line_count_before = await _create_cart_with_items(http_client)
    assert snapshot is not None, "mutating response should carry a snapshot when keys are configured"

    # Simulate a backend that no longer has the cart cached.
    await _delete_cart_everywhere(cart_id)

    # Phase 2 wrapped body: carry the snapshot + the original array payload.
    wrapped = {"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )

    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    # The cart was reconstructed from the snapshot (had the first item) and the
    # new item was applied — even though the server-side cache was wiped.
    assert len(data["lineItems"]) == line_count_before + 1
    # A fresh snapshot is returned for the next request.
    assert data["signedSnapshot"] is not None


@pytest.mark.asyncio
async def test_tampered_wrapped_request_is_rejected(http_client, snapshot_keys):
    """A tampered carried snapshot is rejected before the operation is applied (US3)."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    # Tamper: bump a monetary field inside the carried cart document.
    tampered = {**snapshot}
    cart_doc = dict(tampered.get("cartDocument") or tampered.get("cart_document") or {})
    cart_doc["balanceAmount"] = 0.01
    if "cartDocument" in tampered:
        tampered["cartDocument"] = cart_doc
    else:
        tampered["cart_document"] = cart_doc

    wrapped = {"signedSnapshot": tampered, "payload": [{"itemCode": "49-01", "quantity": 1}]}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )
    # Signature mismatch -> rejected (not a successful 200).
    assert r.status_code != status.HTTP_200_OK, r.text
