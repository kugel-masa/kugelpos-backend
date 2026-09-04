# Copyright 2026 masa@kugel
"""Telling a repeated finalize that repeats itself from one that does not (issue #190).

`cart_id` is the transaction identity, so a second finalize for the same cart is
answered with the transaction already recorded rather than writing another. That
is right, and #152 pins it. What the log did not say is whether the repeat
carried the SAME numbers.

It usually does — a terminal that heard nothing has not advanced. When it does
not, the terminal's running receipt counter has moved past what was recorded,
and that means one of three things: it printed a receipt whose number is in no
transaction log, it advanced without printing (a gap, which #166 allows), or a
different transaction reused the cart_id. The first is worth chasing and the
second is not, and until now both left the same single line behind.

Detection only. What the caller gets back does not change.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tran_service import TranService

pytestmark = pytest.mark.asyncio


def _make_service(audit=None):
    terminal_info = MagicMock()
    terminal_info.tenant_id = "test_tenant"
    terminal_info.store_code = "S0001"
    terminal_info.terminal_no = 1

    with (
        patch("app.services.tran_service.CartStrategyManager") as strategy_mgr,
        patch("app.services.tran_service.PubsubManager"),
    ):
        strategy = MagicMock()
        receipt_strategy = MagicMock()
        receipt_strategy.name = "default"
        strategy.load_strategies.return_value = [receipt_strategy]
        strategy_mgr.return_value = strategy

        return TranService(
            terminal_info=terminal_info,
            terminal_counter_repo=MagicMock(),
            tranlog_repo=MagicMock(),
            tranlog_delivery_status_repo=MagicMock(),
            settings_master_repo=MagicMock(),
            payment_master_repo=MagicMock(),
            transaction_status_repo=MagicMock(),
            cart_restore_log_repo=audit,
        )


def _tranlog(transaction_no=100, receipt_counter=41, receipt_no=111141, when="2026-08-22T10:30:00"):
    return SimpleNamespace(
        cart_id="cart-190",
        tenant_id="test_tenant",
        store_code="S0001",
        transaction_no=transaction_no,
        receipt_counter=receipt_counter,
        receipt_no=receipt_no,
        generate_date_time=when,
    )


def _audit():
    audit = MagicMock()
    audit.add_record_async = AsyncMock()
    return audit


async def _report(service, carried, recorded):
    await service._TranService__report_finalize_repeat_async(carried, recorded)


class TestARepeatThatRepeatsItself:
    async def test_nothing_is_recorded_for_it(self, caplog):
        # The ordinary case: the terminal heard nothing and sent the same thing
        # again. Worth a line, not worth an audit row.
        audit = _audit()
        service = _make_service(audit)
        recorded = _tranlog()

        with caplog.at_level("WARNING"):
            await _report(service, _tranlog(), recorded)

        audit.add_record_async.assert_not_awaited()
        assert any("cart-190" in r.getMessage() for r in caplog.records)

    async def test_it_is_not_reported_as_an_error(self, caplog):
        service = _make_service(_audit())

        with caplog.at_level("WARNING"):
            await _report(service, _tranlog(), _tranlog())

        assert not [r for r in caplog.records if r.levelname == "ERROR"]


class TestARepeatCarryingOtherNumbers:
    @pytest.mark.parametrize(
        "carried,field",
        [
            pytest.param(_tranlog(transaction_no=101), "transaction_no", id="the terminal counted another transaction"),
            pytest.param(_tranlog(receipt_counter=42), "receipt_counter", id="the running receipt counter moved"),
            pytest.param(
                _tranlog(when="2026-08-23T00:00:01"), "generate_date_time", id="across midnight, a different day"
            ),
        ],
    )
    async def test_the_difference_is_recorded(self, carried, field):
        audit = _audit()
        service = _make_service(audit)

        await _report(service, carried, _tranlog())

        audit.add_record_async.assert_awaited_once()
        kwargs = audit.add_record_async.await_args.kwargs
        assert kwargs["result"] == "finalize_repeat_diverged"
        assert kwargs["cart_id"] == "cart-190"
        assert kwargs["diverged"] is True
        assert field in kwargs["reject_reason"], f"the reason does not name {field}: {kwargs['reject_reason']}"

    async def test_a_number_the_server_derived_differently_is_not_the_terminal(self, caplog):
        """Same carried counter, different printed number (issue #208).

        The terminal stopped carrying the printed number; the server derives it
        from the counter and the configured range. If the range moved, or
        master-data was unreachable for one of the two attempts, the two
        derivations disagree while the terminal has not moved at all. Filing that
        as a divergence accuses the terminal of something the server did.
        """
        audit = _audit()
        service = _make_service(audit)

        with caplog.at_level("WARNING"):
            await _report(service, _tranlog(receipt_no=111142), _tranlog(receipt_no=111117))

        audit.add_record_async.assert_not_awaited()
        # Said, though: a range that moves under a live terminal is worth knowing.
        said = [r.getMessage() for r in caplog.records]
        assert any("111142" in m and "111117" in m for m in said), said

    async def test_the_reason_carries_both_values(self):
        # A reader needs what was claimed and what is recorded; either alone says
        # nothing about how far the terminal has moved.
        audit = _audit()
        service = _make_service(audit)

        await _report(service, _tranlog(receipt_counter=42), _tranlog(receipt_counter=41))

        reason = audit.add_record_async.await_args.kwargs["reject_reason"]
        assert "42" in reason and "41" in reason, reason

    async def test_it_is_reported_at_error(self, caplog):
        service = _make_service(_audit())

        with caplog.at_level("ERROR"):
            await _report(service, _tranlog(receipt_counter=42), _tranlog())

        assert [r for r in caplog.records if r.levelname == "ERROR"], "a divergence was not raised above a warning"

    async def test_every_differing_field_is_named_at_once(self):
        audit = _audit()
        service = _make_service(audit)

        await _report(service, _tranlog(transaction_no=101, receipt_counter=42), _tranlog())

        reason = audit.add_record_async.await_args.kwargs["reject_reason"]
        assert "transaction_no" in reason and "receipt_counter" in reason, reason


class TestTheNoteMustNotCostTheTransaction:
    async def test_an_audit_write_that_fails_is_swallowed(self, caplog):
        # The transaction is recorded and the caller has been answered. Losing
        # the note about it must not turn that into a failure.
        audit = _audit()
        audit.add_record_async.side_effect = RuntimeError("the audit collection is unavailable")
        service = _make_service(audit)

        with caplog.at_level("ERROR"):
            await _report(service, _tranlog(receipt_counter=42), _tranlog())

        assert any("Could not record" in r.message for r in caplog.records)

    async def test_no_audit_repository_still_logs(self, caplog):
        service = _make_service(audit=None)

        with caplog.at_level("ERROR"):
            await _report(service, _tranlog(receipt_counter=42), _tranlog())

        assert [r for r in caplog.records if r.levelname == "ERROR"]


class TestWhoDidTheNumbering:
    """Only a terminal's numbers can diverge from what was recorded.

    On the server-numbered path the numbers in hand were issued by *this* request
    from the server's own counter and clock, so a race against a concurrent
    finalize differs by construction. Measured on the running stack with two
    simultaneous bills and no snapshot: `carried 50 vs recorded 49`, timestamps
    apart by microseconds — and nothing there is a terminal that moved on.
    Filing those would bury the rows that mean something.
    """

    async def test_a_server_numbered_repeat_is_not_a_divergence(self):
        audit = _audit()
        service = _make_service(audit)

        await service._TranService__report_finalize_repeat_async(
            _tranlog(transaction_no=50, receipt_no=111160), _tranlog(transaction_no=49), client_numbered=False
        )

        audit.add_record_async.assert_not_awaited()

    async def test_a_client_numbered_repeat_still_is(self):
        audit = _audit()
        service = _make_service(audit)

        await service._TranService__report_finalize_repeat_async(
            _tranlog(transaction_no=50), _tranlog(transaction_no=49), client_numbered=True
        )

        audit.add_record_async.assert_awaited_once()


class TestTheSameInstantWrittenTwoWays:
    @pytest.mark.parametrize(
        "carried_when,recorded_when",
        [
            pytest.param("2026-08-22T10:30:00+00:00", "2026-08-22T10:30:00Z", id="Z against an explicit offset"),
            pytest.param("2026-08-22T10:30:00.000000+09:00", "2026-08-22T10:30:00+09:00", id="zero microseconds"),
        ],
    )
    async def test_it_is_not_reported_as_a_divergence(self, carried_when, recorded_when):
        # The carried value is validated as ISO-8601 and not normalised, so the
        # same moment can arrive written differently. Comparing the strings would
        # report a terminal that had not moved at all.
        audit = _audit()
        service = _make_service(audit)

        await _report(service, _tranlog(when=carried_when), _tranlog(when=recorded_when))

        audit.add_record_async.assert_not_awaited()

    async def test_a_genuinely_different_time_still_is(self):
        audit = _audit()
        service = _make_service(audit)

        await _report(service, _tranlog(when="2026-08-23T00:00:01+09:00"), _tranlog(when="2026-08-22T23:59:59+09:00"))

        audit.add_record_async.assert_awaited_once()


class TestTheConcurrentRaceReportsItToo:
    """The race can surface at the insert or at the commit, and both recover.

    Those two recoveries are separate call sites from the idempotent pre-check,
    and each has to report on its own — the e2e covers only the sequential
    repeat, where the pre-check is what answers. Driving `create_tranlog_async`
    rather than the reporter, so the routing itself is what is under test.
    """

    def _armed(self, failure, winner, audit):
        from unittest.mock import MagicMock

        service = _make_service(audit)
        service.tranlog_delivery_status_repo.create_status_async = AsyncMock()
        service.tranlog_repository.start_transaction = AsyncMock(return_value=MagicMock())
        service.tranlog_repository.create_tranlog_async = AsyncMock(side_effect=failure)
        service.tranlog_repository.commit_transaction = AsyncMock()
        service.tranlog_repository.abort_transaction = AsyncMock()
        service.tranlog_repository.set_session = MagicMock()
        service.tranlog_delivery_status_repo.set_session = MagicMock()
        service.tranlog_repository.get_existing_finalize_async = AsyncMock(return_value=winner)
        # The printed number is derived from the carried counter and this
        # range (issue #208), so the range has to resolve for the two sides
        # to be comparable at all.
        service._get_setting_value_async = AsyncMock(
            side_effect=lambda name: {"RECEIPT_NO_START_VALUE": "111111", "RECEIPT_NO_END_VALUE": "111120"}.get(name)
        )
        service._publish_tranlog_async = AsyncMock()
        service.receipt_data_strategy = MagicMock()
        service.receipt_data_strategy.make_receipt_data.return_value = MagicMock(receipt_text="R", journal_text="J")
        return service

    def _winner(self):
        from kugel_common.models.documents.base_tranlog import BaseTransaction

        winner = BaseTransaction()
        winner.cart_id = "cart-190"
        winner.tenant_id = "test_tenant"
        winner.store_code = "S0001"
        winner.transaction_no = 7
        winner.receipt_counter = 7
        winner.receipt_no = 111117  # derive_receipt_no(7, 111111, 111120)
        winner.generate_date_time = "2026-08-22T10:00:00"
        winner.receipt_text = "R"
        winner.journal_text = "J"
        return winner

    def _cart_carrying(self, counter):
        from kugel_common.enums import TransactionType

        from app.models.documents.cart_document import CartDocument

        cart = CartDocument()
        cart.cart_id = "cart-190"
        cart.transaction_type = TransactionType.NormalSales.value
        cart.business_date = "20260822"
        cart.seq = 8
        cart.receipt_counter = counter
        # No printed number: the cart carries the counter, the server derives
        # the number from it (issue #208).
        cart.transaction_datetime = "2026-08-22T10:00:07"
        cart.sales = CartDocument.SalesInfo()
        cart.sales.total_amount_with_tax = 110.0
        cart.user = None
        return cart

    @pytest.mark.parametrize(
        "failure",
        [
            pytest.param("insert", id="the unique index rejects the insert"),
            pytest.param("commit", id="the unique index rejects at commit"),
        ],
    )
    async def test_a_divergent_loser_is_recorded(self, failure):
        from kugel_common.exceptions import CannotCreateException, DuplicateKeyException

        raised = (
            DuplicateKeyException("dup", "log_tran", {}, None)
            if failure == "insert"
            else CannotCreateException("wrapped duplicate", "log_tran", {}, None)
        )
        audit = _audit()
        service = self._armed(raised, self._winner(), audit)

        await service.create_tranlog_async(self._cart_carrying(counter=9))

        audit.add_record_async.assert_awaited_once()
        assert audit.add_record_async.await_args.kwargs["result"] == "finalize_repeat_diverged"

    async def test_a_loser_carrying_the_same_numbers_is_not(self):
        from kugel_common.exceptions import DuplicateKeyException

        audit = _audit()
        winner = self._winner()
        service = self._armed(DuplicateKeyException("dup", "log_tran", {}, None), winner, audit)
        cart = self._cart_carrying(counter=winner.receipt_counter)
        cart.seq = winner.transaction_no
        cart.transaction_datetime = winner.generate_date_time

        await service.create_tranlog_async(cart)

        audit.add_record_async.assert_not_awaited()

    async def test_a_repeat_reported_before_a_failed_commit_is_not_reported_again(self, caplog):
        """The insert path can report and then fail to commit.

        That lands in the recovery, which reports again — and by then the tranlog
        in hand IS the recorded one, so the second report finds no divergence and
        says the repeat "carried the same numbers". Directly after a line saying
        it carried different ones. The audit row is not at risk (the second
        comparison is the record against itself); the contradiction in the log
        is, and that is what a reader has to work from.
        """
        audit = _audit()
        winner = self._winner()
        service = self._armed(None, winner, audit)
        # A repeat detected by the pre-check: the repository hands back the row
        # that was already there rather than raising.
        service.tranlog_repository.create_tranlog_async = AsyncMock(return_value=winner)
        service.tranlog_repository.commit_transaction = AsyncMock(side_effect=RuntimeError("commit lost"))
        service.tranlog_repository.get_existing_finalize_async = AsyncMock(return_value=winner)

        with caplog.at_level("WARNING"):
            await service.create_tranlog_async(self._cart_carrying(counter=9))

        reports = [r for r in caplog.records if "Finalize repeated" in r.getMessage()]
        assert len(reports) == 1, (
            f"the same repeat was reported {len(reports)} times: {[r.getMessage()[:60] for r in reports]}"
        )
        audit.add_record_async.assert_awaited_once()
