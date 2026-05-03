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
import asyncio
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.documents.stock_document import StockDocument
from app.services.alert_service import AlertService


def make_stock(
    tenant_id="T001",
    store_code="S001",
    item_code="ITEM-01",
    current_quantity=10.0,
    minimum_quantity=5.0,
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


def make_service(cooldown=60):
    """Create AlertService with mocked ConnectionManager.
    settings はモジュール内の __init__ でローカルインポートされるため、
    作成後に alert_cooldown を直接上書きする。
    """
    conn_manager = AsyncMock()
    conn_manager.send_to_store = AsyncMock()
    svc = AlertService(connection_manager=conn_manager)
    svc.alert_cooldown = cooldown  # override after construction
    return svc, conn_manager


# ---------------------------------------------------------------------------
# _should_send_alert
# ---------------------------------------------------------------------------

class TestShouldSendAlert:
    def test_first_alert_is_sent(self):
        svc, _ = make_service()
        assert svc._should_send_alert("key1") is True

    def test_second_alert_within_cooldown_is_suppressed(self):
        svc, _ = make_service(cooldown=60)
        svc._should_send_alert("key1")  # 初回でタイムスタンプ記録
        assert svc._should_send_alert("key1") is False

    def test_alert_after_cooldown_is_sent(self):
        svc, _ = make_service(cooldown=60)
        # クールダウン経過済みのタイムスタンプをセット
        svc.recent_alerts["key1"] = datetime.now(timezone.utc) - timedelta(seconds=61)
        assert svc._should_send_alert("key1") is True

    def test_different_keys_are_independent(self):
        svc, _ = make_service()
        svc._should_send_alert("key1")
        # key2 は未記録なので送信可能
        assert svc._should_send_alert("key2") is True


# ---------------------------------------------------------------------------
# check_and_send_alerts
# ---------------------------------------------------------------------------

class TestCheckAndSendAlerts:
    @pytest.mark.asyncio
    async def test_reorder_point_alert_sent_when_below(self):
        """current_quantity <= reorder_point のときアラート送信。"""
        svc, conn = make_service()
        stock = make_stock(current_quantity=15.0, reorder_point=20.0, minimum_quantity=0.0)

        await svc.check_and_send_alerts(stock)

        conn.send_to_store.assert_called_once()
        payload = json.loads(conn.send_to_store.call_args[0][2])
        assert payload["alert_type"] == "reorder_point"
        assert payload["item_code"] == "ITEM-01"

    @pytest.mark.asyncio
    async def test_minimum_stock_alert_sent_when_below(self):
        """current_quantity < minimum_quantity のときアラート送信。"""
        svc, conn = make_service()
        stock = make_stock(current_quantity=3.0, minimum_quantity=5.0, reorder_point=0.0)

        await svc.check_and_send_alerts(stock)

        conn.send_to_store.assert_called_once()
        payload = json.loads(conn.send_to_store.call_args[0][2])
        assert payload["alert_type"] == "minimum_stock"

    @pytest.mark.asyncio
    async def test_both_alerts_sent_when_both_conditions_met(self):
        """両方の条件が満たされた場合、2件のアラートが送信される。"""
        svc, conn = make_service()
        stock = make_stock(current_quantity=3.0, minimum_quantity=5.0, reorder_point=20.0)

        await svc.check_and_send_alerts(stock)

        assert conn.send_to_store.call_count == 2

    @pytest.mark.asyncio
    async def test_no_alert_when_stock_sufficient(self):
        """在庫が十分な場合はアラート送信なし。"""
        svc, conn = make_service()
        stock = make_stock(current_quantity=100.0, minimum_quantity=5.0, reorder_point=20.0)

        await svc.check_and_send_alerts(stock)

        conn.send_to_store.assert_not_called()

    @pytest.mark.asyncio
    async def test_reorder_alert_suppressed_within_cooldown(self):
        """クールダウン内の重複アラートは抑制される。"""
        svc, conn = make_service(cooldown=60)
        stock = make_stock(current_quantity=5.0, reorder_point=20.0, minimum_quantity=0.0)

        await svc.check_and_send_alerts(stock)
        await svc.check_and_send_alerts(stock)  # クールダウン内の2回目

        conn.send_to_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_reorder_alert_when_reorder_point_zero(self):
        """reorder_point が 0 のときはアラートなし。"""
        svc, conn = make_service()
        stock = make_stock(current_quantity=0.0, reorder_point=0.0, minimum_quantity=0.0)

        await svc.check_and_send_alerts(stock)

        conn.send_to_store.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_minimum_alert_when_minimum_quantity_zero(self):
        """minimum_quantity が 0 のときはアラートなし。"""
        svc, conn = make_service()
        stock = make_stock(current_quantity=0.0, minimum_quantity=0.0, reorder_point=0.0)

        await svc.check_and_send_alerts(stock)

        conn.send_to_store.assert_not_called()


# ---------------------------------------------------------------------------
# send_alert
# ---------------------------------------------------------------------------

class TestSendAlert:
    @pytest.mark.asyncio
    async def test_send_alert_calls_connection_manager(self):
        svc, conn = make_service()
        alert = {
            "type": "stock_alert",
            "alert_type": "reorder_point",
            "tenant_id": "T001",
            "store_code": "S001",
            "item_code": "ITEM-01",
            "current_quantity": 5.0,
            "reorder_point": 20.0,
            "reorder_quantity": 50.0,
            "timestamp": "2024-01-01T00:00:00Z",
        }

        await svc.send_alert(alert)

        conn.send_to_store.assert_called_once()
        args = conn.send_to_store.call_args[0]
        assert args[0] == "T001"
        assert args[1] == "S001"

    @pytest.mark.asyncio
    async def test_send_alert_missing_tenant_id_skips(self):
        """tenant_id がないアラートは connection_manager を呼ばない。"""
        svc, conn = make_service()
        alert = {"alert_type": "reorder_point", "store_code": "S001", "item_code": "ITEM-01"}

        await svc.send_alert(alert)

        conn.send_to_store.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_alert_missing_store_code_skips(self):
        """store_code がないアラートは connection_manager を呼ばない。"""
        svc, conn = make_service()
        alert = {"alert_type": "reorder_point", "tenant_id": "T001", "item_code": "ITEM-01"}

        await svc.send_alert(alert)

        conn.send_to_store.assert_not_called()


# ---------------------------------------------------------------------------
# stop / get_current_alerts
# ---------------------------------------------------------------------------

class TestAlertServiceLifecycle:
    @pytest.mark.asyncio
    async def test_stop_without_start_does_not_raise(self):
        """start() せずに stop() を呼んでも例外が出ない。"""
        svc, _ = make_service()
        await svc.stop()  # _cleanup_task is None — no-op

    @pytest.mark.asyncio
    async def test_get_current_alerts_returns_empty_list(self):
        svc, _ = make_service()
        result = await svc.get_current_alerts("T001", "S001")
        assert result == []

    @pytest.mark.asyncio
    async def test_start_creates_cleanup_task(self):
        """start() creates a background cleanup task (line 28)."""
        svc, _ = make_service()
        assert svc._cleanup_task is None
        svc.start()
        assert svc._cleanup_task is not None
        # Clean up: cancel the task so it doesn't leak
        svc._cleanup_task.cancel()
        try:
            await svc._cleanup_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_stop_after_start_cancels_task(self):
        """stop() after start() properly cancels the background task (lines 33-37)."""
        svc, _ = make_service()
        svc.start()
        task = svc._cleanup_task
        assert not task.done()

        await svc.stop()

        assert task.cancelled() or task.done()
