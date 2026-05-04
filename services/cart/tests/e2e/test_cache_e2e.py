# Copyright 2026 masa@kugel
"""E2E coverage for cart cache management endpoints not exercised by
the cart state-machine tests:

  GET    /cache/terminal/status
  DELETE /cache/terminal
"""
import os

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient, Timeout


@pytest_asyncio.fixture(scope="function")
async def admin_token():
    base_account = os.environ.get("BASE_URL_ACCOUNT", "http://localhost:8000")
    tenant_id = os.environ.get("TENANT_ID")
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
async def test_cache_terminal_status(http_client, admin_token):
    """GET /cache/terminal/status returns cache stats for the tenant."""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = await http_client.get("/api/v1/cache/terminal/status", headers=h)
    assert r.status_code == status.HTTP_200_OK, r.text
    body = r.json()
    assert body["success"] is True
    # data dict keys are passed through as-is (snake_case), not aliased.
    data = body["data"]
    assert data["cache_type"] == "terminal_info"
    assert "tenant_cache_size" in data
    assert "total_cache_size" in data


@pytest.mark.asyncio
async def test_cache_terminal_clear(http_client, admin_token):
    """DELETE /cache/terminal clears the cache for the authenticated tenant."""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = await http_client.delete("/api/v1/cache/terminal", headers=h)
    assert r.status_code == status.HTTP_200_OK, r.text
    body = r.json()
    assert body["success"] is True
    assert "items_cleared" in body["data"]
