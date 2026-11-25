# Copyright 2026 masa@kugel
"""Terminal's side of the settlement at close (#343): asking report, and printing what it confirmed."""
import httpx
import pytest
import respx

from app.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.receipt.receipt_data_model import Page

from app.config.settings import settings
from app.exceptions import SettlementUnavailableException, TerminalCloseException
from app.models.documents.open_close_log import OpenCloseLog
from app.models.repositories.settlement_web_repository import SettlementWebRepository
from app.services.receipt_data.open_close_receipt_data import OpenCloseReceiptData

URL = f"{settings.BASE_URL_REPORT}/internal/tenants/T1/stores/S1/terminals/2/settlements"
DATA = {"settlementId": "sid", "expectedCash": {"total": 1}, "missingCount": 0}


def _repo():
    return SettlementWebRepository(tenant_id="T1", store_code="S1", terminal_no=2)


@pytest.mark.asyncio
@respx.mock
async def test_report_answers_and_the_service_token_is_sent():
    route = respx.post(URL).mock(return_value=httpx.Response(200, json={"success": True, "data": DATA}))

    assert await _repo().confirm_async({"businessCounter": 1}) == DATA
    assert route.calls.last.request.headers["Authorization"].startswith("Bearer ")


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("status", [500, 503, 404, 401, 403])
async def test_report_failures_leave_the_terminal_open(status):
    respx.post(URL).mock(return_value=httpx.Response(status, json={"success": False}))

    with pytest.raises(SettlementUnavailableException):
        await _repo().confirm_async({"businessCounter": 1})


@pytest.mark.asyncio
@respx.mock
async def test_report_unreachable_leaves_the_terminal_open():
    respx.post(URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(SettlementUnavailableException):
        await _repo().confirm_async({"businessCounter": 1})


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("status", [400, 422])
async def test_a_malformed_request_is_terminals_fault(status):
    respx.post(URL).mock(return_value=httpx.Response(status, json={"success": False}))

    with pytest.raises(TerminalCloseException):
        await _repo().confirm_async({"businessCounter": 1})


def _close_lines(**settlement) -> list[str]:
    log = OpenCloseLog(
        tenant_id="T1", store_code="S1", terminal_no=2, operation="close",
        terminal_info=TerminalInfoDocument(physical_amount=9500), **settlement,
    )
    page = Page()
    OpenCloseReceiptData(name="close", width=32)._make_close_receipt_body(log, page)
    return [str(line) for line in page.lines]


def test_the_close_receipt_prints_the_settlement():
    lines = "\n".join(_close_lines(expected_cash=10000, difference=-500, missing_count=2, missing_cash_log_count=1))
    assert "あるべき現金" in lines and "10,000" in lines
    assert "過不足" in lines and "-500" in lines
    assert "未着の取引" in lines and "2件" in lines
    assert "未着の入出金" in lines and "1件" in lines


def test_nothing_uncounted_or_missing_is_printed():
    lines = "\n".join(_close_lines(expected_cash=10000, difference=None, missing_count=0, missing_cash_log_count=0))
    assert "あるべき現金" in lines
    assert "過不足" not in lines
    assert "未着" not in lines
