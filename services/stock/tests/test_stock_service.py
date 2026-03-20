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

from app.services.stock_service import StockService
from app.models.documents import StockDocument, StockUpdateDocument
from app.enums.update_type import UpdateType
from app.exceptions.stock_exceptions import StockNotFoundError


def make_stock(
    tenant_id="T001",
    store_code="S001",
    item_code="ITEM-01",
    current_quantity=100.0,
    minimum_quantity=10.0,
    reorder_point=20.0,
    reorder_quantity=50.0,
):
    return StockDocument(
        tenant_id=tenant_id,
        store_code=store_code,
        item_code=item_code,
        current_quantity=current_quantity,
        minimum_quantity=minimum_quantity,
        reorder_point=reorder_point,
        reorder_quantity=reorder_quantity,
    )


def make_update_record(**kwargs):
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        item_code="ITEM-01",
        update_type=UpdateType.SALE,
        quantity_change=-1.0,
        before_quantity=100.0,
        after_quantity=99.0,
        timestamp=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return StockUpdateDocument(**defaults)


def make_service():
    """Create a StockService with all repositories mocked."""
    mock_db = MagicMock()
    with patch("app.services.stock_service.StockRepository") as MockStockRepo, \
         patch("app.services.stock_service.StockUpdateRepository") as MockUpdateRepo:
        stock_repo = AsyncMock()
        update_repo = AsyncMock()
        MockStockRepo.return_value = stock_repo
        MockUpdateRepo.return_value = update_repo
        service = StockService(database=mock_db)
        # Replace after creation to control behavior
        service._stock_repository = stock_repo
        service._stock_update_repository = update_repo
    return service, stock_repo, update_repo


# ---------------------------------------------------------------------------
# get_stock_async
# ---------------------------------------------------------------------------

class TestGetStock:
    @pytest.mark.asyncio
    async def test_get_stock_returns_doc(self):
        svc, stock_repo, _ = make_service()
        stock = make_stock()
        stock_repo.find_by_item_async.return_value = stock

        result = await svc.get_stock_async("T001", "S001", "ITEM-01")

        assert result == stock

    @pytest.mark.asyncio
    async def test_get_stock_returns_none_when_not_found(self):
        svc, stock_repo, _ = make_service()
        stock_repo.find_by_item_async.return_value = None

        result = await svc.get_stock_async("T001", "S001", "NONEXISTENT")

        assert result is None


# ---------------------------------------------------------------------------
# get_store_stocks_async / get_low_stocks_async / get_reorder_alerts_async
# ---------------------------------------------------------------------------

class TestGetStockLists:
    @pytest.mark.asyncio
    async def test_get_store_stocks(self):
        svc, stock_repo, _ = make_service()
        stocks = [make_stock(), make_stock(item_code="ITEM-02")]
        stock_repo.find_by_store_async.return_value = stocks
        stock_repo.count_by_store_async.return_value = 2

        result, total = await svc.get_store_stocks_async("T001", "S001")

        assert len(result) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_low_stocks(self):
        svc, stock_repo, _ = make_service()
        low_stocks = [make_stock(current_quantity=5.0, minimum_quantity=10.0)]
        stock_repo.find_low_stock_async.return_value = low_stocks

        result, count = await svc.get_low_stocks_async("T001", "S001")

        assert len(result) == 1
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_reorder_alerts(self):
        svc, stock_repo, _ = make_service()
        alerts = [make_stock(current_quantity=15.0, reorder_point=20.0)]
        stock_repo.find_reorder_alerts_async.return_value = alerts

        result, count = await svc.get_reorder_alerts_async("T001", "S001")

        assert len(result) == 1
        assert count == 1


# ---------------------------------------------------------------------------
# update_stock_async
# ---------------------------------------------------------------------------

class TestUpdateStock:
    @pytest.mark.asyncio
    async def test_update_stock_success(self):
        svc, stock_repo, update_repo = make_service()
        updated_stock = make_stock(current_quantity=99.0)
        stock_repo.update_quantity_atomic_async.return_value = updated_stock
        update_repo.create_async.return_value = None

        result = await svc.update_stock_async(
            "T001", "S001", "ITEM-01",
            quantity_change=-1.0,
            update_type=UpdateType.SALE,
        )

        assert result.quantity_change == -1.0
        assert result.after_quantity == 99.0
        assert result.before_quantity == 100.0  # 99 - (-1) = 100

    @pytest.mark.asyncio
    async def test_update_stock_atomic_failure_raises(self):
        svc, stock_repo, _ = make_service()
        stock_repo.update_quantity_atomic_async.return_value = None

        with pytest.raises(StockNotFoundError):
            await svc.update_stock_async(
                "T001", "S001", "NONEXISTENT",
                quantity_change=-1.0,
                update_type=UpdateType.SALE,
            )

    @pytest.mark.asyncio
    async def test_update_stock_negative_logs_warning(self):
        """Stock going negative is allowed but logged as warning."""
        svc, stock_repo, update_repo = make_service()
        # Stock goes to -5 (backorder allowed)
        updated_stock = make_stock(current_quantity=-5.0)
        stock_repo.update_quantity_atomic_async.return_value = updated_stock
        update_repo.create_async.return_value = None

        result = await svc.update_stock_async(
            "T001", "S001", "ITEM-01",
            quantity_change=-105.0,
            update_type=UpdateType.SALE,
        )

        assert result.after_quantity == -5.0

    @pytest.mark.asyncio
    async def test_update_stock_triggers_alert_when_service_configured(self):
        """If alert_service is set, check_and_send_alerts is called."""
        mock_db = MagicMock()
        mock_alert = AsyncMock()
        with patch("app.services.stock_service.StockRepository") as MockStockRepo, \
             patch("app.services.stock_service.StockUpdateRepository") as MockUpdateRepo:
            stock_repo = AsyncMock()
            update_repo = AsyncMock()
            MockStockRepo.return_value = stock_repo
            MockUpdateRepo.return_value = update_repo
            svc = StockService(database=mock_db, alert_service=mock_alert)
            svc._stock_repository = stock_repo
            svc._stock_update_repository = update_repo

        updated_stock = make_stock(current_quantity=5.0)
        stock_repo.update_quantity_atomic_async.return_value = updated_stock
        update_repo.create_async.return_value = None

        await svc.update_stock_async(
            "T001", "S001", "ITEM-01",
            quantity_change=-1.0,
            update_type=UpdateType.SALE,
        )

        mock_alert.check_and_send_alerts.assert_called_once_with(updated_stock)


# ---------------------------------------------------------------------------
# get_stock_history_async
# ---------------------------------------------------------------------------

class TestGetStockHistory:
    @pytest.mark.asyncio
    async def test_get_stock_history(self):
        svc, _, update_repo = make_service()
        updates = [make_update_record(), make_update_record()]
        update_repo.find_by_item_async.return_value = updates
        update_repo.count_by_item_async.return_value = 2

        result, total = await svc.get_stock_history_async("T001", "S001", "ITEM-01")

        assert len(result) == 2
        assert total == 2


# ---------------------------------------------------------------------------
# set_minimum_quantity_async
# ---------------------------------------------------------------------------

class TestSetMinimumQuantity:
    @pytest.mark.asyncio
    async def test_set_minimum_quantity_creates_new_stock(self):
        """When stock doesn't exist, creates a new record."""
        svc, stock_repo, _ = make_service()
        stock_repo.find_by_item_async.return_value = None
        stock_repo.create_async.return_value = None

        result = await svc.set_minimum_quantity_async("T001", "S001", "NEW-ITEM", 15.0)

        assert result is True
        stock_repo.create_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_minimum_quantity_updates_existing(self):
        """When stock exists, updates minimum_quantity."""
        svc, stock_repo, _ = make_service()
        stock_repo.find_by_item_async.return_value = make_stock()
        stock_repo.update_one_async.return_value = True

        result = await svc.set_minimum_quantity_async("T001", "S001", "ITEM-01", 20.0)

        assert result is True
        stock_repo.update_one_async.assert_called_once()


# ---------------------------------------------------------------------------
# set_reorder_parameters_async
# ---------------------------------------------------------------------------

class TestSetReorderParameters:
    @pytest.mark.asyncio
    async def test_set_reorder_creates_new_stock(self):
        """When stock doesn't exist, creates a new record."""
        svc, stock_repo, _ = make_service()
        stock_repo.find_by_item_async.return_value = None
        stock_repo.create_async.return_value = None

        result = await svc.set_reorder_parameters_async("T001", "S001", "NEW-ITEM", 25.0, 50.0)

        assert result is True
        stock_repo.create_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_reorder_updates_existing(self):
        """When stock exists, updates reorder parameters."""
        svc, stock_repo, _ = make_service()
        stock_repo.find_by_item_async.return_value = make_stock()
        stock_repo.update_reorder_parameters_async.return_value = True

        result = await svc.set_reorder_parameters_async("T001", "S001", "ITEM-01", 25.0, 50.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_set_reorder_triggers_alert_when_configured(self):
        """Alert is checked when updating existing stock with alert service."""
        mock_db = MagicMock()
        mock_alert = AsyncMock()
        with patch("app.services.stock_service.StockRepository") as MockStockRepo, \
             patch("app.services.stock_service.StockUpdateRepository") as MockUpdateRepo:
            stock_repo = AsyncMock()
            update_repo = AsyncMock()
            MockStockRepo.return_value = stock_repo
            MockUpdateRepo.return_value = update_repo
            svc = StockService(database=mock_db, alert_service=mock_alert)
            svc._stock_repository = stock_repo
            svc._stock_update_repository = update_repo

        existing_stock = make_stock(current_quantity=15.0)
        updated_stock = make_stock(current_quantity=15.0, reorder_point=25.0)
        stock_repo.find_by_item_async.side_effect = [existing_stock, updated_stock]
        stock_repo.update_reorder_parameters_async.return_value = True

        await svc.set_reorder_parameters_async("T001", "S001", "ITEM-01", 25.0, 50.0)

        mock_alert.check_and_send_alerts.assert_called_once_with(updated_stock)
