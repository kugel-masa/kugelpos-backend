"""The republish job re-sends only what the broker has not taken, and warns once (issue #230).

It used to republish every tranlog not yet ``delivered``, every 5 minutes for 24
hours. Each copy was redelivered on its own, so a tranlog a consumer could not
process was multiplied on the topic. Past 15 minutes it was also marked
``failed`` and warned about on every run, and the republish that followed set
the status back to ``published``.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.documents.tranlog_delivery_status_document import TranlogDeliveryStatus
from tests.unit.test_tran_service import _make_tran_service


def _utc_naive(minutes_ago: float) -> datetime:
    """A time as MongoDB returns it: naive UTC."""
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).replace(tzinfo=None)


def _status(status: str, minutes_old: int, warning_sent_at=None, **fields) -> TranlogDeliveryStatus:
    created = _utc_naive(minutes_old)
    return TranlogDeliveryStatus(
        event_id=f"evt-{status}-{minutes_old}",
        published_at=created,
        created_at=created,
        status=status,
        tenant_id="T1",
        store_code="S1",
        terminal_no=1,
        transaction_no=1,
        business_date="20261022",
        open_counter=1,
        payload={"event_id": f"evt-{status}-{minutes_old}"},
        services=[TranlogDeliveryStatus.ServiceStatus(service_name="journal", status="pending")],
        last_updated_at=created,
        warning_sent_at=warning_sent_at,
        **fields,
    )


async def _run(*statuses, read_up_to=None, claimed=True):
    svc = _make_tran_service()
    repo = svc.tranlog_delivery_status_repo
    repo.find_pending_deliveries = AsyncMock(return_value=list(statuses))
    repo.update_delivery_status = AsyncMock(return_value=True)
    repo.mark_warning_sent = AsyncMock(return_value=True)
    repo.mark_handed_off = AsyncMock(return_value=True)
    repo.find_latest_received_published_at = AsyncMock(return_value=read_up_to)
    repo.claim_republish = AsyncMock(return_value=claimed)
    repo.mark_republished = AsyncMock(return_value=True)
    with patch("app.services.tran_service.send_warning_notification", new_callable=AsyncMock) as warn:
        await svc.republish_undelivered_tranlog_async()
    return svc, repo, warn


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "publish_failed"])
@pytest.mark.parametrize("minutes_old", [10, 180])
async def test_a_tranlog_the_broker_has_not_taken_is_republished(status, minutes_old):
    svc, _, _ = await _run(_status(status, minutes_old))

    svc.pubsub_manager.publish_message_async.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["published", "partially_delivered", "failed"])
@pytest.mark.parametrize("minutes_old", [10, 180])
async def test_a_tranlog_the_broker_has_taken_is_not_republished(status, minutes_old):
    svc, _, _ = await _run(_status(status, minutes_old))

    svc.pubsub_manager.publish_message_async.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "published"])
async def test_an_old_undelivered_tranlog_is_warned_about_once(status):
    _, repo, warn = await _run(_status(status, 180))

    warn.assert_awaited_once()
    repo.mark_warning_sent.assert_awaited_once_with(event_id=f"evt-{status}-180")


@pytest.mark.asyncio
async def test_a_tranlog_already_warned_about_is_not_warned_about_again():
    _, repo, warn = await _run(_status("published", 180, warning_sent_at=datetime.now()))

    warn.assert_not_awaited()
    repo.mark_warning_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_tranlog_not_handed_off_is_still_republished_after_its_warning():
    svc, _, warn = await _run(_status("publish_failed", 180, warning_sent_at=datetime.now()))

    warn.assert_not_awaited()
    svc.pubsub_manager.publish_message_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_status_of_an_old_tranlog_is_not_overwritten_with_failed():
    _, repo, _ = await _run(_status("published", 180))

    assert not any(call.kwargs.get("status") == "failed" for call in repo.update_delivery_status.await_args_list)


@pytest.mark.asyncio
async def test_a_publish_the_broker_takes_records_the_hand_off():
    svc = _make_tran_service()
    svc.tranlog_delivery_status_repo.mark_handed_off = AsyncMock(return_value=True)

    await svc._publish_tranlog_async({"event_id": "evt-1"})

    svc.tranlog_delivery_status_repo.mark_handed_off.assert_awaited_once_with(event_id="evt-1")


@pytest.mark.asyncio
async def test_a_publish_the_broker_refuses_is_recorded_as_publish_failed():
    svc = _make_tran_service()
    svc.pubsub_manager.publish_message_async = AsyncMock(return_value=(False, "broker down"))
    svc.tranlog_delivery_status_repo.update_delivery_status = AsyncMock(return_value=True)

    await svc._publish_tranlog_async({"event_id": "evt-1"})

    svc.tranlog_delivery_status_repo.update_delivery_status.assert_awaited_once_with(
        event_id="evt-1", status="publish_failed"
    )


# ---------------------------------------------------------------------------
# A tranlog a consumer has read past is sent once more
# ---------------------------------------------------------------------------
# The broker took it, but a consumer has since acknowledged a tranlog handed off
# later and still not this one. It is most likely not in the queue: published
# before the subscriber's queue existed, or processed with the acknowledgement lost.

READ_PAST = datetime.now(timezone.utc) - timedelta(minutes=10)


def _taken(status="published", **fields):
    # Handed off 30 minutes ago, past the 15-minute wait.
    return _status(status, 30, handed_off_at=_utc_naive(30), **fields)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["published", "partially_delivered"])
async def test_a_tranlog_a_consumer_read_past_is_sent_once_more(status):
    svc, repo, _ = await _run(_taken(status), read_up_to=READ_PAST)

    svc.pubsub_manager.publish_message_async.assert_awaited_once()
    repo.mark_republished.assert_awaited_once_with(event_id=f"evt-{status}-30")
    # The status is left alone, so the every-run republish does not send it too.
    repo.update_delivery_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_consumer_that_acknowledged_nothing_later_is_left_to_the_queue():
    svc, repo, _ = await _run(_taken(), read_up_to=None)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()
    repo.claim_republish.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_consumer_that_has_not_read_this_far_is_left_to_the_queue():
    svc, _, _ = await _run(_taken(), read_up_to=datetime.now(timezone.utc) - timedelta(minutes=60))

    svc.pubsub_manager.publish_message_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_consumer_that_reported_failure_is_left_to_the_dead_letter_queue():
    status = _taken()
    status.services = [TranlogDeliveryStatus.ServiceStatus(service_name="journal", status="failed")]

    svc, _, _ = await _run(status, read_up_to=READ_PAST)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_tranlog_already_sent_once_more_is_not_sent_again():
    svc, _, _ = await _run(_taken(republished_at=_utc_naive(5)), read_up_to=READ_PAST)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_tranlog_all_consumers_failed_on_is_not_sent_once_more():
    svc, _, _ = await _run(_taken("failed"), read_up_to=READ_PAST)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_tranlog_handed_off_within_the_wait_is_not_sent_once_more():
    # Created long ago, but the broker took it only 5 minutes ago (a refused publish).
    status = _status("published", 120, handed_off_at=_utc_naive(5))

    svc, _, _ = await _run(status, read_up_to=READ_PAST)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_only_the_worker_holding_the_claim_sends_it():
    svc, repo, _ = await _run(_taken(), read_up_to=READ_PAST, claimed=False)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()
    repo.mark_republished.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_send_the_broker_refuses_is_left_for_the_next_run():
    svc = _make_tran_service()
    svc.pubsub_manager.publish_message_async = AsyncMock(return_value=(False, "down"))
    repo = svc.tranlog_delivery_status_repo
    repo.find_pending_deliveries = AsyncMock(return_value=[_taken()])
    repo.find_latest_received_published_at = AsyncMock(return_value=READ_PAST)
    repo.claim_republish = AsyncMock(return_value=True)
    repo.mark_republished = AsyncMock()
    repo.update_delivery_status = AsyncMock()
    repo.mark_warning_sent = AsyncMock()
    with patch("app.services.tran_service.send_warning_notification", new_callable=AsyncMock):
        await svc.republish_undelivered_tranlog_async()

    repo.mark_republished.assert_not_awaited()
    # Not publish_failed: the every-run republish would then send it as well.
    repo.update_delivery_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_each_consumer_position_is_looked_up_once_per_run():
    first, second = _taken(), _taken("partially_delivered")

    _, repo, _ = await _run(first, second, read_up_to=READ_PAST)

    repo.find_latest_received_published_at.assert_awaited_once()
