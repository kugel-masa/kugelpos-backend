# Copyright 2026 masa@kugel
"""E2E setup: ensure tenant DB on stock service."""
import os

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient, Timeout


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _ensure_admin_user():
    """Register admin user on the live account service if not present."""
    from fastapi import status as http_status

    base_account = os.environ.get("BASE_URL_ACCOUNT", "http://localhost:8000")
    tenant_id = os.environ.get("TENANT_ID")
    async with AsyncClient(base_url=base_account, timeout=Timeout(timeout=None)) as client:
        login = await client.post(
            "/api/v1/accounts/token",
            data={"username": "admin", "password": "admin", "client_id": tenant_id},
        )
        if login.status_code == http_status.HTTP_200_OK:
            return
        await client.post(
            "/api/v1/accounts/register",
            json={"username": "admin", "password": "admin", "tenant_id": tenant_id},
        )


@pytest_asyncio.fixture(scope="function")
async def admin_token(_ensure_admin_user):
    base_account = os.environ.get("BASE_URL_ACCOUNT", "http://localhost:8000")
    tenant_id = os.environ.get("TENANT_ID")
    async with AsyncClient(base_url=base_account, timeout=Timeout(timeout=None)) as client:
        response = await client.post(
            "/api/v1/accounts/token",
            data={"username": "admin", "password": "admin", "client_id": tenant_id},
        )
        response.raise_for_status()
        return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def admin_header(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.mark.asyncio
async def test_setup_data(http_client, admin_header):
    """POST /tenants on stock initialises the per-tenant DB."""
    tenant_id = os.environ.get("TENANT_ID")
    response = await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": tenant_id},
        headers=admin_header,
    )
    assert response.status_code in (
        status.HTTP_201_CREATED,
        status.HTTP_400_BAD_REQUEST,
    ), response.text
