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

from app.services.log_service import LogService
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from kugel_common.models.documents.base_tranlog import BaseTransaction


def make_tran():
    """Create a minimal BaseTransaction mock."""
    tran = MagicMock(spec=BaseTransaction)
    tran.model_dump.return_value = {}
    return tran


def make_service():
    tran_repo = AsyncMock()
    cash_repo = AsyncMock()
    oc_repo = AsyncMock()
    svc = LogService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=oc_repo,
    )
    return svc, tran_repo, cash_repo, oc_repo


# ---------------------------------------------------------------------------
# LogService.receive_tranlog_async
# ---------------------------------------------------------------------------

class TestLogServiceReceiveTranlog:
    @pytest.mark.asyncio
    async def test_receive_tranlog_success(self):
        svc, tran_repo, _, _ = make_service()
        tran = make_tran()
        tran_repo.create_tranlog_async.return_value = tran

        result = await svc.receive_tranlog_async(tran)

        assert result == tran
        tran_repo.create_tranlog_async.assert_called_once_with(tran)

    @pytest.mark.asyncio
    async def test_receive_tranlog_error_raises(self):
        """Repository error is re-raised after notification."""
        svc, tran_repo, _, _ = make_service()
        tran = make_tran()
        tran_repo.create_tranlog_async.side_effect = Exception("DB error")

        with patch("app.services.log_service.send_fatal_error_notification", new_callable=AsyncMock):
            with pytest.raises(Exception, match="DB error"):
                await svc.receive_tranlog_async(tran)


# ---------------------------------------------------------------------------
# LogService.receive_cashlog_async
# ---------------------------------------------------------------------------

class TestLogServiceReceiveCashlog:
    @pytest.mark.asyncio
    async def test_receive_cashlog_success(self):
        svc, _, cash_repo, _ = make_service()
        cashlog = CashInOutLog()
        cash_repo.create_cash_in_out_log.return_value = cashlog

        result = await svc.receive_cashlog_async(cashlog)

        assert result == cashlog
        cash_repo.create_cash_in_out_log.assert_called_once_with(cashlog)

    @pytest.mark.asyncio
    async def test_receive_cashlog_error_raises(self):
        """Repository error is re-raised after notification."""
        svc, _, cash_repo, _ = make_service()
        cashlog = CashInOutLog()
        cash_repo.create_cash_in_out_log.side_effect = Exception("DB error")

        with patch("app.services.log_service.send_fatal_error_notification", new_callable=AsyncMock):
            with pytest.raises(Exception, match="DB error"):
                await svc.receive_cashlog_async(cashlog)


# ---------------------------------------------------------------------------
# LogService.receive_open_close_log_async
# ---------------------------------------------------------------------------

class TestLogServiceReceiveOpenCloseLog:
    @pytest.mark.asyncio
    async def test_receive_open_close_log_success(self):
        svc, _, _, oc_repo = make_service()
        oc_log = OpenCloseLog()
        oc_repo.create_open_close_log.return_value = oc_log

        result = await svc.receive_open_close_log_async(oc_log)

        assert result == oc_log
        oc_repo.create_open_close_log.assert_called_once_with(oc_log)

    @pytest.mark.asyncio
    async def test_receive_open_close_log_error_raises(self):
        """Repository error is re-raised after notification."""
        svc, _, _, oc_repo = make_service()
        oc_log = OpenCloseLog()
        oc_repo.create_open_close_log.side_effect = Exception("DB error")

        with patch("app.services.log_service.send_fatal_error_notification", new_callable=AsyncMock):
            with pytest.raises(Exception, match="DB error"):
                await svc.receive_open_close_log_async(oc_log)
