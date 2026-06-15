# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for signed snapshot attachment (issue #148, T015).

Every cart-mutating response must carry a self-verifying signed snapshot
of the full cart document (masters included). Query (GET) responses carry
none, and with no signing keys configured the operation still succeeds
with a null snapshot (degraded mode).
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


@pytest.fixture
def snapshot_keys(monkeypatch):
    """Enable snapshot signing for the app under test."""
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", KEY_SPEC)
    snapshot_service.init_snapshot_signer(force=True)
    yield KEY_SPEC
    snapshot_service.init_snapshot_signer(force=True)


@pytest.fixture
def snapshot_keys_unset(monkeypatch):
    """Force degraded mode (no signing keys)."""
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", "")
    snapshot_service.init_snapshot_signer(force=True)
    yield
    snapshot_service.init_snapshot_signer(force=True)


def _api_headers():
    return {
        "X-API-KEY": "test-api-key-12345",
        "Content-Type": "application/json",
    }


def _terminal_id():
    return f"{os.environ.get('TENANT_ID')}-5678-9"


def _assert_valid_snapshot(data: dict, expected_cart_id: str | None = None) -> dict:
    """Assert the response data carries a self-verifying snapshot; return it."""
    snapshot = data.get("signedSnapshot")
    assert snapshot is not None, f"signedSnapshot missing in response data: {list(data.keys())}"
    envelope = SnapshotEnvelope(**snapshot).model_dump(mode="json")
    signature = envelope.pop("signature")
    signer = HmacSigner.from_spec(KEY_SPEC)
    assert signer.verify(envelope, envelope["kid"], signature) is True
    assert envelope["schema_version"] == snapshot_service.SNAPSHOT_SCHEMA_VERSION
    assert envelope["tenant_id"] == os.environ.get("TENANT_ID")
    assert envelope["store_code"] == "5678"
    assert envelope["terminal_no"] == 9
    if expected_cart_id is not None:
        assert envelope["cart_document"]["cart_id"] == expected_cart_id
    return envelope


async def _create_cart(http_client, user_id="9999"):
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={_terminal_id()}",
        json={
            "tenant_id": os.environ.get("TENANT_ID"),
            "terminal_id": _terminal_id(),
            "operator_code": user_id,
            "operator_name": "Test Operator",
        },
        headers=_api_headers(),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_all_mutating_endpoints_attach_snapshot(http_client, snapshot_keys):
    """Walk the full mutating surface; every response carries a valid snapshot."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    # POST /carts
    create_data = await _create_cart(http_client)
    cart_id = create_data["cartId"]
    _assert_valid_snapshot(create_data, cart_id)

    # POST /carts/{id}/lineItems
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}, {"itemCode": "49-02", "quantity": 1}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    envelope = _assert_valid_snapshot(r.json()["data"], cart_id)
    # Masters travel with the snapshot: the scanned item is embedded
    master_item_codes = [i["item_code"] for i in envelope["cart_document"]["masters"]["items"]]
    assert "49-01" in master_item_codes

    # PATCH /carts/{id}/lineItems/{lineNo}/quantity
    r = await http_client.patch(
        f"/api/v1/carts/{cart_id}/lineItems/1/quantity?terminal_id={terminal_id}",
        json={"quantity": 3},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)

    # PATCH /carts/{id}/lineItems/{lineNo}/unitPrice
    r = await http_client.patch(
        f"/api/v1/carts/{cart_id}/lineItems/1/unitPrice?terminal_id={terminal_id}",
        json={"unitPrice": 120.0},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)

    # POST /carts/{id}/lineItems/{lineNo}/discounts
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems/1/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 10}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)

    # POST /carts/{id}/lineItems/{lineNo}/cancel (cancel line 2)
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems/2/cancel?terminal_id={terminal_id}",
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)

    # POST /carts/{id}/subtotal
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)

    # POST /carts/{id}/discounts
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 5}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)

    # POST /carts/{id}/resume-item-entry
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/resume-item-entry?terminal_id={terminal_id}",
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)

    # subtotal again, then payments + bill
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = r.json()["data"]["balanceAmount"]

    # POST /carts/{id}/payments
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": int(balance)}],
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)

    # POST /carts/{id}/bill
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)


@pytest.mark.asyncio
async def test_cancel_endpoint_attaches_snapshot(http_client, snapshot_keys):
    """POST /carts/{id}/cancel also carries a snapshot."""
    create_data = await _create_cart(http_client)
    cart_id = create_data["cartId"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel?terminal_id={_terminal_id()}",
        headers=_api_headers(),
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    _assert_valid_snapshot(r.json()["data"], cart_id)


@pytest.mark.asyncio
async def test_degraded_mode_mutation_succeeds_without_snapshot(http_client, snapshot_keys_unset):
    """With no keys configured the operation succeeds and the field is null."""
    create_data = await _create_cart(http_client)
    cart_id = create_data["cartId"]
    assert create_data.get("signedSnapshot") is None

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={_terminal_id()}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=_api_headers(),
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["data"].get("signedSnapshot") is None
