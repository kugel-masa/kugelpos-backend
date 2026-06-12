# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for terminal lifecycle endpoints.

Covers the 9 endpoints test_terminal.py doesn't exercise:
  POST   /auth/token             (API key -> JWT)
  PATCH  /terminals/{tid}/description
  POST   /terminals/{tid}/sign-in
  POST   /terminals/{tid}/sign-out
  POST   /terminals/{tid}/open
  POST   /terminals/{tid}/close
  POST   /terminals/{tid}/cash-in
  POST   /terminals/{tid}/cash-out
  POST   /terminals/{tid}/delivery-status

Driven in-process via ASGITransport. Master-data staff lookup is mocked
in the parent conftest's mock_outbound_services fixture so sign-in
resolves S001 without a running master-data service. Dapr publishes go
to the same conftest's localhost:3500 catch-all.
"""
import os
from datetime import datetime
from kugel_common.utils.misc import get_app_time

import pytest
from fastapi import status


_TERMINAL_NO_COUNTER = [50]  # Use distinct terminal_no per test to avoid 400 collisions


async def _create_terminal(http_client, header, store_code="5678"):
    """Create a tenant + store + a fresh terminal; return (terminal_id, api_key).

    Each call increments the terminal_no counter so tests don't collide
    against the in-process app's persistent terminal collection (only
    dropped once per session via _setup_terminal_db).
    """
    tenant_id = os.environ.get("TENANT_ID")
    terminal_no = _TERMINAL_NO_COUNTER[0]
    _TERMINAL_NO_COUNTER[0] += 1

    response = await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": tenant_id, "tenant_name": "Lifecycle Tenant", "stores": [], "tags": ["lifecycle"]},
        headers=header,
    )
    assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST)

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores",
        json={"store_code": store_code, "store_name": "Lifecycle Store", "tags": []},
        headers=header,
    )
    assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST)

    response = await http_client.post(
        "/api/v1/terminals",
        json={"store_code": store_code, "terminal_no": terminal_no, "description": "Lifecycle Terminal"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()["data"]
    return data["terminalId"], data["apiKey"]


@pytest.mark.asyncio
async def test_patch_description(http_client, admin_header, mock_outbound_services):
    """PATCH /terminals/{tid}/description updates description in place."""
    terminal_id, _ = await _create_terminal(http_client, admin_header)

    response = await http_client.patch(
        f"/api/v1/terminals/{terminal_id}/description",
        json={"description": "Updated description"},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["description"] == "Updated description"


@pytest.mark.asyncio
async def test_auth_token_with_api_key(http_client, admin_header, mock_outbound_services):
    """POST /auth/token exchanges API key for a terminal JWT."""
    terminal_id, api_key = await _create_terminal(http_client, admin_header)

    response = await http_client.post(
        f"/api/v1/auth/token?terminal_id={terminal_id}",
        headers={"X-API-KEY": api_key},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()["data"]
    # TokenResponse inherits plain BaseModel (no alias), so fields stay snake_case.
    assert body["access_token"]
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_auth_token_invalid_api_key(http_client, admin_header, mock_outbound_services):
    """Invalid API key -> 401 from /auth/token."""
    response = await http_client.post(
        "/api/v1/auth/token",
        headers={"X-API-KEY": "definitely-not-a-valid-key"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def _signin(http_client, header, terminal_id, staff_id="S001"):
    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/sign-in",
        json={"staff_id": staff_id},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response


async def _open(http_client, header, terminal_id, initial_amount=50000.0):
    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/open",
        json={"initial_amount": initial_amount},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response


@pytest.mark.asyncio
async def test_sign_in(http_client, admin_header, mock_outbound_services):
    """POST /sign-in associates a staff with the terminal, returns X-New-Token."""
    terminal_id, _ = await _create_terminal(http_client, admin_header)
    response = await _signin(http_client, admin_header, terminal_id)
    assert response.json()["data"]["staff"]["staffId"] == "S001"
    assert response.headers.get("x-new-token"), "sign-in should issue X-New-Token"


@pytest.mark.asyncio
async def test_sign_out(http_client, admin_header, mock_outbound_services):
    """POST /sign-out clears staff association."""
    terminal_id, _ = await _create_terminal(http_client, admin_header)
    await _signin(http_client, admin_header, terminal_id)

    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/sign-out",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["staff"] is None


@pytest.mark.asyncio
async def test_open(http_client, admin_header, mock_outbound_services):
    """POST /open transitions the terminal into the Opened state."""
    terminal_id, _ = await _create_terminal(http_client, admin_header)
    await _signin(http_client, admin_header, terminal_id)
    response = await _open(http_client, admin_header, terminal_id)
    business_date = get_app_time().strftime("%Y%m%d")
    assert response.json()["data"]["businessDate"] == business_date
    assert response.headers.get("x-new-token"), "open should issue X-New-Token"


@pytest.mark.asyncio
async def test_cash_in(http_client, admin_header, mock_outbound_services):
    """POST /cash-in records a cash deposit on an open terminal."""
    terminal_id, _ = await _create_terminal(http_client, admin_header)
    await _signin(http_client, admin_header, terminal_id)
    await _open(http_client, admin_header, terminal_id)

    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/cash-in",
        json={"amount": 5000.0, "description": "Refill"},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_cash_out(http_client, admin_header, mock_outbound_services):
    """POST /cash-out records a cash withdrawal on an open terminal."""
    terminal_id, _ = await _create_terminal(http_client, admin_header)
    await _signin(http_client, admin_header, terminal_id)
    await _open(http_client, admin_header, terminal_id)

    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/cash-out",
        json={"amount": 1500.0, "description": "Petty"},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_close(http_client, admin_header, mock_outbound_services):
    """POST /close transitions an opened terminal into Closed."""
    terminal_id, _ = await _create_terminal(http_client, admin_header)
    await _signin(http_client, admin_header, terminal_id)
    await _open(http_client, admin_header, terminal_id)

    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/close",
        json={"physical_amount": 50000.0},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_delivery_status_update_requires_pubsub_auth(http_client, admin_header, mock_outbound_services):
    """POST /terminals/{tid}/delivery-status is meant to be called by Dapr
    pub/sub subscribers, not by admin tokens. Calling it with a regular
    admin JWT is expected to be rejected with 401.

    This still exercises the route at integration level, just verifying
    its auth boundary rather than its happy-path business logic.
    """
    terminal_id, _ = await _create_terminal(http_client, admin_header)

    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/delivery-status",
        json={
            "event_id": "evt-lifecycle-001",
            "service": "report",
            "status": "delivered",
            "message": "ok",
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
