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
