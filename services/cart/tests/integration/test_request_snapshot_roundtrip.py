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
async def test_carried_finalize_context_drives_numbering(http_client, snapshot_keys):
    """A stateless bill uses the client-supplied seq/receipt/time (carried numbering)."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, _, _ = await _create_cart_with_items(http_client)

    r = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = r.json()["data"]["balanceAmount"]

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": int(balance)}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    paying_snapshot = r.json()["data"]["signedSnapshot"]
    assert paying_snapshot is not None

    # Distinctive carried values a server counter would never produce.
    finalize_ctx = {"seq": 7777, "receiptNo": 8888, "transactionDatetime": "2026-06-14T01:02:03"}
    wrapped = {"signedSnapshot": paying_snapshot, "payload": finalize_ctx}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    bill_data = r.json()["data"]
    assert bill_data["cartStatus"] == "Completed"
    # The carried finalize context drove the numbering, not server counters.
    assert bill_data["transactionNo"] == 7777, bill_data
    assert bill_data["receiptNo"] == 8888, bill_data


@pytest.mark.asyncio
async def test_retried_carried_finalize_is_idempotent(http_client, snapshot_keys):
    """B2: a retried finalize (same snapshot + finalize context) returns the same
    result, not a 500 — the duplicate insert is handled idempotently."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, _, _ = await _create_cart_with_items(http_client)
    r = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = r.json()["data"]["balanceAmount"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": int(balance)}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    paying_snapshot = r.json()["data"]["signedSnapshot"]

    ctx = {"seq": 5151, "receiptNo": 5152, "transactionDatetime": "2026-06-14T02:03:04"}
    wrapped = {"signedSnapshot": paying_snapshot, "payload": ctx}

    r1 = await http_client.post(f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", json=wrapped, headers=headers)
    assert r1.status_code == status.HTTP_200_OK, r1.text
    assert r1.json()["data"]["transactionNo"] == 5151

    # Retry the exact same finalize: reconstructs from the same paying snapshot,
    # produces the same (cart_id, seq) -> idempotent, same result, no 500.
    r2 = await http_client.post(f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", json=wrapped, headers=headers)
    assert r2.status_code == status.HTTP_200_OK, r2.text
    assert r2.json()["data"]["transactionNo"] == 5151


async def _bill_a_sale(http_client, terminal_id, headers):
    """Create -> add item -> subtotal -> pay -> (legacy) bill. Returns
    (transaction_no, paid_amount) for the committed sale."""
    cart_id, _, _ = await _create_cart_with_items(http_client)
    r = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = int(r.json()["data"]["balanceAmount"])
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": balance}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    r = await http_client.post(f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    return r.json()["data"]["transactionNo"], balance


@pytest.mark.asyncio
async def test_carried_void_uses_signed_finalize_context(http_client, snapshot_keys):
    """Void carries a signed finalize-context envelope (issue #156, B案): the void
    draws its per-open seq / receipt_no from the verified carried values (a stable
    cart_id, not a server counter), routed through the same envelope middleware."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = 9
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    headers = _api_headers()

    transaction_no, paid = await _bill_a_sale(http_client, terminal_id, headers)

    # Build the void's signed finalize-context envelope (the terminal would do this).
    from types import SimpleNamespace

    terminal_info = SimpleNamespace(tenant_id=tenant_id, store_code=store_code, terminal_no=terminal_no)
    void_env = snapshot_service.build_finalize_context_envelope(
        cart_id="void-cart-it-0001",
        seq=6543,  # distinctive per-open seq a server counter would never produce
        receipt_no=6544,
        transaction_datetime="2026-06-14T07:08:09",
        terminal_info=terminal_info,
    )
    assert void_env is not None

    wrapped = {"signedSnapshot": void_env, "payload": [{"paymentCode": "01", "amount": paid}]}
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}"
        f"/transactions/{transaction_no}/void?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    void_data = r.json()["data"]
    assert void_data["transactionNo"] == 6543, void_data
    assert void_data["receiptNo"] == 6544, void_data


@pytest.mark.asyncio
async def test_carried_void_rejects_tampered_seq(http_client, snapshot_keys):
    """Forging the carried void numbering (re-writing seq after signing) is rejected."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = 9
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    headers = _api_headers()

    transaction_no, paid = await _bill_a_sale(http_client, terminal_id, headers)

    from types import SimpleNamespace

    terminal_info = SimpleNamespace(tenant_id=tenant_id, store_code=store_code, terminal_no=terminal_no)
    void_env = snapshot_service.build_finalize_context_envelope(
        cart_id="void-cart-it-0002",
        seq=10,
        receipt_no=11,
        transaction_datetime="2026-06-14T07:08:09",
        terminal_info=terminal_info,
    )
    void_env["finalize_context"]["seq"] = 999999  # tamper after signing

    wrapped = {"signedSnapshot": void_env, "payload": [{"paymentCode": "01", "amount": paid}]}
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}"
        f"/transactions/{transaction_no}/void?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )
    assert r.status_code != status.HTTP_200_OK, r.text


@pytest.mark.asyncio
async def test_required_mode_rejects_snapshotless_mutation(http_client, snapshot_keys, monkeypatch):
    """B3: in REQUIRED mode a snapshot-less mutating request is rejected."""
    from app.config.settings import settings

    terminal_id = _terminal_id()
    headers = _api_headers()
    cart_id, _, _ = await _create_cart_with_items(http_client)

    monkeypatch.setattr(settings, "CART_REQUEST_SNAPSHOT_MODE", "REQUIRED")

    # A snapshot-less mutating request is rejected.
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=headers,
    )
    assert r.status_code != status.HTTP_200_OK, r.text


@pytest.mark.asyncio
async def test_snapshotless_bill_with_finalize_context_is_rejected(http_client, snapshot_keys):
    """bug_006: a finalize context (client-supplied numbering) on the
    cache-authoritative path (no signed snapshot) must be rejected — otherwise a
    phase-1 client could forge the transaction/receipt numbers."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, _, _ = await _create_cart_with_items(http_client)
    r = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = r.json()["data"]["balanceAmount"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": int(balance)}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    # No wrapped body / no signed snapshot, but a finalize context is supplied.
    forged = {"seq": 1, "receiptNo": 2, "transactionDatetime": "2026-06-14T03:04:05"}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
        json=forged,
        headers=headers,
    )
    # Carried numbering requires the stateless (snapshot) path -> rejected.
    assert r.status_code != status.HTTP_200_OK, r.text


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

    # The per-request rejection is audited, and records which API it came from.
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"db_cart_{os.environ.get('TENANT_ID')}")
    logs = [
        doc
        async for doc in db[settings.DB_COLLECTION_NAME_LOG_CART_RESTORE].find({"cart_id": cart_id, "result": "rejected"})
    ]
    assert logs, "expected a rejected audit record for the tampered request"
    assert any((log.get("api_path") or "").endswith("/lineItems") for log in logs), logs
