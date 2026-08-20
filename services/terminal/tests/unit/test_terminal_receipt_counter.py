# Copyright 2026 masa@kugel
"""Open-time reconcile of the running receipt counter (issue #166).

The terminal owns the counter and may advance it offline, so open reconciles
with max(). That only works because the counter is a running count: the printed
receipt number wraps at the end of its configured range, and a wrapped number
compared with max() would undo the wrap - which is the defect this covers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.enums.terminal_status import TerminalStatus
from app.exceptions import TerminalOpenException
from app.services.terminal_service import TerminalService


def _make_service():
    repos = {
        "terminal_info_repo": AsyncMock(),
        "staff_master_repo": AsyncMock(),
        "store_info_repo": AsyncMock(),
        "cash_in_out_log_repo": AsyncMock(),
        "open_close_log_repo": AsyncMock(),
        "tran_log_repo": AsyncMock(),
        "terminal_log_delivery_status_repo": AsyncMock(),
    }
    return TerminalService(terminal_id="TID-001", **repos), repos


def _make_terminal(**counters):
    """An idle terminal whose counters are real integers, not mock attributes."""
    staff = MagicMock()
    staff.id = "STAFF-01"
    staff.name = "Test Staff"
    terminal = MagicMock()
    terminal.terminal_id = "TID-001"
    terminal.tenant_id = "TENANT-01"
    terminal.store_code = "S001"
    terminal.terminal_no = 1
    terminal.status = TerminalStatus.Idle.value
    terminal.staff = staff
    terminal.business_date = "20260319"
    terminal.open_counter = 0
    terminal.business_counter = 0
    terminal.initial_amount = 0
    terminal.physical_amount = None
    terminal.api_key = "dummy-key"
    terminal.receipt_no = counters.get("receipt_no")
    terminal.receipt_counter = counters.get("receipt_counter")
    terminal.model_copy.return_value = MagicMock(api_key="****")
    terminal.model_dump.return_value = {"tenant_id": "TENANT-01"}
    return terminal


async def _open(svc, repos, terminal, **carried):
    """Drive open_terminal_async with everything around the reconcile mocked out."""
    repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = terminal
    store = MagicMock()
    store.store_name = "Test Store"
    repos["store_info_repo"].get_store_info_async.return_value = store

    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    repos["open_close_log_repo"].start_transaction.return_value = ctx

    svc.pubsub_manager = AsyncMock()
    svc.pubsub_manager.publish_message_async.return_value = (True, None)

    with patch("app.services.terminal_service.OpenCloseReceiptData") as oc, patch(
        "app.services.terminal_service.CashInOutReceiptData"
    ) as cash:
        for cls_mock in (oc, cash):
            inst = MagicMock()
            inst.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
            cls_mock.return_value = inst
        await svc.open_terminal_async(initial_amout=10000, **carried)
    return terminal


class TestSeeding:
    @pytest.mark.asyncio
    async def test_first_open_seeds_zero(self):
        svc, repos = _make_service()
        terminal = await _open(svc, repos, _make_terminal())
        # Nothing counted yet; the client's first finalize becomes counter 1,
        # which it maps to RECEIPT_NO_START_VALUE.
        assert terminal.receipt_counter == 0

    @pytest.mark.asyncio
    async def test_pre_166_stored_value_is_read_as_the_counter(self):
        # Existing stored values are already running counts: those clients
        # counted 1, 2, 3 with no wrap. Migration is a read, not a conversion.
        svc, repos = _make_service()
        terminal = await _open(svc, repos, _make_terminal(receipt_no=42))
        assert terminal.receipt_counter == 42

    @pytest.mark.asyncio
    async def test_legacy_field_is_kept_in_step(self):
        svc, repos = _make_service()
        terminal = await _open(svc, repos, _make_terminal(receipt_counter=7), client_receipt_counter=9)
        assert terminal.receipt_counter == 9
        assert terminal.receipt_no == 9


class TestReconcile:
    @pytest.mark.asyncio
    async def test_offline_advance_is_adopted(self):
        svc, repos = _make_service()
        terminal = await _open(svc, repos, _make_terminal(receipt_counter=10), client_receipt_counter=17)
        assert terminal.receipt_counter == 17

    @pytest.mark.asyncio
    async def test_stale_client_value_does_not_walk_the_counter_back(self):
        # Walking it back would reissue numbers already printed.
        svc, repos = _make_service()
        terminal = await _open(svc, repos, _make_terminal(receipt_counter=10), client_receipt_counter=4)
        assert terminal.receipt_counter == 10

    @pytest.mark.asyncio
    async def test_pre_166_client_sends_the_counter_under_the_old_name(self):
        svc, repos = _make_service()
        terminal = await _open(svc, repos, _make_terminal(receipt_counter=3), client_receipt_no=8)
        assert terminal.receipt_counter == 8

    @pytest.mark.asyncio
    async def test_new_field_wins_when_a_client_sends_both(self):
        svc, repos = _make_service()
        terminal = await _open(
            svc, repos, _make_terminal(receipt_counter=3), client_receipt_no=5, client_receipt_counter=9
        )
        assert terminal.receipt_counter == 9


class TestWrapSurvival:
    """The regression this issue is about."""

    @pytest.mark.asyncio
    async def test_a_wrap_is_not_undone(self):
        # Range 111111..111115: counter 5 printed 111115, counter 6 printed
        # 111111. Reconciling the counters keeps the wrap; reconciling the
        # printed numbers - max(111115, 111111) - would have thrown it away.
        svc, repos = _make_service()
        terminal = await _open(svc, repos, _make_terminal(receipt_counter=5), client_receipt_counter=6)
        assert terminal.receipt_counter == 6

    @pytest.mark.asyncio
    async def test_many_cycles_keep_advancing(self):
        svc, repos = _make_service()
        terminal = await _open(svc, repos, _make_terminal(receipt_counter=888889), client_receipt_counter=888890)
        assert terminal.receipt_counter == 888890


class TestJumpGuard:
    @pytest.mark.asyncio
    async def test_implausible_jump_is_rejected(self):
        # The reconcile is irreversible, so a malformed client must not be able
        # to burn the number space permanently.
        svc, repos = _make_service()
        with pytest.raises(TerminalOpenException):
            await _open(svc, repos, _make_terminal(receipt_counter=10), client_receipt_counter=10_000_000)

    @pytest.mark.asyncio
    async def test_offline_sized_jump_is_allowed(self):
        svc, repos = _make_service()
        terminal = await _open(svc, repos, _make_terminal(receipt_counter=10), client_receipt_counter=5_000)
        assert terminal.receipt_counter == 5_000
