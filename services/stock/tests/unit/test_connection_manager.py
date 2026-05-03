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
from unittest.mock import AsyncMock, MagicMock

from app.websocket.connection_manager import ConnectionManager


def make_ws():
    """モック WebSocket を作成。"""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self):
        mgr = ConnectionManager()
        ws = make_ws()

        await mgr.connect(ws, "T001", "S001")

        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_registers_connection(self):
        mgr = ConnectionManager()
        ws = make_ws()

        await mgr.connect(ws, "T001", "S001")

        assert mgr.get_connection_count("T001", "S001") == 1

    @pytest.mark.asyncio
    async def test_multiple_connections_same_store(self):
        mgr = ConnectionManager()
        ws1 = make_ws()
        ws2 = make_ws()

        await mgr.connect(ws1, "T001", "S001")
        await mgr.connect(ws2, "T001", "S001")

        assert mgr.get_connection_count("T001", "S001") == 2


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self):
        mgr = ConnectionManager()
        ws = make_ws()
        await mgr.connect(ws, "T001", "S001")

        await mgr.disconnect(ws, "T001", "S001")

        assert mgr.get_connection_count("T001", "S001") == 0

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_empty_structures(self):
        mgr = ConnectionManager()
        ws = make_ws()
        await mgr.connect(ws, "T001", "S001")

        await mgr.disconnect(ws, "T001", "S001")

        # tenant_id entry should be removed
        assert "T001" not in mgr._connections

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_is_noop(self):
        """切断済みの WebSocket を再度切断しても例外が出ない。"""
        mgr = ConnectionManager()
        ws = make_ws()

        await mgr.disconnect(ws, "T001", "S001")  # never connected


class TestSendToStore:
    @pytest.mark.asyncio
    async def test_send_to_connected_clients(self):
        mgr = ConnectionManager()
        ws1 = make_ws()
        ws2 = make_ws()
        await mgr.connect(ws1, "T001", "S001")
        await mgr.connect(ws2, "T001", "S001")

        await mgr.send_to_store("T001", "S001", "hello")

        ws1.send_text.assert_called_once_with("hello")
        ws2.send_text.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_store_is_noop(self):
        mgr = ConnectionManager()

        await mgr.send_to_store("T001", "NOSTORE", "msg")  # no error

    @pytest.mark.asyncio
    async def test_failed_send_removes_connection(self):
        """送信失敗した WebSocket は切断される。"""
        mgr = ConnectionManager()
        ws_ok = make_ws()
        ws_bad = make_ws()
        ws_bad.send_text.side_effect = RuntimeError("connection lost")
        await mgr.connect(ws_ok, "T001", "S001")
        await mgr.connect(ws_bad, "T001", "S001")

        await mgr.send_to_store("T001", "S001", "msg")

        # ws_bad is removed, ws_ok stays
        assert mgr.get_connection_count("T001", "S001") == 1


class TestBroadcastToTenant:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_stores(self):
        mgr = ConnectionManager()
        ws1 = make_ws()
        ws2 = make_ws()
        await mgr.connect(ws1, "T001", "S001")
        await mgr.connect(ws2, "T001", "S002")

        await mgr.broadcast_to_tenant("T001", "broadcast_msg")

        ws1.send_text.assert_called_once_with("broadcast_msg")
        ws2.send_text.assert_called_once_with("broadcast_msg")

    @pytest.mark.asyncio
    async def test_broadcast_nonexistent_tenant_is_noop(self):
        mgr = ConnectionManager()

        await mgr.broadcast_to_tenant("NOONE", "msg")  # no error


class TestGetConnectionCount:
    @pytest.mark.asyncio
    async def test_count_by_tenant_and_store(self):
        mgr = ConnectionManager()
        await mgr.connect(make_ws(), "T001", "S001")
        await mgr.connect(make_ws(), "T001", "S001")

        assert mgr.get_connection_count("T001", "S001") == 2

    @pytest.mark.asyncio
    async def test_count_by_tenant(self):
        mgr = ConnectionManager()
        await mgr.connect(make_ws(), "T001", "S001")
        await mgr.connect(make_ws(), "T001", "S002")

        assert mgr.get_connection_count("T001") == 2

    @pytest.mark.asyncio
    async def test_count_total(self):
        mgr = ConnectionManager()
        await mgr.connect(make_ws(), "T001", "S001")
        await mgr.connect(make_ws(), "T002", "S001")

        assert mgr.get_connection_count() == 2

    def test_count_empty(self):
        mgr = ConnectionManager()
        assert mgr.get_connection_count() == 0
