"""Unit tests for item store master API endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from datetime import datetime

from kugel_common.exceptions import DocumentAlreadyExistsException, DocumentNotFoundException
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_tenant_id_with_security_by_query_optional

from app.api.v1.item_store_master import router as item_store_router
from app.dependencies.common import parse_sort

TENANT_ID = "test_tenant"
STORE_CODE = "STORE01"
NOW = datetime(2025, 1, 1, 12, 0, 0)


def make_app():
    app = FastAPI()
    app.include_router(item_store_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: TENANT_ID
    app.dependency_overrides[parse_sort] = lambda: [("item_code", 1)]
    return app


def _make_item_store_doc(code="ITEM001"):
    doc = MagicMock()
    doc.item_code = code
    doc.store_price = 120.0
    doc.created_at = NOW
    doc.updated_at = NOW
    return doc


def _make_item_store_detail_doc(code="ITEM001"):
    doc = MagicMock()
    doc.item_code = code
    doc.description = "Test Item"
    doc.unit_price = 100.0
    doc.unit_cost = 50.0
    doc.store_price = 120.0
    doc.item_details = ["detail1"]
    doc.image_urls = ["http://example.com/img.jpg"]
    doc.category_code = "CAT001"
    doc.tax_code = "TAX01"
    doc.is_discount_restricted = False
    doc.is_deleted = False
    doc.created_at = NOW
    doc.updated_at = NOW
    return doc


@pytest.mark.asyncio
async def test_create_item_store_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_item_async.return_value = _make_item_store_doc()

    with patch(
        "app.api.v1.item_store_master.get_item_store_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/stores/{STORE_CODE}/items",
                json={"item_code": "ITEM001", "store_price": 120.0},
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["itemCode"] == "ITEM001"


@pytest.mark.asyncio
async def test_create_item_store_duplicate():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_item_async.side_effect = DocumentAlreadyExistsException(
        "Item store already exists"
    )

    with patch(
        "app.api.v1.item_store_master.get_item_store_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/stores/{STORE_CODE}/items",
                json={"item_code": "ITEM001", "store_price": 120.0},
            )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_list_item_store_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_item_all_paginated_async.return_value = (
        [_make_item_store_doc("ITEM001"), _make_item_store_doc("ITEM002")],
        2,
    )

    with patch(
        "app.api.v1.item_store_master.get_item_store_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/tenants/{TENANT_ID}/stores/{STORE_CODE}/items"
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["metadata"] is not None


@pytest.mark.asyncio
async def test_get_item_store_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_item_by_code_async.return_value = _make_item_store_doc()

    with patch(
        "app.api.v1.item_store_master.get_item_store_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/tenants/{TENANT_ID}/stores/{STORE_CODE}/items/ITEM001"
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["itemCode"] == "ITEM001"


@pytest.mark.asyncio
async def test_get_item_store_not_found():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_item_by_code_async.return_value = None

    with patch(
        "app.api.v1.item_store_master.get_item_store_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/tenants/{TENANT_ID}/stores/{STORE_CODE}/items/NOTFOUND"
            )
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_update_item_store_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.update_item_async.return_value = _make_item_store_doc()

    with patch(
        "app.api.v1.item_store_master.get_item_store_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                f"/api/v1/tenants/{TENANT_ID}/stores/{STORE_CODE}/items/ITEM001",
                json={"store_price": 150.0},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_delete_item_store_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.delete_item_async.return_value = None

    with patch(
        "app.api.v1.item_store_master.get_item_store_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/api/v1/tenants/{TENANT_ID}/stores/{STORE_CODE}/items/ITEM001"
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["itemCode"] == "ITEM001"


@pytest.mark.asyncio
async def test_get_item_store_detail_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_item_store_detail_by_code_async.return_value = _make_item_store_detail_doc()

    with patch(
        "app.api.v1.item_store_master.get_item_store_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/tenants/{TENANT_ID}/stores/{STORE_CODE}/items/ITEM001/details"
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["itemCode"] == "ITEM001"
    assert body["data"]["storePrice"] == 120.0


@pytest.mark.asyncio
async def test_get_item_store_detail_not_found():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_item_store_detail_by_code_async.return_value = None

    with patch(
        "app.api.v1.item_store_master.get_item_store_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/tenants/{TENANT_ID}/stores/{STORE_CODE}/items/NOTFOUND/details"
            )
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
