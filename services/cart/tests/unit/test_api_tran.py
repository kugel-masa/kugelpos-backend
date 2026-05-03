"""Unit tests for transaction API endpoints (app/api/v1/tran.py)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from kugel_common.exceptions import register_exception_handlers
from app.api.v1.tran import (
    router as tran_router,
    get_tran_service,
    get_tran_service_for_pubsub_notification,
    parse_sort,
)


def _make_app():
    app = FastAPI()
    app.include_router(tran_router, prefix="/api/v1")
    register_exception_handlers(app)
    return app


def _make_tran_service_mock():
    """Create a mock TranService with terminal_info."""
    svc = AsyncMock()
    terminal_info = MagicMock()
    terminal_info.terminal_id = "tenant1-store1-1"
    terminal_info.tenant_id = "tenant1"
    terminal_info.store_code = "store1"
    terminal_info.terminal_no = 1
    svc.terminal_info = terminal_info
    return svc


TRAN_DICT = {
    "tenant_id": "tenant1",
    "store_code": "store1",
    "store_name": "Test Store",
    "terminal_no": 1,
    "total_amount": 1000.0,
    "total_amount_with_tax": 1100.0,
    "total_quantity": 2,
    "total_discount_amount": 0.0,
    "deposit_amount": 1100.0,
    "change_amount": 0.0,
    "stamp_duty_amount": 0.0,
    "receipt_no": 1,
    "transaction_no": 100,
    "transaction_type": 1,
    "business_date": "20260320",
    "generate_date_time": "2026-03-20T10:00:00",
    "line_items": [],
    "payments": [],
    "taxes": [],
    "subtotal_discounts": [],
    "receipt_text": None,
    "journal_text": None,
    "staff": None,
    "status": None,
}


def _make_tran_schema_mock():
    """Return a mock that mimics a Tran schema object."""
    m = MagicMock()
    m.model_dump.return_value = TRAN_DICT
    return m


def _patch_transformer_tran():
    return patch(
        "app.api.v1.tran.SchemasTransformerV1.transform_tran",
        return_value=_make_tran_schema_mock(),
    )


BASE_TRAN_PATH = "/api/v1/tenants/tenant1/stores/store1/terminals/1/transactions"


# ---------------------------------------------------------------------------
# get_transactions_by_query
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_transactions_success():
    app = _make_app()
    svc = _make_tran_service_mock()

    paginated = MagicMock()
    paginated.data = [MagicMock()]  # one tranlog
    paginated.metadata.model_dump.return_value = {"total": 1, "page": 1, "limit": 100, "sort": None, "filter": None}
    svc.get_tranlog_by_query_async.return_value = paginated

    app.dependency_overrides[get_tran_service] = lambda: svc

    with _patch_transformer_tran():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(BASE_TRAN_PATH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_get_transactions_tenant_mismatch():
    app = _make_app()
    svc = _make_tran_service_mock()

    app.dependency_overrides[get_tran_service] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use wrong tenant_id in URL
        resp = await client.get(
            "/api/v1/tenants/wrong-tenant/stores/store1/terminals/1/transactions"
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_transactions_service_error():
    app = _make_app()
    svc = _make_tran_service_mock()
    svc.get_tranlog_by_query_async.side_effect = Exception("DB error")

    app.dependency_overrides[get_tran_service] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(BASE_TRAN_PATH)
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# get_transaction_by_transaction_no
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_transaction_success():
    app = _make_app()
    svc = _make_tran_service_mock()
    svc.get_tranlog_by_transaction_no_async.return_value = MagicMock()

    app.dependency_overrides[get_tran_service] = lambda: svc

    with _patch_transformer_tran():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"{BASE_TRAN_PATH}/100")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_get_transaction_tenant_mismatch():
    app = _make_app()
    svc = _make_tran_service_mock()

    app.dependency_overrides[get_tran_service] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/tenants/wrong/stores/store1/terminals/1/transactions/100"
        )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# void_transaction_by_transaction_no
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_void_transaction_success():
    app = _make_app()
    svc = _make_tran_service_mock()
    svc.get_tranlog_by_transaction_no_async.return_value = MagicMock()
    svc.void_async.return_value = MagicMock()

    app.dependency_overrides[get_tran_service] = lambda: svc

    with _patch_transformer_tran() as mock_transform:
        mock_transform.return_value = _make_tran_schema_mock()
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"{BASE_TRAN_PATH}/100/void",
                json=[{"payment_code": "CASH", "amount": 1100}],
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_void_transaction_store_mismatch():
    """Void with mismatched store_code raises InvalidRequestDataException."""
    app = _make_app()
    svc = _make_tran_service_mock()

    app.dependency_overrides[get_tran_service] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/tenants/tenant1/stores/wrong-store/terminals/1/transactions/100/void",
            json=[{"payment_code": "CASH", "amount": 1100}],
        )
    # InvalidRequestDataException has status_code=422
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_void_transaction_terminal_mismatch():
    """Void with mismatched terminal_no raises InvalidRequestDataException."""
    app = _make_app()
    svc = _make_tran_service_mock()

    app.dependency_overrides[get_tran_service] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/tenants/tenant1/stores/store1/terminals/99/transactions/100/void",
            json=[{"payment_code": "CASH", "amount": 1100}],
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# return_transaction_by_transaction_no
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_return_transaction_success():
    app = _make_app()
    svc = _make_tran_service_mock()
    svc.get_tranlog_by_transaction_no_async.return_value = MagicMock()
    svc.return_async.return_value = MagicMock()

    app.dependency_overrides[get_tran_service] = lambda: svc

    with _patch_transformer_tran() as mock_transform:
        mock_transform.return_value = _make_tran_schema_mock()
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"{BASE_TRAN_PATH}/100/return",
                json=[{"payment_code": "CASH", "amount": 1100}],
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_return_transaction_tenant_mismatch():
    app = _make_app()
    svc = _make_tran_service_mock()

    app.dependency_overrides[get_tran_service] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/tenants/wrong/stores/store1/terminals/1/transactions/100/return",
            json=[{"payment_code": "CASH", "amount": 1100}],
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# notify_delivery_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_delivery_status_success():
    app = _make_app()
    svc = _make_tran_service_mock()
    svc.update_delivery_status_async.return_value = None

    app.dependency_overrides[get_tran_service_for_pubsub_notification] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"{BASE_TRAN_PATH}/100/delivery-status",
            json={
                "event_id": "evt-001",
                "service": "journal",
                "status": "delivered",
                "message": "OK",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["event_id"] == "evt-001"


@pytest.mark.asyncio
async def test_notify_delivery_status_error():
    app = _make_app()
    svc = _make_tran_service_mock()
    svc.update_delivery_status_async.side_effect = Exception("Update failed")

    app.dependency_overrides[get_tran_service_for_pubsub_notification] = lambda: svc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"{BASE_TRAN_PATH}/100/delivery-status",
            json={
                "event_id": "evt-001",
                "service": "journal",
                "status": "delivered",
            },
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# parse_sort unit test
# ---------------------------------------------------------------------------


def test_parse_sort_default():
    result = parse_sort(sort=None)
    assert result == [("transaction_no", -1)]


def test_parse_sort_custom():
    result = parse_sort(sort="field1:1,field2:-1")
    assert result == [("field1", 1), ("field2", -1)]
