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
Unit tests for the repository layer of the stock service.

Tests verify query construction, filter logic, pagination, atomic updates,
and date-based operations using mocked MongoDB collections.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timedelta, timezone

from app.models.repositories.stock_repository import StockRepository
from app.models.repositories.stock_snapshot_repository import StockSnapshotRepository
from app.models.repositories.stock_update_repository import StockUpdateRepository
from app.models.documents.stock_document import StockDocument
from app.models.documents.stock_snapshot_document import StockSnapshotDocument, StockSnapshotItem
from app.models.documents.stock_update_document import StockUpdateDocument
from app.enums.update_type import UpdateType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT = "T001"
STORE = "S001"
ITEM = "ITEM001"


def _make_mock_cursor(return_docs=None):
    """Create a mock cursor that supports chaining (sort/skip/limit/to_list)."""
    if return_docs is None:
        return_docs = []
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=return_docs)
    return cursor


def _make_mock_collection():
    """Create a mock MongoDB collection with common async methods."""
    coll = MagicMock()
    coll.find = MagicMock(return_value=_make_mock_cursor())
    coll.find_one = AsyncMock(return_value=None)
    coll.find_one_and_update = AsyncMock(return_value=None)
    coll.insert_one = AsyncMock()
    coll.update_one = AsyncMock()
    coll.count_documents = AsyncMock(return_value=0)
    coll.delete_many = AsyncMock()
    return coll


def _stock_doc_dict(**overrides):
    """Return a minimal dict that can construct a StockDocument."""
    base = {
        "tenant_id": TENANT,
        "store_code": STORE,
        "item_code": ITEM,
        "current_quantity": 50.0,
        "minimum_quantity": 10.0,
        "reorder_point": 20.0,
        "reorder_quantity": 100.0,
        "last_transaction_id": None,
    }
    base.update(overrides)
    return base


def _snapshot_doc_dict(**overrides):
    """Return a minimal dict that can construct a StockSnapshotDocument."""
    base = {
        "tenant_id": TENANT,
        "store_code": STORE,
        "total_items": 5,
        "total_quantity": 100.0,
        "stocks": [],
        "created_by": "system",
        "generate_date_time": "2025-01-01T00:00:00",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


def _update_doc_dict(**overrides):
    """Return a minimal dict that can construct a StockUpdateDocument."""
    base = {
        "tenant_id": TENANT,
        "store_code": STORE,
        "item_code": ITEM,
        "update_type": UpdateType.SALE,
        "quantity_change": -1.0,
        "before_quantity": 50.0,
        "after_quantity": 49.0,
        "reference_id": "REF001",
        "timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc),
        "operator_id": "admin",
        "note": None,
    }
    base.update(overrides)
    return base


# ============================================================================
# StockRepository Tests
# ============================================================================

class TestStockRepository:
    """Tests for StockRepository."""

    def _make_repo(self):
        mock_db = MagicMock()
        repo = StockRepository(mock_db)
        repo.dbcollection = _make_mock_collection()
        return repo

    # -- find_by_item_async --------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_item_async_constructs_correct_filter(self):
        repo = self._make_repo()
        repo.dbcollection.find_one.return_value = _stock_doc_dict()

        result = await repo.find_by_item_async(TENANT, STORE, ITEM)

        repo.dbcollection.find_one.assert_called_once_with(
            {"tenant_id": TENANT, "store_code": STORE, "item_code": ITEM}
        )
        assert result is not None
        assert result.item_code == ITEM

    @pytest.mark.asyncio
    async def test_find_by_item_async_returns_none_when_not_found(self):
        repo = self._make_repo()
        repo.dbcollection.find_one.return_value = None

        result = await repo.find_by_item_async(TENANT, STORE, ITEM)
        assert result is None

    # -- find_by_store_async -------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_store_async_pagination(self):
        repo = self._make_repo()
        doc = _stock_doc_dict()
        cursor = _make_mock_cursor([doc])
        repo.dbcollection.find.return_value = cursor

        result = await repo.find_by_store_async(TENANT, STORE, skip=10, limit=5)

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args == {"tenant_id": TENANT, "store_code": STORE}
        cursor.sort.assert_called_once_with("item_code", 1)
        cursor.skip.assert_called_once_with(10)
        cursor.limit.assert_called_once_with(5)
        cursor.to_list.assert_called_once_with(length=5)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_by_store_async_default_pagination(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor

        await repo.find_by_store_async(TENANT, STORE)

        cursor.skip.assert_called_once_with(0)
        cursor.limit.assert_called_once_with(100)

    # -- find_low_stock_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_low_stock_async_expr_query(self):
        repo = self._make_repo()
        doc = _stock_doc_dict(current_quantity=5.0, minimum_quantity=10.0)
        cursor = _make_mock_cursor([doc])
        repo.dbcollection.find.return_value = cursor

        result = await repo.find_low_stock_async(TENANT, STORE)

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args["tenant_id"] == TENANT
        assert call_args["store_code"] == STORE
        assert "$expr" in call_args
        assert call_args["$expr"] == {"$lt": ["$current_quantity", "$minimum_quantity"]}
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_low_stock_async_returns_empty_list(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor

        result = await repo.find_low_stock_async(TENANT, STORE)
        assert result == []

    # -- find_reorder_alerts_async -------------------------------------------

    @pytest.mark.asyncio
    async def test_find_reorder_alerts_async_expr_query(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor

        await repo.find_reorder_alerts_async(TENANT, STORE)

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args["tenant_id"] == TENANT
        assert call_args["store_code"] == STORE
        assert "$expr" in call_args
        expr = call_args["$expr"]
        assert "$and" in expr
        conditions = expr["$and"]
        assert len(conditions) == 2
        assert {"$gt": ["$reorder_point", 0]} in conditions
        assert {"$lte": ["$current_quantity", "$reorder_point"]} in conditions

    # -- update_quantity_atomic_async ----------------------------------------

    @pytest.mark.asyncio
    async def test_update_quantity_atomic_async_inc_and_upsert(self):
        repo = self._make_repo()
        result_doc = _stock_doc_dict(current_quantity=55.0)
        repo.dbcollection.find_one_and_update = AsyncMock(return_value=result_doc)

        fixed_time = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        with patch("app.models.repositories.stock_repository.get_app_time", return_value=fixed_time):
            result = await repo.update_quantity_atomic_async(
                TENANT, STORE, ITEM, quantity_change=5.0, transaction_id="TXN001"
            )

        call_kwargs = repo.dbcollection.find_one_and_update.call_args
        assert call_kwargs.kwargs["filter"] == {
            "tenant_id": TENANT,
            "store_code": STORE,
            "item_code": ITEM,
        }

        update = call_kwargs.kwargs["update"]
        assert update["$inc"] == {"current_quantity": 5.0}
        assert update["$set"]["last_transaction_id"] == "TXN001"
        assert update["$set"]["updated_at"] == fixed_time
        assert update["$setOnInsert"]["tenant_id"] == TENANT
        assert update["$setOnInsert"]["store_code"] == STORE
        assert update["$setOnInsert"]["item_code"] == ITEM
        assert update["$setOnInsert"]["minimum_quantity"] == 0.0
        assert update["$setOnInsert"]["created_at"] == fixed_time

        assert call_kwargs.kwargs["upsert"] is True
        assert call_kwargs.kwargs["return_document"] is True

        assert result is not None
        assert isinstance(result, StockDocument)
        assert result.current_quantity == 55.0

    @pytest.mark.asyncio
    async def test_update_quantity_atomic_async_returns_none_when_no_result(self):
        repo = self._make_repo()
        repo.dbcollection.find_one_and_update = AsyncMock(return_value=None)

        with patch("app.models.repositories.stock_repository.get_app_time"):
            result = await repo.update_quantity_atomic_async(TENANT, STORE, ITEM, 5.0)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_quantity_atomic_async_initializes_collection(self):
        mock_db = MagicMock()
        repo = StockRepository(mock_db)
        repo.dbcollection = None

        mock_coll = _make_mock_collection()
        mock_coll.find_one_and_update = AsyncMock(return_value=_stock_doc_dict())
        mock_db.get_collection = MagicMock(return_value=mock_coll)

        with patch("app.models.repositories.stock_repository.get_app_time"):
            result = await repo.update_quantity_atomic_async(TENANT, STORE, ITEM, 1.0)

        mock_db.get_collection.assert_called_once()
        assert result is not None

    # -- count_by_store_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_count_by_store_async_filter(self):
        repo = self._make_repo()
        repo.dbcollection.count_documents = AsyncMock(return_value=42)

        result = await repo.count_by_store_async(TENANT, STORE)

        repo.dbcollection.count_documents.assert_called_once_with(
            {"tenant_id": TENANT, "store_code": STORE}
        )
        assert result == 42

    @pytest.mark.asyncio
    async def test_count_by_store_async_initializes_collection(self):
        mock_db = MagicMock()
        repo = StockRepository(mock_db)
        repo.dbcollection = None

        mock_coll = _make_mock_collection()
        mock_coll.count_documents = AsyncMock(return_value=10)
        mock_db.get_collection = MagicMock(return_value=mock_coll)

        result = await repo.count_by_store_async(TENANT, STORE)

        mock_db.get_collection.assert_called_once()
        assert result == 10

    # -- create_async (inherited) --------------------------------------------

    @pytest.mark.asyncio
    async def test_create_async_stock_document(self):
        repo = self._make_repo()
        mock_response = MagicMock()
        mock_response.inserted_id = "abc123"
        repo.dbcollection.insert_one = AsyncMock(return_value=mock_response)

        doc = StockDocument(**_stock_doc_dict())

        with patch("kugel_common.models.repositories.abstract_repository.get_app_time") as mock_time:
            mock_time.return_value = datetime(2025, 1, 1, tzinfo=timezone.utc)
            result = await repo.create_async(doc)

        assert result is True
        repo.dbcollection.insert_one.assert_called_once()

    # -- update_quantity_async (thin wrapper) ---------------------------------

    @pytest.mark.asyncio
    async def test_update_quantity_async_delegates_to_update_one(self):
        repo = self._make_repo()
        mock_response = MagicMock()
        mock_response.modified_count = 1
        repo.dbcollection.update_one = AsyncMock(return_value=mock_response)

        with patch("kugel_common.models.repositories.abstract_repository.get_app_time"):
            result = await repo.update_quantity_async(TENANT, STORE, ITEM, 99.0, "TXN002")

        call_args = repo.dbcollection.update_one.call_args
        filter_arg = call_args[0][0]
        update_arg = call_args[0][1]
        assert filter_arg == {"tenant_id": TENANT, "store_code": STORE, "item_code": ITEM}
        assert update_arg["$set"]["current_quantity"] == 99.0
        assert update_arg["$set"]["last_transaction_id"] == "TXN002"
        assert result is True

    # -- update_reorder_parameters_async -------------------------------------

    @pytest.mark.asyncio
    async def test_update_reorder_parameters_async(self):
        repo = self._make_repo()
        mock_response = MagicMock()
        mock_response.modified_count = 1
        repo.dbcollection.update_one = AsyncMock(return_value=mock_response)

        with patch("kugel_common.models.repositories.abstract_repository.get_app_time"):
            result = await repo.update_reorder_parameters_async(TENANT, STORE, ITEM, 25.0, 200.0)

        call_args = repo.dbcollection.update_one.call_args
        filter_arg = call_args[0][0]
        update_arg = call_args[0][1]
        assert filter_arg == {"tenant_id": TENANT, "store_code": STORE, "item_code": ITEM}
        assert update_arg["$set"]["reorder_point"] == 25.0
        assert update_arg["$set"]["reorder_quantity"] == 200.0
        assert result is True


# ============================================================================
# StockSnapshotRepository Tests
# ============================================================================

class TestStockSnapshotRepository:
    """Tests for StockSnapshotRepository."""

    def _make_repo(self):
        mock_db = MagicMock()
        repo = StockSnapshotRepository(mock_db)
        repo.dbcollection = _make_mock_collection()
        return repo

    # -- create_async (inherited) --------------------------------------------

    @pytest.mark.asyncio
    async def test_create_async_snapshot(self):
        repo = self._make_repo()
        mock_response = MagicMock()
        mock_response.inserted_id = "snap123"
        repo.dbcollection.insert_one = AsyncMock(return_value=mock_response)

        doc = StockSnapshotDocument(**_snapshot_doc_dict())

        with patch("kugel_common.models.repositories.abstract_repository.get_app_time") as mock_time:
            mock_time.return_value = datetime(2025, 1, 1, tzinfo=timezone.utc)
            result = await repo.create_async(doc)

        assert result is True
        repo.dbcollection.insert_one.assert_called_once()

    # -- find_by_store_async -------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_store_async_pagination_and_sort(self):
        repo = self._make_repo()
        doc = _snapshot_doc_dict()
        cursor = _make_mock_cursor([doc])
        repo.dbcollection.find.return_value = cursor

        result = await repo.find_by_store_async(TENANT, STORE, skip=5, limit=10)

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args == {"tenant_id": TENANT, "store_code": STORE}
        cursor.sort.assert_called_once_with("created_at", -1)
        cursor.skip.assert_called_once_with(5)
        cursor.limit.assert_called_once_with(10)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_by_store_async_default_pagination(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor

        await repo.find_by_store_async(TENANT, STORE)

        cursor.skip.assert_called_once_with(0)
        cursor.limit.assert_called_once_with(20)

    # -- find_by_date_range_async --------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_date_range_async_date_operators(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 6, 30, tzinfo=timezone.utc)

        await repo.find_by_date_range_async(TENANT, STORE, start, end)

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args["tenant_id"] == TENANT
        assert call_args["store_code"] == STORE
        assert call_args["created_at"]["$gte"] == start
        assert call_args["created_at"]["$lte"] == end
        cursor.sort.assert_called_once_with("created_at", -1)

    @pytest.mark.asyncio
    async def test_find_by_date_range_async_returns_documents(self):
        repo = self._make_repo()
        docs = [_snapshot_doc_dict(), _snapshot_doc_dict(total_items=10)]
        cursor = _make_mock_cursor(docs)
        repo.dbcollection.find.return_value = cursor

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 6, 30, tzinfo=timezone.utc)

        result = await repo.find_by_date_range_async(TENANT, STORE, start, end)
        assert len(result) == 2
        assert all(isinstance(r, StockSnapshotDocument) for r in result)

    # -- delete_old_snapshots_async ------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_old_snapshots_async_cutoff_calculation(self):
        repo = self._make_repo()
        mock_result = MagicMock()
        mock_result.deleted_count = 3
        repo.dbcollection.delete_many = AsyncMock(return_value=mock_result)

        retention_days = 30
        before = datetime.now(timezone.utc)
        result = await repo.delete_old_snapshots_async(TENANT, STORE, retention_days)
        after = datetime.now(timezone.utc)

        call_args = repo.dbcollection.delete_many.call_args[0][0]
        assert call_args["tenant_id"] == TENANT
        assert call_args["store_code"] == STORE
        cutoff = call_args["created_at"]["$lt"]

        # Verify cutoff is approximately retention_days ago
        expected_cutoff_before = before - timedelta(days=retention_days)
        expected_cutoff_after = after - timedelta(days=retention_days)
        assert expected_cutoff_before <= cutoff <= expected_cutoff_after
        assert result == 3

    @pytest.mark.asyncio
    async def test_delete_old_snapshots_async_default_retention(self):
        repo = self._make_repo()
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        repo.dbcollection.delete_many = AsyncMock(return_value=mock_result)

        before = datetime.now(timezone.utc)
        await repo.delete_old_snapshots_async(TENANT, STORE)
        after = datetime.now(timezone.utc)

        call_args = repo.dbcollection.delete_many.call_args[0][0]
        cutoff = call_args["created_at"]["$lt"]
        # Default is 90 days
        expected_before = before - timedelta(days=90)
        expected_after = after - timedelta(days=90)
        assert expected_before <= cutoff <= expected_after

    # -- find_by_generate_date_time_async ------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_generate_date_time_async_with_dates(self):
        repo = self._make_repo()
        doc = _snapshot_doc_dict()
        cursor = _make_mock_cursor([doc])
        repo.dbcollection.find.return_value = cursor
        repo.dbcollection.count_documents = AsyncMock(return_value=1)

        snapshots, count = await repo.find_by_generate_date_time_async(
            TENANT, STORE, "2025-01-01T00:00:00", "2025-06-30T23:59:59", skip=0, limit=10
        )

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args["tenant_id"] == TENANT
        assert call_args["store_code"] == STORE
        assert call_args["generate_date_time"]["$ne"] is None
        assert call_args["generate_date_time"]["$gte"] == "2025-01-01T00:00:00"
        assert call_args["generate_date_time"]["$lte"] == "2025-06-30T23:59:59"
        assert count == 1
        assert len(snapshots) == 1

    @pytest.mark.asyncio
    async def test_find_by_generate_date_time_async_without_dates(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor
        repo.dbcollection.count_documents = AsyncMock(return_value=0)

        snapshots, count = await repo.find_by_generate_date_time_async(
            TENANT, STORE, None, None, skip=0, limit=100
        )

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args["generate_date_time"] == {"$ne": None}
        # No $gte/$lte when dates are None
        assert "$gte" not in call_args.get("generate_date_time", {})
        assert "$lte" not in call_args.get("generate_date_time", {})
        assert count == 0

    @pytest.mark.asyncio
    async def test_find_by_generate_date_time_async_pagination(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor
        repo.dbcollection.count_documents = AsyncMock(return_value=50)

        await repo.find_by_generate_date_time_async(
            TENANT, STORE, None, None, skip=20, limit=10
        )

        cursor.sort.assert_called_once_with("generate_date_time", -1)
        cursor.skip.assert_called_once_with(20)
        cursor.limit.assert_called_once_with(10)

    # -- count_by_store_async ------------------------------------------------

    @pytest.mark.asyncio
    async def test_count_by_store_async(self):
        repo = self._make_repo()
        repo.dbcollection.count_documents = AsyncMock(return_value=15)

        result = await repo.count_by_store_async(TENANT, STORE)

        repo.dbcollection.count_documents.assert_called_once_with(
            {"tenant_id": TENANT, "store_code": STORE}
        )
        assert result == 15

    # -- get_latest_snapshot_async -------------------------------------------

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_async_delegates_with_sort(self):
        repo = self._make_repo()

        # Mock the parent class method that get_latest_snapshot_async delegates to
        doc = StockSnapshotDocument(**_snapshot_doc_dict())
        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock_method:
            mock_method.return_value = [doc]
            result = await repo.get_latest_snapshot_async(TENANT, STORE)

        mock_method.assert_called_once_with(
            filter={"tenant_id": TENANT, "store_code": STORE},
            limit=1,
            page=1,
            sort=[("created_at", -1)],
        )
        assert result is not None
        assert isinstance(result, StockSnapshotDocument)

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_async_returns_none_when_empty(self):
        repo = self._make_repo()

        with patch.object(repo, "get_list_async_with_sort_and_paging", new_callable=AsyncMock) as mock_method:
            mock_method.return_value = []
            result = await repo.get_latest_snapshot_async(TENANT, STORE)

        assert result is None


# ============================================================================
# StockUpdateRepository Tests
# ============================================================================

class TestStockUpdateRepository:
    """Tests for StockUpdateRepository."""

    def _make_repo(self):
        mock_db = MagicMock()
        repo = StockUpdateRepository(mock_db)
        repo.dbcollection = _make_mock_collection()
        return repo

    # -- create_async (inherited) --------------------------------------------

    @pytest.mark.asyncio
    async def test_create_async_update_document(self):
        repo = self._make_repo()
        mock_response = MagicMock()
        mock_response.inserted_id = "upd123"
        repo.dbcollection.insert_one = AsyncMock(return_value=mock_response)

        doc = StockUpdateDocument(**_update_doc_dict())

        with patch("kugel_common.models.repositories.abstract_repository.get_app_time") as mock_time:
            mock_time.return_value = datetime(2025, 1, 1, tzinfo=timezone.utc)
            result = await repo.create_async(doc)

        assert result is True
        repo.dbcollection.insert_one.assert_called_once()

    # -- find_by_item_async --------------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_item_async_filter_and_pagination(self):
        repo = self._make_repo()
        doc = _update_doc_dict()
        cursor = _make_mock_cursor([doc])
        repo.dbcollection.find.return_value = cursor

        result = await repo.find_by_item_async(TENANT, STORE, ITEM, skip=5, limit=25)

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args == {
            "tenant_id": TENANT,
            "store_code": STORE,
            "item_code": ITEM,
        }
        cursor.sort.assert_called_once_with("timestamp", -1)
        cursor.skip.assert_called_once_with(5)
        cursor.limit.assert_called_once_with(25)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_by_item_async_default_pagination(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor

        await repo.find_by_item_async(TENANT, STORE, ITEM)

        cursor.skip.assert_called_once_with(0)
        cursor.limit.assert_called_once_with(100)

    # -- find_by_reference_async ---------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_reference_async_filter(self):
        repo = self._make_repo()
        repo.dbcollection.find_one = AsyncMock(return_value=_update_doc_dict())

        result = await repo.find_by_reference_async("REF001")

        repo.dbcollection.find_one.assert_called_once_with({"reference_id": "REF001"})
        assert result is not None

    # -- find_by_date_range_async --------------------------------------------

    @pytest.mark.asyncio
    async def test_find_by_date_range_async_without_type(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 6, 30, tzinfo=timezone.utc)

        await repo.find_by_date_range_async(TENANT, STORE, start, end)

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args["tenant_id"] == TENANT
        assert call_args["store_code"] == STORE
        assert call_args["timestamp"]["$gte"] == start
        assert call_args["timestamp"]["$lte"] == end
        assert "update_type" not in call_args

    @pytest.mark.asyncio
    async def test_find_by_date_range_async_with_type(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 6, 30, tzinfo=timezone.utc)

        await repo.find_by_date_range_async(TENANT, STORE, start, end, update_type=UpdateType.SALE)

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args["update_type"] == "sale"

    # -- get_latest_update_async ---------------------------------------------

    @pytest.mark.asyncio
    async def test_get_latest_update_async_sort_and_limit(self):
        repo = self._make_repo()
        doc = _update_doc_dict()
        cursor = _make_mock_cursor([doc])
        repo.dbcollection.find.return_value = cursor

        result = await repo.get_latest_update_async(TENANT, STORE, ITEM)

        call_args = repo.dbcollection.find.call_args[0][0]
        assert call_args == {
            "tenant_id": TENANT,
            "store_code": STORE,
            "item_code": ITEM,
        }
        cursor.sort.assert_called_once_with("timestamp", -1)
        cursor.limit.assert_called_once_with(1)
        assert result is not None
        assert isinstance(result, StockUpdateDocument)

    @pytest.mark.asyncio
    async def test_get_latest_update_async_returns_none_when_empty(self):
        repo = self._make_repo()
        cursor = _make_mock_cursor([])
        repo.dbcollection.find.return_value = cursor

        result = await repo.get_latest_update_async(TENANT, STORE, ITEM)
        assert result is None

    # -- count_by_item_async -------------------------------------------------

    @pytest.mark.asyncio
    async def test_count_by_item_async_filter(self):
        repo = self._make_repo()
        repo.dbcollection.count_documents = AsyncMock(return_value=7)

        result = await repo.count_by_item_async(TENANT, STORE, ITEM)

        repo.dbcollection.count_documents.assert_called_once_with(
            {"tenant_id": TENANT, "store_code": STORE, "item_code": ITEM}
        )
        assert result == 7

    @pytest.mark.asyncio
    async def test_count_by_item_async_initializes_collection(self):
        mock_db = MagicMock()
        repo = StockUpdateRepository(mock_db)
        repo.dbcollection = None

        mock_coll = _make_mock_collection()
        mock_coll.count_documents = AsyncMock(return_value=3)
        mock_db.get_collection = MagicMock(return_value=mock_coll)

        result = await repo.count_by_item_async(TENANT, STORE, ITEM)

        mock_db.get_collection.assert_called_once()
        assert result == 3
