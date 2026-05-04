"""Unit tests for journal API endpoints (POST and GET journals)."""

import pytest
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api.v1.journal import router, parse_sort
from app.dependencies.get_journal_service import get_journal_service
from app.models.documents.jornal_document import JournalDocument
from kugel_common.security import get_tenant_id_with_security_by_query_optional
from kugel_common.schemas.base_schemas import Metadata
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.exceptions import register_exception_handlers


def make_app():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    return app


def _sample_journal_doc(**overrides):
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        transaction_no=100,
        transaction_type=101,
        business_date="20260101",
        open_counter=1,
        business_counter=1,
        generate_date_time="20260101T120000",
        receipt_no=1,
        amount=1000.0,
        quantity=3,
        staff_id="staff1",
        user_id="user1",
        journal_text="journal text",
        receipt_text="receipt text",
    )
    defaults.update(overrides)
    return JournalDocument(**defaults)


# ---------------------------------------------------------------------------
# POST /tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/journals
# ---------------------------------------------------------------------------

class TestReceiveJournals:

    @pytest.mark.asyncio
    async def test_receive_journals_success(self):
        mock_service = AsyncMock()
        mock_service.receive_journal_async.return_value = _sample_journal_doc()

        app = make_app()
        app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
        app.dependency_overrides[get_journal_service] = lambda: mock_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tenants/T001/stores/S001/terminals/1/journals",
                json={
                    "tenant_id": "T001",
                    "store_code": "S001",
                    "terminal_no": 1,
                    "transaction_type": 101,
                    "business_date": "20260101",
                    "open_counter": 1,
                    "business_counter": 1,
                    "generate_date_time": "20260101T120000",
                    "journal_text": "journal text",
                    "receipt_text": "receipt text",
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        # response_model=ApiResponse (no type param), data is plain dict with snake_case keys
        assert body["data"]["tenant_id"] == "T001"
        mock_service.receive_journal_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_receive_journals_service_error_returns_500(self):
        mock_service = AsyncMock()
        mock_service.receive_journal_async.side_effect = Exception("DB error")

        app = make_app()
        app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
        app.dependency_overrides[get_journal_service] = lambda: mock_service

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tenants/T001/stores/S001/terminals/1/journals",
                json={
                    "tenant_id": "T001",
                    "store_code": "S001",
                    "terminal_no": 1,
                    "transaction_type": 101,
                    "business_date": "20260101",
                    "open_counter": 1,
                    "business_counter": 1,
                    "generate_date_time": "20260101T120000",
                    "journal_text": "journal text",
                    "receipt_text": "receipt text",
                },
            )

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /tenants/{tenant_id}/stores/{store_code}/journals
# ---------------------------------------------------------------------------

class TestGetJournals:

    @pytest.mark.asyncio
    async def test_get_journals_success(self):
        doc = _sample_journal_doc()
        metadata = Metadata(total=1, page=1, limit=100, sort=None, filter=None)
        paginated = PaginatedResult(data=[doc], metadata=metadata)

        mock_service = AsyncMock()
        mock_service.get_journals_paginated_async.return_value = paginated

        app = make_app()
        app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
        app.dependency_overrides[get_journal_service] = lambda: mock_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/tenants/T001/stores/S001/journals")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1
        # response_model=ApiResponse[list[JournalSchema]] serializes with by_alias (camelCase)
        assert body["data"][0]["tenantId"] == "T001"

    @pytest.mark.asyncio
    async def test_get_journals_empty_list(self):
        metadata = Metadata(total=0, page=1, limit=100, sort=None, filter=None)
        paginated = PaginatedResult(data=[], metadata=metadata)

        mock_service = AsyncMock()
        mock_service.get_journals_paginated_async.return_value = paginated

        app = make_app()
        app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
        app.dependency_overrides[get_journal_service] = lambda: mock_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/tenants/T001/stores/S001/journals")

        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["metadata"]["total"] == 0

    @pytest.mark.asyncio
    async def test_get_journals_service_error_returns_500(self):
        mock_service = AsyncMock()
        mock_service.get_journals_paginated_async.side_effect = Exception("DB error")

        app = make_app()
        app.dependency_overrides[get_tenant_id_with_security_by_query_optional] = lambda: "T001"
        app.dependency_overrides[get_journal_service] = lambda: mock_service

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/tenants/T001/stores/S001/journals")

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# parse_sort utility
# ---------------------------------------------------------------------------

class TestParseSort:

    def test_default_sort(self):
        result = parse_sort(sort=None)
        assert result == [("terminal_no", 1), ("business_date", 1), ("receipt_no", 1)]

    def test_custom_sort(self):
        result = parse_sort(sort="amount:-1,receipt_no:1")
        assert result == [("amount", -1), ("receipt_no", 1)]
