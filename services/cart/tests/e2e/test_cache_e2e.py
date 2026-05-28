# Copyright 2026 masa@kugel
"""E2E coverage for the cart master-data cache management endpoint:

  DELETE /cache/master-data

(The terminal_info cache and its endpoints were removed in #127.)
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
async def test_invalidate_master_data_cache(http_client, admin_token):
    """DELETE /cache/master-data bumps the namespace generation for the tenant."""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = await http_client.delete(
        "/api/v1/cache/master-data",
        params={"namespace": "promotion_master", "store_code": "5678"},
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["cache_type"] == "master_data"
    assert data["namespace"] == "promotion_master"
    assert data["new_generation"] >= 1
