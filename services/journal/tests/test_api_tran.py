"""Unit tests for transaction/pub-sub API endpoints in tran.py."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api.v1.tran import router, get_log_service, get_log_service_from_request
from app.services.log_service import LogService
from kugel_common.security import get_tenant_id_with_security_by_query_optional
from kugel_common.exceptions import register_exception_handlers


def make_app():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    return app


def _mock_log_service():
    svc = AsyncMock(spec=LogService)
    svc.receive_tranlog_async = AsyncMock()
    svc.receive_cashlog_async = AsyncMock()
    svc.receive_open_close_log_async = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# POST /tranlog  (Dapr pub/sub)
# ---------------------------------------------------------------------------

class TestHandleTranlog:

    @pytest.mark.asyncio
    async def test_health_check_returns_success(self):
        """Health check message should be handled without a real LogService."""
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tranlog",
                json={"data": {"test": "health-check"}},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_tranlog_success(self):
        """Valid tranlog message should be processed successfully."""
        mock_svc = _mock_log_service()
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: mock_svc

        with patch("app.api.v1.tran.get_state", new_callable=AsyncMock, return_value=None), \
             patch("app.api.v1.tran.save_state", new_callable=AsyncMock, return_value=True), \
             patch("app.api.v1.tran._notify_pubsub_status", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tranlog",
                    json={
                        "data": {
                            "event_id": "evt-001",
                            "tenant_id": "T001",
                            "store_code": "S001",
                            "terminal_no": 1,
                            "transaction_no": 100,
                            "transaction_type": 101,
                            "business_date": "20260101",
                            "open_counter": 1,
                            "business_counter": 1,
                            "generate_date_time": "20260101T120000",
                            "receipt_no": 1,
                            "items": [],
                            "payments": [],
                            "tax_details": [],
                        }
                    },
                )

        assert response.status_code == 200
        mock_svc.receive_tranlog_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tranlog_missing_event_id_returns_drop(self):
        """Missing event_id in data should return DROP status."""
        mock_svc = _mock_log_service()
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: mock_svc

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tranlog",
                json={"data": {"tenant_id": "T001"}},
            )

        # handle_log returns a tuple (dict, status_code); FastAPI serializes the tuple as JSON array
        assert response.status_code == 200
        body = response.json()
        assert body[0]["status"] == "DROP"
        assert body[1] == 400

    @pytest.mark.asyncio
    async def test_tranlog_duplicate_event_returns_success(self):
        """Already-processed event_id should return SUCCESS without re-processing."""
        mock_svc = _mock_log_service()
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: mock_svc

        with patch("app.api.v1.tran.get_state", new_callable=AsyncMock, return_value={"event_id": "evt-001"}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tranlog",
                    json={
                        "data": {
                            "event_id": "evt-001",
                            "tenant_id": "T001",
                            "store_code": "S001",
                            "terminal_no": 1,
                            "transaction_no": 100,
                            "transaction_type": 101,
                            "business_date": "20260101",
                            "open_counter": 1,
                            "business_counter": 1,
                            "generate_date_time": "20260101T120000",
                            "receipt_no": 1,
                            "items": [],
                            "payments": [],
                            "tax_details": [],
                        }
                    },
                )

        assert response.status_code == 200
        body = response.json()
        assert body[0]["status"] == "SUCCESS"
        mock_svc.receive_tranlog_async.assert_not_awaited()


# ---------------------------------------------------------------------------
# POST /cashlog  (Dapr pub/sub)
# ---------------------------------------------------------------------------

class TestHandleCashlog:

    @pytest.mark.asyncio
    async def test_cashlog_health_check(self):
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/cashlog",
                json={"data": {"test": "health-check"}},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "SUCCESS"


# ---------------------------------------------------------------------------
# POST /opencloselog  (Dapr pub/sub)
# ---------------------------------------------------------------------------

class TestHandleOpencloselog:

    @pytest.mark.asyncio
    async def test_opencloselog_health_check(self):
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/opencloselog",
                json={"data": {"test": "health-check"}},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "SUCCESS"


# ---------------------------------------------------------------------------
# POST /tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions
# ---------------------------------------------------------------------------

class TestReceiveTransactions:

    @pytest.mark.asyncio
    async def test_receive_transactions_success(self):
        mock_svc = _mock_log_service()
        app = make_app()
        app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
        app.dependency_overrides[get_log_service] = lambda: mock_svc

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tenants/T001/stores/S001/terminals/1/transactions",
                json={
                    "event_id": "evt-001",
                    "tenant_id": "T001",
                    "store_code": "S001",
                    "terminal_no": 1,
                    "transaction_no": 100,
                    "transaction_type": 101,
                    "business_date": "20260101",
                    "open_counter": 1,
                    "business_counter": 1,
                    "generate_date_time": "20260101T120000",
                    "receipt_no": 1,
                    "items": [],
                    "payments": [],
                    "tax_details": [],
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        # response_model=ApiResponse[TranResponse] serializes with by_alias (camelCase)
        assert body["data"]["transactionNo"] == 100
        mock_svc.receive_tranlog_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_receive_transactions_service_error_returns_500(self):
        mock_svc = _mock_log_service()
        mock_svc.receive_tranlog_async.side_effect = Exception("DB error")

        app = make_app()
        app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
        app.dependency_overrides[get_log_service] = lambda: mock_svc

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tenants/T001/stores/S001/terminals/1/transactions",
                json={
                    "event_id": "evt-001",
                    "tenant_id": "T001",
                    "store_code": "S001",
                    "terminal_no": 1,
                    "transaction_no": 100,
                    "transaction_type": 101,
                    "business_date": "20260101",
                    "open_counter": 1,
                    "business_counter": 1,
                    "generate_date_time": "20260101T120000",
                    "receipt_no": 1,
                    "items": [],
                    "payments": [],
                    "tax_details": [],
                },
            )

        assert response.status_code == 500
