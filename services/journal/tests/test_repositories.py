# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Unit tests for the journal service repository layer.

Tests cover query filter construction, shard key generation,
duplicate handling, and paginated result construction for all
four repositories: JournalRepository, TranlogRepository,
CashInOutLogRepository, and OpenCloseLogRepository.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from kugel_common.schemas.pagination import PaginatedResult, Metadata

from app.models.documents.jornal_document import JournalDocument
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from kugel_common.models.documents.base_tranlog import BaseTransaction

from app.models.repositories.journal_repository import JournalRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db():
    """Create a MagicMock that looks like AsyncIOMotorDatabase."""
    return MagicMock()


def _make_journal_doc(**overrides) -> JournalDocument:
    """Create a minimal JournalDocument with sensible defaults."""
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        transaction_no=100,
        transaction_type=1,
        business_date="20240115",
        open_counter=1,
        business_counter=1,
        receipt_no=50,
        amount=1000.0,
        quantity=3,
        generate_date_time="2024-01-15T10:30:00Z",
        journal_text="sample journal text",
        receipt_text="sample receipt text",
    )
    defaults.update(overrides)
    return JournalDocument(**defaults)


def _make_tranlog(**overrides) -> BaseTransaction:
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        transaction_no=100,
        transaction_type=1,
        business_date="20240115",
        open_counter=1,
        business_counter=1,
        generate_date_time="2024-01-15T10:30:00Z",
        receipt_no=50,
    )
    defaults.update(overrides)
    return BaseTransaction(**defaults)


def _make_cash_log(**overrides) -> CashInOutLog:
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        business_date="20240115",
        open_counter=1,
        business_counter=1,
        generate_date_time="2024-01-15T10:30:00Z",
        amount=5000.0,
        description="float",
    )
    defaults.update(overrides)
    return CashInOutLog(**defaults)


def _make_open_close_log(**overrides) -> OpenCloseLog:
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        business_date="20240115",
        open_counter=1,
        business_counter=1,
        operation="open",
        generate_date_time="2024-01-15T08:00:00Z",
    )
    defaults.update(overrides)
    return OpenCloseLog(**defaults)


# ===========================================================================
# JournalRepository tests
# ===========================================================================

class TestJournalRepositoryGetJournals:
    """Tests for JournalRepository.get_journals_async query filter building."""

    @pytest.fixture
    def repo(self):
        return JournalRepository(_make_mock_db(), "T001")

    # --- minimal query (store_code only) ---
    @pytest.mark.asyncio
    async def test_minimal_query(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(store_code="S001", limit=10, page=1, sort=[])
            query = mock.call_args[1]["filter"]
            assert query == {"tenant_id": "T001", "store_code": "S001"}

    # --- terminals filter ($in) ---
    @pytest.mark.asyncio
    async def test_terminals_filter(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(store_code="S001", terminals=[1, 2, 3], limit=10, page=1, sort=[])
            query = mock.call_args[1]["filter"]
            assert query["terminal_no"] == {"$in": [1, 2, 3]}

    # --- transaction_types filter ($in) ---
    @pytest.mark.asyncio
    async def test_transaction_types_filter(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(store_code="S001", transaction_types=[1, 2], limit=10, page=1, sort=[])
            query = mock.call_args[1]["filter"]
            assert query["transaction_type"] == {"$in": [1, 2]}

    # --- business_date range ---
    @pytest.mark.asyncio
    async def test_business_date_range(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                business_date_from="20240101",
                business_date_to="20240131",
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert query["business_date"] == {"$gte": "20240101", "$lte": "20240131"}

    # --- business_date_from only (no to) should NOT add filter ---
    @pytest.mark.asyncio
    async def test_business_date_from_only(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                business_date_from="20240101",
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert "business_date" not in query

    # --- generate_date_time range ---
    @pytest.mark.asyncio
    async def test_generate_date_time_range(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                generate_date_time_from="2024-01-01T00:00:00Z",
                generate_date_time_to="2024-01-31T23:59:59Z",
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert query["generate_date_time"] == {
                "$gte": "2024-01-01T00:00:00Z",
                "$lte": "2024-01-31T23:59:59Z",
            }

    # --- generate_date_time_from only (no to) should NOT add filter ---
    @pytest.mark.asyncio
    async def test_generate_date_time_from_only(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                generate_date_time_from="2024-01-01T00:00:00Z",
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert "generate_date_time" not in query

    # --- receipt_no range ---
    @pytest.mark.asyncio
    async def test_receipt_no_range(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                receipt_no_from=1,
                receipt_no_to=100,
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert query["receipt_no"] == {"$gte": 1, "$lte": 100}

    # --- receipt_no_from only (no to) should NOT add filter ---
    @pytest.mark.asyncio
    async def test_receipt_no_from_only(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                receipt_no_from=1,
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert "receipt_no" not in query

    # --- keyword search (single keyword) ---
    @pytest.mark.asyncio
    async def test_keyword_search_single(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                keywords=["milk"],
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert query["journal_text"] == {"$regex": "milk"}

    # --- keyword search (multiple keywords joined with |) ---
    @pytest.mark.asyncio
    async def test_keyword_search_multiple(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                keywords=["milk", "bread", "eggs"],
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert query["journal_text"] == {"$regex": "milk|bread|eggs"}

    # --- empty keywords list should NOT add filter ---
    @pytest.mark.asyncio
    async def test_empty_keywords(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                keywords=[],
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert "journal_text" not in query

    # --- combined filters ---
    @pytest.mark.asyncio
    async def test_combined_filters(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001",
                terminals=[1, 2],
                transaction_types=[1],
                business_date_from="20240101",
                business_date_to="20240131",
                generate_date_time_from="2024-01-01T00:00:00Z",
                generate_date_time_to="2024-01-31T23:59:59Z",
                receipt_no_from=10,
                receipt_no_to=50,
                keywords=["apple"],
                limit=20, page=2, sort=[("business_date", -1)],
            )
            query = mock.call_args[1]["filter"]
            assert query["tenant_id"] == "T001"
            assert query["store_code"] == "S001"
            assert query["terminal_no"] == {"$in": [1, 2]}
            assert query["transaction_type"] == {"$in": [1]}
            assert query["business_date"] == {"$gte": "20240101", "$lte": "20240131"}
            assert query["generate_date_time"] == {
                "$gte": "2024-01-01T00:00:00Z",
                "$lte": "2024-01-31T23:59:59Z",
            }
            assert query["receipt_no"] == {"$gte": 10, "$lte": 50}
            assert query["journal_text"] == {"$regex": "apple"}
            # verify paging/sorting forwarded
            assert mock.call_args[1]["limit"] == 20
            assert mock.call_args[1]["page"] == 2
            assert mock.call_args[1]["sort"] == [("business_date", -1)]

    # --- propagation of limit, page, sort ---
    @pytest.mark.asyncio
    async def test_pagination_params_forwarded(self, repo):
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await repo.get_journals_async(
                store_code="S001", limit=50, page=3, sort=[("receipt_no", 1)],
            )
            assert mock.call_args[1]["limit"] == 50
            assert mock.call_args[1]["page"] == 3
            assert mock.call_args[1]["sort"] == [("receipt_no", 1)]


class TestJournalRepositoryGetJournalsPaginated:
    """Tests for JournalRepository.get_journals_paginated_async."""

    @pytest.fixture
    def repo(self):
        return JournalRepository(_make_mock_db(), "T001")

    @pytest.mark.asyncio
    async def test_paginated_delegates_to_get_paginated_list(self, repo):
        paginated = PaginatedResult(
            metadata=Metadata(total=1, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.return_value = paginated
            result = await repo.get_journals_paginated_async(store_code="S001", limit=10, page=1, sort=[])
            assert result is paginated
            query = mock.call_args[1]["filter"]
            assert query["tenant_id"] == "T001"
            assert query["store_code"] == "S001"

    @pytest.mark.asyncio
    async def test_paginated_filter_with_terminals_and_keywords(self, repo):
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.return_value = paginated
            await repo.get_journals_paginated_async(
                store_code="S001",
                terminals=[5],
                keywords=["hello", "world"],
                limit=10, page=1, sort=[],
            )
            query = mock.call_args[1]["filter"]
            assert query["terminal_no"] == {"$in": [5]}
            assert query["journal_text"] == {"$regex": "hello|world"}

    @pytest.mark.asyncio
    async def test_paginated_raises_on_error(self, repo):
        from kugel_common.exceptions import DocumentNotFoundException
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("db error")
            with pytest.raises(DocumentNotFoundException):
                await repo.get_journals_paginated_async(store_code="S001", limit=10, page=1, sort=[])


class TestJournalRepositoryCreate:
    """Tests for JournalRepository.create_journal_async."""

    @pytest.fixture
    def repo(self):
        return JournalRepository(_make_mock_db(), "T001")

    @pytest.mark.asyncio
    async def test_create_sets_shard_key(self, repo):
        doc = _make_journal_doc()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.create_journal_async(doc)
            assert result.shard_key == "T001_S001_1_20240115"

    @pytest.mark.asyncio
    async def test_create_returns_existing_on_duplicate(self, repo):
        existing = _make_journal_doc()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=existing):
            result = await repo.create_journal_async(_make_journal_doc())
            assert result is existing

    @pytest.mark.asyncio
    async def test_create_raises_cannot_create_on_failure(self, repo):
        from kugel_common.exceptions import CannotCreateException
        doc = _make_journal_doc()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(CannotCreateException):
                await repo.create_journal_async(doc)


class TestJournalRepositoryShardKey:
    """Tests for shard key generation in JournalRepository."""

    def test_shard_key_format(self):
        repo = JournalRepository(_make_mock_db(), "T001")
        doc = _make_journal_doc(
            tenant_id="TENANT_A", store_code="STORE_B", terminal_no=5, business_date="20240301"
        )
        # Access the name-mangled private method
        key = repo._JournalRepository__get_shard_key(doc)
        assert key == "TENANT_A_STORE_B_5_20240301"


class TestJournalRepositoryGetJournalsError:
    """Tests for error handling in get_journals_async."""

    @pytest.fixture
    def repo(self):
        return JournalRepository(_make_mock_db(), "T001")

    @pytest.mark.asyncio
    async def test_raises_document_not_found_on_error(self, repo):
        from kugel_common.exceptions import DocumentNotFoundException
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("db error")
            with pytest.raises(DocumentNotFoundException):
                await repo.get_journals_async(store_code="S001", limit=10, page=1, sort=[])


# ===========================================================================
# TranlogRepository tests
# ===========================================================================

class TestTranlogRepositoryCreate:
    """Tests for TranlogRepository.create_tranlog_async."""

    @pytest.fixture
    def repo(self):
        return TranlogRepository(_make_mock_db(), "T001")

    @pytest.mark.asyncio
    async def test_create_sets_shard_key(self, repo):
        doc = _make_tranlog()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.create_tranlog_async(doc)
            # shard_key = tenant_id + store_code + terminal_no + date part of generate_date_time
            assert result.shard_key == "T001_S001_1_2024-01-15"

    @pytest.mark.asyncio
    async def test_create_returns_existing_on_duplicate(self, repo):
        existing = _make_tranlog()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=existing):
            result = await repo.create_tranlog_async(_make_tranlog())
            assert result is not None

    @pytest.mark.asyncio
    async def test_create_raises_cannot_create_on_failure(self, repo):
        from kugel_common.exceptions import CannotCreateException
        doc = _make_tranlog()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(CannotCreateException):
                await repo.create_tranlog_async(doc)

    @pytest.mark.asyncio
    async def test_duplicate_check_filter(self, repo):
        """Verify the duplicate check uses the correct filter keys."""
        doc = _make_tranlog(tenant_id="TX", store_code="SX", terminal_no=7, transaction_no=42)
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get,
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            await repo.create_tranlog_async(doc)
            expected_filter = {
                "tenant_id": "TX",
                "store_code": "SX",
                "terminal_no": 7,
                "transaction_no": 42,
            }
            mock_get.assert_called_once_with(expected_filter)


class TestTranlogRepositoryShardKey:
    """Tests for shard key generation in TranlogRepository."""

    def test_shard_key_splits_datetime(self):
        repo = TranlogRepository(_make_mock_db(), "T001")
        doc = _make_tranlog(
            tenant_id="T1", store_code="S1", terminal_no=3,
            generate_date_time="2024-06-15T14:30:00Z",
        )
        key = repo._TranlogRepository__get_shard_key(doc)
        assert key == "T1_S1_3_2024-06-15"


class TestTranlogRepositoryQuery:
    """Tests for TranlogRepository.get_tranlog_list_by_query_async filter building."""

    @pytest.fixture
    def repo(self):
        return TranlogRepository(_make_mock_db(), "T001")

    @pytest.mark.asyncio
    async def test_minimal_query(self, repo):
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.return_value = paginated
            await repo.get_tranlog_list_by_query_async(store_code="S001", terminal_no=1)
            query = mock.call_args[1]["filter"]
            assert query["tenant_id"] == "T001"
            assert query["store_code"] == "S001"
            assert query["terminal_no"] == 1
            # default: exclude cancelled
            assert query["sales.is_cancelled"] is False

    @pytest.mark.asyncio
    async def test_include_cancelled(self, repo):
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.return_value = paginated
            await repo.get_tranlog_list_by_query_async(
                store_code="S001", terminal_no=1, include_cancelled=True
            )
            query = mock.call_args[1]["filter"]
            assert "sales.is_cancelled" not in query

    @pytest.mark.asyncio
    async def test_all_optional_filters(self, repo):
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.return_value = paginated
            await repo.get_tranlog_list_by_query_async(
                store_code="S001",
                terminal_no=2,
                business_date="20240115",
                open_counter=3,
                transaction_type=[1, 2],
                receipt_no=99,
                limit=25,
                page=2,
                sort=[("generate_date_time", -1)],
            )
            query = mock.call_args[1]["filter"]
            assert query["business_date"] == "20240115"
            assert query["open_counter"] == 3
            assert query["transaction_type"] == {"$in": [1, 2]}
            assert query["receipt_no"] == 99
            assert mock.call_args[1]["limit"] == 25
            assert mock.call_args[1]["page"] == 2
            assert mock.call_args[1]["sort"] == [("generate_date_time", -1)]


# ===========================================================================
# CashInOutLogRepository tests
# ===========================================================================

class TestCashInOutLogRepositoryCreate:
    """Tests for CashInOutLogRepository.create_cash_in_out_log."""

    @pytest.fixture
    def repo(self):
        return CashInOutLogRepository(_make_mock_db(), "T001")

    @pytest.mark.asyncio
    async def test_create_sets_shard_key(self, repo):
        doc = _make_cash_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.create_cash_in_out_log(doc)
            assert result.shard_key == "T001_S001_1_20240115"

    @pytest.mark.asyncio
    async def test_create_returns_existing_on_duplicate(self, repo):
        existing = _make_cash_log()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=existing):
            result = await repo.create_cash_in_out_log(_make_cash_log())
            assert result is not None

    @pytest.mark.asyncio
    async def test_create_raises_on_failure(self, repo):
        from kugel_common.exceptions import CannotCreateException
        doc = _make_cash_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(CannotCreateException):
                await repo.create_cash_in_out_log(doc)

    @pytest.mark.asyncio
    async def test_duplicate_check_filter(self, repo):
        doc = _make_cash_log(
            tenant_id="TX", store_code="SX", terminal_no=3,
            business_date="20240201", open_counter=2,
            generate_date_time="2024-02-01T09:00:00Z",
        )
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get,
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            await repo.create_cash_in_out_log(doc)
            expected_filter = {
                "tenant_id": "TX",
                "store_code": "SX",
                "terminal_no": 3,
                "business_date": "20240201",
                "open_counter": 2,
                "generate_date_time": "2024-02-01T09:00:00Z",
            }
            mock_get.assert_called_once_with(expected_filter)


class TestCashInOutLogRepositoryShardKey:

    def test_shard_key_format(self):
        repo = CashInOutLogRepository(_make_mock_db(), "T001")
        doc = _make_cash_log(tenant_id="A", store_code="B", terminal_no=9, business_date="20240601")
        key = repo._CashInOutLogRepository__get_shard_key(doc)
        assert key == "A_B_9_20240601"


class TestCashInOutLogRepositoryQuery:

    @pytest.fixture
    def repo(self):
        return CashInOutLogRepository(_make_mock_db(), "T001")

    @pytest.mark.asyncio
    async def test_get_cash_in_out_logs_delegates(self, repo):
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        test_filter = {"tenant_id": "T001", "store_code": "S001"}
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.return_value = paginated
            result = await repo.get_cash_in_out_logs(
                filter=test_filter, limit=20, page=2, sort=[("amount", 1)]
            )
            assert result is paginated
            mock.assert_called_once_with(test_filter, 20, 2, [("amount", 1)])


# ===========================================================================
# OpenCloseLogRepository tests
# ===========================================================================

class TestOpenCloseLogRepositoryCreate:
    """Tests for OpenCloseLogRepository.create_open_close_log."""

    @pytest.fixture
    def repo(self):
        return OpenCloseLogRepository(_make_mock_db(), "T001")

    @pytest.mark.asyncio
    async def test_create_sets_shard_key(self, repo):
        doc = _make_open_close_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            result = await repo.create_open_close_log(doc)
            assert result.shard_key == "T001_S001_1_20240115"

    @pytest.mark.asyncio
    async def test_create_returns_existing_on_duplicate(self, repo):
        existing = _make_open_close_log()
        with patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=existing):
            result = await repo.create_open_close_log(_make_open_close_log())
            assert result is not None

    @pytest.mark.asyncio
    async def test_create_raises_on_failure(self, repo):
        from kugel_common.exceptions import CannotCreateException
        doc = _make_open_close_log()
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None),
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=False),
        ):
            with pytest.raises(CannotCreateException):
                await repo.create_open_close_log(doc)

    @pytest.mark.asyncio
    async def test_duplicate_check_filter(self, repo):
        doc = _make_open_close_log(
            tenant_id="TX", store_code="SX", terminal_no=4,
            business_date="20240301", open_counter=2, operation="close",
        )
        with (
            patch.object(repo, "get_one_async", new_callable=AsyncMock, return_value=None) as mock_get,
            patch.object(repo, "create_async", new_callable=AsyncMock, return_value=True),
        ):
            await repo.create_open_close_log(doc)
            expected_filter = {
                "tenant_id": "TX",
                "store_code": "SX",
                "terminal_no": 4,
                "business_date": "20240301",
                "open_counter": 2,
                "operation": "close",
            }
            mock_get.assert_called_once_with(filter=expected_filter)


class TestOpenCloseLogRepositoryShardKey:

    def test_shard_key_format(self):
        repo = OpenCloseLogRepository(_make_mock_db(), "T001")
        doc = _make_open_close_log(
            tenant_id="X", store_code="Y", terminal_no=7, business_date="20241225"
        )
        key = repo._OpenCloseLogRepository__get_shard_key(doc)
        assert key == "X_Y_7_20241225"


class TestOpenCloseLogRepositoryQuery:

    @pytest.fixture
    def repo(self):
        return OpenCloseLogRepository(_make_mock_db(), "T001")

    @pytest.mark.asyncio
    async def test_minimal_query(self, repo):
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.return_value = paginated
            await repo.get_open_close_logs(store_code="S001", business_date="20240115")
            query = mock.call_args[0][0]
            assert query == {
                "tenant_id": "T001",
                "store_code": "S001",
                "business_date": "20240115",
            }

    @pytest.mark.asyncio
    async def test_all_optional_filters(self, repo):
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.return_value = paginated
            await repo.get_open_close_logs(
                store_code="S001",
                business_date="20240115",
                terminal_no=2,
                open_counter=3,
                operation="close",
                limit=50,
                page=2,
                sort=[("generate_date_time", -1)],
            )
            query = mock.call_args[0][0]
            assert query["terminal_no"] == 2
            assert query["open_counter"] == 3
            assert query["operation"] == "close"

    @pytest.mark.asyncio
    async def test_optional_filters_excluded_when_none(self, repo):
        paginated = PaginatedResult(
            metadata=Metadata(total=0, page=1, limit=10, sort="", filter={}),
            data=[],
        )
        with patch.object(repo, "get_paginated_list_async", new_callable=AsyncMock) as mock:
            mock.return_value = paginated
            await repo.get_open_close_logs(store_code="S001", business_date="20240115")
            query = mock.call_args[0][0]
            assert "terminal_no" not in query
            assert "open_counter" not in query
            assert "operation" not in query
