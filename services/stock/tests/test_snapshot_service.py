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
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.documents.stock_document import StockDocument
from app.models.documents.stock_snapshot_document import StockSnapshotDocument
from app.services.snapshot_service import SnapshotService


def make_stock(item_code="ITEM-01", current_quantity=100.0,
               minimum_quantity=10.0, reorder_point=20.0, reorder_quantity=50.0):
    return StockDocument(
        tenant_id="T001",
        store_code="S001",
        item_code=item_code,
        current_quantity=current_quantity,
        minimum_quantity=minimum_quantity,
        reorder_point=reorder_point,
        reorder_quantity=reorder_quantity,
    )


def make_snapshot(tenant_id="T001", store_code="S001", total_items=2, total_quantity=200.0):
    s = MagicMock(spec=StockSnapshotDocument)
    s.tenant_id = tenant_id
    s.store_code = store_code
    s.total_items = total_items
    s.total_quantity = total_quantity
    s.snapshot_id = "SNAP-001"
    return s


def make_service():
    """StockRepository と StockSnapshotRepository をモックした SnapshotService を作成。"""
    mock_db = MagicMock()
    with patch("app.services.snapshot_service.StockRepository") as MockStockRepo, \
         patch("app.services.snapshot_service.StockSnapshotRepository") as MockSnapshotRepo:
        stock_repo = AsyncMock()
        snapshot_repo = AsyncMock()
        MockStockRepo.return_value = stock_repo
        MockSnapshotRepo.return_value = snapshot_repo
        svc = SnapshotService(database=mock_db)
        svc._stock_repository = stock_repo
        svc._snapshot_repository = snapshot_repo
    return svc, stock_repo, snapshot_repo


# ---------------------------------------------------------------------------
# create_snapshot_async
# ---------------------------------------------------------------------------

class TestCreateSnapshot:
    @pytest.mark.asyncio
    async def test_create_snapshot_success(self):
        """在庫データからスナップショットを作成し、返却する。"""
        svc, stock_repo, snapshot_repo = make_service()
        stocks = [make_stock("ITEM-01", 100.0), make_stock("ITEM-02", 50.0)]
        stock_repo.find_by_store_async.return_value = stocks
        snapshot_repo.create_async.return_value = True
        created = make_snapshot(total_items=2, total_quantity=150.0)
        snapshot_repo.get_latest_snapshot_async.return_value = created

        result = await svc.create_snapshot_async("T001", "S001")

        assert result.total_items == 2
        assert result.total_quantity == 150.0
        snapshot_repo.create_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_snapshot_raises_on_save_failure(self):
        """create_async が False を返したら例外を発生させる。"""
        svc, stock_repo, snapshot_repo = make_service()
        stock_repo.find_by_store_async.return_value = [make_stock()]
        snapshot_repo.create_async.return_value = False

        with pytest.raises(Exception, match="Failed to create snapshot"):
            await svc.create_snapshot_async("T001", "S001")

    @pytest.mark.asyncio
    async def test_create_snapshot_returns_original_when_retrieval_fails(self):
        """get_latest_snapshot_async が None を返した場合は元のスナップショットを返す。"""
        svc, stock_repo, snapshot_repo = make_service()
        stock_repo.find_by_store_async.return_value = [make_stock()]
        snapshot_repo.create_async.return_value = True
        snapshot_repo.get_latest_snapshot_async.return_value = None

        result = await svc.create_snapshot_async("T001", "S001")

        # None ではなく StockSnapshotDocument インスタンスが返る
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_snapshot_empty_store(self):
        """在庫ゼロの店舗でスナップショットを作成できる。"""
        svc, stock_repo, snapshot_repo = make_service()
        stock_repo.find_by_store_async.return_value = []
        snapshot_repo.create_async.return_value = True
        created = make_snapshot(total_items=0, total_quantity=0.0)
        snapshot_repo.get_latest_snapshot_async.return_value = created

        result = await svc.create_snapshot_async("T001", "S001")

        assert result.total_items == 0

    @pytest.mark.asyncio
    async def test_create_snapshot_custom_created_by(self):
        """created_by パラメータがリポジトリに渡されることを確認。"""
        svc, stock_repo, snapshot_repo = make_service()
        stock_repo.find_by_store_async.return_value = [make_stock()]
        snapshot_repo.create_async.return_value = True
        snapshot_repo.get_latest_snapshot_async.return_value = make_snapshot()

        await svc.create_snapshot_async("T001", "S001", created_by="admin")

        # create_async に渡された引数の created_by を確認
        call_arg = snapshot_repo.create_async.call_args[0][0]
        assert call_arg.created_by == "admin"


# ---------------------------------------------------------------------------
# get_snapshots_async
# ---------------------------------------------------------------------------

class TestGetSnapshots:
    @pytest.mark.asyncio
    async def test_get_snapshots_returns_list_and_count(self):
        svc, _, snapshot_repo = make_service()
        snapshots = [make_snapshot(), make_snapshot()]
        snapshot_repo.find_by_store_async.return_value = snapshots
        snapshot_repo.count_by_store_async.return_value = 2

        result, total = await svc.get_snapshots_async("T001", "S001")

        assert len(result) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_snapshots_empty(self):
        svc, _, snapshot_repo = make_service()
        snapshot_repo.find_by_store_async.return_value = []
        snapshot_repo.count_by_store_async.return_value = 0

        result, total = await svc.get_snapshots_async("T001", "S001")

        assert result == []
        assert total == 0


# ---------------------------------------------------------------------------
# get_snapshot_by_id_async
# ---------------------------------------------------------------------------

class TestGetSnapshotById:
    @pytest.mark.asyncio
    async def test_get_snapshot_by_id_found(self):
        svc, _, snapshot_repo = make_service()
        snap = make_snapshot()
        snapshot_repo.get_by_id_async.return_value = snap

        result = await svc.get_snapshot_by_id_async("SNAP-001")

        assert result == snap

    @pytest.mark.asyncio
    async def test_get_snapshot_by_id_not_found(self):
        svc, _, snapshot_repo = make_service()
        snapshot_repo.get_by_id_async.return_value = None

        result = await svc.get_snapshot_by_id_async("NONEXISTENT")

        assert result is None


# ---------------------------------------------------------------------------
# get_snapshots_by_date_range_async
# ---------------------------------------------------------------------------

class TestGetSnapshotsByDateRange:
    @pytest.mark.asyncio
    async def test_get_snapshots_by_date_range(self):
        svc, _, snapshot_repo = make_service()
        snapshots = [make_snapshot()]
        snapshot_repo.find_by_date_range_async.return_value = snapshots

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        result = await svc.get_snapshots_by_date_range_async("T001", "S001", start, end)

        assert len(result) == 1
        snapshot_repo.find_by_date_range_async.assert_called_once_with("T001", "S001", start, end)


# ---------------------------------------------------------------------------
# cleanup_old_snapshots_async
# ---------------------------------------------------------------------------

class TestCleanupOldSnapshots:
    @pytest.mark.asyncio
    async def test_cleanup_returns_deleted_count(self):
        svc, _, snapshot_repo = make_service()
        snapshot_repo.delete_old_snapshots_async.return_value = 5

        result = await svc.cleanup_old_snapshots_async("T001", "S001", retention_days=30)

        assert result == 5
        snapshot_repo.delete_old_snapshots_async.assert_called_once_with("T001", "S001", 30)

    @pytest.mark.asyncio
    async def test_cleanup_default_retention_days(self):
        svc, _, snapshot_repo = make_service()
        snapshot_repo.delete_old_snapshots_async.return_value = 0

        await svc.cleanup_old_snapshots_async("T001", "S001")

        # デフォルトは 90 日
        snapshot_repo.delete_old_snapshots_async.assert_called_once_with("T001", "S001", 90)


# ---------------------------------------------------------------------------
# get_snapshots_by_generate_date_time_async
# ---------------------------------------------------------------------------

class TestGetSnapshotsByGenerateDateTime:
    @pytest.mark.asyncio
    async def test_get_snapshots_by_generate_date_time(self):
        svc, _, snapshot_repo = make_service()
        snapshots = [make_snapshot()]
        snapshot_repo.find_by_generate_date_time_async.return_value = (snapshots, 1)

        result, total = await svc.get_snapshots_by_generate_date_time_async(
            "T001", "S001", "20240101", "20240131"
        )

        assert len(result) == 1
        assert total == 1
