"""Unit tests for tax master API endpoints (list and get only)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from datetime import datetime

from kugel_common.exceptions import DocumentNotFoundException
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_tenant_id_with_security_by_query_optional

from app.api.v1.tax_master import router as tax_router
from app.dependencies.common import parse_sort

TENANT_ID = "test_tenant"


def make_app():
    app = FastAPI()
    app.include_router(tax_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: TENANT_ID
    app.dependency_overrides[parse_sort] = lambda: [("tax_code", 1)]
    return app


def _make_tax_doc(code="TAX01"):
    doc = MagicMock()
    doc.tax_code = code
    doc.tax_type = "inclusive"
    doc.tax_name = "Standard Tax"
    doc.rate = 10.0
    doc.round_digit = 0
    doc.round_method = "round"
    doc.created_at = None
    doc.updated_at = None
    return doc


@pytest.mark.asyncio
async def test_list_taxes_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_all_taxes_paginated_async.return_value = (
        [_make_tax_doc("TAX01"), _make_tax_doc("TAX02")],
        2,
    )

    with patch(
        "app.api.v1.tax_master.get_tax_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/taxes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["metadata"] is not None


@pytest.mark.asyncio
async def test_get_tax_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_tax_by_code_async.return_value = _make_tax_doc()

    with patch(
        "app.api.v1.tax_master.get_tax_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/taxes/TAX01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["taxCode"] == "TAX01"


@pytest.mark.asyncio
async def test_get_tax_not_found():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_tax_by_code_async.return_value = None

    with patch(
        "app.api.v1.tax_master.get_tax_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/taxes/NOTFOUND")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
