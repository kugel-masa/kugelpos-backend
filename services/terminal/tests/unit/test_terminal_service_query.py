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

