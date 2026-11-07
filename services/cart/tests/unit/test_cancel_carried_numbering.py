# Copyright 2026 masa@kugel
"""A cancellation is a finalize and must be numbered like one (issue #170).

`create_tranlog_async` branches on `cart.transaction_datetime is not None`,
which the client stamps at finalize. A cancellation that carries nothing takes
the server-side counters, whose transaction_no shares the
(business_counter, transaction_no) key space with the carried per-open seq.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.exceptions import FinalizeNumberingRequiredException, SnapshotInvalidException


def _make_cart_service(stateless=True):
    """A CartService with the collaborators cancel touches mocked out."""
    from app.services.cart_service import CartService

    terminal_info = MagicMock()
    terminal_info.tenant_id = "test_tenant"
    terminal_info.store_code = "S0001"
    terminal_info.terminal_no = 1
    terminal_info.business_date = "20260101"
    terminal_info.business_counter = 1
    terminal_info.open_counter = 1
    terminal_info.staff = MagicMock(id="staff1", name="Staff One")

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
            cart_id="cart-170",
            cart_restore_log_repo=AsyncMock(),
        )

    svc._stateless = stateless
    return svc


def _arm(svc, cart_doc):
    """Point the private cache helpers at a prepared cart document."""
    svc._CartService__get_cached_cart_async = AsyncMock(return_value=cart_doc)
    svc._CartService__remove_cached_cart_async = AsyncMock()
    svc.state_manager = MagicMock()
    svc.tran_service.create_tranlog_async = AsyncMock(return_value=MagicMock())
    return svc


def _cart_doc():
    doc = MagicMock()
    doc.sales = MagicMock()
    doc.seq = 0
    doc.receipt_no = None
    doc.receipt_counter = None
    doc.transaction_datetime = None
    return doc


class TestCarriedCancel:
    @pytest.mark.asyncio
    async def test_carried_context_lands_on_the_cart_document(self):
        # Which is what puts the tranlog on the carried numbering branch.
        doc = _cart_doc()
        svc = _arm(_make_cart_service(), doc)

        await svc.cancel_transaction_async(
            seq=7, receipt_counter=7, transaction_datetime="2026-08-20T12:00:00"
        )

        assert doc.seq == 7
        assert doc.receipt_counter == 7
        # The printed number is derived when the tranlog is built, not carried
        # onto the cart document (issue #208); the counter is what lands here.
        assert doc.receipt_counter == 7
        assert doc.transaction_datetime == "2026-08-20T12:00:00"

    @pytest.mark.asyncio
    async def test_cancellation_still_writes_a_tranlog(self):
        doc = _cart_doc()
        svc = _arm(_make_cart_service(), doc)

        await svc.cancel_transaction_async(
            seq=7, receipt_counter=7, transaction_datetime="2026-08-20T12:00:00"
        )

        svc.tran_service.create_tranlog_async.assert_awaited_once_with(doc)
        assert doc.sales.is_cancelled is True


class TestFallback:
    @pytest.mark.asyncio
    async def test_no_context_leaves_the_document_untouched(self):
        # Legacy path: the server numbers it, exactly as before.
        doc = _cart_doc()
        svc = _arm(_make_cart_service(stateless=False), doc)

        await svc.cancel_transaction_async()

        assert doc.transaction_datetime is None
        assert doc.receipt_counter is None

    @pytest.mark.asyncio
    async def test_a_terminal_with_its_own_series_is_reported(self, caplog):
        # #168: the finalize will be numbered from the server-side series while
        # this terminal numbers its own, so the two can collide. The terminal
        # carries nothing, so it is reported rather than refused - a carried
        # cancel without numbering is refused instead (see TestCarriedWithoutNumbering).
        doc = _cart_doc()
        svc = _arm(_make_cart_service(stateless=False), doc)
        svc.terminal_info.receipt_counter = 42
        svc.cart_restore_log_repo = None  # audit unavailable; the log still has to say it

        with caplog.at_level("ERROR"):
            await svc.cancel_transaction_async()

        assert "server-side series" in caplog.text
        assert "issue #168" in caplog.text


class TestGuard:
    @pytest.mark.asyncio
    async def test_context_without_a_snapshot_is_rejected(self):
        # Unsigned numbers are whatever the caller typed; same rule as bill.
        svc = _arm(_make_cart_service(stateless=False), _cart_doc())

        with pytest.raises(SnapshotInvalidException):
            await svc.cancel_transaction_async(
                seq=7, receipt_counter=7, transaction_datetime="2026-08-20T12:00:00"
            )


def _healthy_signer():
    # A degraded key is let through on purpose; these tests are about the case
    # where signing works and the client simply did not carry the numbering.
    return patch("app.services.cart_service.snapshot_service.get_snapshot_signer", return_value=object())


class TestCarriedWithoutNumbering:
    """Carrying and numbering go together, on both finalize paths.

    Removing the call from either path must fail here.
    """

    @pytest.mark.asyncio
    async def test_a_carried_bill_without_numbering_is_refused(self):
        doc = _cart_doc()
        doc.balance_amount = 0
        svc = _arm(_make_cart_service(stateless=True), doc)
        svc._CartService__subtotal_async = AsyncMock(return_value=doc)
        svc._CartService__cache_cart_async = AsyncMock()

        with _healthy_signer(), pytest.raises(FinalizeNumberingRequiredException):
            await svc.bill_async()

        svc.tran_service.create_tranlog_async.assert_not_awaited()
        kwargs = svc.cart_restore_log_repo.add_record_async.await_args.kwargs
        assert kwargs["result"] == "numbering_fallback"
        assert kwargs["reject_reason"] == "snapshot_without_finalize_context"
        assert kwargs["api_path"] == "bill"

    @pytest.mark.asyncio
    async def test_a_carried_cancel_without_numbering_is_refused(self):
        doc = _cart_doc()
        svc = _arm(_make_cart_service(stateless=True), doc)

        with _healthy_signer(), pytest.raises(FinalizeNumberingRequiredException):
            await svc.cancel_transaction_async()

        svc.tran_service.create_tranlog_async.assert_not_awaited()
        svc._CartService__remove_cached_cart_async.assert_not_awaited()
        assert svc.cart_restore_log_repo.add_record_async.await_args.kwargs["api_path"] == "cancel"
