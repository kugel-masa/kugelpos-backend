# Copyright 2026 masa@kugel
"""Carried receipt numbering (issues #166, #208).

The terminal carries a running receipt counter; the printed number is derived
from it and the configured range. Before #166, the carried path recorded
whatever number the client sent and the configured range was ignored entirely.

Since #208 the printed number is not accepted at all. The counter and the range
are sufficient, and accepting a number as well meant the request body could name
what got printed - which the signed envelope exists to prevent for the rest of
the numbering. What the client sends is a counter; what it gets is derived.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.tran_service import TranService

# Deliberately tiny range so a wrap is reachable.
START, END = "111111", "111115"


def _make_tran_service():
    terminal_info = MagicMock()
    terminal_info.tenant_id = "test_tenant"
    terminal_info.store_code = "S0001"
    terminal_info.terminal_no = 1
    terminal_info.business_date = "20260101"
    terminal_info.business_counter = 1
    terminal_info.open_counter = 1

    with (
        patch("app.services.tran_service.CartStrategyManager") as mock_strategy_mgr,
        patch("app.services.tran_service.PubsubManager") as mock_pubsub_cls,
    ):
        strategy = MagicMock()
        receipt_strategy = MagicMock()
        receipt_strategy.name = "default"
        strategy.load_strategies.return_value = [receipt_strategy]
        mock_strategy_mgr.return_value = strategy
        pubsub = MagicMock()
        pubsub.publish_message_async = AsyncMock(return_value=(True, None))
        mock_pubsub_cls.return_value = pubsub

        return TranService(
            terminal_info=terminal_info,
            terminal_counter_repo=MagicMock(),
            tranlog_repo=MagicMock(),
            tranlog_delivery_status_repo=MagicMock(),
            settings_master_repo=MagicMock(),
            payment_master_repo=MagicMock(),
            transaction_status_repo=MagicMock(),
        )


def _with_range(svc, start=START, end=END):
    svc._get_setting_value_async = AsyncMock(
        side_effect=lambda name: {"RECEIPT_NO_START_VALUE": start, "RECEIPT_NO_END_VALUE": end}.get(name)
    )
    return svc


class TestDerivation:
    @pytest.mark.asyncio
    async def test_first_transaction_prints_the_configured_start(self):
        # Before #166 this printed 1: the range was never consulted.
        svc = _with_range(_make_tran_service())
        assert await svc._carried_receipt_no_async(1) == 111111

    @pytest.mark.asyncio
    async def test_counts_up_inside_the_range(self):
        svc = _with_range(_make_tran_service())
        assert [await svc._carried_receipt_no_async(n) for n in (1, 2, 3)] == [111111, 111112, 111113]

    @pytest.mark.asyncio
    async def test_wraps_at_the_configured_end(self):
        svc = _with_range(_make_tran_service())
        assert await svc._carried_receipt_no_async(5) == 111115
        assert await svc._carried_receipt_no_async(6) == 111111

    @pytest.mark.asyncio
    async def test_settings_are_read_as_strings(self):
        # master-data /settings/{name}/value returns the value as-is.
        svc = _with_range(_make_tran_service(), start="200", end="204")
        assert await svc._carried_receipt_no_async(6) == 200


class TestTheClientDoesNotNameTheNumber:
    """The counter decides; a named number has nowhere to enter (issue #208)."""

    @pytest.mark.asyncio
    async def test_the_derivation_takes_the_counter_and_nothing_else(self):
        # The signature is the guarantee: no argument is left through which a
        # request body could name the printed number.
        import inspect

        params = list(inspect.signature(TranService._carried_receipt_no_async).parameters)

        assert params == ["self", "receipt_counter"], f"a second input reappeared: {params}"

    @pytest.mark.asyncio
    async def test_the_context_schema_has_no_printed_number(self):
        from app.api.v1.schemas import FinalizeContext

        assert "receipt_no" not in FinalizeContext.model_fields, "the schema accepts a printed number again"

    @pytest.mark.asyncio
    async def test_a_context_naming_only_the_number_is_refused(self):
        # What a pre-#166 terminal sends. It no longer supplies a usable
        # context, and a 422 tells it so - rather than its number being
        # recorded as the one printed.
        import pydantic

        from app.api.v1.schemas import FinalizeContext

        with pytest.raises(pydantic.ValidationError):
            FinalizeContext(seq=1, receipt_no=999, transaction_datetime="2026-08-30T10:00:00")

    @pytest.mark.asyncio
    async def test_a_context_carrying_the_counter_is_accepted(self):
        from app.api.v1.schemas import FinalizeContext

        context = FinalizeContext(seq=1, receipt_counter=2, transaction_datetime="2026-08-30T10:00:00")

        assert context.receipt_counter == 2


class TestWhenTheRangeCannotBeHad:
    """No carried number to fall back on now, so the counter is recorded raw.

    Failing the sale is worse: payment has already been taken. A number that is
    visibly outside the range, said loudly, is the lesser harm.
    """

    @pytest.mark.asyncio
    async def test_a_misconfigured_range_records_the_counter(self):
        svc = _with_range(_make_tran_service(), start="999999", end="111111")
        assert await svc._carried_receipt_no_async(3) == 3

    @pytest.mark.asyncio
    async def test_a_misconfigured_range_is_reported(self, caplog):
        svc = _with_range(_make_tran_service(), start="999999", end="111111")
        with caplog.at_level("ERROR"):
            await svc._carried_receipt_no_async(3)
        assert "Cannot derive receipt_no" in caplog.text

    @pytest.mark.asyncio
    async def test_an_unavailable_range_records_the_counter_and_says_so(self, caplog):
        # The settings read is a cached master-data call; when it degrades the
        # derived number would leave the configured range entirely.
        svc = _make_tran_service()
        svc._get_setting_value_async = AsyncMock(return_value=None)
        with caplog.at_level("ERROR"):
            assert await svc._carried_receipt_no_async(3) == 3
        assert "Receipt number range unavailable" in caplog.text
        assert "outside the configured range" in caplog.text


class TestRangeResolution:
    @pytest.mark.asyncio
    async def test_reads_both_ends_from_settings(self):
        svc = _with_range(_make_tran_service())
        assert await svc._receipt_range_async() == (111111, 111115, True)

    @pytest.mark.asyncio
    async def test_unresolved_range_is_reported_as_such(self):
        import sys

        svc = _make_tran_service()
        svc._get_setting_value_async = AsyncMock(return_value=None)
        # The fallback is unbounded, and the caller is told it is a fallback.
        assert await svc._receipt_range_async() == (1, sys.maxsize, False)

    @pytest.mark.asyncio
    async def test_a_half_configured_range_counts_as_unresolved(self):
        svc = _make_tran_service()
        svc._get_setting_value_async = AsyncMock(
            side_effect=lambda name: "111111" if name == "RECEIPT_NO_START_VALUE" else None
        )
        _, _, resolved = await svc._receipt_range_async()
        assert resolved is False
