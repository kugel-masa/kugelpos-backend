"""Unit tests for transaction/pub-sub API endpoints (app/api/v1/tran.py)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.api.v1.tran import router, get_log_service, get_log_service_from_request
from kugel_common.security import get_tenant_id_with_security_by_query_optional

import os
from kugel_common.utils.dapr_app_token import DAPR_APP_TOKEN_HEADER

# What the service's Dapr sidecar sends on every pub/sub delivery (issue #134).
DAPR_DELIVERY_HEADERS = {DAPR_APP_TOKEN_HEADER: os.environ["APP_API_TOKEN"]}


def make_app(mock_log_service=None, mock_tenant_id="test-tenant"):
    """Create a FastAPI app with overridden dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    if mock_log_service is None:
        mock_log_service = AsyncMock()

    app.dependency_overrides[get_log_service] = lambda: mock_log_service
    app.dependency_overrides[get_log_service_from_request] = lambda: mock_log_service
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: mock_tenant_id
    return app


RECEIVE_TRAN_URL = "/api/v1/tenants/test-tenant/stores/STORE01/terminals/1/transactions"


# ---------------------------------------------------------------------------
# receive_transactions (REST endpoint)
# ---------------------------------------------------------------------------
class TestReceiveTransactions:
    @pytest.mark.asyncio
    async def test_success(self):
        """Happy path: transaction is received and stored."""
        mock_service = AsyncMock()
        mock_service.receive_tranlog_async.return_value = None
        app = make_app(mock_log_service=mock_service)

        tran_data = {
            "tenant_id": "test-tenant",
            "store_code": "STORE01",
            "terminal_no": 1,
            "transaction_no": 100,
            "business_date": "20260101",
            "open_counter": 1,
            "transaction_type": 1,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(RECEIVE_TRAN_URL, json=tran_data)
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["transactionNo"] == 100

    @pytest.mark.asyncio
    async def test_service_error_propagates(self):
        """If receive_tranlog_async raises, the exception propagates (no try/except in endpoint)."""
        mock_service = AsyncMock()
        mock_service.receive_tranlog_async.side_effect = Exception("db error")
        app = make_app(mock_log_service=mock_service)

        tran_data = {
            "tenant_id": "test-tenant",
            "store_code": "STORE01",
            "terminal_no": 1,
            "transaction_no": 100,
            "business_date": "20260101",
            "open_counter": 1,
            "transaction_type": 1,
        }

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(RECEIVE_TRAN_URL, json=tran_data)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# handle_tranlog (pub/sub endpoint)
# ---------------------------------------------------------------------------
class TestHandleTranlog:
    @pytest.mark.asyncio
    async def test_health_check_returns_success(self):
        """Health check messages should be dropped with success."""
        # For health check, get_log_service_from_request returns None
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_log_service_from_request] = lambda: None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tranlog", headers=DAPR_DELIVERY_HEADERS,
                json={"data": {"test": "health-check"}},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_null_service_non_health_returns_500(self):
        """When log_service is None and it is not a health check, return 500."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_log_service_from_request] = lambda: None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tranlog", headers=DAPR_DELIVERY_HEADERS,
                json={"data": {"event_id": "evt-1", "tenant_id": "t1"}},
            )
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_duplicate_at_db_layer_returns_success_not_retry(self):
        """If DuplicateKeyException leaks past the state-store check (state
        evicted / TTL expired), the handler must return 200 SUCCESS rather
        than 500 RETRY — otherwise Dapr loops forever on a row that already
        exists. See issue #97."""
        from kugel_common.exceptions import DuplicateKeyException

        mock_service = AsyncMock()
        mock_service.receive_tranlog_async.side_effect = DuplicateKeyException(
            message="duplicate", collection_name="log_tran", key={"event_id": "evt-dup-001"}
        )
        app = make_app(mock_log_service=mock_service)

        # state-store says "not seen" so handler proceeds to DB write,
        # which raises DuplicateKeyException.
        with patch(
            "app.api.v1.tran.state_store_manager.get_state",
            new_callable=AsyncMock,
            return_value=(None, None),
        ), patch(
            "app.api.v1.tran.state_store_manager.save_state",
            new_callable=AsyncMock,
            return_value=(True, None),
        ) as save_mock, patch(
            "app.api.v1.tran._notify_pubsub_status", new_callable=AsyncMock
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/tranlog", headers=DAPR_DELIVERY_HEADERS,
                    json={
                        "data": {
                            "event_id": "evt-dup-001",
                            "tenant_id": "test-tenant",
                            "store_code": "STORE01",
                            "terminal_no": 1,
                            "transaction_no": 100,
                            "transaction_type": 101,
                            "business_date": "20260101",
                            "open_counter": 1,
                            "business_counter": 1,
                            "generate_date_time": "20260101T120000",
                            "receipt_no": 1,
                        }
                    },
                )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "SUCCESS"
        # Best-effort state save to short-circuit future redeliveries
        save_mock.assert_awaited()


# ---------------------------------------------------------------------------
# handle_cashlog (pub/sub endpoint)
# ---------------------------------------------------------------------------
class TestHandleCashlog:
    @pytest.mark.asyncio
    async def test_health_check_returns_success(self):
        """Health check messages for cashlog are dropped with success."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_log_service_from_request] = lambda: None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/cashlog", headers=DAPR_DELIVERY_HEADERS,
                json={"data": {"test": "health-check"}},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "SUCCESS"


# ---------------------------------------------------------------------------
# handle_opencloselog (pub/sub endpoint)
# ---------------------------------------------------------------------------
class TestHandleOpenCloseLog:
    @pytest.mark.asyncio
    async def test_health_check_returns_success(self):
        """Health check messages for opencloselog are dropped with success."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_log_service_from_request] = lambda: None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/opencloselog", headers=DAPR_DELIVERY_HEADERS,
                json={"data": {"test": "health-check"}},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "SUCCESS"


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
        mock_service = AsyncMock()
        getattr(mock_service, receive_method).side_effect = RuntimeError("db down")
        app = make_app(mock_log_service=mock_service)

        with patch(
            "app.api.v1.tran.state_store_manager.get_state",
            new_callable=AsyncMock,
            return_value=(None, None),
        ), patch(
            "app.api.v1.tran.state_store_manager.save_state",
            new_callable=AsyncMock,
            return_value=(True, None),
        ) as save_mock, patch("app.api.v1.tran._notify_pubsub_status", new_callable=AsyncMock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(url, headers=DAPR_DELIVERY_HEADERS, json={"data": {"event_id": "evt-fail-001", "tenant_id": "test-tenant"}})

        assert resp.status_code == 500, resp.text
        assert resp.json()["status"] == "RETRY"
        # A failed event must not be marked as processed, or the retry is skipped
        save_mock.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("url,receive_method", PUBSUB_ENDPOINTS)
    async def test_success_returns_200_success(self, url, receive_method):
        mock_service = AsyncMock()
        app = make_app(mock_log_service=mock_service)

        with patch(
            "app.api.v1.tran.state_store_manager.get_state",
            new_callable=AsyncMock,
            return_value=(None, None),
        ), patch(
            "app.api.v1.tran.state_store_manager.save_state",
            new_callable=AsyncMock,
            return_value=(True, None),
        ), patch("app.api.v1.tran._notify_pubsub_status", new_callable=AsyncMock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(url, headers=DAPR_DELIVERY_HEADERS, json={"data": {"event_id": "evt-ok-001", "tenant_id": "test-tenant"}})

        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "SUCCESS"
        getattr(mock_service, receive_method).assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_event_id_returns_200_drop(self):
        """DROP is honoured only on a 2xx; a 400 would be redelivered forever."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/cashlog", headers=DAPR_DELIVERY_HEADERS, json={"data": {"tenant_id": "test-tenant"}})

        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "DROP"
