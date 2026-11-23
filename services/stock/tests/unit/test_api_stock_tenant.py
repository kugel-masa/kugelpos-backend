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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error, expected",
    [
        # The #185 detail is commons' own text and is kept for the operator
        (
            "database",
            "DatabaseException: Index tenant_id_1 is not unique. Documents sharing this key: {'tenant_id': 'T1'} x2",
        ),
        # A driver error is summarised, anything else is named by its type (#318)
        ("driver", "DuplicateKeyError: code->11000, codeName->DuplicateKey"),
        ("other", "ValueError"),
    ],
)
async def test_a_setup_failure_carries_only_a_safe_reason(client, error, expected):
    from kugel_common.database.database_exceptions import DatabaseException
    from pymongo.errors import DuplicateKeyError

    errors = {
        "database": DatabaseException(
            "Index tenant_id_1 is not unique. Documents sharing this key: {'tenant_id': 'T1'} x2"
        ),
        "driver": DuplicateKeyError(
            'dup key: { pin: "9876" }', 11000, {"code": 11000, "codeName": "DuplicateKey", "keyValue": {"pin": "9876"}}
        ),
        "other": ValueError("pin=9876"),
    }
    with patch("app.api.v1.tenant.database_setup") as mock_setup:
        mock_setup.execute = AsyncMock(side_effect=errors[error])

        resp = await client.post("/api/v1/tenants", json={"tenantId": TENANT})

    assert resp.status_code == 500
    assert "9876" not in resp.text
    body = resp.json()
    # The test app has no shared handlers, so the HTTPException comes back as FastAPI's "detail"
    assert body.get("message", body.get("detail")) == f"Error creating tenant: {TENANT} : {expected}"
