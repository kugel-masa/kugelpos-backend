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
from app.exceptions import (
    ReportDateException,
    ReportNotFoundException,
    ReportGenerationException,
)
from app.exceptions.report_exceptions import SessionNotSettledException



def _batches(*batches):
    """A stand-in for SettlementRecordRepository.iter_daily_reports_async."""

    def iterate(settlement_ids, report_type):
        async def gen():
            for batch in batches:
                yield batch

        return gen()

    return iterate

def make_service(report_makers=None):
    """全リポジトリをモックした ReportService を作成。
    ReportPluginManager.load_plugins をパッチして外部ファイル読み込みを回避。
    """
    tran_repo = AsyncMock()
    tran_repo.tenant_id = "T001"
    cash_repo = AsyncMock()
    open_close_repo = AsyncMock()
    settlement_repo = AsyncMock()
    terminal_repo = AsyncMock()
    for repo in (tran_repo, cash_repo, open_close_repo):
        repo.execute_pipeline.return_value = []
    settlement_repo.find_final_async.return_value = []

    makers = report_makers if report_makers is not None else {}

    with patch("app.services.report_service.ReportPluginManager") as MockPluginMgr:
        mock_mgr = MagicMock()
        mock_mgr.load_plugins.return_value = makers
        MockPluginMgr.return_value = mock_mgr
        svc = ReportService(
            tran_repository=tran_repo,
            cash_in_out_log_repository=cash_repo,
            open_close_log_repository=open_close_repo,
            terminal_info_repository=terminal_repo,
            settlement_repository=settlement_repo,
        )

    # リポジトリを直接上書き（__init__ 後に差し替え）
    svc.tran_repository = tran_repo
    svc.cash_in_out_log_repository = cash_repo
    svc.open_close_log_repository = open_close_repo
    svc.settlement_repository = settlement_repo
    svc.terminal_repository = terminal_repo
    svc.report_makers = makers

    return svc, {
        "tran": tran_repo,
        "cash": cash_repo,
        "open_close": open_close_repo,
        "settlement": settlement_repo,
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
    async def test_daily_report_with_an_unsettled_session_raises(self):
        """A session with a log but no final settlement refuses the daily report (#343)."""
        maker = make_mock_maker()
        svc, repos = make_service(report_makers={"sales": maker})
        repos["open_close"].execute_pipeline.return_value = [
            {"_id": {"terminal_no": 2, "business_counter": 7}, "business_date": "20240101", "open_counter": 1}
        ]

        with pytest.raises(SessionNotSettledException) as exc_info:
            await svc.get_report_for_store_async(
                store_code="S001", report_scope="daily", report_type="sales", business_date="20240101"
            )

        assert exc_info.value.unsettled_sessions == [
            {"terminalNo": 2, "businessCounter": 7, "businessDate": "20240101", "openCounter": 1}
        ]
        maker.generate_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_daily_report_merges_the_settled_sessions(self):
        """Every session settled: their frozen reports are merged (#343)."""
        maker = make_mock_maker()
        merged = MagicMock()
        maker.merge = MagicMock(return_value=merged)
        svc, repos = make_service(report_makers={"sales": maker})
        records = [
            MagicMock(terminal_no=t, business_counter=bc, settlement_id=f"s{t}", settled_at=f"t{t}",
                      missing_count=t - 1, missing_ranges=[MagicMock(first=9, last=9)] if t == 2 else [])
            for t, bc in [(1, 5), (2, 7)]
        ]
        repos["open_close"].execute_pipeline.return_value = [
            {"_id": {"terminal_no": 1, "business_counter": 5}, "business_date": "20240101", "open_counter": 1},
            {"_id": {"terminal_no": 2, "business_counter": 7}, "business_date": "20240101", "open_counter": 1},
        ]
        repos["settlement"].find_final_async.return_value = records
        repos["settlement"].iter_daily_reports_async = _batches([{"a": 1}], [{"b": 2}])

        with patch("app.services.report_service.MERGERS", {"sales": lambda reports: {"folded": reports}}):
            result = await svc.get_report_for_store_async(
                store_code="S001", report_scope="daily", report_type="sales",
                business_date_from="20240101", business_date_to="20240131",
            )

        assert result is merged
        # Folded a batch at a time, oldest settlement first
        assert maker.merge.call_args.args[0] == [{"folded": [{"a": 1}, {"b": 2}]}]
        assert maker.merge.call_args.kwargs["terminal_no"] is None
        assert merged.missing_count == 1
        assert merged.missing_ranges == [{"terminal_no": 2, "business_date": records[1].business_date, "business_counter": 7, "first": 9, "last": 9}]
        maker.generate_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_daily_report_with_nothing_in_scope_is_the_empty_report(self):
        maker = make_mock_maker("empty")
        svc, _ = make_service(report_makers={"sales": maker})

        result = await svc.get_report_for_store_async(
            store_code="S001", report_scope="daily", report_type="sales", business_date="20240101"
        )

        assert result == "empty"

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
    async def test_daily_terminal_with_one_settled_session_is_the_frozen_report(self):
        maker = make_mock_maker()
        frozen = MagicMock()
        maker.from_saved = MagicMock(return_value=frozen)
        svc, repos = make_service(report_makers={"sales": maker})
        repos["tran"].execute_pipeline.return_value = [
            {"_id": {"terminal_no": 1, "business_counter": 5}, "business_date": "20240101", "open_counter": 1}
        ]
        repos["settlement"].find_final_async.return_value = [
            MagicMock(terminal_no=1, business_counter=5, settlement_id="s1", settled_at="t", missing_count=0, missing_ranges=[])
        ]
        repos["settlement"].iter_daily_reports_async = _batches([{"x": 1}])

        result = await svc.get_report_for_terminal_async(
            store_code="S001", terminal_no=1, report_scope="daily", report_type="sales",
            business_date="20240101", open_counter=1,
        )

        assert result is frozen
        maker.from_saved.assert_called_once_with({"x": 1})

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
# A date range given by one end (#314)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("report_type", ["sales", "payment", "item", "category", "promotion"])
@pytest.mark.parametrize(
    "bounds", [{"business_date_from": "20240101"}, {"business_date_to": "20240131"}]
)
@pytest.mark.parametrize("scope", ["store", "terminal"])
class TestHalfDateRange:
    @pytest.mark.asyncio
    async def test_a_half_range_is_refused_before_the_terminal_check_and_any_maker(self, scope, bounds, report_type):
        maker = make_mock_maker()
        svc, repos = make_service(report_makers={report_type: maker})
        call = svc.get_report_for_store_async if scope == "store" else svc.get_report_for_terminal_async
        target = {"store_code": "S001"} if scope == "store" else {"store_code": "S001", "terminal_no": 1}

        with pytest.raises(ReportDateException) as exc_info:
            await call(**target, report_scope="daily", report_type=report_type, business_date="20240115", **bounds)

        assert exc_info.value.status_code == 400
        maker.generate_report.assert_not_called()
        svc.settlement_repository.find_final_async.assert_not_awaited()
