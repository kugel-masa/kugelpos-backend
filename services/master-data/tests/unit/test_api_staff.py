"""Unit tests for staff master API endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from datetime import datetime

from kugel_common.exceptions import DocumentAlreadyExistsException, DocumentNotFoundException
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_tenant_id_with_security_by_query_optional

from app.api.v1.staff_master import router as staff_router
from app.dependencies.common import parse_sort

TENANT_ID = "test_tenant"
NOW = datetime(2025, 1, 1, 12, 0, 0)


def make_app():
    app = FastAPI()
    app.include_router(staff_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: TENANT_ID
    app.dependency_overrides[parse_sort] = lambda: [("id", 1)]
    return app


def _make_staff_doc(staff_id="STAFF001"):
    doc = MagicMock()
    doc.id = staff_id
    doc.name = "John Doe"
    doc.pin = "1234"
    doc.roles = ["cashier"]
    doc.created_at = NOW
    doc.updated_at = NOW
    return doc


def _staff_create_body(staff_id="STAFF001"):
    return {
        "id": staff_id,
        "name": "John Doe",
        "pin": "1234",
        "roles": ["cashier"],
    }


@pytest.mark.asyncio
async def test_create_staff_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_staff_async.return_value = _make_staff_doc()

    with patch(
        "app.api.v1.staff_master.get_staff_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/staff",
                json=_staff_create_body(),
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] == "STAFF001"


@pytest.mark.asyncio
async def test_create_staff_duplicate():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_staff_async.side_effect = DocumentAlreadyExistsException(
        "Staff already exists"
    )

    with patch(
        "app.api.v1.staff_master.get_staff_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/staff",
                json=_staff_create_body(),
            )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_list_staff_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_staff_all_paginated_async.return_value = (
        [_make_staff_doc("STAFF001"), _make_staff_doc("STAFF002")],
        2,
    )

    with patch(
        "app.api.v1.staff_master.get_staff_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/staff")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["metadata"] is not None


@pytest.mark.asyncio
async def test_get_staff_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_staff_by_id_async.return_value = _make_staff_doc()

    with patch(
        "app.api.v1.staff_master.get_staff_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/staff/STAFF001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] == "STAFF001"


@pytest.mark.asyncio
async def test_get_staff_not_found():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_staff_by_id_async.return_value = None

    with patch(
        "app.api.v1.staff_master.get_staff_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/staff/NOTFOUND")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_update_staff_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.update_staff_async.return_value = _make_staff_doc()

    with patch(
        "app.api.v1.staff_master.get_staff_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                f"/api/v1/tenants/{TENANT_ID}/staff/STAFF001",
                json={
                    "name": "Jane Doe",
                    "pin": "5678",
                    "roles": ["manager"],
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_delete_staff_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.delete_staff_async.return_value = None

    with patch(
        "app.api.v1.staff_master.get_staff_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"/api/v1/tenants/{TENANT_ID}/staff/STAFF001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
