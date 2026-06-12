# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for restore rejections (issue #148, T024).

Every rejection must use its distinct 4015xx code, leave no cart behind,
and land in the log_cart_restore audit trail as 'rejected'.
"""
import base64
import os

import pytest
from fastapi import status

from kugel_common.utils.hmac_signer import HmacSigner

from app.api.common.schemas import SnapshotEnvelope
from app.config.settings import settings
from app.services import snapshot_service


KEY_SPEC = "it-v1:" + base64.b64encode(b"integration-test-key-32-bytes!!!").decode()
ROTATED_ONLY_SPEC = "it-v2:" + base64.b64encode(b"integration-test-key-rotated!!!!").decode()


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
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"db_cart_{tenant_id}")
    await db[settings.DB_COLLECTION_NAME_CACHE_CART].delete_many({"cart_id": cart_id})


async def _cart_exists(cart_id: str) -> bool:
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"db_cart_{tenant_id}")
    return await db[settings.DB_COLLECTION_NAME_CACHE_CART].count_documents({"cart_id": cart_id}) > 0


async def _rejected_reasons(cart_id: str) -> list[str | None]:
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"db_cart_{tenant_id}")
    cursor = db[settings.DB_COLLECTION_NAME_LOG_CART_RESTORE].find({"cart_id": cart_id, "result": "rejected"})
    return [doc["reject_reason"] async for doc in cursor]


async def _orphan_snapshot(http_client):
    """Create a cart with one item, capture its snapshot, then wipe it server-side."""
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
    snapshot = r.json()["data"]["signedSnapshot"]
    await _delete_cart_everywhere(cart_id)
    return cart_id, snapshot


async def _post_restore(http_client, snapshot):
    return await http_client.post(
        f"/api/v1/carts/restore?terminal_id={_terminal_id()}",
        json=snapshot,
        headers=_api_headers(),
    )


def _resign(snapshot: dict, key_spec: str) -> dict:
    """Re-sign a (possibly modified) wire-form snapshot with the given key."""
    envelope = SnapshotEnvelope(**snapshot).model_dump(mode="json")
    envelope.pop("signature")
    signer = HmacSigner.from_spec(key_spec)
    signed = {**envelope, "kid": signer.current_kid}
    signed["signature"] = signer.sign(signed)
    return signed


@pytest.mark.asyncio
async def test_tampered_snapshot_rejected_401501(http_client, snapshot_keys):
    cart_id, snapshot = await _orphan_snapshot(http_client)
    snapshot["cartDocument"]["balance_amount"] = 0.01

    r = await _post_restore(http_client, snapshot)
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
    assert r.json()["user_error"]["code"] == "401501"
    assert not await _cart_exists(cart_id)
    assert "401501" in await _rejected_reasons(cart_id)


@pytest.mark.asyncio
async def test_garbled_signature_rejected_401502(http_client, snapshot_keys):
    cart_id, snapshot = await _orphan_snapshot(http_client)
    snapshot["signature"] = ""

    r = await _post_restore(http_client, snapshot)
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
    assert r.json()["user_error"]["code"] == "401502"
    assert not await _cart_exists(cart_id)
    assert "401502" in await _rejected_reasons(cart_id)


@pytest.mark.asyncio
async def test_missing_signature_field_fails_validation(http_client, snapshot_keys):
    _, snapshot = await _orphan_snapshot(http_client)
    snapshot.pop("signature")

    r = await _post_restore(http_client, snapshot)
    # Required-field enforcement happens at the schema layer
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, r.text


@pytest.mark.asyncio
async def test_unknown_kid_rejected_401503(http_client, snapshot_keys, monkeypatch):
    cart_id, snapshot = await _orphan_snapshot(http_client)

    # Keys rotated and the grace generation dropped: it-v1 is gone
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", ROTATED_ONLY_SPEC)
    snapshot_service.init_snapshot_signer(force=True)

    r = await _post_restore(http_client, snapshot)
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
    assert r.json()["user_error"]["code"] == "401503"
    assert not await _cart_exists(cart_id)
    assert "401503" in await _rejected_reasons(cart_id)


@pytest.mark.asyncio
async def test_previous_generation_key_accepted_after_rotation(http_client, snapshot_keys, monkeypatch):
    cart_id, snapshot = await _orphan_snapshot(http_client)

    # Rotation with grace: current=it-v2, previous=it-v1
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", f"{ROTATED_ONLY_SPEC},{KEY_SPEC}")
    snapshot_service.init_snapshot_signer(force=True)

    r = await _post_restore(http_client, snapshot)
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    assert data["restored"] is True
    # The fresh snapshot is signed with the new current key
    assert data["signedSnapshot"]["kid"] == "it-v2"
    assert await _cart_exists(cart_id)


@pytest.mark.asyncio
async def test_unsupported_version_rejected_401504(http_client, snapshot_keys):
    cart_id, snapshot = await _orphan_snapshot(http_client)
    snapshot["schemaVersion"] = 99

    r = await _post_restore(http_client, snapshot)
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
    assert r.json()["user_error"]["code"] == "401504"
    assert not await _cart_exists(cart_id)
    assert "401504" in await _rejected_reasons(cart_id)


@pytest.mark.asyncio
async def test_other_store_snapshot_rejected_401505(http_client, snapshot_keys):
    """A validly-signed snapshot from another store fails the scope check."""
    cart_id, snapshot = await _orphan_snapshot(http_client)
    snapshot["storeCode"] = "9999"
    snapshot["cartDocument"]["store_code"] = "9999"
    snapshot = _resign(snapshot, KEY_SPEC)

    r = await _post_restore(http_client, snapshot)
    assert r.status_code == status.HTTP_403_FORBIDDEN, r.text
    assert r.json()["user_error"]["code"] == "401505"
    assert not await _cart_exists(cart_id)
    assert "401505" in await _rejected_reasons(cart_id)


@pytest.mark.asyncio
async def test_other_tenant_snapshot_rejected_401505(http_client, snapshot_keys):
    cart_id, snapshot = await _orphan_snapshot(http_client)
    snapshot["tenantId"] = "T0000"
    snapshot = _resign(snapshot, KEY_SPEC)

    r = await _post_restore(http_client, snapshot)
    assert r.status_code == status.HTTP_403_FORBIDDEN, r.text
    assert r.json()["user_error"]["code"] == "401505"
    assert not await _cart_exists(cart_id)
