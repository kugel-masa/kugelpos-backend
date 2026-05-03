"""
Unit tests for tenant API endpoint.
Tests use FastAPI dependency overrides with mock services.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.api.v1.tenant import router
from kugel_common.security import get_tenant_id_with_token


# -- helpers --

TENANT = "test_tenant"


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


# -- fixtures --

@pytest.fixture
def app():
    app = _make_app()

    async def override_security():
        return TENANT

    app.dependency_overrides[get_tenant_id_with_token] = override_security
    return app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ===== create_tenant =====

@pytest.mark.asyncio
async def test_create_tenant_success(client):
    with patch("app.api.v1.tenant.database_setup") as mock_setup:
        mock_setup.execute = AsyncMock()

        payload = {"tenantId": TENANT}
        resp = await client.post("/api/v1/tenants", json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["tenantId"] == TENANT
    mock_setup.execute.assert_called_once_with(tenant_id=TENANT)


@pytest.mark.asyncio
async def test_create_tenant_id_mismatch(client):
    """When request tenant_id does not match token tenant_id, return 400."""
    payload = {"tenantId": "other_tenant"}
    resp = await client.post("/api/v1/tenants", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_tenant_setup_failure(client):
    """When database setup fails, return 500."""
    with patch("app.api.v1.tenant.database_setup") as mock_setup:
        mock_setup.execute = AsyncMock(side_effect=Exception("DB connection failed"))

        payload = {"tenantId": TENANT}
        resp = await client.post("/api/v1/tenants", json=payload)

    assert resp.status_code == 500
