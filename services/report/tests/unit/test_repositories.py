"""
Unit tests for the report service repository layer.

Covers:
- TranlogRepository
- CashInOutLogRepository
- OpenCloseLogRepository
- DailyInfoDocumentRepository

Tests verify filter dict construction, shard key generation,
duplicate handling, and error mapping without requiring a real database.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kugel_common.exceptions import CannotCreateException, DuplicateKeyException
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.schemas.pagination import PaginatedResult, Metadata

from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.models.documents.daily_info_document import DailyInfoDocument
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db():
    """Create a mock AsyncIOMotorDatabase."""
    return MagicMock()


def _make_tranlog(**overrides) -> BaseTransaction:
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        store_name="Test Store",
        terminal_no=1,
        transaction_no=100,
        transaction_type=1,
        business_date="20250101",
        open_counter=1,
        generate_date_time="2025-01-01T10:00:00Z",
        receipt_no=50,
        sales=BaseTransaction.SalesInfo(is_cancelled=False),
    )
    defaults.update(overrides)
    return BaseTransaction(**defaults)


def _make_cash_in_out_log(**overrides) -> CashInOutLog:
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        business_date="20250101",
        open_counter=1,
        generate_date_time="2025-01-01T10:00:00Z",
        amount=1000.0,
    )
    defaults.update(overrides)
    return CashInOutLog(**defaults)


def _make_open_close_log(**overrides) -> OpenCloseLog:
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        business_date="20250101",
        open_counter=1,
        operation="open",
        generate_date_time="2025-01-01T10:00:00Z",
    )
    defaults.update(overrides)
    return OpenCloseLog(**defaults)


def _make_daily_info(**overrides) -> DailyInfoDocument:
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        business_date="20250101",
        open_counter=1,
        verified=True,
    )
    defaults.update(overrides)
    return DailyInfoDocument(**defaults)


def _empty_paginated_result():
    return PaginatedResult(
        metadata=Metadata(total=0, page=1, limit=100, sort="", filter={}),
        data=[],
    )


# ===========================================================================
# TranlogRepository
# ===========================================================================

class TestTranlogRepository:
    """Tests for TranlogRepository."""

    def test_collection_name(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        assert repo.collection_name == "log_tran"

    def test_tenant_id_stored(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        assert repo.tenant_id == "T001"

    # -- create_tranlog_async --

    @pytest.mark.asyncio
    async def test_create_tranlog_sets_shard_key(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        doc = _make_tranlog()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.create_tranlog_async(doc)
            # shard_key = tenant_id_store_code_terminal_no_date
            assert result.shard_key == "T001_S001_1_2025-01-01"

    @pytest.mark.asyncio
    async def test_create_tranlog_calls_create_async(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        doc = _make_tranlog()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create,
        ):
            await repo.create_tranlog_async(doc)
            mock_create.assert_awaited_once_with(doc)

    @pytest.mark.asyncio
    async def test_create_tranlog_skips_if_already_exists(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        doc = _make_tranlog()
        existing = _make_tranlog()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=existing),
            patch.object(repo, "create_async", new_callable=AsyncMock) as mock_create,
        ):
            result = await repo.create_tranlog_async(doc)
            mock_create.assert_not_awaited()
            assert result is doc

    @pytest.mark.asyncio
    async def test_create_tranlog_duplicate_check_filter(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        doc = _make_tranlog(
            tenant_id="T002",
            store_code="S005",
            terminal_no=3,
            transaction_no=999,
        )
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc) as mock_get,
            patch.object(repo, "create_async", new_callable=AsyncMock),
        ):
            await repo.create_tranlog_async(doc)
            expected_filter = {
                "tenant_id": "T002",
                "store_code": "S005",
                "terminal_no": 3,
                "transaction_no": 999,
            }
            mock_get.assert_awaited_once_with(expected_filter)

    @pytest.mark.asyncio
    async def test_create_tranlog_raises_cannot_create_on_failure(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        doc = _make_tranlog()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(CannotCreateException):
                await repo.create_tranlog_async(doc)

    # -- get_tranlog_list_by_query_async --

    @pytest.mark.asyncio
    async def test_query_filter_minimal(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_tranlog_list_by_query_async(store_code="S001", terminal_no=1)
            called_filter = mock_pag.call_args[1]["filter"]
            assert called_filter == {
                "tenant_id": "T001",
                "store_code": "S001",
                "terminal_no": 1,
                "sales.is_cancelled": False,
            }

    @pytest.mark.asyncio
    async def test_query_filter_with_business_date(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_tranlog_list_by_query_async(
                store_code="S001", terminal_no=1, business_date="20250101"
            )
            called_filter = mock_pag.call_args[1]["filter"]
            assert called_filter["business_date"] == "20250101"

    @pytest.mark.asyncio
    async def test_query_filter_with_open_counter(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_tranlog_list_by_query_async(
                store_code="S001", terminal_no=1, open_counter=3
            )
            called_filter = mock_pag.call_args[1]["filter"]
            assert called_filter["open_counter"] == 3

    @pytest.mark.asyncio
    async def test_query_filter_with_transaction_type(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_tranlog_list_by_query_async(
                store_code="S001", terminal_no=1, transaction_type=[1, 2]
            )
            called_filter = mock_pag.call_args[1]["filter"]
            assert called_filter["transaction_type"] == {"$in": [1, 2]}

    @pytest.mark.asyncio
    async def test_query_filter_with_receipt_no(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_tranlog_list_by_query_async(
                store_code="S001", terminal_no=1, receipt_no=42
            )
            called_filter = mock_pag.call_args[1]["filter"]
            assert called_filter["receipt_no"] == 42

    @pytest.mark.asyncio
    async def test_query_filter_include_cancelled(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_tranlog_list_by_query_async(
                store_code="S001", terminal_no=1, include_cancelled=True
            )
            called_filter = mock_pag.call_args[1]["filter"]
            assert "sales.is_cancelled" not in called_filter

    @pytest.mark.asyncio
    async def test_query_passes_pagination_params(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            sort_param = [("business_date", -1)]
            await repo.get_tranlog_list_by_query_async(
                store_code="S001", terminal_no=1, limit=50, page=2, sort=sort_param
            )
            mock_pag.assert_awaited_once()
            kwargs = mock_pag.call_args[1]
            assert kwargs["limit"] == 50
            assert kwargs["page"] == 2
            assert kwargs["sort"] == sort_param

    @pytest.mark.asyncio
    async def test_query_filter_all_params(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_tranlog_list_by_query_async(
                store_code="S001",
                terminal_no=1,
                business_date="20250101",
                open_counter=2,
                transaction_type=[1],
                receipt_no=10,
                include_cancelled=False,
            )
            called_filter = mock_pag.call_args[1]["filter"]
            assert called_filter == {
                "tenant_id": "T001",
                "store_code": "S001",
                "terminal_no": 1,
                "business_date": "20250101",
                "open_counter": 2,
                "transaction_type": {"$in": [1]},
                "receipt_no": 10,
                "sales.is_cancelled": False,
            }

    # -- shard key --

    def test_shard_key_format(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        doc = _make_tranlog(
            tenant_id="TX",
            store_code="SX",
            terminal_no=9,
            generate_date_time="2025-06-15T23:59:59Z",
        )
        # Access private method via name mangling
        key = repo._TranlogRepository__get_shard_key(doc)
        assert key == "TX_SX_9_2025-06-15"


# ===========================================================================
# CashInOutLogRepository
# ===========================================================================

class TestCashInOutLogRepository:
    """Tests for CashInOutLogRepository."""

    def test_collection_name(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        assert repo.collection_name == "log_cash_in_out"

    def test_tenant_id_stored(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        assert repo.tenant_id == "T001"

    # -- create_cash_in_out_log --

    @pytest.mark.asyncio
    async def test_create_sets_shard_key(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        doc = _make_cash_in_out_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.create_cash_in_out_log(doc)
            assert result.shard_key == "T001_S001_1_20250101"

    @pytest.mark.asyncio
    async def test_create_calls_create_async(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        doc = _make_cash_in_out_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create,
        ):
            await repo.create_cash_in_out_log(doc)
            mock_create.assert_awaited_once_with(doc)

    @pytest.mark.asyncio
    async def test_create_skips_if_already_exists(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        doc = _make_cash_in_out_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "create_async", new_callable=AsyncMock) as mock_create,
        ):
            result = await repo.create_cash_in_out_log(doc)
            mock_create.assert_not_awaited()
            assert result is doc

    @pytest.mark.asyncio
    async def test_create_duplicate_check_filter(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        doc = _make_cash_in_out_log(
            tenant_id="T002",
            store_code="S005",
            terminal_no=3,
            business_date="20250202",
            open_counter=2,
            generate_date_time="2025-02-02T12:00:00Z",
        )
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc) as mock_get,
            patch.object(repo, "create_async", new_callable=AsyncMock),
        ):
            await repo.create_cash_in_out_log(doc)
            expected_filter = {
                "tenant_id": "T002",
                "store_code": "S005",
                "terminal_no": 3,
                "business_date": "20250202",
                "open_counter": 2,
                "generate_date_time": "2025-02-02T12:00:00Z",
            }
            mock_get.assert_awaited_once_with(expected_filter)

    @pytest.mark.asyncio
    async def test_create_raises_cannot_create_on_failure(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        doc = _make_cash_in_out_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(CannotCreateException):
                await repo.create_cash_in_out_log(doc)

    # -- get_cash_in_out_logs --

    @pytest.mark.asyncio
    async def test_get_logs_delegates_to_paginated(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        expected = _empty_paginated_result()
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=expected
        ) as mock_pag:
            query_filter = {"tenant_id": "T001", "store_code": "S001"}
            result = await repo.get_cash_in_out_logs(query_filter, limit=50, page=2)
            mock_pag.assert_awaited_once_with(query_filter, 50, 2, None)
            assert result is expected

    # -- shard key --

    def test_shard_key_format(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        doc = _make_cash_in_out_log(
            tenant_id="TX", store_code="SX", terminal_no=7, business_date="20250615"
        )
        key = repo._CashInOutLogRepository__get_shard_key(doc)
        assert key == "TX_SX_7_20250615"


# ===========================================================================
# OpenCloseLogRepository
# ===========================================================================

class TestOpenCloseLogRepository:
    """Tests for OpenCloseLogRepository."""

    def test_collection_name(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        assert repo.collection_name == "log_open_close"

    def test_tenant_id_stored(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        assert repo.tenant_id == "T001"

    # -- create_open_close_log --

    @pytest.mark.asyncio
    async def test_create_sets_shard_key(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        doc = _make_open_close_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.create_open_close_log(doc)
            assert result.shard_key == "T001_S001_1_20250101"

    @pytest.mark.asyncio
    async def test_create_calls_create_async(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        doc = _make_open_close_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create,
        ):
            await repo.create_open_close_log(doc)
            mock_create.assert_awaited_once_with(doc)

    @pytest.mark.asyncio
    async def test_create_skips_if_already_exists(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        doc = _make_open_close_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc),
            patch.object(repo, "create_async", new_callable=AsyncMock) as mock_create,
        ):
            result = await repo.create_open_close_log(doc)
            mock_create.assert_not_awaited()
            assert result is doc

    @pytest.mark.asyncio
    async def test_create_duplicate_check_filter(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        doc = _make_open_close_log(
            tenant_id="T002",
            store_code="S005",
            terminal_no=3,
            business_date="20250202",
            open_counter=2,
            operation="close",
        )
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=doc) as mock_get,
            patch.object(repo, "create_async", new_callable=AsyncMock),
        ):
            await repo.create_open_close_log(doc)
            expected_filter = {
                "tenant_id": "T002",
                "store_code": "S005",
                "terminal_no": 3,
                "business_date": "20250202",
                "open_counter": 2,
                "operation": "close",
            }
            mock_get.assert_awaited_once_with(expected_filter)

    @pytest.mark.asyncio
    async def test_create_raises_cannot_create_on_failure(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        doc = _make_open_close_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(CannotCreateException):
                await repo.create_open_close_log(doc)

    # -- get_open_close_logs --

    @pytest.mark.asyncio
    async def test_get_logs_minimal_filter(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_open_close_logs(store_code="S001", business_date="20250101")
            called_filter = mock_pag.call_args[0][0]
            assert called_filter == {
                "tenant_id": "T001",
                "store_code": "S001",
                "business_date": "20250101",
            }

    @pytest.mark.asyncio
    async def test_get_logs_with_terminal_no(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_open_close_logs(
                store_code="S001", business_date="20250101", terminal_no=2
            )
            called_filter = mock_pag.call_args[0][0]
            assert called_filter["terminal_no"] == 2

    @pytest.mark.asyncio
    async def test_get_logs_with_open_counter(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_open_close_logs(
                store_code="S001", business_date="20250101", open_counter=5
            )
            called_filter = mock_pag.call_args[0][0]
            assert called_filter["open_counter"] == 5

    @pytest.mark.asyncio
    async def test_get_logs_with_operation(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_open_close_logs(
                store_code="S001", business_date="20250101", operation="close"
            )
            called_filter = mock_pag.call_args[0][0]
            assert called_filter["operation"] == "close"

    @pytest.mark.asyncio
    async def test_get_logs_all_params(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_open_close_logs(
                store_code="S001",
                business_date="20250101",
                terminal_no=3,
                open_counter=2,
                operation="open",
                limit=25,
                page=3,
            )
            called_filter = mock_pag.call_args[0][0]
            assert called_filter == {
                "tenant_id": "T001",
                "store_code": "S001",
                "business_date": "20250101",
                "terminal_no": 3,
                "open_counter": 2,
                "operation": "open",
            }
            assert mock_pag.call_args[0][1] == 25  # limit
            assert mock_pag.call_args[0][2] == 3   # page

    # -- shard key --

    def test_shard_key_format(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        doc = _make_open_close_log(
            tenant_id="TX", store_code="SX", terminal_no=4, business_date="20250615"
        )
        key = repo._OpenCloseLogRepository__get_shard_key(doc)
        assert key == "TX_SX_4_20250615"


# ===========================================================================
# DailyInfoDocumentRepository
# ===========================================================================

class TestDailyInfoDocumentRepository:
    """Tests for DailyInfoDocumentRepository."""

    def test_collection_name(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        assert repo.collection_name == "info_daily"

    def test_tenant_id_stored(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        assert repo.tenant_id == "T001"

    # -- create_daily_info_document --

    @pytest.mark.asyncio
    async def test_create_sets_shard_key(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        doc = _make_daily_info()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True):
            result = await repo.create_daily_info_document(doc)
            assert result.shard_key == "T001_S001_1_20250101"

    @pytest.mark.asyncio
    async def test_create_calls_create_async(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        doc = _make_daily_info()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True) as mock_create:
            await repo.create_daily_info_document(doc)
            mock_create.assert_awaited_once_with(doc)

    @pytest.mark.asyncio
    async def test_create_handles_duplicate_key_with_replace(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        doc = _make_daily_info()
        dup_exc = DuplicateKeyException("dup", "info_daily", {"key": 1})
        with (
            patch.object(repo, "create_async", new_callable=AsyncMock, side_effect=dup_exc),
            patch.object(repo, "replace_one_async", new_callable=AsyncMock, return_value=True) as mock_replace,
        ):
            result = await repo.create_daily_info_document(doc)
            expected_filter = {
                "tenant_id": "T001",
                "store_code": "S001",
                "terminal_no": 1,
                "business_date": "20250101",
                "open_counter": 1,
            }
            mock_replace.assert_awaited_once_with(expected_filter, doc)
            assert result is doc

    @pytest.mark.asyncio
    async def test_create_raises_cannot_create_on_failure(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        doc = _make_daily_info()
        with patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False):
            with pytest.raises(CannotCreateException):
                await repo.create_daily_info_document(doc)

    # -- get_daily_info_documents --

    @pytest.mark.asyncio
    async def test_get_documents_minimal_filter(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_daily_info_documents(store_code="S001", business_date="20250101")
            called_filter = mock_pag.call_args[0][0]
            assert called_filter == {
                "tenant_id": "T001",
                "store_code": "S001",
                "business_date": "20250101",
            }

    @pytest.mark.asyncio
    async def test_get_documents_with_open_counter(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_daily_info_documents(
                store_code="S001", business_date="20250101", open_counter=3
            )
            called_filter = mock_pag.call_args[0][0]
            assert called_filter["open_counter"] == 3

    @pytest.mark.asyncio
    async def test_get_documents_with_terminal_no(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_daily_info_documents(
                store_code="S001", business_date="20250101", terminal_no=5
            )
            called_filter = mock_pag.call_args[0][0]
            assert called_filter["terminal_no"] == 5

    @pytest.mark.asyncio
    async def test_get_documents_all_params(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        with patch.object(
            repo, "get_paginated_list_async", new_callable=AsyncMock, return_value=_empty_paginated_result()
        ) as mock_pag:
            await repo.get_daily_info_documents(
                store_code="S001",
                business_date="20250101",
                open_counter=2,
                terminal_no=4,
                limit=25,
                page=3,
            )
            called_filter = mock_pag.call_args[0][0]
            assert called_filter == {
                "tenant_id": "T001",
                "store_code": "S001",
                "business_date": "20250101",
                "open_counter": 2,
                "terminal_no": 4,
            }
            assert mock_pag.call_args[0][1] == 25  # limit
            assert mock_pag.call_args[0][2] == 3   # page

    # -- update_daily_info_document --

    @pytest.mark.asyncio
    async def test_update_delegates_to_update_one_async(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=True) as mock_update:
            filter_dict = {"tenant_id": "T001", "store_code": "S001"}
            update_data = {"verified": True}
            result = await repo.update_daily_info_document(filter_dict, update_data)
            mock_update.assert_awaited_once_with(filter_dict, update_data)
            assert result is True

    @pytest.mark.asyncio
    async def test_update_returns_false_when_not_found(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        with patch.object(repo, "update_one_async", new_callable=AsyncMock, return_value=False):
            result = await repo.update_daily_info_document(
                {"tenant_id": "T001"}, {"verified": False}
            )
            assert result is False

    # -- shard key --

    def test_shard_key_format(self):
        repo = DailyInfoDocumentRepository(_make_mock_db(), "T001")
        doc = _make_daily_info(
            tenant_id="TX", store_code="SX", terminal_no=6, business_date="20250615"
        )
        key = repo._DailyInfoDocumentRepository__get_shard_key(doc)
        assert key == "TX_SX_6_20250615"
