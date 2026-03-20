"""Unit tests for tenant API endpoint (app/api/v1/tenant.py)."""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.api.v1.tenant import router
from kugel_common.security import get_tenant_id_with_token


def make_app(mock_tenant_id="test-tenant"):
    """Create a FastAPI app with overridden dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_tenant_id_with_token] = lambda: mock_tenant_id
    return app


CREATE_TENANT_URL = "/api/v1/tenants"


# ---------------------------------------------------------------------------
# create_tenant
# ---------------------------------------------------------------------------
class TestCreateTenant:
    @pytest.mark.asyncio
    @patch("app.api.v1.tenant.database_setup")
    async def test_success(self, mock_db_setup):
        """Happy path: tenant is created successfully."""
        mock_db_setup.execute = AsyncMock(return_value=None)
        app = make_app(mock_tenant_id="test-tenant")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                CREATE_TENANT_URL,
                json={"tenant_id": "test-tenant"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["tenantId"] == "test-tenant"

    @pytest.mark.asyncio
    async def test_mismatched_tenant_id_returns_400(self):
        """Tenant ID in body does not match token -> 400."""
        app = make_app(mock_tenant_id="test-tenant")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                CREATE_TENANT_URL,
                json={"tenant_id": "wrong-tenant"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    @patch("app.api.v1.tenant.database_setup")
    async def test_database_setup_failure_returns_500(self, mock_db_setup):
        """If database_setup.execute raises, endpoint returns 500."""
        mock_db_setup.execute = AsyncMock(side_effect=Exception("db error"))
        app = make_app(mock_tenant_id="test-tenant")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                CREATE_TENANT_URL,
                json={"tenant_id": "test-tenant"},
            )
        assert resp.status_code == 500
