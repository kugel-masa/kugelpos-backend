"""Unit tests for item common master API endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from datetime import datetime

from kugel_common.exceptions import DocumentAlreadyExistsException, DocumentNotFoundException
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_tenant_id_with_security_by_query_optional

from app.api.v1.item_common_master import router as item_router
from app.dependencies.common import parse_sort

TENANT_ID = "test_tenant"
NOW = datetime(2025, 1, 1, 12, 0, 0)


def make_app():
    app = FastAPI()
    app.include_router(item_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: TENANT_ID
    app.dependency_overrides[parse_sort] = lambda: [("item_code", 1)]
    return app


def _make_item_doc(code="ITEM001"):
    doc = MagicMock()
    doc.item_code = code
    doc.description = "Test Item"
    doc.unit_price = 100.0
    doc.unit_cost = 50.0
    doc.item_details = ["detail1"]
    doc.image_urls = ["http://example.com/img.jpg"]
    doc.category_code = "CAT001"
    doc.tax_code = "TAX01"
    doc.is_discount_restricted = False
    doc.is_deleted = False
    doc.created_at = NOW
    doc.updated_at = NOW
    return doc


def _item_create_body(code="ITEM001"):
    return {
        "item_code": code,
        "description": "Test Item",
        "unit_price": 100.0,
        "unit_cost": 50.0,
        "item_details": ["detail1"],
        "image_urls": ["http://example.com/img.jpg"],
        "category_code": "CAT001",
        "tax_code": "TAX01",
    }


@pytest.mark.asyncio
async def test_create_item_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_item_async.return_value = _make_item_doc()
    mock_service.item_common_master_repo = MagicMock()
    mock_service.item_common_master_repo.collection_name = "item_common_master"

    with patch(
        "app.api.v1.item_common_master.get_item_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/items",
                json=_item_create_body(),
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["itemCode"] == "ITEM001"


@pytest.mark.asyncio
async def test_create_item_duplicate():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_item_async.side_effect = DocumentAlreadyExistsException(
        "Item already exists"
    )
    mock_service.item_common_master_repo = MagicMock()
    mock_service.item_common_master_repo.collection_name = "item_common_master"

    with patch(
        "app.api.v1.item_common_master.get_item_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/items",
                json=_item_create_body(),
            )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_list_items_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_item_all_paginated_async.return_value = (
        [_make_item_doc("ITEM001"), _make_item_doc("ITEM002")],
        2,
    )

    with patch(
        "app.api.v1.item_common_master.get_item_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/items")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["metadata"] is not None


@pytest.mark.asyncio
async def test_get_item_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_item_by_code_async.return_value = _make_item_doc()

    with patch(
        "app.api.v1.item_common_master.get_item_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/items/ITEM001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["itemCode"] == "ITEM001"


@pytest.mark.asyncio
async def test_get_item_not_found():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_item_by_code_async.return_value = None

    with patch(
        "app.api.v1.item_common_master.get_item_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/items/NOTFOUND")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_update_item_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.update_item_async.return_value = _make_item_doc()

    with patch(
        "app.api.v1.item_common_master.get_item_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                f"/api/v1/tenants/{TENANT_ID}/items/ITEM001",
                json={
                    "description": "Updated Item",
                    "unit_price": 200.0,
                    "unit_cost": 100.0,
                    "item_details": ["updated"],
                    "image_urls": [],
                    "category_code": "CAT001",
                    "tax_code": "TAX01",
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_delete_item_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.delete_item_async.return_value = None

    with patch(
        "app.api.v1.item_common_master.get_item_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"/api/v1/tenants/{TENANT_ID}/items/ITEM001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["itemCode"] == "ITEM001"
