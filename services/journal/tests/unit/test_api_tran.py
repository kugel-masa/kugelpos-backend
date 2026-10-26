"""Unit tests for transaction/pub-sub API endpoints in tran.py."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api.v1.tran import router, get_log_service, get_log_service_from_request
from app.services.log_service import LogService
from kugel_common.security import get_tenant_id_with_security_by_query_optional
from kugel_common.exceptions import register_exception_handlers

import os
from kugel_common.utils.dapr_app_token import DAPR_APP_TOKEN_HEADER

# What the service's Dapr sidecar sends on every pub/sub delivery (issue #134).
DAPR_DELIVERY_HEADERS = {DAPR_APP_TOKEN_HEADER: os.environ["APP_API_TOKEN"]}


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
                "/api/v1/tranlog", headers=DAPR_DELIVERY_HEADERS,
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
                    "/api/v1/tranlog", headers=DAPR_DELIVERY_HEADERS,
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
                "/api/v1/tranlog", headers=DAPR_DELIVERY_HEADERS,
                json={"data": {"tenant_id": "T001"}},
            )

        # DROP is honoured by Dapr only on a 2xx; a non-2xx would be retried (#135)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "DROP"

    @pytest.mark.asyncio
    async def test_tranlog_duplicate_event_returns_success(self):
        """Already-processed event_id should return SUCCESS without re-processing."""
        mock_svc = _mock_log_service()
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: mock_svc

        with patch("app.api.v1.tran.get_state", new_callable=AsyncMock, return_value={"event_id": "evt-001"}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tranlog", headers=DAPR_DELIVERY_HEADERS,
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
        assert body["status"] == "SUCCESS"
        mock_svc.receive_tranlog_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_tranlog_duplicate_at_db_layer_returns_success_not_retry(self):
        """If DuplicateKeyException leaks past the state-store check (state
        evicted / TTL expired), the handler must return 200 SUCCESS rather
        than 500 RETRY — otherwise Dapr loops forever on a row that already
        exists. See issue #97."""
        from kugel_common.exceptions import DuplicateKeyException

        mock_svc = _mock_log_service()
        mock_svc.receive_tranlog_async.side_effect = DuplicateKeyException(
            message="duplicate", collection_name="log_tran", key={"event_id": "evt-dup-001"}
        )
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: mock_svc

        with patch("app.api.v1.tran.get_state", new_callable=AsyncMock, return_value=None), \
             patch("app.api.v1.tran.save_state", new_callable=AsyncMock, return_value=True) as save_mock, \
             patch("app.api.v1.tran._notify_pubsub_status", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/tranlog", headers=DAPR_DELIVERY_HEADERS,
                    json={
                        "data": {
                            "event_id": "evt-dup-001",
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

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "SUCCESS"
        # Best-effort state save to short-circuit future redeliveries
        save_mock.assert_awaited()


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
                "/api/v1/cashlog", headers=DAPR_DELIVERY_HEADERS,
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
                "/api/v1/opencloselog", headers=DAPR_DELIVERY_HEADERS,
                json={"data": {"test": "health-check"}},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "SUCCESS"


# ---------------------------------------------------------------------------
# POST /tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions
# ---------------------------------------------------------------------------

class TestReceiveTransactions:

    # Minimal payload satisfying the receive_transactions input-validation
    # contract (sales / staff / user are required nested blocks; the
    # contents only need to be parseable by BaseTransaction).
    _VALID_TRAN_PAYLOAD = {
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
        "sales": {"total_amount_with_tax": 100.0, "total_quantity": 1},
        "staff": {"id": "S001", "name": "Staff One"},
        "user": {"id": "u1"},
    }

    @pytest.mark.asyncio
    async def test_receive_transactions_success(self):
        mock_svc = _mock_log_service()
        app = make_app()
        app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
        app.dependency_overrides[get_log_service] = lambda: mock_svc

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tenants/T001/stores/S001/terminals/1/transactions",
                json=self._VALID_TRAN_PAYLOAD,
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
                json=self._VALID_TRAN_PAYLOAD,
            )

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# Dapr status contract (issue #135)
# ---------------------------------------------------------------------------
# Dapr acts on the HTTP status: a non-2xx is retried (and dead-lettered once
# the retries run out), a 2xx is acked. handle_log used to return a
# ``(body, status)`` tuple, which FastAPI serialised as a JSON array under
# 200, so every failed event was acked and lost.
PUBSUB_ENDPOINTS = [
    ("/api/v1/cashlog", "receive_cashlog_async"),
    ("/api/v1/opencloselog", "receive_open_close_log_async"),
]


class TestDaprStatusContract:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("url,receive_method", PUBSUB_ENDPOINTS)
    async def test_processing_failure_returns_500_retry(self, url, receive_method):
        mock_svc = _mock_log_service()
        getattr(mock_svc, receive_method).side_effect = RuntimeError("db down")
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: mock_svc

        with patch("app.api.v1.tran.get_state", new_callable=AsyncMock, return_value=None), \
             patch("app.api.v1.tran.save_state", new_callable=AsyncMock, return_value=True) as save_mock, \
             patch("app.api.v1.tran._notify_pubsub_status", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(url, headers=DAPR_DELIVERY_HEADERS, json={"data": {"event_id": "evt-fail-001", "tenant_id": "T001"}})

        assert response.status_code == 500, response.text
        assert response.json()["status"] == "RETRY"
        # A failed event must not be marked as processed, or the retry is skipped
        save_mock.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("url,receive_method", PUBSUB_ENDPOINTS)
    async def test_success_returns_200_success(self, url, receive_method):
        mock_svc = _mock_log_service()
        app = make_app()
        app.dependency_overrides[get_log_service_from_request] = lambda: mock_svc

        with patch("app.api.v1.tran.get_state", new_callable=AsyncMock, return_value=None), \
             patch("app.api.v1.tran.save_state", new_callable=AsyncMock, return_value=True), \
             patch("app.api.v1.tran._notify_pubsub_status", new_callable=AsyncMock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(url, headers=DAPR_DELIVERY_HEADERS, json={"data": {"event_id": "evt-ok-001", "tenant_id": "T001"}})

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "SUCCESS"
        getattr(mock_svc, receive_method).assert_awaited_once()
