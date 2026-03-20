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

from kugel_common.exceptions import ServiceException

from app.services.report_service import ReportService
from kugel_common.exceptions import CannotCreateException
from app.exceptions import (
    ReportNotFoundException,
    ReportGenerationException,
    TerminalNotClosedException,
    OpenCloseLogMissingException,
    CashInOutMissingException,
    TransactionMissingException,
)
from app.models.documents.daily_info_document import DailyInfoDocument


def make_service(report_makers=None):
    """全リポジトリをモックした ReportService を作成。
    ReportPluginManager.load_plugins をパッチして外部ファイル読み込みを回避。
    """
    tran_repo = AsyncMock()
    tran_repo.tenant_id = "T001"
    cash_repo = AsyncMock()
    open_close_repo = AsyncMock()
    daily_repo = AsyncMock()
    terminal_repo = AsyncMock()

    makers = report_makers if report_makers is not None else {}

    with patch("app.services.report_service.ReportPluginManager") as MockPluginMgr:
        mock_mgr = MagicMock()
        mock_mgr.load_plugins.return_value = makers
        MockPluginMgr.return_value = mock_mgr
        svc = ReportService(
            tran_repository=tran_repo,
            cash_in_out_log_repository=cash_repo,
            open_close_log_repository=open_close_repo,
            daily_info_repository=daily_repo,
            terminal_info_repository=terminal_repo,
        )

    # リポジトリを直接上書き（__init__ 後に差し替え）
    svc.tran_repository = tran_repo
    svc.cash_in_out_log_repository = cash_repo
    svc.open_close_log_repository = open_close_repo
    svc.daily_info_repository = daily_repo
    svc.terminal_repository = terminal_repo
    svc.report_makers = makers

    return svc, {
        "tran": tran_repo,
        "cash": cash_repo,
        "open_close": open_close_repo,
        "daily": daily_repo,
        "terminal": terminal_repo,
    }


def make_mock_maker(report_data="mock_report"):
    """generate_report を持つモックプラグインを作成。"""
    maker = AsyncMock()
    maker.generate_report = AsyncMock(return_value=report_data)
    # business_date_from を co_varnames に含める（date range対応を示す）
    code_mock = MagicMock()
    code_mock.co_varnames = ["self", "store_code", "terminal_no", "business_date",
                              "open_counter", "report_scope", "report_type",
                              "limit", "page", "sort", "business_counter",
                              "business_date_from", "business_date_to"]
    maker.generate_report.__code__ = code_mock
    return maker


# ---------------------------------------------------------------------------
# get_report_for_store_async
# ---------------------------------------------------------------------------

class TestGetReportForStore:
    @pytest.mark.asyncio
    async def test_flash_report_success(self):
        """flash スコープはターミナルクローズチェックなしでレポート生成。"""
        maker = make_mock_maker("flash_result")
        svc, repos = make_service(report_makers={"sales": maker})

        result = await svc.get_report_for_store_async(
            store_code="S001",
            report_scope="flash",
            report_type="sales",
            business_date="20240101",
        )

        assert result == "flash_result"
        maker.generate_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_normalized_to_flash(self):
        """'flush' は下位互換のため 'flash' に正規化される。"""
        maker = make_mock_maker("result")
        svc, _ = make_service(report_makers={"sales": maker})

        # flush でもターミナルクローズチェックをスキップする（flash 扱い）
        result = await svc.get_report_for_store_async(
            store_code="S001",
            report_scope="flush",
            report_type="sales",
            business_date="20240101",
        )

        assert result == "result"

    @pytest.mark.asyncio
    async def test_invalid_report_type_raises_not_found(self):
        """存在しないレポートタイプは ReportNotFoundException を発生させる。"""
        svc, _ = make_service(report_makers={})

        with pytest.raises(ReportNotFoundException):
            await svc.get_report_for_store_async(
                store_code="S001",
                report_scope="flash",
                report_type="nonexistent",
                business_date="20240101",
            )

    @pytest.mark.asyncio
    async def test_daily_report_terminal_not_closed_raises(self):
        """daily スコープでターミナルが未クローズの場合 TerminalNotClosedException。"""
        maker = make_mock_maker()
        svc, repos = make_service(report_makers={"sales": maker})

        # _check_if_terminal_closed が ServiceException を発生させる
        svc._check_if_terminal_closed = AsyncMock(
            side_effect=ServiceException("not closed", None)
        )

        with pytest.raises(TerminalNotClosedException):
            await svc.get_report_for_store_async(
                store_code="S001",
                report_scope="daily",
                report_type="sales",
                business_date="20240101",
                open_counter=1,
            )

    @pytest.mark.asyncio
    async def test_daily_report_with_date_range_skips_terminal_check(self):
        """date range 指定時は daily でもターミナルクローズチェックをスキップ。"""
        maker = make_mock_maker("range_result")
        svc, _ = make_service(report_makers={"sales": maker})
        svc._check_if_terminal_closed = AsyncMock(
            side_effect=ServiceException("should not be called", None)
        )

        result = await svc.get_report_for_store_async(
            store_code="S001",
            report_scope="daily",
            report_type="sales",
            business_date_from="20240101",
            business_date_to="20240131",
        )

        assert result == "range_result"
        svc._check_if_terminal_closed.assert_not_called()

    @pytest.mark.asyncio
    async def test_report_generation_exception_wraps_error(self):
        """maker が例外を発生させた場合 ReportGenerationException でラップされる。"""
        maker = make_mock_maker()
        maker.generate_report.side_effect = ValueError("generation error")
        svc, _ = make_service(report_makers={"sales": maker})

        with pytest.raises(ReportGenerationException):
            await svc.get_report_for_store_async(
                store_code="S001",
                report_scope="flash",
                report_type="sales",
                business_date="20240101",
            )

    @pytest.mark.asyncio
    async def test_api_key_request_calls_send_to_journal(self):
        """API キーリクエスト時は _send_report_to_journal が呼ばれる。"""
        maker = make_mock_maker("data")
        svc, _ = make_service(report_makers={"sales": maker})
        svc._send_report_to_journal = AsyncMock()

        await svc.get_report_for_store_async(
            store_code="S001",
            report_scope="flash",
            report_type="sales",
            business_date="20240101",
            is_api_key_request=True,
        )

        svc._send_report_to_journal.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_api_key_request_skips_journal(self):
        """通常リクエスト時は _send_report_to_journal を呼ばない。"""
        maker = make_mock_maker("data")
        svc, _ = make_service(report_makers={"sales": maker})
        svc._send_report_to_journal = AsyncMock()

        await svc.get_report_for_store_async(
            store_code="S001",
            report_scope="flash",
            report_type="sales",
            business_date="20240101",
            is_api_key_request=False,
        )

        svc._send_report_to_journal.assert_not_called()


# ---------------------------------------------------------------------------
# get_report_for_terminal_async
# ---------------------------------------------------------------------------

class TestGetReportForTerminal:
    @pytest.mark.asyncio
    async def test_flash_terminal_report_success(self):
        """flash スコープのターミナルレポートが正常に返る。"""
        maker = make_mock_maker("terminal_flash")
        svc, _ = make_service(report_makers={"sales": maker})

        result = await svc.get_report_for_terminal_async(
            store_code="S001",
            terminal_no=1,
            report_scope="flash",
            report_type="sales",
            business_date="20240101",
        )

        assert result == "terminal_flash"

    @pytest.mark.asyncio
    async def test_invalid_report_type_raises_not_found(self):
        """存在しないタイプは ReportNotFoundException。"""
        svc, _ = make_service(report_makers={})

        with pytest.raises(ReportNotFoundException):
            await svc.get_report_for_terminal_async(
                store_code="S001",
                terminal_no=1,
                report_scope="flash",
                report_type="unknown",
                business_date="20240101",
            )

    @pytest.mark.asyncio
    async def test_daily_terminal_not_closed_raises(self):
        """daily スコープでターミナル未クローズは TerminalNotClosedException。"""
        maker = make_mock_maker()
        svc, _ = make_service(report_makers={"sales": maker})
        svc._check_if_terminal_closed = AsyncMock(
            side_effect=ServiceException("not closed", None)
        )

        with pytest.raises(TerminalNotClosedException):
            await svc.get_report_for_terminal_async(
                store_code="S001",
                terminal_no=1,
                report_scope="daily",
                report_type="sales",
                business_date="20240101",
                open_counter=1,
            )

    @pytest.mark.asyncio
    async def test_flush_normalized_to_flash_terminal(self):
        """'flush' → 'flash' の正規化がターミナルレポートでも機能する。"""
        maker = make_mock_maker("result")
        svc, _ = make_service(report_makers={"sales": maker})

        result = await svc.get_report_for_terminal_async(
            store_code="S001",
            terminal_no=1,
            report_scope="flush",
            report_type="sales",
            business_date="20240101",
        )

        assert result == "result"

    @pytest.mark.asyncio
    async def test_terminal_report_generation_exception(self):
        """maker エラーは ReportGenerationException でラップされる。"""
        maker = make_mock_maker()
        maker.generate_report.side_effect = RuntimeError("fail")
        svc, _ = make_service(report_makers={"sales": maker})

        with pytest.raises(ReportGenerationException):
            await svc.get_report_for_terminal_async(
                store_code="S001",
                terminal_no=1,
                report_scope="flash",
                report_type="sales",
                business_date="20240101",
            )


# ---------------------------------------------------------------------------
# _create_daily_info
# ---------------------------------------------------------------------------

def make_paginated_result(data=None, total=0):
    """PaginatedResult 互換のモックオブジェクトを作成。"""
    result = MagicMock()
    result.data = data or []
    result.metadata = MagicMock()
    result.metadata.total = total
    return result


class TestCreateDailyInfo:
    @pytest.mark.asyncio
    async def test_create_daily_info_success(self):
        svc, repos = make_service()
        repos["daily"].create_daily_info_document.return_value = None
        daily_info = DailyInfoDocument(tenant_id="T001", store_code="S001", terminal_no=1)

        await svc._create_daily_info(daily_info, True, "All OK")

        assert daily_info.verified is True
        assert daily_info.verified_message == "All OK"
        repos["daily"].create_daily_info_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_daily_info_raises_on_failure(self):
        svc, repos = make_service()
        repos["daily"].create_daily_info_document.side_effect = Exception("DB error")
        daily_info = DailyInfoDocument(tenant_id="T001", store_code="S001", terminal_no=1)

        with pytest.raises(CannotCreateException):
            await svc._create_daily_info(daily_info, False, "fail")


# ---------------------------------------------------------------------------
# _check_if_terminal_closed
# ---------------------------------------------------------------------------

class TestCheckIfTerminalClosed:
    @pytest.mark.asyncio
    async def test_terminal_check_calls_commit_terminal(self):
        """terminal_no 指定時は _commit_terminal_report_async が呼ばれる。"""
        svc, _ = make_service()
        svc._commit_terminal_report_async = AsyncMock()

        await svc._check_if_terminal_closed("S001", "20240101", 1, terminal_no=1)

        svc._commit_terminal_report_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_check_calls_commit_store(self):
        """terminal_no=None なら _commit_store_report_async が呼ばれる。"""
        svc, _ = make_service()
        svc._commit_store_report_async = AsyncMock()

        await svc._check_if_terminal_closed("S001", "20240101", 1, terminal_no=None)

        svc._commit_store_report_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_raises_service_exception_on_failure(self):
        """内部検証が失敗したら ServiceException を発生させる。"""
        svc, _ = make_service()
        svc._commit_terminal_report_async = AsyncMock(
            side_effect=ServiceException("not verified", None)
        )

        with pytest.raises(ServiceException):
            await svc._check_if_terminal_closed("S001", "20240101", 1, terminal_no=1)


# ---------------------------------------------------------------------------
# _commit_store_report_async
# ---------------------------------------------------------------------------

class TestCommitStoreReport:
    @pytest.mark.asyncio
    async def test_all_terminals_verified(self):
        """全ターミナルが検証成功なら正常終了。"""
        svc, repos = make_service()
        terminal1 = MagicMock()
        terminal1.terminal_no = 1
        terminal2 = MagicMock()
        terminal2.terminal_no = 2
        repos["terminal"].get_terminal_info_list_async.return_value = [terminal1, terminal2]
        svc._commit_terminal_report_async = AsyncMock()

        await svc._commit_store_report_async("S001", "20240101", 1)

        assert svc._commit_terminal_report_async.call_count == 2

    @pytest.mark.asyncio
    async def test_some_terminals_fail_raises(self):
        """一部ターミナルが検証失敗なら ServiceException。"""
        svc, repos = make_service()
        terminal1 = MagicMock()
        terminal1.terminal_no = 1
        repos["terminal"].get_terminal_info_list_async.return_value = [terminal1]
        svc._commit_terminal_report_async = AsyncMock(
            side_effect=ServiceException("fail", None)
        )

        with pytest.raises(ServiceException):
            await svc._commit_store_report_async("S001", "20240101", 1)


# ---------------------------------------------------------------------------
# _commit_terminal_report_async
# ---------------------------------------------------------------------------

class TestCommitTerminalReport:
    @pytest.mark.asyncio
    async def test_already_verified_returns_early(self):
        """既に verified=True の場合は早期リターン。"""
        svc, repos = make_service()
        daily = MagicMock()
        daily.verified = True
        repos["daily"].get_daily_info_documents.return_value = make_paginated_result(data=[daily], total=1)

        await svc._commit_terminal_report_async("T001", "S001", 1, "20240101", 1)

        # open_close は呼ばれない（早期リターン）
        repos["open_close"].get_open_close_logs.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_open_log_returns_early(self):
        """open ログがない場合は早期リターン（まだ開店していない）。"""
        svc, repos = make_service()
        repos["daily"].get_daily_info_documents.return_value = make_paginated_result(total=0)
        repos["open_close"].get_open_close_logs.return_value = make_paginated_result(total=0)

        await svc._commit_terminal_report_async("T001", "S001", 1, "20240101", 1)

        # create_daily_info は呼ばれない
        repos["daily"].create_daily_info_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_close_log_raises(self):
        """close ログがない場合は OpenCloseLogMissingException。"""
        svc, repos = make_service()
        repos["daily"].get_daily_info_documents.return_value = make_paginated_result(total=0)
        # open ログはある
        repos["open_close"].get_open_close_logs.side_effect = [
            make_paginated_result(data=[MagicMock()], total=1),  # open log
            make_paginated_result(total=0),  # close log missing
        ]
        repos["daily"].create_daily_info_document.return_value = None

        with pytest.raises(OpenCloseLogMissingException):
            await svc._commit_terminal_report_async("T001", "S001", 1, "20240101", 1)

    @pytest.mark.asyncio
    async def test_cash_log_count_mismatch_raises(self):
        """cash ログ件数が一致しない場合 CashInOutMissingException。"""
        svc, repos = make_service()
        repos["daily"].get_daily_info_documents.return_value = make_paginated_result(total=0)

        close_log = MagicMock()
        close_log.cash_in_out_count = 5
        close_log.cash_in_out_last_datetime = "2024-01-01T10:00:00"
        close_log.cart_transaction_count = 0
        close_log.cart_transaction_last_no = 0

        repos["open_close"].get_open_close_logs.side_effect = [
            make_paginated_result(data=[MagicMock()], total=1),  # open
            make_paginated_result(data=[close_log], total=1),  # close
        ]
        # cash logs count mismatch
        repos["cash"].get_cash_in_out_logs.return_value = make_paginated_result(total=3)
        repos["daily"].create_daily_info_document.return_value = None

        with pytest.raises(CashInOutMissingException):
            await svc._commit_terminal_report_async("T001", "S001", 1, "20240101", 1)

    @pytest.mark.asyncio
    async def test_tran_log_count_mismatch_raises(self):
        """tran ログ件数が一致しない場合 TransactionMissingException。"""
        svc, repos = make_service()
        repos["daily"].get_daily_info_documents.return_value = make_paginated_result(total=0)

        close_log = MagicMock()
        close_log.cash_in_out_count = 0
        close_log.cash_in_out_last_datetime = None
        close_log.cart_transaction_count = 10
        close_log.cart_transaction_last_no = 100

        repos["open_close"].get_open_close_logs.side_effect = [
            make_paginated_result(data=[MagicMock()], total=1),
            make_paginated_result(data=[close_log], total=1),
        ]
        repos["cash"].get_cash_in_out_logs.return_value = make_paginated_result(total=0)
        # tran logs count mismatch
        repos["tran"].get_tranlog_list_by_query_async.return_value = make_paginated_result(total=5)
        repos["daily"].create_daily_info_document.return_value = None

        with pytest.raises(TransactionMissingException):
            await svc._commit_terminal_report_async("T001", "S001", 1, "20240101", 1)

    @pytest.mark.asyncio
    async def test_all_logs_verified_creates_daily_info(self):
        """全ログが一致すれば daily_info を verified=True で作成。"""
        svc, repos = make_service()
        repos["daily"].get_daily_info_documents.return_value = make_paginated_result(total=0)

        close_log = MagicMock()
        close_log.cash_in_out_count = 2
        close_log.cash_in_out_last_datetime = "2024-01-01T12:00:00"
        close_log.cart_transaction_count = 5
        close_log.cart_transaction_last_no = 105

        repos["open_close"].get_open_close_logs.side_effect = [
            make_paginated_result(data=[MagicMock()], total=1),
            make_paginated_result(data=[close_log], total=1),
        ]

        cash_log = MagicMock()
        cash_log.generate_date_time = "2024-01-01T12:00:00"
        repos["cash"].get_cash_in_out_logs.return_value = make_paginated_result(data=[cash_log], total=2)

        tran_log = MagicMock()
        tran_log.transaction_no = 105
        repos["tran"].get_tranlog_list_by_query_async.return_value = make_paginated_result(data=[tran_log], total=5)
        repos["daily"].create_daily_info_document.return_value = None

        await svc._commit_terminal_report_async("T001", "S001", 1, "20240101", 1)

        repos["daily"].create_daily_info_document.assert_called_once()
