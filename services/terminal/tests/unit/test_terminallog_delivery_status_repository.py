# Copyright 2026 masa@kugel
"""Unit tests for TestTerminallogDeliveryStatusRepository (split from
test_repositories.py by class group)."""
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta

import pytest

from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.tenant_info_document import TenantInfoDocument, StoreInfo
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.models.documents.terminallog_delivery_status_document import TerminallogDeliveryStatus
from kugel_common.exceptions import (
    AlreadyExistException,
    CannotCreateException,
    NotFoundException,
    UpdateNotWorkException,
    CannotDeleteException,
    DuplicateKeyException,
)
from kugel_common.schemas.pagination import PaginatedResult, Metadata

from ._helpers import _mock_db


# ===========================================================================

class TestTerminallogDeliveryStatusRepository:
    """Tests for TerminallogDeliveryStatusRepository."""

    def _make_terminal_info(self, **overrides):
        from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument as CommonTerminalInfoDoc
        defaults = dict(
            tenant_id="T1",
            store_code="S1",
            terminal_no=1,
            business_date="20260101",
            open_counter=5,
        )
        defaults.update(overrides)
        return CommonTerminalInfoDoc(**defaults)

    def _make_repo(self, terminal_info=None):
        from app.models.repositories.terminallog_delivery_status_repository import TerminallogDeliveryStatusRepository
        if terminal_info is None:
            terminal_info = self._make_terminal_info()
        return TerminallogDeliveryStatusRepository(_mock_db(), terminal_info)

    # -- create_status_async --------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_status_success(self):
        repo = self._make_repo()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create:
            result = await repo.create_status_async(
                event_id="evt-001",
                payload={"type": "tranlog"},
                services=[{"service_name": "report", "status": "pending"}],
            )
            assert result is True
            created_doc = mock_create.call_args[0][0]
            assert created_doc.event_id == "evt-001"
            assert created_doc.tenant_id == "T1"
            assert created_doc.store_code == "S1"
            assert created_doc.terminal_no == 1
            assert created_doc.business_date == "20260101"
            assert created_doc.open_counter == 5
            assert created_doc.status == "published"
            assert len(created_doc.services) == 1
            assert created_doc.services[0].service_name == "report"

    @pytest.mark.asyncio
    async def test_create_status_with_custom_terminal_info(self):
        repo = self._make_repo()
        custom_info = self._make_terminal_info(tenant_id="T2", store_code="S2", terminal_no=3)
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create:
            await repo.create_status_async(
                event_id="evt-002",
                payload={},
                terminal_info=custom_info,
            )
            created_doc = mock_create.call_args[0][0]
            assert created_doc.tenant_id == "T2"
            assert created_doc.store_code == "S2"
            assert created_doc.terminal_no == 3

    @pytest.mark.asyncio
    async def test_create_status_no_services(self):
        repo = self._make_repo()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create:
            await repo.create_status_async(event_id="evt-003", payload={"x": 1})
            created_doc = mock_create.call_args[0][0]
            assert created_doc.services == []

    # -- find_by_event_id -----------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_event_id(self):
        repo = self._make_repo()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=MagicMock()) as mock_get:
            await repo.find_by_event_id("evt-001")
            mock_get.assert_awaited_once_with({"event_id": "evt-001"})

    # -- find_by_terminal_info ------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_terminal_info(self):
        repo = self._make_repo()
        with patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_get:
            await repo.find_by_terminal_info("T1", "S1", 1)
            mock_get.assert_awaited_once_with({"tenant_id": "T1", "store_code": "S1", "terminal_no": 1})

    # -- find_by_business_date ------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_business_date(self):
        repo = self._make_repo()
        with patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_get:
            await repo.find_by_business_date("T1", "S1", "20260101")
            mock_get.assert_awaited_once_with({"tenant_id": "T1", "store_code": "S1", "business_date": "20260101"})

    # -- find_pending_deliveries ----------------------------------------------

    @pytest.mark.asyncio
    async def test_find_pending_deliveries(self):
        repo = self._make_repo()
        with patch.object(repo, "get_list_async", new_callable=AsyncMock, return_value=[]) as mock_get:
            await repo.find_pending_deliveries(hours_ago=12)
            call_filter = mock_get.call_args[0][0]
            assert "$gte" in call_filter["published_at"]
            assert call_filter["status"] == {"$nin": ["delivered"]}

    # -- update_service_status ------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_service_status_success(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        repo.dbcollection = mock_collection

        result = await repo.update_service_status("evt-001", "report", "received", message="ok")
        assert result is True
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"event_id": "evt-001"}
        update_set = call_args[0][1]["$set"]
        assert update_set["services.$[elem].status"] == "received"
        assert update_set["services.$[elem].message"] == "ok"
        assert call_args[1]["array_filters"] == [{"elem.service_name": "report"}]

    @pytest.mark.asyncio
    async def test_update_service_status_not_modified(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        repo.dbcollection = mock_collection

        result = await repo.update_service_status("evt-999", "report", "received")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_service_status_exception_returns_false(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_collection.update_one = AsyncMock(side_effect=Exception("db error"))
        repo.dbcollection = mock_collection

        result = await repo.update_service_status("evt-001", "report", "received")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_service_status_without_message(self):
        repo = self._make_repo()
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        repo.dbcollection = mock_collection

        await repo.update_service_status("evt-001", "report", "received")
        call_args = mock_collection.update_one.call_args
        update_set = call_args[0][1]["$set"]
        assert "services.$[elem].message" not in update_set

    @pytest.mark.asyncio
    async def test_update_service_status_initializes_collection(self):
        repo = self._make_repo()
        repo.dbcollection = None
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        with patch.object(repo, "initialize", new_callable=AsyncMock) as mock_init:
            # After initialize, set the collection
            async def set_collection():
                repo.dbcollection = mock_collection
            mock_init.side_effect = set_collection
            result = await repo.update_service_status("evt-001", "report", "received")
            mock_init.assert_awaited_once()
            assert result is True

    # -- update_delivery_status -----------------------------------------------

    @pytest.mark.asyncio
    async def test_update_delivery_status(self):
        repo = self._make_repo()
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_update:
            result = await repo.update_delivery_status("evt-001", "delivered")
            assert result is True
            call_args = mock_update.call_args
            assert call_args[0][0] == {"event_id": "evt-001"}
            assert call_args[0][1]["status"] == "delivered"
            assert "last_updated_at" in call_args[0][1]
