"""Unit tests for category master API endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from datetime import datetime

from kugel_common.exceptions import DocumentAlreadyExistsException, DocumentNotFoundException
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_tenant_id_with_security_by_query_optional
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.schemas.base_schemas import Metadata

from app.api.v1.category_master import router as category_router
from app.dependencies.common import parse_sort

TENANT_ID = "test_tenant"
NOW = datetime(2025, 1, 1, 12, 0, 0)


def make_app():
    app = FastAPI()
    app.include_router(category_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: TENANT_ID
    app.dependency_overrides[parse_sort] = lambda: [("category_code", 1)]
    return app


def _make_category_doc(code="CAT001"):
    doc = MagicMock()
    doc.category_code = code
    doc.description = "Test Category"
    doc.description_short = "TC"
    doc.tax_code = "TAX01"
    doc.tenant_id = TENANT_ID
    doc.created_at = NOW
    doc.updated_at = NOW
    return doc


def _make_paginated_result(docs):
    result = MagicMock()
    result.data = docs
    result.metadata = Metadata(total=len(docs), page=1, limit=100, sort=None, filter=None)
    return result


@pytest.mark.asyncio
async def test_create_category_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_category_async.return_value = _make_category_doc()

    with patch(
        "app.api.v1.category_master.get_category_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/categories",
                json={
                    "category_code": "CAT001",
                    "description": "Test Category",
                    "description_short": "TC",
                    "tax_code": "TAX01",
                },
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["categoryCode"] == "CAT001"


@pytest.mark.asyncio
async def test_create_category_duplicate():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_category_async.side_effect = DocumentAlreadyExistsException(
        "Category already exists"
    )

    with patch(
        "app.api.v1.category_master.get_category_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/categories",
                json={
                    "category_code": "CAT001",
                    "description": "Test Category",
                    "description_short": "TC",
                    "tax_code": "TAX01",
                },
            )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_list_categories_success():
    app = make_app()
    mock_service = AsyncMock()
    docs = [_make_category_doc("CAT001"), _make_category_doc("CAT002")]
    mock_service.get_categories_paginated_async.return_value = _make_paginated_result(docs)

    with patch(
        "app.api.v1.category_master.get_category_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/categories")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["metadata"] is not None


@pytest.mark.asyncio
async def test_get_category_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_category_by_code_async.return_value = _make_category_doc()

    with patch(
        "app.api.v1.category_master.get_category_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/categories/CAT001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["categoryCode"] == "CAT001"


@pytest.mark.asyncio
async def test_get_category_not_found():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_category_by_code_async.return_value = None

    with patch(
        "app.api.v1.category_master.get_category_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/categories/NOTFOUND")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_update_category_success():
    app = make_app()
    mock_service = AsyncMock()
    updated_doc = _make_category_doc()
    updated_doc.description = "Updated"
    mock_service.update_category_async.return_value = updated_doc

    with patch(
        "app.api.v1.category_master.get_category_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                f"/api/v1/tenants/{TENANT_ID}/categories/CAT001",
                json={
                    "description": "Updated",
                    "description_short": "U",
                    "tax_code": "TAX01",
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_delete_category_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.delete_category_async.return_value = None

    with patch(
        "app.api.v1.category_master.get_category_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"/api/v1/tenants/{TENANT_ID}/categories/CAT001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["categoryCode"] == "CAT001"
