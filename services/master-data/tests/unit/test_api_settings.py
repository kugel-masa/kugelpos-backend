"""Unit tests for settings master API endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from datetime import datetime

from kugel_common.exceptions import DocumentAlreadyExistsException, DocumentNotFoundException
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_tenant_id_with_security_by_query_optional

from app.api.v1.settings_master import router as settings_router
from app.dependencies.common import parse_sort

TENANT_ID = "test_tenant"
NOW = datetime(2025, 1, 1, 12, 0, 0)


def make_app():
    app = FastAPI()
    app.include_router(settings_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: TENANT_ID
    app.dependency_overrides[parse_sort] = lambda: [("name", 1)]
    return app


def _make_settings_value():
    val = MagicMock()
    val.store_code = "STORE01"
    val.terminal_no = 1
    val.value = "custom_value"
    return val


def _make_settings_doc(name="receipt_header"):
    doc = MagicMock()
    doc.name = name
    doc.default_value = "default"
    doc.values = [_make_settings_value()]
    doc.created_at = NOW
    doc.updated_at = NOW
    return doc


def _settings_create_body(name="receipt_header"):
    return {
        "name": name,
        "default_value": "default",
        "values": [
            {"store_code": "STORE01", "terminal_no": 1, "value": "custom_value"}
        ],
    }


@pytest.mark.asyncio
async def test_create_settings_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_settings_async.return_value = _make_settings_doc()

    with patch(
        "app.api.v1.settings_master.get_settings_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/settings",
                json=_settings_create_body(),
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_create_settings_duplicate():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_settings_async.side_effect = DocumentAlreadyExistsException(
        "Settings already exists"
    )

    with patch(
        "app.api.v1.settings_master.get_settings_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/settings",
                json=_settings_create_body(),
            )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_list_settings_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_settings_all_paginated_async.return_value = (
        [_make_settings_doc("receipt_header"), _make_settings_doc("store_name")],
        2,
    )

    with patch(
        "app.api.v1.settings_master.get_settings_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["metadata"] is not None


@pytest.mark.asyncio
async def test_get_settings_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_settings_by_name_async.return_value = _make_settings_doc()

    with patch(
        "app.api.v1.settings_master.get_settings_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/settings/receipt_header")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_get_settings_not_found():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_settings_by_name_async.return_value = None

    with patch(
        "app.api.v1.settings_master.get_settings_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/settings/NOTFOUND")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_get_settings_value_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_settings_value_by_name_async.return_value = "custom_value"

    with patch(
        "app.api.v1.settings_master.get_settings_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/tenants/{TENANT_ID}/settings/receipt_header/value",
                params={"store_code": "STORE01", "terminal_no": 1},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["value"] == "custom_value"


@pytest.mark.asyncio
async def test_get_settings_value_not_found():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_settings_value_by_name_async.return_value = None

    with patch(
        "app.api.v1.settings_master.get_settings_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/tenants/{TENANT_ID}/settings/NOTFOUND/value",
                params={"store_code": "STORE01", "terminal_no": 1},
            )
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_update_settings_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.update_settings_async.return_value = _make_settings_doc()

    with patch(
        "app.api.v1.settings_master.get_settings_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                f"/api/v1/tenants/{TENANT_ID}/settings/receipt_header",
                json={
                    "default_value": "new_default",
                    "values": [
                        {"store_code": "STORE01", "terminal_no": 1, "value": "new_value"}
                    ],
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_delete_settings_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.delete_settings_async.return_value = None

    with patch(
        "app.api.v1.settings_master.get_settings_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"/api/v1/tenants/{TENANT_ID}/settings/receipt_header")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
