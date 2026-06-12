# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for snapshot replay handling (issue #148, T027).

Replay posture is accept + detect: old snapshots are valid by construction,
so the conflict path returns the existing cart with a divergence notice,
terminal-state snapshots are rejected idempotently, and the audit trail
makes every replay traceable per cart_id.

Note: preventing double-counting when a *pre-terminal* snapshot of an
already-finalized transaction is restored and re-billed is out of scope
here — that is issue #152 (cart_id on tranlog). This module verifies the
detection side only.
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


async def _get_db():
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    return await db_helper.get_db_async(f"db_cart_{tenant_id}")


async def _restore_logs(cart_id: str) -> list[dict]:
    db = await _get_db()
    cursor = db[settings.DB_COLLECTION_NAME_LOG_CART_RESTORE].find({"cart_id": cart_id})
    return [doc async for doc in cursor]


async def _tranlog_count() -> int:
    db = await _get_db()
    return await db[settings.DB_COLLECTION_NAME_TRAN_LOG].count_documents({})


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
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    return cart_id, r.json()["data"]["signedSnapshot"]


@pytest.mark.asyncio
async def test_old_snapshot_replay_detected_as_divergence(http_client, snapshot_keys):
    """Replaying an old snapshot of a progressed cart: existing wins, diverged=true."""
    terminal_id = _terminal_id()
    headers = _api_headers()
    cart_id, old_snapshot = await _create_cart_with_items(http_client)

    # The transaction progresses past the captured snapshot
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-02", "quantity": 2}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    # Replay the old snapshot
    r = await http_client.post(
        f"/api/v1/carts/restore?terminal_id={terminal_id}",
        json=old_snapshot,
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    assert data["restored"] is False
    assert data["diverged"] is True
    # No rollback: both line items are still there
    assert len(data["lineItems"]) == 2
    # The fresh snapshot reflects the server state, not the replayed one
    assert len(data["signedSnapshot"]["cartDocument"]["line_items"]) == 2

    logs = await _restore_logs(cart_id)
    assert [log["result"] for log in logs] == ["existing_returned"]
    assert logs[0]["diverged"] is True


@pytest.mark.asyncio
async def test_terminal_state_snapshot_rejected_401506(http_client, snapshot_keys):
    """A snapshot of a finalized cart is rejected idempotently with no new tranlog."""
    terminal_id = _terminal_id()
    headers = _api_headers()
    cart_id, _ = await _create_cart_with_items(http_client)

    # Finalize the transaction and capture the terminal-state snapshot
    r = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=headers)
    balance = r.json()["data"]["balanceAmount"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": int(balance)}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    r = await http_client.post(f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", headers=headers)
    assert r.status_code == status.HTTP_200_OK, r.text
    completed_snapshot = r.json()["data"]["signedSnapshot"]
    assert completed_snapshot["cartDocument"]["status"] == "Completed"

    tranlogs_before = await _tranlog_count()

    r = await http_client.post(
        f"/api/v1/carts/restore?terminal_id={terminal_id}",
        json=completed_snapshot,
        headers=headers,
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
    assert r.json()["user_error"]["code"] == "401506"

    # Idempotent rejection: nothing was counted, nothing was created
    assert await _tranlog_count() == tranlogs_before

    logs = await _restore_logs(cart_id)
    assert [log["result"] for log in logs] == ["rejected"]
    assert logs[0]["reject_reason"] == "401506"


@pytest.mark.asyncio
async def test_audit_trail_traces_full_replay_history(http_client, snapshot_keys):
    """log_cart_restore keyed by cart_id yields the full attempt history."""
    terminal_id = _terminal_id()
    headers = _api_headers()
    cart_id, snapshot = await _create_cart_with_items(http_client)

    # Attempt 1: existing cart -> existing_returned (no divergence)
    r = await http_client.post(f"/api/v1/carts/restore?terminal_id={terminal_id}", json=snapshot, headers=headers)
    assert r.status_code == status.HTTP_200_OK

    # Attempt 2: progress the cart, replay -> existing_returned + diverged
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-02", "quantity": 1}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK
    r = await http_client.post(f"/api/v1/carts/restore?terminal_id={terminal_id}", json=snapshot, headers=headers)
    assert r.status_code == status.HTTP_200_OK

    # Attempt 3: tampered replay -> rejected
    tampered = dict(snapshot)
    tampered["cartDocument"] = dict(snapshot["cartDocument"])
    tampered["cartDocument"]["balance_amount"] = 0.01
    r = await http_client.post(f"/api/v1/carts/restore?terminal_id={terminal_id}", json=tampered, headers=headers)
    assert r.status_code == status.HTTP_400_BAD_REQUEST

    logs = await _restore_logs(cart_id)
    assert [log["result"] for log in logs] == ["existing_returned", "existing_returned", "rejected"]
    assert [log["diverged"] for log in logs] == [False, True, False]
    # Issuing terminal and requesting terminal are both recorded (FR-012)
    for log in logs:
        assert log["snapshot_terminal_no"] == 9
        assert log["terminal_no"] == 9
        assert log["snapshot_issued_at"]
        assert log["snapshot_kid"] == "it-v1"
        assert log["event_datetime"]
