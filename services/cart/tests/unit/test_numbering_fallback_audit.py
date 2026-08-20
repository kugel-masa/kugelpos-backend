# Copyright 2026 masa@kugel
"""Detection of a finalize that falls into the other numbering series (#168).

DUAL mode keeps two independent receipt-number sources: a carried finalize
numbers from the terminal's running counter, a snapshot-less one from cart's
own counter. The branch is per transaction, so a phase 2 terminal whose snapshot
signing has degraded silently falls into the other series and can print a number
it has already issued. This is detected rather than blocked - refusing the
finalize would stop a store selling over a key misconfiguration.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_service(stateless=False, terminal_receipt_counter=None):
    from app.services.cart_service import CartService

    terminal_info = MagicMock()
    terminal_info.tenant_id = "test_tenant"
    terminal_info.store_code = "S0001"
    terminal_info.terminal_no = 1
    terminal_info.receipt_counter = terminal_receipt_counter

    with (
        patch("app.services.cart_service.CartStrategyManager") as strategy_mgr,
        patch("app.services.cart_service.PromotionMasterWebRepository"),
    ):
        strategy = MagicMock()
        strategy.load_strategies.return_value = []
        strategy_mgr.return_value = strategy

        svc = CartService(
            terminal_info=terminal_info,
            cart_repo=AsyncMock(),
            terminal_counter_repo=AsyncMock(),
            settings_master_repo=AsyncMock(),
            tax_master_repo=AsyncMock(),
            item_master_repo=AsyncMock(),
            payment_master_repo=AsyncMock(),
            store_info_repo=AsyncMock(),
            tran_service=AsyncMock(),
            cart_id="cart-168",
            cart_restore_log_repo=AsyncMock(),
        )
    svc._stateless = stateless
    return svc


async def _detect(svc, api_path="bill"):
    await svc._CartService__audit_numbering_fallback_async("cart-168", api_path)


def _signer(present):
    return patch(
        "app.services.cart_service.snapshot_service.get_snapshot_signer", return_value=object() if present else None
    )


class TestWhenItFires:
    @pytest.mark.asyncio
    async def test_terminal_with_its_own_series(self):
        svc = _make_service(terminal_receipt_counter=42)
        with _signer(present=True):
            await _detect(svc)

        svc.cart_restore_log_repo.add_record_async.assert_awaited_once()
        assert svc.cart_restore_log_repo.add_record_async.await_args.kwargs["result"] == "numbering_fallback"
        assert svc.cart_restore_log_repo.add_record_async.await_args.kwargs["reject_reason"] == "no_carried_context"

    @pytest.mark.asyncio
    async def test_degraded_signing_even_for_an_unknown_terminal(self):
        # No snapshots are issued at all, so every phase 2 client degrades - the
        # terminal's counter may not have reached this service yet.
        svc = _make_service(terminal_receipt_counter=None)
        with _signer(present=False):
            await _detect(svc)

        assert svc.cart_restore_log_repo.add_record_async.await_args.kwargs["reject_reason"] == "signing_degraded"

    @pytest.mark.asyncio
    async def test_the_api_path_reaches_the_audit(self):
        svc = _make_service(terminal_receipt_counter=7)
        with _signer(present=True):
            await _detect(svc, api_path="cancel")

        assert svc.cart_restore_log_repo.add_record_async.await_args.kwargs["api_path"] == "cancel"

    @pytest.mark.asyncio
    async def test_the_log_names_the_issue_and_the_remedy(self, caplog):
        svc = _make_service(terminal_receipt_counter=42)
        with _signer(present=True), caplog.at_level("ERROR"):
            await _detect(svc)

        assert "issue #168" in caplog.text
        assert "CART_REQUEST_SNAPSHOT_MODE=REQUIRED" in caplog.text


class TestWhenItStaysQuiet:
    @pytest.mark.asyncio
    async def test_a_phase_1_terminal_is_not_flagged(self):
        # Server-side numbering is simply how this terminal works; there is no
        # second series to collide with.
        svc = _make_service(terminal_receipt_counter=None)
        with _signer(present=True):
            await _detect(svc)

        svc.cart_restore_log_repo.add_record_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_zero_counter_alone_is_not_a_series(self):
        # Open seeds every terminal with zero, phase 1 included, so zero on its
        # own cannot mean "numbers its own receipts" - treating it that way would
        # report every legacy finalize as an incident. A phase 2 terminal sitting
        # at zero is caught by the snapshot signal instead (see below).
        svc = _make_service(terminal_receipt_counter=0)
        with _signer(present=True):
            await _detect(svc)

        svc.cart_restore_log_repo.add_record_async.assert_not_awaited()


class TestTheSnapshotSignal:
    """What a zero counter would otherwise miss."""

    @pytest.mark.asyncio
    async def test_a_snapshot_without_a_finalize_context_is_flagged(self):
        # Carrying a snapshot makes this a phase 2 client whatever its counter
        # says, so the finalize going to the server-side series is an incident.
        svc = _make_service(stateless=True, terminal_receipt_counter=0)
        with _signer(present=True):
            await _detect(svc)

        assert (
            svc.cart_restore_log_repo.add_record_async.await_args.kwargs["reject_reason"]
            == "snapshot_without_finalize_context"
        )


class TestAuditFailureIsNotFatal:
    @pytest.mark.asyncio
    async def test_a_missing_audit_repository_does_not_break_the_finalize(self, caplog):
        svc = _make_service(terminal_receipt_counter=42)
        svc.cart_restore_log_repo = None

        with _signer(present=True), caplog.at_level("ERROR"):
            await _detect(svc)  # must not raise

        assert "issue #168" in caplog.text
