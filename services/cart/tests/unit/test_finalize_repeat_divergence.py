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
            pytest.param(_tranlog(receipt_no=111142), "receipt_no", id="a different number was printed"),
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
