"""Unit tests for payment master API endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from datetime import datetime

from kugel_common.exceptions import DocumentAlreadyExistsException, DocumentNotFoundException
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_tenant_id_with_security_by_query_optional, get_tenant_id_refusing_terminal

from app.api.v1.payment_master import router as payment_router
from app.dependencies.common import parse_sort

TENANT_ID = "test_tenant"
NOW = datetime(2025, 1, 1, 12, 0, 0)


def make_app():
    app = FastAPI()
    app.include_router(payment_router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: TENANT_ID
    app.dependency_overrides[get_tenant_id_refusing_terminal] = lambda: TENANT_ID
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


# Payment variants (issue #311)


def _variant(code="VISA", name="VISA", is_active=True):
    from app.models.documents.payment_master_document import PaymentVariant

    return PaymentVariant(variant_code=code, name=name, is_active=is_active, created_at=NOW)


async def _call(app, method, url, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


VARIANTS_URL = f"/api/v1/tenants/{TENANT_ID}/payments/11/variants"


@pytest.mark.asyncio
async def test_create_payment_variant_success():
    mock_service = AsyncMock()
    mock_service.add_variant_async.return_value = _variant()

    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=mock_service):
        resp = await _call(make_app(), "POST", VARIANTS_URL, json={"variantCode": "VISA", "name": "VISA"})

    assert resp.status_code == 201
    assert resp.json()["data"] == {
        "variantCode": "VISA",
        "name": "VISA",
        "isActive": True,
        "entryDatetime": "2025-01-01 12:00:00",
        "lastUpdateDatetime": None,
    }
    mock_service.add_variant_async.assert_awaited_once_with("11", "VISA", "VISA", True)


@pytest.mark.asyncio
async def test_create_payment_variant_duplicate():
    mock_service = AsyncMock()
    mock_service.add_variant_async.side_effect = DocumentAlreadyExistsException("dup", None)

    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=mock_service):
        resp = await _call(make_app(), "POST", VARIANTS_URL, json={"variantCode": "VISA", "name": "VISA"})

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_payment_variant_under_an_unknown_method():
    mock_service = AsyncMock()
    mock_service.add_variant_async.side_effect = DocumentNotFoundException("nf", None)

    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=mock_service):
        resp = await _call(make_app(), "POST", VARIANTS_URL, json={"variantCode": "VISA", "name": "VISA"})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_payment_variant_with_a_bad_code_is_refused():
    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=AsyncMock()):
        resp = await _call(make_app(), "POST", VARIANTS_URL, json={"variantCode": "a/b", "name": "VISA"})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_and_get_payment_variants():
    mock_service = AsyncMock()
    mock_service.get_variants_async.return_value = [_variant("JCB", "JCB"), _variant("VISA", "VISA", False)]
    mock_service.get_variant_async.return_value = _variant("VISA", "VISA", False)

    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=mock_service):
        listed = await _call(make_app(), "GET", VARIANTS_URL)
        one = await _call(make_app(), "GET", f"{VARIANTS_URL}/VISA")

    assert listed.status_code == 200
    assert [v["variantCode"] for v in listed.json()["data"]] == ["JCB", "VISA"]
    assert one.status_code == 200
    assert one.json()["data"]["isActive"] is False


@pytest.mark.asyncio
async def test_update_payment_variant_success():
    mock_service = AsyncMock()
    mock_service.update_variant_async.return_value = _variant("VISA", "VISA card", False)

    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=mock_service):
        resp = await _call(make_app(), "PUT", f"{VARIANTS_URL}/VISA", json={"name": "VISA card", "isActive": False})

    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "VISA card"
    mock_service.update_variant_async.assert_awaited_once_with("11", "VISA", "VISA card", False)


@pytest.mark.asyncio
async def test_update_payment_variant_refuses_the_code_in_the_body():
    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=AsyncMock()):
        resp = await _call(
            make_app(), "PUT", f"{VARIANTS_URL}/VISA", json={"name": "VISA", "isActive": True, "variantCode": "JCB"}
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_a_payment_variant_cannot_be_deleted():
    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=AsyncMock()):
        resp = await _call(make_app(), "DELETE", f"{VARIANTS_URL}/VISA")

    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_a_terminal_cannot_write_payment_variants_but_can_read_them():
    from fastapi import HTTPException

    def _refuse_terminal():
        raise HTTPException(status_code=403, detail="terminal")

    app = make_app()
    app.dependency_overrides[get_tenant_id_refusing_terminal] = _refuse_terminal
    mock_service = AsyncMock()
    mock_service.get_variants_async.return_value = []

    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=mock_service):
        created = await _call(app, "POST", VARIANTS_URL, json={"variantCode": "VISA", "name": "VISA"})
        updated = await _call(app, "PUT", f"{VARIANTS_URL}/VISA", json={"name": "VISA", "isActive": True})
        listed = await _call(app, "GET", VARIANTS_URL)

    assert created.status_code == 403
    assert updated.status_code == 403
    assert listed.status_code == 200


@pytest.mark.asyncio
async def test_get_payment_carries_its_variants():
    from app.models.documents.payment_master_document import PaymentMasterDocument

    doc = PaymentMasterDocument(
        tenant_id=TENANT_ID,
        payment_code="11",
        description="Cashless",
        limit_amount=0.0,
        can_refund=True,
        can_deposit_over=False,
        can_change=False,
        is_active=True,
        created_at=NOW,
        variants=[_variant("VISA", "VISA"), _variant("AMEX", "AMEX", False)],
    )
    mock_service = AsyncMock()
    mock_service.get_payment_by_code.return_value = doc

    with patch("app.api.v1.payment_master.get_payment_master_service_async", return_value=mock_service):
        resp = await _call(make_app(), "GET", f"/api/v1/tenants/{TENANT_ID}/payments/11")

    assert resp.status_code == 200
    assert [v["variantCode"] for v in resp.json()["data"]["variants"]] == ["AMEX", "VISA"]
