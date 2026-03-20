"""
Unit tests for terminal API endpoints.

Tests the request/response flow through the terminal router using
httpx.AsyncClient + ASGITransport with mocked service layer.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, HTTPException, status

from app.api.v1.terminal import router
from app.dependencies.get_terminal_service import (
    get_tenant_id_with_token_wrapper,
    get_tenant_id_with_security_wrapper,
    get_tenant_id_with_security_by_query_optional_wrapper,
    get_tenant_id_for_pubsub_notification,
    parse_sort,
)
from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.open_close_log import OpenCloseLog
from app.models.documents.cash_in_out_log import CashInOutLog
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.schemas.base_schemas import Metadata


TENANT_ID = "T001"
TERMINAL_ID = "T001-S001-1"
NOW = datetime(2025, 1, 1, 12, 0, 0)


def _make_terminal_doc(**overrides) -> TerminalInfoDocument:
    defaults = dict(
        terminal_id=TERMINAL_ID,
        tenant_id=TENANT_ID,
        store_code="S001",
        terminal_no=1,
        description="Register 1",
        function_mode="Sales",
        status="Closed",
        business_date="20250101",
        open_counter=1,
        business_counter=0,
        initial_amount=0.0,
        physical_amount=0.0,
        staff=None,
        api_key="test-api-key",
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return TerminalInfoDocument(**defaults)


def _make_open_close_log(**overrides) -> OpenCloseLog:
    terminal_doc = _make_terminal_doc()
    defaults = dict(
        tenant_id=TENANT_ID,
        store_code="S001",
        terminal_no=1,
        business_date="20250101",
        open_counter=1,
        business_counter=0,
        operation="open",
        terminal_info=terminal_doc,
        receipt_text="OPEN RECEIPT",
        journal_text="OPEN JOURNAL",
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return OpenCloseLog(**defaults)


def _make_cash_log(**overrides) -> CashInOutLog:
    defaults = dict(
        tenant_id=TENANT_ID,
        store_code="S001",
        terminal_no=1,
        amount=100.0,
        description="Cash In",
        receipt_text="CASH RECEIPT",
        journal_text="CASH JOURNAL",
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return CashInOutLog(**defaults)


def make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    # Override auth dependencies
    app.dependency_overrides[get_tenant_id_with_token_wrapper] = lambda: TENANT_ID
    app.dependency_overrides[get_tenant_id_with_security_wrapper] = lambda: TENANT_ID
    app.dependency_overrides[get_tenant_id_with_security_by_query_optional_wrapper] = lambda: TENANT_ID
    app.dependency_overrides[get_tenant_id_for_pubsub_notification] = lambda: TENANT_ID
    app.dependency_overrides[parse_sort] = lambda: [("terminal_id", 1)]
    return app


# ---------------------------------------------------------------------------
# POST /terminals  (create)
# ---------------------------------------------------------------------------
class TestCreateTerminal:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.staff_master_repo = MagicMock(tenant_id=TENANT_ID)
        mock_service.create_terminal_async.return_value = _make_terminal_doc()

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/terminals",
                    json={"store_code": "S001", "terminal_no": 1, "description": "Register 1"},
                )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["terminalId"] == TERMINAL_ID

    @pytest.mark.asyncio
    async def test_service_raises_exception(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.staff_master_repo = MagicMock(tenant_id=TENANT_ID)
        mock_service.create_terminal_async.side_effect = HTTPException(
            status_code=400, detail="Duplicate terminal"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/terminals",
                    json={"store_code": "S001", "terminal_no": 1, "description": "Register 1"},
                )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /terminals  (list)
# ---------------------------------------------------------------------------
class TestGetTerminals:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        terminal_doc = _make_terminal_doc()
        mock_service.get_terminal_info_list_paginated_async.return_value = PaginatedResult(
            data=[terminal_doc],
            metadata=Metadata(total=1, page=1, limit=100, sort=None, filter=None),
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/terminals")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 1

    @pytest.mark.asyncio
    async def test_empty_list(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.get_terminal_info_list_paginated_async.return_value = PaginatedResult(
            data=[],
            metadata=Metadata(total=0, page=1, limit=100, sort=None, filter=None),
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/terminals")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# GET /terminals/{terminal_id}  (get)
# ---------------------------------------------------------------------------
class TestGetTerminal:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.get_terminal_info_async.return_value = _make_terminal_doc()

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/terminals/{TERMINAL_ID}")
        assert resp.status_code == 200
        assert resp.json()["data"]["terminalId"] == TERMINAL_ID

    @pytest.mark.asyncio
    async def test_not_found(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.get_terminal_info_async.side_effect = HTTPException(
            status_code=404, detail="Terminal not found"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/terminals/{TERMINAL_ID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /terminals/{terminal_id}
# ---------------------------------------------------------------------------
class TestDeleteTerminal:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.delete_terminal_async.return_value = None

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(f"/api/v1/terminals/{TERMINAL_ID}")
        assert resp.status_code == 200
        assert resp.json()["data"]["terminalId"] == TERMINAL_ID

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.delete_terminal_async.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(f"/api/v1/terminals/{TERMINAL_ID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /terminals/{terminal_id}/description
# ---------------------------------------------------------------------------
class TestUpdateDescription:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.update_terminal_description_async.return_value = _make_terminal_doc(
            description="Updated"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(
                    f"/api/v1/terminals/{TERMINAL_ID}/description",
                    json={"description": "Updated"},
                )
        assert resp.status_code == 200
        assert resp.json()["data"]["description"] == "Updated"

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.update_terminal_description_async.side_effect = HTTPException(
            status_code=404, detail="Not found"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(
                    f"/api/v1/terminals/{TERMINAL_ID}/description",
                    json={"description": "Updated"},
                )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /terminals/{terminal_id}/function_mode
# ---------------------------------------------------------------------------
class TestUpdateFunctionMode:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.update_terminal_function_mode_async.return_value = _make_terminal_doc(
            function_mode="Return"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(
                    f"/api/v1/terminals/{TERMINAL_ID}/function_mode",
                    json={"function_mode": "Return"},
                )
        assert resp.status_code == 200
        assert resp.json()["data"]["functionMode"] == "Return"

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.update_terminal_function_mode_async.side_effect = HTTPException(
            status_code=400, detail="Invalid mode"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(
                    f"/api/v1/terminals/{TERMINAL_ID}/function_mode",
                    json={"function_mode": "Invalid"},
                )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /terminals/{terminal_id}/sign-in
# ---------------------------------------------------------------------------
class TestSignIn:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.sign_in_terminal_async.return_value = _make_terminal_doc(status="SignedIn")

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/sign-in",
                    json={"staff_id": "STAFF01"},
                )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.sign_in_terminal_async.side_effect = HTTPException(
            status_code=400, detail="Already signed in"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/sign-in",
                    json={"staff_id": "STAFF01"},
                )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /terminals/{terminal_id}/sign-out
# ---------------------------------------------------------------------------
class TestSignOut:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.sign_out_terminal_async.return_value = _make_terminal_doc(status="Closed")

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(f"/api/v1/terminals/{TERMINAL_ID}/sign-out")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.sign_out_terminal_async.side_effect = HTTPException(
            status_code=400, detail="Not signed in"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(f"/api/v1/terminals/{TERMINAL_ID}/sign-out")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /terminals/{terminal_id}/open
# ---------------------------------------------------------------------------
class TestTerminalOpen:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.open_terminal_async.return_value = _make_open_close_log(operation="open")

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/open",
                    json={"initial_amount": 10000},
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["terminalId"] == TERMINAL_ID

    @pytest.mark.asyncio
    async def test_no_body(self):
        """Open with no request body should default to None initial_amount."""
        app = make_app()
        mock_service = AsyncMock()
        mock_service.open_terminal_async.return_value = _make_open_close_log(operation="open")

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(f"/api/v1/terminals/{TERMINAL_ID}/open")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.open_terminal_async.side_effect = HTTPException(
            status_code=400, detail="Already open"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/open",
                    json={"initial_amount": 10000},
                )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /terminals/{terminal_id}/close
# ---------------------------------------------------------------------------
class TestTerminalClose:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.close_terminal_async.return_value = _make_open_close_log(operation="close")

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/close",
                    json={"physical_amount": 15000},
                )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_no_body(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.close_terminal_async.return_value = _make_open_close_log(operation="close")

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(f"/api/v1/terminals/{TERMINAL_ID}/close")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.close_terminal_async.side_effect = HTTPException(
            status_code=400, detail="Not open"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/close",
                    json={"physical_amount": 15000},
                )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /terminals/{terminal_id}/cash-in
# ---------------------------------------------------------------------------
class TestCashIn:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.cash_in_out_async.return_value = _make_cash_log(amount=500.0, description="Petty cash")

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/cash-in",
                    json={"amount": 500.0, "description": "Petty cash"},
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["amount"] == 500.0

    @pytest.mark.asyncio
    async def test_default_description(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.cash_in_out_async.return_value = _make_cash_log(
            amount=100.0, description="Cash In (Default)"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/cash-in",
                    json={"amount": 100.0},
                )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.cash_in_out_async.side_effect = HTTPException(
            status_code=400, detail="Terminal not open"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/cash-in",
                    json={"amount": 500.0},
                )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /terminals/{terminal_id}/cash-out
# ---------------------------------------------------------------------------
class TestCashOut:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.cash_in_out_async.return_value = _make_cash_log(
            amount=-200.0, description="Withdrawal"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/cash-out",
                    json={"amount": 200.0, "description": "Withdrawal"},
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["amount"] == -200.0

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.cash_in_out_async.side_effect = HTTPException(
            status_code=400, detail="Not enough cash"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/cash-out",
                    json={"amount": 200.0},
                )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /terminals/{terminal_id}/delivery-status
# ---------------------------------------------------------------------------
class TestDeliveryStatus:
    @pytest.mark.asyncio
    async def test_success(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.update_delivery_status_async.return_value = None

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/delivery-status",
                    json={
                        "event_id": "EVT001",
                        "service": "report",
                        "status": "delivered",
                    },
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["event_id"] == "EVT001"
        assert body["data"]["success"] is True

    @pytest.mark.asyncio
    async def test_service_error(self):
        app = make_app()
        mock_service = AsyncMock()
        mock_service.update_delivery_status_async.side_effect = HTTPException(
            status_code=500, detail="Internal error"
        )

        with patch("app.api.v1.terminal.get_terminal_service_async", return_value=mock_service):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/terminals/{TERMINAL_ID}/delivery-status",
                    json={
                        "event_id": "EVT001",
                        "service": "report",
                        "status": "delivered",
                    },
                )
        assert resp.status_code == 500
