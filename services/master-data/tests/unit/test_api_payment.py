"""Unit tests for payment master API endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from datetime import datetime

from kugel_common.exceptions import DocumentAlreadyExistsException, DocumentNotFoundException
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_tenant_id_with_security_by_query_optional

from app.api.v1.payment_master import router as payment_router
from app.dependencies.common import parse_sort

TENANT_ID = "test_tenant"
NOW = datetime(2025, 1, 1, 12, 0, 0)


def make_app():
    app = FastAPI()
    app.include_router(payment_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: TENANT_ID
    app.dependency_overrides[parse_sort] = lambda: [("payment_code", 1)]
    return app


def _make_payment_doc(code="PAY001"):
    doc = MagicMock()
    doc.tenant_id = TENANT_ID
    doc.payment_code = code
    doc.description = "Cash"
    doc.limit_amount = 10000.0
    doc.can_refund = True
    doc.can_deposit_over = False
    doc.can_change = True
    doc.is_active = True
    doc.created_at = NOW
    doc.updated_at = NOW
    return doc


def _payment_create_body(code="PAY001"):
    return {
        "payment_code": code,
        "description": "Cash",
        "limit_amount": 10000.0,
        "can_refund": True,
        "can_deposit_over": False,
        "can_change": True,
        "is_active": True,
    }


@pytest.mark.asyncio
async def test_create_payment_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_payment_async.return_value = _make_payment_doc()

    with patch(
        "app.api.v1.payment_master.get_payment_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/payments",
                json=_payment_create_body(),
            )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["paymentCode"] == "PAY001"


@pytest.mark.asyncio
async def test_create_payment_duplicate():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.create_payment_async.side_effect = DocumentAlreadyExistsException(
        "Payment already exists"
    )

    with patch(
        "app.api.v1.payment_master.get_payment_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/tenants/{TENANT_ID}/payments",
                json=_payment_create_body(),
            )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_list_payments_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_all_payments_paginated.return_value = (
        [_make_payment_doc("PAY001"), _make_payment_doc("PAY002")],
        2,
    )

    with patch(
        "app.api.v1.payment_master.get_payment_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/payments")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["metadata"] is not None


@pytest.mark.asyncio
async def test_get_payment_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_payment_by_code.return_value = _make_payment_doc()

    with patch(
        "app.api.v1.payment_master.get_payment_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/payments/PAY001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["paymentCode"] == "PAY001"


@pytest.mark.asyncio
async def test_get_payment_not_found():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.get_payment_by_code.return_value = None

    with patch(
        "app.api.v1.payment_master.get_payment_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/tenants/{TENANT_ID}/payments/NOTFOUND")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_update_payment_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.update_payment_async.return_value = _make_payment_doc()

    with patch(
        "app.api.v1.payment_master.get_payment_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                f"/api/v1/tenants/{TENANT_ID}/payments/PAY001",
                json={
                    "description": "Updated Cash",
                    "limit_amount": 20000.0,
                    "can_refund": True,
                    "can_deposit_over": True,
                    "can_change": True,
                    "is_active": True,
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_delete_payment_success():
    app = make_app()
    mock_service = AsyncMock()
    mock_service.delete_payment_async.return_value = None

    with patch(
        "app.api.v1.payment_master.get_payment_master_service_async",
        return_value=mock_service,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"/api/v1/tenants/{TENANT_ID}/payments/PAY001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["paymentCode"] == "PAY001"
