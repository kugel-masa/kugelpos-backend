"""Unit tests for tenant API endpoint (POST /tenants)."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api.v1.tenant import router
from kugel_common.security import get_tenant_id_with_token


def make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# POST /tenants
# ---------------------------------------------------------------------------

class TestCreateTenant:

    @pytest.mark.asyncio
    async def test_create_tenant_success(self):
        app = make_app()
        app.dependency_overrides[get_tenant_id_with_token] = lambda: "T001"

        with patch("app.api.v1.tenant.database_setup") as mock_setup:
            mock_setup.execute = AsyncMock()

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tenants",
                    json={"tenant_id": "T001"},
                )

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["tenantId"] == "T001"
        mock_setup.execute.assert_awaited_once_with(tenant_id="T001")

    @pytest.mark.asyncio
    async def test_create_tenant_id_mismatch_returns_400(self):
        app = make_app()
        app.dependency_overrides[get_tenant_id_with_token] = lambda: "T001"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tenants",
                json={"tenant_id": "T999"},
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_tenant_db_error_returns_500(self):
        app = make_app()
        app.dependency_overrides[get_tenant_id_with_token] = lambda: "T001"

        with patch("app.api.v1.tenant.database_setup") as mock_setup:
            mock_setup.execute = AsyncMock(side_effect=Exception("DB error"))

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tenants",
                    json={"tenant_id": "T001"},
                )

        assert response.status_code == 500
