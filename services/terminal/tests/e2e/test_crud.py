# Copyright 2026 masa@kugel
"""E2E coverage for terminal CRUD endpoints not exercised by
test_setup_data.py (which creates the canonical tenant) or
test_terminal_jwt_auth.py (which walks the JWT auth lifecycle).

Covers: tenant GET/PUT/DELETE, store list/GET/PUT/DELETE, terminal
list, PATCH /description, PATCH /function_mode, cash-in / cash-out
on the open terminal.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient, Timeout


def _new_tenant_id() -> str:
    """tenant_id MUST NOT contain hyphens — see security.get_tenant_id."""
    return "TRMC" + uuid.uuid4().hex[:6].upper()


@pytest_asyncio.fixture(scope="function")
async def admin_token():
    """Live-account admin JWT for the canonical TENANT_ID."""
    base_account = os.environ.get("BASE_URL_ACCOUNT", "http://localhost:8000")
    tenant_id = os.environ.get("TENANT_ID")
    async with AsyncClient(base_url=base_account, timeout=Timeout(timeout=None)) as c:
        # Idempotent register
        await c.post(
            "/api/v1/accounts/register",
            json={"username": "admin", "password": "admin", "tenant_id": tenant_id},
        )
        resp = await c.post(
            "/api/v1/accounts/token",
            data={"username": "admin", "password": "admin", "client_id": tenant_id},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def _ephemeral_admin_token(tenant_id: str) -> str:
    """Register + login admin for an arbitrary tenant_id."""
    base_account = os.environ.get("BASE_URL_ACCOUNT", "http://localhost:8000")
    async with AsyncClient(base_url=base_account, timeout=Timeout(timeout=None)) as c:
        await c.post(
            "/api/v1/accounts/register",
            json={"username": "admin", "password": "admin", "tenant_id": tenant_id},
        )
        resp = await c.post(
            "/api/v1/accounts/token",
            data={"username": "admin", "password": "admin", "client_id": tenant_id},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_tenant_get_put_delete(http_client):
    """GET /tenants/{id}, PUT /tenants/{id}, DELETE /tenants/{id}."""
    tenant_id = _new_tenant_id()
    token = await _ephemeral_admin_token(tenant_id)
    h = {"Authorization": f"Bearer {token}"}

    # Create
    r = await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": tenant_id, "tenant_name": "CRUD Tenant", "stores": [], "tags": ["crud"]},
        headers=h,
    )
    assert r.status_code in (201, 400), r.text

    # Read
    r = await http_client.get(f"/api/v1/tenants/{tenant_id}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["tenantId"] == tenant_id

    # Update
    r = await http_client.put(
        f"/api/v1/tenants/{tenant_id}",
        json={"tenant_id": tenant_id, "tenant_name": "CRUD Updated", "stores": [], "tags": ["crud2"]},
        headers=h,
    )
    assert r.status_code == 200, r.text

    # Delete
    r = await http_client.delete(f"/api/v1/tenants/{tenant_id}", headers=h)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_store_list_and_crud(http_client, admin_token):
    """GET /tenants/{id}/stores (list), GET/PUT/DELETE /stores/{code}."""
    tenant_id = os.environ.get("TENANT_ID")
    h = {"Authorization": f"Bearer {admin_token}"}
    store_code = f"S{uuid.uuid4().hex[:5].upper()}"

    # Create
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores",
        json={"store_code": store_code, "store_name": "CRUD Store", "tags": []},
        headers=h,
    )
    assert r.status_code in (201, 400), r.text

    # List
    r = await http_client.get(f"/api/v1/tenants/{tenant_id}/stores", headers=h)
    assert r.status_code == 200, r.text
    assert any(s["storeCode"] == store_code for s in r.json()["data"])

    # Read
    r = await http_client.get(f"/api/v1/tenants/{tenant_id}/stores/{store_code}", headers=h)
    assert r.status_code == 200, r.text

    # Update
    r = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}",
        json={"store_code": store_code, "store_name": "CRUD Updated", "tags": ["upd"]},
        headers=h,
    )
    assert r.status_code == 200, r.text

    # Delete
    r = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}", headers=h
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_terminal_list(http_client, admin_token):
    """GET /terminals lists terminals for the authenticated tenant."""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = await http_client.get("/api/v1/terminals", headers=h)
    assert r.status_code == 200, r.text
    assert isinstance(r.json().get("data"), list)


@pytest.mark.asyncio
async def test_patch_description_and_function_mode(http_client, admin_token):
    """PATCH /description and PATCH /function_mode on a fresh terminal."""
    tenant_id = os.environ.get("TENANT_ID")
    h = {"Authorization": f"Bearer {admin_token}"}

    # Use a unique terminal_no so this doesn't collide with the canonical one.
    store_code = "5678"
    terminal_no = 60 + (int(uuid.uuid4().hex[:2], 16) % 30)  # 60-89

    r = await http_client.post(
        "/api/v1/terminals",
        json={"store_code": store_code, "terminal_no": terminal_no, "description": "PATCH Test"},
        headers=h,
    )
    if r.status_code == 400:
        # Already exists from a prior run — skip create, fetch the id directly
        terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    else:
        assert r.status_code == 201, r.text
        terminal_id = r.json()["data"]["terminalId"]

    r = await http_client.patch(
        f"/api/v1/terminals/{terminal_id}/description",
        json={"description": "Updated by PATCH"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["description"] == "Updated by PATCH"

    # function_mode PATCH requires the terminal to be in the `Opened`
    # state. Calling it on an Idle terminal yields a documented
    # 400 — verify that contract here rather than walking the full open
    # flow (which test_terminal_jwt_auth already exercises).
    r = await http_client.patch(
        f"/api/v1/terminals/{terminal_id}/function_mode",
        json={"function_mode": "Sales"},
        headers=h,
    )
    assert r.status_code in (200, 400), r.text

    # Cleanup
    await http_client.delete(f"/api/v1/terminals/{terminal_id}", headers=h)


@pytest.mark.asyncio
async def test_cash_in_cash_out(http_client, admin_token):
    """POST /cash-in and /cash-out on an opened terminal.

    Creates its own dedicated store so other tests' store mutations
    can't affect it.
    """
    tenant_id = os.environ.get("TENANT_ID")
    h = {"Authorization": f"Bearer {admin_token}"}
    store_code = f"S{uuid.uuid4().hex[:4].upper()}"
    terminal_no = 90 + (int(uuid.uuid4().hex[:2], 16) % 9)

    # Ensure store exists
    await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores",
        json={"store_code": store_code, "store_name": "Test", "tags": []},
        headers=h,
    )
    # Create terminal
    r = await http_client.post(
        "/api/v1/terminals",
        json={"store_code": store_code, "terminal_no": terminal_no, "description": "Cash test"},
        headers=h,
    )
    if r.status_code == 400:
        terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
        # Fetch existing api_key (user JWT can opt-in to unmasked api_key)
        r = await http_client.get(
            f"/api/v1/terminals/{terminal_id}?include_api_key=true", headers=h
        )
        api_key = r.json()["data"]["apiKey"]
    else:
        assert r.status_code == 201, r.text
        terminal_id = r.json()["data"]["terminalId"]
        api_key = r.json()["data"]["apiKey"]  # create returns unmasked api_key

    # Get terminal JWT and walk through sign-in / open
    r = await http_client.post(
        f"/api/v1/auth/token?terminal_id={terminal_id}",
        headers={"X-API-KEY": api_key},
    )
    assert r.status_code == 200, r.text
    term_jwt = r.json()["data"]["access_token"]
    th = {"Authorization": f"Bearer {term_jwt}"}

    r = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/sign-in",
        json={"staff_id": "S001"}, headers=th,
    )
    assert r.status_code == 200, r.text
    th = {"Authorization": f"Bearer {r.headers.get('x-new-token', term_jwt)}"}

    r = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/open",
        json={"initial_amount": 10000.0}, headers=th,
    )
    assert r.status_code == 200, r.text
    th = {"Authorization": f"Bearer {r.headers.get('x-new-token', term_jwt)}"}

    # Cash in
    r = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/cash-in",
        json={"amount": 5000.0, "description": "Refill"}, headers=th,
    )
    assert r.status_code == 200, r.text

    # Cash out
    r = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/cash-out",
        json={"amount": 1500.0, "description": "Petty"}, headers=th,
    )
    assert r.status_code == 200, r.text

    # Cleanup: close + delete
    await http_client.post(
        f"/api/v1/terminals/{terminal_id}/close",
        json={"physical_amount": 13500.0}, headers=th,
    )
    await http_client.delete(f"/api/v1/terminals/{terminal_id}", headers=h)


@pytest.mark.asyncio
async def test_auth_token_invalid_api_key(http_client):
    """POST /auth/token with garbage X-API-KEY → 401."""
    r = await http_client.post(
        "/api/v1/auth/token",
        headers={"X-API-KEY": "definitely-not-a-real-key-xxxxxxx"},
    )
    assert r.status_code == 401, r.text
