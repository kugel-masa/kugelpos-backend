# Copyright 2026 masa@kugel
"""Carried receipt numbering (issue #166).

The terminal carries a running receipt counter; the printed number is derived
from it and the configured range. Before this, the carried path recorded
whatever number the client sent and the configured range was ignored entirely.
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
        assert await svc._carried_receipt_no_async(1, None) == 111111

    @pytest.mark.asyncio
    async def test_counts_up_inside_the_range(self):
        svc = _with_range(_make_tran_service())
        assert [await svc._carried_receipt_no_async(n, None) for n in (1, 2, 3)] == [111111, 111112, 111113]

    @pytest.mark.asyncio
    async def test_wraps_at_the_configured_end(self):
        svc = _with_range(_make_tran_service())
        assert await svc._carried_receipt_no_async(5, None) == 111115
        assert await svc._carried_receipt_no_async(6, None) == 111111

    @pytest.mark.asyncio
    async def test_settings_are_read_as_strings(self):
        # master-data /settings/{name}/value returns the value as-is.
        svc = _with_range(_make_tran_service(), start="200", end="204")
        assert await svc._carried_receipt_no_async(6, None) == 200


class TestCarriedValueWins:
    @pytest.mark.asyncio
    async def test_agreeing_client_value_is_kept(self):
        svc = _with_range(_make_tran_service())
        assert await svc._carried_receipt_no_async(2, 111112) == 111112

    @pytest.mark.asyncio
    async def test_disagreement_keeps_the_number_the_customer_holds(self):
        # The client printed it on paper before the backend saw the transaction,
        # so the server records that and reports the disagreement.
        svc = _with_range(_make_tran_service())
        assert await svc._carried_receipt_no_async(2, 999) == 999

    @pytest.mark.asyncio
    async def test_disagreement_is_logged(self, caplog):
        svc = _with_range(_make_tran_service())
        with caplog.at_level("WARNING"):
            await svc._carried_receipt_no_async(2, 999)
        assert "does not match the configured range" in caplog.text


class TestCompatibilityAndFailure:
    @pytest.mark.asyncio
    async def test_pre_166_client_without_a_counter_is_passed_through(self):
        svc = _with_range(_make_tran_service())
        assert await svc._carried_receipt_no_async(None, 55) == 55

    @pytest.mark.asyncio
    async def test_misconfigured_range_keeps_the_carried_number(self):
        # An inverted range must not cost the customer their receipt number.
        svc = _with_range(_make_tran_service(), start="999999", end="111111")
        assert await svc._carried_receipt_no_async(3, 77) == 77

    @pytest.mark.asyncio
    async def test_missing_settings_fall_back_to_an_unbounded_range(self):
        svc = _make_tran_service()
        svc._get_setting_value_async = AsyncMock(return_value=None)
        assert await svc._carried_receipt_no_async(3, None) == 3


class TestRangeResolution:
    @pytest.mark.asyncio
    async def test_reads_both_ends_from_settings(self):
        svc = _with_range(_make_tran_service())
        assert await svc._receipt_range_async() == (111111, 111115)

    @pytest.mark.asyncio
    async def test_defaults_when_unset(self):
        import sys

        svc = _make_tran_service()
        svc._get_setting_value_async = AsyncMock(return_value=None)
        assert await svc._receipt_range_async() == (1, sys.maxsize)
