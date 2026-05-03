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
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.terminal_service import TerminalService
from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.enums.terminal_status import TerminalStatus
from app.enums.function_mode import FunctionMode
from app.exceptions import (
    NotFoundException,
    AlreadyExistException,
    TerminalNotFoundException,
    TerminalAlreadyExistsException,
    TerminalAlreadySignedInException,
    TerminalStatusException,
    SignInOutException,
    StoreNotFoundException,
    InternalErrorException,
)
from app.models.documents.terminallog_delivery_status_document import TerminallogDeliveryStatus
from app.exceptions import (
    TerminalNotSignedInException,
    CashInOutException,
    TerminalOpenException,
    TerminalCloseException,
)


def make_terminal(
    terminal_id="TID-001",
    store_code="S001",
    terminal_no=1,
    status=None,
    staff=None,
):
    t = TerminalInfoDocument()
    t.terminal_id = terminal_id
    t.store_code = store_code
    t.terminal_no = terminal_no
    t.status = status or TerminalStatus.Idle.value
    t.staff = staff
    return t


def make_service(terminal_id="TID-001", **repo_overrides):
    """Create a TerminalService with all repos mocked."""
    defaults = {
        "terminal_info_repo": AsyncMock(),
        "staff_master_repo": AsyncMock(),
        "store_info_repo": AsyncMock(),
        "cash_in_out_log_repo": AsyncMock(),
        "open_close_log_repo": AsyncMock(),
        "tran_log_repo": AsyncMock(),
        "terminal_log_delivery_status_repo": AsyncMock(),
    }
    defaults.update(repo_overrides)
    svc = TerminalService(terminal_id=terminal_id, **defaults)
    return svc, defaults


# ---------------------------------------------------------------------------
# TerminalService.create_terminal_async
# ---------------------------------------------------------------------------

class TestTerminalServiceCreate:
    @pytest.mark.asyncio
    async def test_create_success(self):
        svc, repos = make_service()
        terminal = make_terminal()
        repos["terminal_info_repo"].create_terminal_info.return_value = terminal

        result = await svc.create_terminal_async("S001", 1, "Test terminal")

        assert result == terminal
        assert svc.terminal_id == "TID-001"

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].create_terminal_info.side_effect = AlreadyExistException(
            "exists", "col", "key"
        )

        with pytest.raises(TerminalAlreadyExistsException):
            await svc.create_terminal_async("S001", 1, "Test terminal")

    @pytest.mark.asyncio
    async def test_create_other_error_propagates(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].create_terminal_info.side_effect = RuntimeError("unexpected")

        with pytest.raises(RuntimeError):
            await svc.create_terminal_async("S001", 1, "Test terminal")


# ---------------------------------------------------------------------------
# TerminalService.delete_terminal_async
# ---------------------------------------------------------------------------

class TestTerminalServiceDelete:
    @pytest.mark.asyncio
    async def test_delete_success(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].delete_terminal_info_async.return_value = True

        result = await svc.delete_terminal_async()

        assert result is True


# ---------------------------------------------------------------------------
# TerminalService.update_terminal_description_async
# ---------------------------------------------------------------------------

class TestTerminalServiceUpdateDescription:
    @pytest.mark.asyncio
    async def test_update_description_success(self):
        svc, repos = make_service()
        terminal = make_terminal()
        updated = make_terminal()
        updated.description = "New desc"
        repos["terminal_info_repo"].get_terminal_info_by_id_async.side_effect = [terminal, updated]

        result = await svc.update_terminal_description_async("New desc")

        assert result.description == "New desc"

    @pytest.mark.asyncio
    async def test_update_description_not_found_raises(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = None

        with pytest.raises(TerminalNotFoundException):
            await svc.update_terminal_description_async("New desc")


# ---------------------------------------------------------------------------
# TerminalService.update_terminal_function_mode_async
# ---------------------------------------------------------------------------

class TestTerminalServiceUpdateFunctionMode:
    @pytest.mark.asyncio
    async def test_update_function_mode_not_found_raises(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = None

        with pytest.raises(TerminalNotFoundException):
            await svc.update_terminal_function_mode_async(FunctionMode.Sales.value)

    @pytest.mark.asyncio
    async def test_update_function_mode_opened_terminal_cannot_open_again(self):
        """OpenTerminal mode not allowed when terminal is already opened."""
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Opened.value)
        updated = make_terminal(status=TerminalStatus.Opened.value)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.side_effect = [terminal, terminal, updated]

        with pytest.raises(TerminalStatusException):
            await svc.update_terminal_function_mode_async(FunctionMode.OpenTerminal.value)

    @pytest.mark.asyncio
    async def test_update_function_mode_closed_terminal_cannot_do_sales(self):
        """Sales mode not allowed when terminal is not opened."""
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Idle.value)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.side_effect = [terminal, terminal]

        with pytest.raises(TerminalStatusException):
            await svc.update_terminal_function_mode_async(FunctionMode.Sales.value)

    @pytest.mark.asyncio
    async def test_update_function_mode_success(self):
        """Valid mode change succeeds."""
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Opened.value)
        updated = make_terminal(status=TerminalStatus.Opened.value)
        updated.function_mode = FunctionMode.Sales.value
        repos["terminal_info_repo"].get_terminal_info_by_id_async.side_effect = [terminal, terminal, updated]

        result = await svc.update_terminal_function_mode_async(FunctionMode.Sales.value)

        assert result.function_mode == FunctionMode.Sales.value


# ---------------------------------------------------------------------------
# TerminalService.sign_in_terminal_async / sign_out_terminal_async
# ---------------------------------------------------------------------------

class TestTerminalServiceSignInOut:
    @pytest.mark.asyncio
    async def test_sign_in_success(self):
        svc, repos = make_service()
        terminal = make_terminal(staff=None)
        signed_in = make_terminal()
        signed_in.staff = MagicMock(staff_id="ST01")
        repos["terminal_info_repo"].get_terminal_info_by_id_async.side_effect = [terminal, signed_in]
        repos["staff_master_repo"].get_staff_by_id_async.return_value = MagicMock(staff_id="ST01")

        result = await svc.sign_in_terminal_async("ST01")

        assert result.staff is not None

    @pytest.mark.asyncio
    async def test_sign_in_terminal_not_found_raises(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = None

        with pytest.raises(TerminalNotFoundException):
            await svc.sign_in_terminal_async("ST01")

    @pytest.mark.asyncio
    async def test_sign_in_already_signed_in_raises(self):
        svc, repos = make_service()
        terminal = make_terminal(staff=MagicMock())  # staff already set

        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        with pytest.raises(TerminalAlreadySignedInException):
            await svc.sign_in_terminal_async("ST01")

    @pytest.mark.asyncio
    async def test_sign_in_staff_not_found_raises(self):
        svc, repos = make_service()
        terminal = make_terminal(staff=None)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal
        repos["staff_master_repo"].get_staff_by_id_async.side_effect = NotFoundException(
            "staff not found", "col", "key"
        )

        with pytest.raises(SignInOutException):
            await svc.sign_in_terminal_async("UNKNOWN")

    @pytest.mark.asyncio
    async def test_sign_out_success(self):
        svc, repos = make_service()
        terminal = make_terminal(staff=MagicMock())
        signed_out = make_terminal(staff=None)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.side_effect = [terminal, signed_out]

        result = await svc.sign_out_terminal_async()

        assert result.staff is None

    @pytest.mark.asyncio
    async def test_sign_out_terminal_not_found_raises(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = None

        with pytest.raises(TerminalNotFoundException):
            await svc.sign_out_terminal_async()

    @pytest.mark.asyncio
    async def test_sign_out_already_signed_out_returns_terminal(self):
        """Signing out a terminal already signed out just returns the terminal."""
        svc, repos = make_service()
        terminal = make_terminal(staff=None)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        result = await svc.sign_out_terminal_async()

        assert result == terminal
        # replace_terminal_info_async should NOT be called
        repos["terminal_info_repo"].replace_terminal_info_async.assert_not_called()


# ---------------------------------------------------------------------------
# TerminalService.get_terminal_info_async / get_terminal_info_list_async / is_* checks
# ---------------------------------------------------------------------------

class TestTerminalServiceGetAndStatus:
    @pytest.mark.asyncio
    async def test_get_terminal_info(self):
        svc, repos = make_service()
        terminal = make_terminal()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        result = await svc.get_terminal_info_async()

        assert result == terminal

    @pytest.mark.asyncio
    async def test_get_terminal_info_list(self):
        svc, repos = make_service()
        terminals = [make_terminal("T1"), make_terminal("T2")]
        repos["terminal_info_repo"].get_terminal_info_list_async.return_value = terminals

        result = await svc.get_terminal_info_list_async(limit=10, page=1, sort=[])

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_terminal_info_list_paginated(self):
        svc, repos = make_service()
        mock_result = MagicMock()
        repos["terminal_info_repo"].get_terminal_info_list_paginated_async.return_value = mock_result

        result = await svc.get_terminal_info_list_paginated_async(limit=5, page=2, sort=[])

        assert result == mock_result

    @pytest.mark.asyncio
    async def test_is_signed_in_true(self):
        svc, repos = make_service()
        terminal = make_terminal(staff=MagicMock())
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        assert await svc.is_sigin_in_async() is True

    @pytest.mark.asyncio
    async def test_is_signed_in_false(self):
        svc, repos = make_service()
        terminal = make_terminal(staff=None)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        assert await svc.is_sigin_in_async() is False

    @pytest.mark.asyncio
    async def test_is_opened_true(self):
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Opened.value)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        assert await svc.is_opened_async() is True

    @pytest.mark.asyncio
    async def test_is_opened_false(self):
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Idle.value)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        assert await svc.is_opened_async() is False


# ---------------------------------------------------------------------------
# get_terminal_info_list_async / get_terminal_info_list_paginated_async
# ---------------------------------------------------------------------------

class TestTerminalServiceList:
    @pytest.mark.asyncio
    async def test_get_terminal_info_list(self):
        svc, repos = make_service()
        terminals = [make_terminal(), make_terminal(terminal_no=2)]
        repos["terminal_info_repo"].get_terminal_info_list_async.return_value = terminals

        result = await svc.get_terminal_info_list_async(limit=10, page=1, sort=[("terminal_no", 1)])

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_terminal_info_list_with_store_filter(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].get_terminal_info_list_async.return_value = [make_terminal()]

        result = await svc.get_terminal_info_list_async(limit=10, page=1, sort=[], store_code="S001")

        repos["terminal_info_repo"].get_terminal_info_list_async.assert_called_once_with(
            limit=10, page=1, sort=[], store_code="S001"
        )

    @pytest.mark.asyncio
    async def test_get_terminal_info_list_paginated(self):
        svc, repos = make_service()
        paginated_result = MagicMock()
        repos["terminal_info_repo"].get_terminal_info_list_paginated_async.return_value = paginated_result

        result = await svc.get_terminal_info_list_paginated_async(limit=10, page=1, sort=[])

        assert result == paginated_result


# ---------------------------------------------------------------------------
# get_terminal_info_async
# ---------------------------------------------------------------------------

class TestTerminalServiceGetInfo:
    @pytest.mark.asyncio
    async def test_get_terminal_info(self):
        svc, repos = make_service()
        terminal = make_terminal()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        result = await svc.get_terminal_info_async()

        assert result.terminal_id == "TID-001"


# ---------------------------------------------------------------------------
# _publish_cash_in_out_log_async / _publish_open_close_log
# ---------------------------------------------------------------------------

class TestTerminalServicePublish:
    @pytest.mark.asyncio
    async def test_publish_cash_log_success(self):
        svc, repos = make_service()
        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (True, None)
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        await svc._publish_cash_in_out_log_async({"event_id": "EVT-001", "amount": 100})

        svc.pubsub_manager.publish_message_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_cash_log_failure_updates_status(self):
        svc, repos = make_service()
        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (False, "pub error")
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True
        repos["terminal_log_delivery_status_repo"].update_service_status.return_value = True

        await svc._publish_cash_in_out_log_async({"event_id": "EVT-001"})

        # delivery status should be updated to failed
        repos["terminal_log_delivery_status_repo"].update_delivery_status.assert_called()

    @pytest.mark.asyncio
    async def test_publish_open_close_log_success(self):
        svc, repos = make_service()
        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (True, None)
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        await svc._publish_open_close_log({"event_id": "EVT-002", "operation": "open"})

        svc.pubsub_manager.publish_message_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_open_close_log_failure(self):
        svc, repos = make_service()
        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (False, "timeout")
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True
        repos["terminal_log_delivery_status_repo"].update_service_status.return_value = True

        await svc._publish_open_close_log({"event_id": "EVT-002"})

        repos["terminal_log_delivery_status_repo"].update_delivery_status.assert_called()


# ---------------------------------------------------------------------------
# _update_delivery_status_internal_async / update_delivery_status_async
# ---------------------------------------------------------------------------

class TestTerminalServiceDeliveryStatus:
    @pytest.mark.asyncio
    async def test_update_delivery_status_internal_overall(self):
        svc, repos = make_service()
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        result = await svc._update_delivery_status_internal_async("EVT-001", "published")

        assert result is True
        repos["terminal_log_delivery_status_repo"].update_delivery_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_delivery_status_internal_service(self):
        svc, repos = make_service()
        repos["terminal_log_delivery_status_repo"].update_service_status.return_value = True

        result = await svc._update_delivery_status_internal_async(
            "EVT-001", "received", service_name="report"
        )

        assert result is True
        repos["terminal_log_delivery_status_repo"].update_service_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_delivery_status_internal_raises_on_error(self):
        svc, repos = make_service()
        repos["terminal_log_delivery_status_repo"].update_delivery_status.side_effect = Exception("DB error")

        with pytest.raises(InternalErrorException):
            await svc._update_delivery_status_internal_async("EVT-001", "published")

    @pytest.mark.asyncio
    async def test_update_delivery_status_all_received(self):
        """全サービス received なら overall を delivered に更新。"""
        svc, repos = make_service()
        repos["terminal_log_delivery_status_repo"].update_service_status.return_value = True
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        status_doc = MagicMock()
        svc1 = MagicMock()
        svc1.status = "received"
        svc2 = MagicMock()
        svc2.status = "received"
        status_doc.services = [svc1, svc2]
        repos["terminal_log_delivery_status_repo"].find_by_event_id.return_value = status_doc

        await svc.update_delivery_status_async("EVT-001", "received", "report", "ok")

        # delivered に更新されたことを確認
        calls = repos["terminal_log_delivery_status_repo"].update_delivery_status.call_args_list
        statuses = [c[1]["status"] for c in calls]
        assert "delivered" in statuses

    @pytest.mark.asyncio
    async def test_update_delivery_status_partially_delivered(self):
        """一部サービスのみ received なら partially_delivered。"""
        svc, repos = make_service()
        repos["terminal_log_delivery_status_repo"].update_service_status.return_value = True
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        status_doc = MagicMock()
        svc1 = MagicMock()
        svc1.status = "received"
        svc2 = MagicMock()
        svc2.status = "pending"
        status_doc.services = [svc1, svc2]
        repos["terminal_log_delivery_status_repo"].find_by_event_id.return_value = status_doc

        await svc.update_delivery_status_async("EVT-001", "received", "report", "ok")

        calls = repos["terminal_log_delivery_status_repo"].update_delivery_status.call_args_list
        statuses = [c[1]["status"] for c in calls]
        assert "partially_delivered" in statuses

    @pytest.mark.asyncio
    async def test_update_delivery_status_all_failed(self):
        """全サービス failed なら overall を failed に更新。"""
        svc, repos = make_service()
        repos["terminal_log_delivery_status_repo"].update_service_status.return_value = True
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        status_doc = MagicMock()
        svc1 = MagicMock()
        svc1.status = "failed"
        svc2 = MagicMock()
        svc2.status = "failed"
        status_doc.services = [svc1, svc2]
        repos["terminal_log_delivery_status_repo"].find_by_event_id.return_value = status_doc

        await svc.update_delivery_status_async("EVT-001", "failed", "report", "timeout")

        calls = repos["terminal_log_delivery_status_repo"].update_delivery_status.call_args_list
        statuses = [c[1]["status"] for c in calls]
        assert "failed" in statuses

    @pytest.mark.asyncio
    async def test_update_delivery_status_not_found_raises(self):
        """delivery status が見つからない場合 InternalErrorException。"""
        svc, repos = make_service()
        repos["terminal_log_delivery_status_repo"].update_service_status.return_value = True
        repos["terminal_log_delivery_status_repo"].find_by_event_id.return_value = None

        with pytest.raises(InternalErrorException):
            await svc.update_delivery_status_async("EVT-001", "received", "report", "ok")


# ---------------------------------------------------------------------------
# _convert_datetime
# ---------------------------------------------------------------------------

class TestTerminalServiceConvertDatetime:
    def test_convert_dict_with_datetime(self):
        from datetime import datetime
        svc, _ = make_service()
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = svc._convert_datetime({"key": dt, "nested": {"dt": dt}})

        assert result["key"] == dt.isoformat()
        assert result["nested"]["dt"] == dt.isoformat()

    def test_convert_list_with_datetime(self):
        from datetime import datetime
        svc, _ = make_service()
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = svc._convert_datetime([dt, "text", 123])

        assert result[0] == dt.isoformat()
        assert result[1] == "text"
        assert result[2] == 123

    def test_convert_plain_value(self):
        svc, _ = make_service()
        assert svc._convert_datetime("hello") == "hello"
        assert svc._convert_datetime(42) == 42


# ---------------------------------------------------------------------------
# _get_store_name
# ---------------------------------------------------------------------------

class TestTerminalServiceGetStoreName:
    @pytest.mark.asyncio
    async def test_get_store_name_success(self):
        svc, repos = make_service()
        store = MagicMock()
        store.store_name = " Test Store "
        repos["store_info_repo"].get_store_info_async.return_value = store

        result = await svc._get_store_name()

        assert result == "Test Store"

    @pytest.mark.asyncio
    async def test_get_store_name_none_raises(self):
        svc, repos = make_service()
        repos["store_info_repo"].get_store_info_async.return_value = None

        with pytest.raises(StoreNotFoundException):
            await svc._get_store_name()

    @pytest.mark.asyncio
    async def test_get_store_name_with_none_name(self):
        svc, repos = make_service()
        store = MagicMock()
        store.store_name = None
        repos["store_info_repo"].get_store_info_async.return_value = store

        result = await svc._get_store_name()

        assert result is None


# ---------------------------------------------------------------------------
# Helper: set up transaction mock for a repo
# ---------------------------------------------------------------------------

def _setup_transaction_mock(repo_mock):
    """Configure a repo mock so `async with await repo.start_transaction() as session` works."""
    mock_session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    repo_mock.start_transaction.return_value = ctx
    return mock_session


def _make_idle_terminal():
    """Convenience: MagicMock terminal that is signed-in but idle (not opened)."""
    staff = MagicMock()
    staff.id = "STAFF-01"
    staff.name = "Test Staff"
    t = MagicMock()
    t.terminal_id = "TID-001"
    t.store_code = "S001"
    t.terminal_no = 1
    t.status = TerminalStatus.Idle.value
    t.staff = staff
    t.tenant_id = "TENANT-01"
    t.business_date = "20260319"  # different day so open_counter resets
    t.open_counter = 0
    t.business_counter = 0
    t.initial_amount = 0
    t.physical_amount = None
    t.api_key = "dummy-key"
    t.model_copy.return_value = MagicMock(api_key="****-****-****-****")
    t.model_dump.return_value = {"tenant_id": "TENANT-01"}
    return t


def _make_opened_terminal(**kwargs):
    """Convenience: MagicMock terminal that is signed-in and opened."""
    staff = MagicMock()
    staff.id = "STAFF-01"
    staff.name = "Test Staff"
    t = MagicMock()
    t.terminal_id = "TID-001"
    t.store_code = "S001"
    t.terminal_no = 1
    t.status = TerminalStatus.Opened.value
    t.staff = staff
    t.tenant_id = "TENANT-01"
    t.business_date = "20260320"
    t.open_counter = 1
    t.business_counter = 1
    t.initial_amount = 10000
    t.physical_amount = None
    t.api_key = "dummy-key"
    t.model_copy.return_value = MagicMock(api_key="****-****-****-****")
    t.model_dump.return_value = {
        "tenant_id": "TENANT-01",
        "store_code": "S001",
        "terminal_no": 1,
        "business_date": "20260320",
    }
    return t


# ---------------------------------------------------------------------------
# TerminalService.cash_in_out_async
# ---------------------------------------------------------------------------

class TestTerminalServiceCashInOut:
    @pytest.mark.asyncio
    @patch("app.services.terminal_service.CashInOutReceiptData")
    async def test_cash_in_out_success(self, mock_receipt_cls):
        svc, repos = make_service()
        terminal = _make_opened_terminal()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        store = MagicMock()
        store.store_name = "Test Store"
        repos["store_info_repo"].get_store_info_async.return_value = store

        # receipt mock
        mock_receipt = MagicMock()
        mock_receipt.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
        mock_receipt_cls.return_value = mock_receipt

        # transaction mock
        _setup_transaction_mock(repos["cash_in_out_log_repo"])
        repos["cash_in_out_log_repo"].create_cash_in_out_log.return_value = MagicMock()

        # pubsub
        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (True, None)

        result = await svc.cash_in_out_async(amount=500, description="test cash in")

        assert result is not None
        repos["cash_in_out_log_repo"].create_cash_in_out_log.assert_called_once()
        repos["cash_in_out_log_repo"].commit_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_cash_in_out_terminal_not_found(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = None

        with pytest.raises(TerminalNotFoundException):
            await svc.cash_in_out_async(amount=500, description="test")

    @pytest.mark.asyncio
    async def test_cash_in_out_not_signed_in(self):
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Opened.value, staff=None)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        with pytest.raises(TerminalNotSignedInException):
            await svc.cash_in_out_async(amount=500, description="test")

    @pytest.mark.asyncio
    async def test_cash_in_out_not_opened(self):
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Idle.value, staff=MagicMock())
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        with pytest.raises(TerminalStatusException):
            await svc.cash_in_out_async(amount=500, description="test")

    @pytest.mark.asyncio
    @patch("app.services.terminal_service.CashInOutReceiptData")
    async def test_cash_in_out_transaction_error_raises(self, mock_receipt_cls):
        """Transaction failure should raise CashInOutException."""
        svc, repos = make_service()
        terminal = _make_opened_terminal()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        store = MagicMock()
        store.store_name = "Test Store"
        repos["store_info_repo"].get_store_info_async.return_value = store

        mock_receipt = MagicMock()
        mock_receipt.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
        mock_receipt_cls.return_value = mock_receipt

        _setup_transaction_mock(repos["cash_in_out_log_repo"])
        repos["cash_in_out_log_repo"].create_cash_in_out_log.side_effect = RuntimeError("DB error")

        svc.pubsub_manager = AsyncMock()

        with pytest.raises(CashInOutException):
            await svc.cash_in_out_async(amount=500, description="test")

        repos["cash_in_out_log_repo"].abort_transaction.assert_called_once()


# ---------------------------------------------------------------------------
# TerminalService.open_terminal_async
# ---------------------------------------------------------------------------

class TestTerminalServiceOpenTerminal:
    @pytest.mark.asyncio
    @patch("app.services.terminal_service.OpenCloseReceiptData")
    @patch("app.services.terminal_service.CashInOutReceiptData")
    async def test_open_terminal_success(self, mock_cash_receipt_cls, mock_oc_receipt_cls):
        svc, repos = make_service()
        terminal = _make_idle_terminal()

        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        store = MagicMock()
        store.store_name = "Test Store"
        repos["store_info_repo"].get_store_info_async.return_value = store

        for cls_mock in (mock_cash_receipt_cls, mock_oc_receipt_cls):
            inst = MagicMock()
            inst.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
            cls_mock.return_value = inst

        _setup_transaction_mock(repos["open_close_log_repo"])

        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (True, None)

        result = await svc.open_terminal_async(initial_amout=10000)

        assert result is not None
        assert result.operation == "open"
        repos["open_close_log_repo"].commit_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_open_terminal_not_found(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = None

        with pytest.raises(TerminalNotFoundException):
            await svc.open_terminal_async(initial_amout=10000)

    @pytest.mark.asyncio
    async def test_open_terminal_already_opened(self):
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Opened.value)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        with pytest.raises(TerminalStatusException):
            await svc.open_terminal_async(initial_amout=10000)

    @pytest.mark.asyncio
    @patch("app.services.terminal_service.OpenCloseReceiptData")
    @patch("app.services.terminal_service.CashInOutReceiptData")
    async def test_open_terminal_transaction_error_raises(self, mock_cash_receipt_cls, mock_oc_receipt_cls):
        svc, repos = make_service()
        terminal = _make_idle_terminal()

        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        store = MagicMock()
        store.store_name = "Test Store"
        repos["store_info_repo"].get_store_info_async.return_value = store

        for cls_mock in (mock_cash_receipt_cls, mock_oc_receipt_cls):
            inst = MagicMock()
            inst.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
            cls_mock.return_value = inst

        _setup_transaction_mock(repos["open_close_log_repo"])
        repos["open_close_log_repo"].create_open_close_log.side_effect = RuntimeError("DB error")

        svc.pubsub_manager = AsyncMock()

        with pytest.raises(TerminalOpenException):
            await svc.open_terminal_async(initial_amout=10000)

        repos["open_close_log_repo"].abort_transaction.assert_called_once()


# ---------------------------------------------------------------------------
# TerminalService.close_terminal_async
# ---------------------------------------------------------------------------

class TestTerminalServiceCloseTerminal:
    @pytest.mark.asyncio
    @patch("app.services.terminal_service.OpenCloseReceiptData")
    async def test_close_terminal_success(self, mock_oc_receipt_cls):
        svc, repos = make_service()
        terminal = _make_opened_terminal()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        store = MagicMock()
        store.store_name = "Test Store"
        repos["store_info_repo"].get_store_info_async.return_value = store

        inst = MagicMock()
        inst.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
        mock_oc_receipt_cls.return_value = inst

        # cash_in_out_log_repo paginated result
        cash_paginated = MagicMock()
        cash_paginated.metadata.total = 0
        cash_paginated.data = []
        repos["cash_in_out_log_repo"].get_cash_in_out_logs.return_value = cash_paginated

        # tran_log_repo paginated result
        tran_paginated = MagicMock()
        tran_paginated.metadata.total = 0
        tran_paginated.data = []
        repos["tran_log_repo"].get_tran_log_list_async.return_value = tran_paginated

        _setup_transaction_mock(repos["open_close_log_repo"])

        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (True, None)

        result = await svc.close_terminal_async(physical_amount=9500)

        assert result is not None
        assert result.operation == "close"
        repos["open_close_log_repo"].commit_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_terminal_not_found(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = None

        with pytest.raises(TerminalNotFoundException):
            await svc.close_terminal_async(physical_amount=9500)

    @pytest.mark.asyncio
    async def test_close_terminal_not_opened_idle(self):
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Idle.value)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        with pytest.raises(TerminalStatusException):
            await svc.close_terminal_async(physical_amount=9500)

    @pytest.mark.asyncio
    async def test_close_terminal_already_closed(self):
        svc, repos = make_service()
        terminal = make_terminal(status=TerminalStatus.Closed.value)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        with pytest.raises(TerminalStatusException):
            await svc.close_terminal_async(physical_amount=9500)

    @pytest.mark.asyncio
    @patch("app.services.terminal_service.OpenCloseReceiptData")
    async def test_close_terminal_transaction_error_raises(self, mock_oc_receipt_cls):
        svc, repos = make_service()
        terminal = _make_opened_terminal()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        store = MagicMock()
        store.store_name = "Test Store"
        repos["store_info_repo"].get_store_info_async.return_value = store

        inst = MagicMock()
        inst.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
        mock_oc_receipt_cls.return_value = inst

        cash_paginated = MagicMock()
        cash_paginated.metadata.total = 0
        cash_paginated.data = []
        repos["cash_in_out_log_repo"].get_cash_in_out_logs.return_value = cash_paginated

        tran_paginated = MagicMock()
        tran_paginated.metadata.total = 0
        tran_paginated.data = []
        repos["tran_log_repo"].get_tran_log_list_async.return_value = tran_paginated

        _setup_transaction_mock(repos["open_close_log_repo"])
        repos["open_close_log_repo"].create_open_close_log.side_effect = RuntimeError("DB error")

        svc.pubsub_manager = AsyncMock()

        with pytest.raises(TerminalCloseException):
            await svc.close_terminal_async(physical_amount=9500)

        repos["open_close_log_repo"].abort_transaction.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.terminal_service.OpenCloseReceiptData")
    async def test_close_terminal_with_transactions(self, mock_oc_receipt_cls):
        """Close with existing transactions and cash logs."""
        svc, repos = make_service()
        terminal = _make_opened_terminal()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        store = MagicMock()
        store.store_name = "Test Store"
        repos["store_info_repo"].get_store_info_async.return_value = store

        inst = MagicMock()
        inst.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
        mock_oc_receipt_cls.return_value = inst

        # cash logs exist
        cash_log_entry = MagicMock()
        cash_log_entry.generate_date_time = "2026-03-20T10:00:00"
        cash_paginated = MagicMock()
        cash_paginated.metadata.total = 3
        cash_paginated.data = [cash_log_entry]
        repos["cash_in_out_log_repo"].get_cash_in_out_logs.return_value = cash_paginated

        # tran logs exist
        tran_entry = MagicMock()
        tran_entry.transaction_no = 5
        tran_paginated = MagicMock()
        tran_paginated.metadata.total = 5
        tran_paginated.data = [tran_entry]
        repos["tran_log_repo"].get_tran_log_list_async.return_value = tran_paginated

        _setup_transaction_mock(repos["open_close_log_repo"])

        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (True, None)

        result = await svc.close_terminal_async(physical_amount=9500)

        assert result.cart_transaction_count == 5
        assert result.cart_transaction_last_no == 5
        assert result.cash_in_out_count == 3


# ---------------------------------------------------------------------------
# TerminalService.republish_undelivered_terminallog_async
# ---------------------------------------------------------------------------

class TestTerminalServiceRepublishUndelivered:
    @pytest.mark.asyncio
    async def test_no_undelivered_logs_noop(self):
        svc, repos = make_service()
        repos["terminal_log_delivery_status_repo"].find_pending_deliveries.return_value = []

        await svc.republish_undelivered_terminallog_async()

        svc.pubsub_manager = AsyncMock()
        # No publish calls should have been made — pubsub_manager was not even touched

    @pytest.mark.asyncio
    async def test_no_undelivered_logs_none(self):
        svc, repos = make_service()
        repos["terminal_log_delivery_status_repo"].find_pending_deliveries.return_value = None

        await svc.republish_undelivered_terminallog_async()

    @pytest.mark.asyncio
    @patch("app.services.terminal_service.send_warning_notification", new_callable=AsyncMock)
    async def test_republish_cash_in_out_log(self, mock_notify):
        """Undelivered cash_in_out log older than interval but within failed period is republished."""
        from datetime import datetime, timedelta
        svc, repos = make_service()
        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (True, None)
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        status = MagicMock()
        status.event_id = "EVT-100"
        status.tenant_id = "TENANT-01"
        status.store_code = "S001"
        status.terminal_no = 1
        # Created 10 minutes ago (older than default 5 min interval, within failed period)
        status.created_at = datetime.now() - timedelta(minutes=10)
        status.payload = {"event_type": "cash_in_out", "event_id": "EVT-100"}
        status.model_dump = MagicMock(return_value={})

        repos["terminal_log_delivery_status_repo"].find_pending_deliveries.return_value = [status]

        await svc.republish_undelivered_terminallog_async()

        svc.pubsub_manager.publish_message_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.terminal_service.send_warning_notification", new_callable=AsyncMock)
    async def test_republish_open_close_log(self, mock_notify):
        """Undelivered open log is republished."""
        from datetime import datetime, timedelta
        svc, repos = make_service()
        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (True, None)
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        status = MagicMock()
        status.event_id = "EVT-200"
        status.tenant_id = "TENANT-01"
        status.store_code = "S001"
        status.terminal_no = 1
        status.created_at = datetime.now() - timedelta(minutes=10)
        status.payload = {"event_type": "open", "event_id": "EVT-200"}
        status.model_dump = MagicMock(return_value={})

        repos["terminal_log_delivery_status_repo"].find_pending_deliveries.return_value = [status]

        await svc.republish_undelivered_terminallog_async()

        svc.pubsub_manager.publish_message_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.terminal_service.send_warning_notification", new_callable=AsyncMock)
    async def test_republish_skips_recent_logs(self, mock_notify):
        """Logs created very recently (within interval) are skipped."""
        from datetime import datetime, timedelta
        svc, repos = make_service()
        svc.pubsub_manager = AsyncMock()

        status = MagicMock()
        status.event_id = "EVT-300"
        status.created_at = datetime.now() - timedelta(minutes=1)  # only 1 min ago
        status.payload = {"event_type": "cash_in_out", "event_id": "EVT-300"}

        repos["terminal_log_delivery_status_repo"].find_pending_deliveries.return_value = [status]

        await svc.republish_undelivered_terminallog_async()

        svc.pubsub_manager.publish_message_async.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.terminal_service.send_warning_notification", new_callable=AsyncMock)
    async def test_republish_marks_old_as_failed(self, mock_notify):
        """Logs older than failed period are marked as failed and a warning is sent."""
        from datetime import datetime, timedelta
        svc, repos = make_service()
        svc.pubsub_manager = AsyncMock()
        svc.pubsub_manager.publish_message_async.return_value = (True, None)
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        status = MagicMock()
        status.event_id = "EVT-400"
        status.tenant_id = "TENANT-01"
        status.store_code = "S001"
        status.terminal_no = 1
        # Very old — beyond failed threshold (default 60 min)
        status.created_at = datetime.now() - timedelta(hours=3)
        status.payload = {"event_type": "cash_in_out", "event_id": "EVT-400"}
        status.model_dump = MagicMock(return_value={})

        repos["terminal_log_delivery_status_repo"].find_pending_deliveries.return_value = [status]

        await svc.republish_undelivered_terminallog_async()

        # Should have been marked as failed
        repos["terminal_log_delivery_status_repo"].update_delivery_status.assert_called()
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.terminal_service.send_warning_notification", new_callable=AsyncMock)
    async def test_republish_unknown_event_type_marks_failed(self, mock_notify):
        """Unknown event_type should mark the log as failed."""
        from datetime import datetime, timedelta
        svc, repos = make_service()
        svc.pubsub_manager = AsyncMock()
        repos["terminal_log_delivery_status_repo"].update_delivery_status.return_value = True

        status = MagicMock()
        status.event_id = "EVT-500"
        status.tenant_id = "TENANT-01"
        status.store_code = "S001"
        status.terminal_no = 1
        status.created_at = datetime.now() - timedelta(minutes=10)
        status.payload = {"event_type": "unknown_type", "event_id": "EVT-500"}
        status.model_dump = MagicMock(return_value={})

        repos["terminal_log_delivery_status_repo"].find_pending_deliveries.return_value = [status]

        await svc.republish_undelivered_terminallog_async()

        # Should not have tried to publish
        svc.pubsub_manager.publish_message_async.assert_not_called()
        # Should have updated status to failed
        repos["terminal_log_delivery_status_repo"].update_delivery_status.assert_called()
