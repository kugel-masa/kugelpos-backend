"""Unit tests for tenant setup API endpoint."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_tenant_id_with_token

from app.api.v1.tenant import router as tenant_router

TENANT_ID = "test_tenant"


def make_app():
    app = FastAPI()
    app.include_router(tenant_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_tenant_id_with_token] = lambda: TENANT_ID
    return app


@pytest.mark.asyncio
async def test_create_tenant_success():
    app = make_app()

    with patch("app.api.v1.tenant.database_setup") as mock_db_setup:
        mock_db_setup.execute = AsyncMock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants",
                json={"tenant_id": TENANT_ID},
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["tenantId"] == TENANT_ID


@pytest.mark.asyncio
async def test_create_tenant_mismatch():
    app = make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/tenants",
            json={"tenant_id": "wrong_tenant"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_tenant_db_error():
    app = make_app()

    with patch("app.api.v1.tenant.database_setup") as mock_db_setup:
        mock_db_setup.execute = AsyncMock(side_effect=Exception("DB error"))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants",
                json={"tenant_id": TENANT_ID},
            )
    assert resp.status_code == 500
