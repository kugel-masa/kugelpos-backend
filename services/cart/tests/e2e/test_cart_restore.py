# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""E2E coverage for the signed cart snapshot + restore API (issue #148, T028).

Drives the quickstart scenario against the live stack: capture a snapshot,
wipe the cart from the real Redis cartstore (simulating cache loss / a
backend that never saw the cart), restore via JWT auth, and continue the
transaction to completion. JWT auth matters here: terminal info is rebuilt
from the token claims (#67), which is the failover prerequisite.

Prerequisite: the cart service must run with SNAPSHOT_HMAC_KEYS configured
(e.g. in services/cart/.env) and the same value must be visible to this
test process (root .env.test). The test skips with instructions otherwise.
"""

import os
import subprocess

import pytest
from fastapi import status
from httpx import AsyncClient

from app.enums.cart_status import CartStatus

REDIS_CONTAINER = "redis"


def _snapshot_keys_or_skip() -> str:
    key_spec = os.environ.get("SNAPSHOT_HMAC_KEYS", "")
    if not key_spec.strip():
        pytest.skip(
            "SNAPSHOT_HMAC_KEYS not configured: set it in services/cart/.env "
            "(service side) and root .env.test (test side) to run restore e2e"
        )
    return key_spec


# Helper - obtain admin auth token
async def get_authentication_token():
    tenant_id = os.environ.get("TENANT_ID")
    token_url = os.environ.get("TOKEN_URL")
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}
    async with AsyncClient() as http_auth_client:
        response = await http_auth_client.post(url=token_url, data=login_data)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json().get("access_token")


# Helper - create tenant (idempotent)
async def create_tenant(http_client, token):
    tenant_id = os.environ.get("TENANT_ID")
    header = {"Authorization": f"Bearer {token}"}
    response = await http_client.post("/api/v1/tenants", json={"tenant_id": tenant_id}, headers=header)
    assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_409_CONFLICT), response.text
    return tenant_id


# Helper - open the terminal (function_mode -> sign-in -> open -> Sales mode).
# Idempotent: other e2e suites may have left the terminal opened/signed-in,
# so terminal-status business errors (4060xx, e.g. "already opened") are
# tolerated on each step.
async def open_terminal():
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}
    base_url = os.environ.get("BASE_URL_TERMINAL")

    def _ok(r):
        if r.status_code == status.HTTP_200_OK:
            return
        if r.status_code == status.HTTP_400_BAD_REQUEST and '"4060' in r.text:
            return  # already in the desired state
        raise AssertionError(r.text)

    async with AsyncClient(base_url=base_url) as client:
        r = await client.patch(
            f"/terminals/{terminal_id}/function_mode", json={"function_mode": "OpenTerminal"}, headers=header
        )
        _ok(r)
        r = await client.post(
            f"/terminals/{terminal_id}/sign-in", json={"staff_id": "S001", "staff_pin": "1234"}, headers=header
        )
        _ok(r)
        r = await client.post(f"/terminals/{terminal_id}/open", json={"initial_amount": 50000}, headers=header)
        _ok(r)
        r = await client.patch(
            f"/terminals/{terminal_id}/function_mode", json={"function_mode": "Sales"}, headers=header
        )
        assert r.status_code == status.HTTP_200_OK, r.text


# Helper - terminal JWT (terminal info travels in the claims, #67)
async def get_terminal_jwt() -> str:
    api_key = os.environ.get("API_KEY")
    base_url = os.environ.get("BASE_URL_TERMINAL").removesuffix("/api/v1")
    async with AsyncClient(base_url=base_url) as client:
        r = await client.post(
            "/api/v1/auth/token",
            headers={"X-API-KEY": api_key},
        )
    assert r.status_code == status.HTTP_200_OK, r.text
    return r.json()["data"]["access_token"]


def delete_cart_from_redis(cart_id: str):
    """Wipe the cart's keys from the live Redis cartstore (quickstart §3)."""
    scan = subprocess.run(
        ["docker", "exec", REDIS_CONTAINER, "redis-cli", "--scan", "--pattern", f"*{cart_id}*"],
        capture_output=True,
        text=True,
        check=True,
    )
    keys = [k for k in scan.stdout.splitlines() if k.strip()]
    assert keys, f"expected cart {cart_id} keys in redis before deletion"
    subprocess.run(
        ["docker", "exec", REDIS_CONTAINER, "redis-cli", "del", *keys],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.mark.asyncio
async def test_restore_after_cache_loss_with_jwt(http_client):
    """SC-001/SC-002: continue a transaction from the client-held snapshot
    after the server-side cache lost the cart, authenticated via JWT."""
    _snapshot_keys_or_skip()
    terminal_id = os.environ.get("TERMINAL_ID")

    token = await get_authentication_token()
    await create_tenant(http_client, token)
    await open_terminal()

    jwt_token = await get_terminal_jwt()
    jwt_header = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}

    # Create a cart and add items; keep the last snapshot like a POS would
    r = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=jwt_header,
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text
    cart_id = r.json()["data"]["cartId"]

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=jwt_header,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    snapshot = r.json()["data"]["signedSnapshot"]
    assert snapshot is not None, "cart service is not configured with SNAPSHOT_HMAC_KEYS"

    # The backend loses the cart (Redis data loss / failover to a fresh backend)
    delete_cart_from_redis(cart_id)
    r = await http_client.get(f"/api/v1/carts/{cart_id}?terminal_id={terminal_id}", headers=jwt_header)
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text

    # Restore from the client-held snapshot (JWT-only: terminal info from claims)
    r = await http_client.post(
        f"/api/v1/carts/restore?terminal_id={terminal_id}",
        json=snapshot,
        headers=jwt_header,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    assert data["restored"] is True
    assert data["diverged"] is False
    assert data["cartId"] == cart_id
    assert len(data["lineItems"]) == 1
    assert data["signedSnapshot"] is not None

    # Continue the transaction to completion — zero re-entry
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-02", "quantity": 1}],
        headers=jwt_header,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    r = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=jwt_header)
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = r.json()["data"]["balanceAmount"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": int(balance), "detail": "Cash payment"}],
        headers=jwt_header,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    r = await http_client.post(f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", headers=jwt_header)
    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["data"]["cartStatus"] == CartStatus.Completed.value


@pytest.mark.asyncio
async def test_restore_rejections_e2e(http_client):
    """Tampered snapshots are rejected; restoring over an existing cart
    returns the existing cart without overwrite."""
    _snapshot_keys_or_skip()
    terminal_id = os.environ.get("TERMINAL_ID")

    token = await get_authentication_token()
    await create_tenant(http_client, token)
    await open_terminal()
    jwt_token = await get_terminal_jwt()
    jwt_header = {"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"}

    r = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=jwt_header,
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text
    cart_id = r.json()["data"]["cartId"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=jwt_header,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    snapshot = r.json()["data"]["signedSnapshot"]

    # Conflict: cart still exists -> existing returned, no overwrite
    r = await http_client.post(f"/api/v1/carts/restore?terminal_id={terminal_id}", json=snapshot, headers=jwt_header)
    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["data"]["restored"] is False

    # Tamper: flip one amount -> 401501, cart untouched
    tampered = dict(snapshot)
    tampered["cartDocument"] = dict(snapshot["cartDocument"])
    tampered["cartDocument"]["balance_amount"] = 0.01
    r = await http_client.post(f"/api/v1/carts/restore?terminal_id={terminal_id}", json=tampered, headers=jwt_header)
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
    assert r.json()["user_error"]["code"] == "401501"

    # Cleanup: cancel the open cart so later suites start clean
    r = await http_client.post(f"/api/v1/carts/{cart_id}/cancel?terminal_id={terminal_id}", headers=jwt_header)
    assert r.status_code == status.HTTP_200_OK, r.text
