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
        staff_mock = MagicMock()
        staff_mock.id = "S001"
        terminal = make_terminal(staff=staff_mock)
        signed_out = make_terminal(staff=None)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.side_effect = [terminal, signed_out]

        result, previous_staff_id = await svc.sign_out_terminal_async()

        assert result.staff is None
        assert previous_staff_id == "S001"

    @pytest.mark.asyncio
    async def test_sign_out_terminal_not_found_raises(self):
        svc, repos = make_service()
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = None

        with pytest.raises(TerminalNotFoundException):
            await svc.sign_out_terminal_async()

    @pytest.mark.asyncio
    async def test_sign_out_already_signed_out_returns_terminal(self):
        """Signing out a terminal already signed out returns it with previous_staff_id=None."""
        svc, repos = make_service()
        terminal = make_terminal(staff=None)
        repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal

        result, previous_staff_id = await svc.sign_out_terminal_async()

        assert result == terminal
        assert previous_staff_id is None
        # replace_terminal_info_async should NOT be called
        repos["terminal_info_repo"].replace_terminal_info_async.assert_not_called()


# ---------------------------------------------------------------------------
# TerminalService.get_terminal_info_async / get_terminal_info_list_async / is_* checks
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

