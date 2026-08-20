# Copyright 2026 masa@kugel
"""Recovery when a concurrent finalize wins the race (issue #172).

Two identical finalizes in flight - what a POS with a short timeout produces -
end with the loser's insert rejected by the unique cart_id index. When that
rejection arrives at COMMIT rather than at the insert, the failure used to reach
the generic handler, which aborted an already-committed session; the driver's
complaint about that replaced the real error and the caller got a 500 for a
transaction that had in fact been written exactly once.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import FinalizeConflictException, InternalErrorException
from app.models.documents.cart_document import CartDocument
from app.services.tran_service import TranService
from kugel_common.enums import TransactionType
from kugel_common.exceptions import CannotCreateException, DuplicateKeyException
from kugel_common.models.documents.base_tranlog import BaseTransaction


def _make_service():
    terminal_info = MagicMock()
    terminal_info.tenant_id = "test_tenant"
    terminal_info.store_code = "S0001"
    terminal_info.terminal_no = 1
    terminal_info.staff = SimpleNamespace(id="S001", name="Staff1")

    with (
        patch("app.services.tran_service.CartStrategyManager") as strategy_mgr,
        patch("app.services.tran_service.PubsubManager"),
    ):
        strategy = MagicMock()
        receipt_strategy = MagicMock()
        receipt_strategy.name = "default"
        strategy.load_strategies.return_value = [receipt_strategy]
        strategy_mgr.return_value = strategy

        svc = TranService(
            terminal_info=terminal_info,
            terminal_counter_repo=MagicMock(),
            tranlog_repo=MagicMock(),
            tranlog_delivery_status_repo=MagicMock(),
            settings_master_repo=MagicMock(),
            payment_master_repo=MagicMock(),
            transaction_status_repo=MagicMock(),
        )

    svc.tranlog_repository.abort_transaction = AsyncMock()
    svc.tranlog_repository.set_session = MagicMock()
    svc.tranlog_delivery_status_repo.set_session = MagicMock()
    return svc


def _tranlog(cart_id="cart-172"):
    return SimpleNamespace(cart_id=cart_id, tenant_id="test_tenant", store_code="S0001")


def _cart(cart_id="cart-172"):
    """A cart carrying its finalize context, i.e. on the stateless path."""
    cart = CartDocument()
    cart.cart_id = cart_id
    cart.transaction_type = TransactionType.NormalSales.value
    cart.business_date = "20260820"
    cart.seq = 7
    cart.receipt_counter = 7
    cart.receipt_no = 111117
    cart.transaction_datetime = "2026-08-20T10:00:00"
    cart.sales = CartDocument.SalesInfo()
    cart.sales.total_amount_with_tax = 110.0
    cart.user = None
    return cart


def _persisted_winner(cart_id="cart-172"):
    """What a concurrent request already committed for the same finalize."""
    winner = BaseTransaction()
    winner.cart_id = cart_id
    winner.tenant_id = "test_tenant"
    winner.store_code = "S0001"
    winner.transaction_no = 7
    winner.receipt_no = 111117
    winner.receipt_text = "R"
    winner.journal_text = "J"
    return winner


async def _recover(svc, tranlog):
    """The private recovery, reached through its mangled name."""
    return await svc._TranService__recover_concurrent_finalize(tranlog)


class TestRecovery:
    @pytest.mark.asyncio
    async def test_returns_the_winners_tranlog(self):
        svc = _make_service()
        winner = _tranlog()
        svc.tranlog_repository.get_existing_finalize_async = AsyncMock(return_value=winner)

        assert await _recover(svc, _tranlog()) is winner

    @pytest.mark.asyncio
    async def test_returns_nothing_when_no_one_wrote_it(self):
        # Then the failure was not this race and the caller must surface it.
        svc = _make_service()
        svc.tranlog_repository.get_existing_finalize_async = AsyncMock(return_value=None)

        assert await _recover(svc, _tranlog()) is None

    @pytest.mark.asyncio
    async def test_aborts_and_drops_the_poisoned_session_first(self):
        # The lookup has to run outside the failed transaction.
        svc = _make_service()
        svc.tranlog_repository.get_existing_finalize_async = AsyncMock(return_value=None)

        await _recover(svc, _tranlog())

        svc.tranlog_repository.abort_transaction.assert_awaited_once()
        svc.tranlog_repository.set_session.assert_called_once_with(session=None)
        svc.tranlog_delivery_status_repo.set_session.assert_called_once_with(session=None)

    @pytest.mark.asyncio
    async def test_a_different_operation_still_conflicts(self):
        # bug_008 must not be softened into an idempotent success.
        svc = _make_service()
        svc.tranlog_repository.get_existing_finalize_async = AsyncMock(
            side_effect=FinalizeConflictException("different op", None)
        )

        with pytest.raises(FinalizeConflictException):
            await _recover(svc, _tranlog())


class TestReachedFromBothFailureShapes:
    """The race can surface at the insert or at the commit; both must recover.

    These drive create_tranlog_async itself rather than the private helper: what
    is being checked is that the exception handlers route to recovery at all, so
    a test that calls the helper directly would pass with the routing broken.
    """

    def _armed(self, failure, winner):
        """A service whose finalize fails with `failure` while `winner` is persisted."""
        svc = _make_service()
        svc.tranlog_delivery_status_repo.create_status_async = AsyncMock()
        svc.tranlog_repository.start_transaction = AsyncMock(return_value=MagicMock())
        svc.tranlog_repository.create_tranlog_async = AsyncMock(side_effect=failure)
        svc.tranlog_repository.commit_transaction = AsyncMock()
        svc.tranlog_repository.get_existing_finalize_async = AsyncMock(return_value=winner)
        svc._get_setting_value_async = AsyncMock(return_value=None)
        svc._publish_tranlog_async = AsyncMock()
        svc.receipt_data_strategy = MagicMock()
        svc.receipt_data_strategy.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
        return svc

    @pytest.mark.asyncio
    async def test_duplicate_at_insert(self):
        winner = _persisted_winner()
        svc = self._armed(DuplicateKeyException("dup", "log_tran", {}, None), winner)
        cart = _cart()

        result = await svc.create_tranlog_async(cart)

        assert result is winner
        assert cart.receipt_no == winner.receipt_no  # the response is built from the cart
        svc._publish_tranlog_async.assert_not_awaited()  # the winner already published

    @pytest.mark.asyncio
    async def test_failure_at_commit(self):
        # The duplicate arrives wrapped (CannotCreateException, "Failed to save
        # document to database"), which is why it used to reach the generic
        # handler and become a 500.
        winner = _persisted_winner()
        svc = self._armed(CannotCreateException("wrapped duplicate", "log_tran", {}, None), winner)
        cart = _cart()

        result = await svc.create_tranlog_async(cart)

        assert result is winner
        assert cart.receipt_no == winner.receipt_no
        svc._publish_tranlog_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_failure_with_nothing_persisted_still_fails(self):
        # Recovery must not turn an unrelated failure into a success.
        svc = self._armed(RuntimeError("disk on fire"), winner=None)

        with pytest.raises(InternalErrorException):
            await svc.create_tranlog_async(_cart())
