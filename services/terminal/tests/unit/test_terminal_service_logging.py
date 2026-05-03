"""Unit tests split out from test_terminal_service.py.

Imports / helpers preserved from the original.
"""
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
