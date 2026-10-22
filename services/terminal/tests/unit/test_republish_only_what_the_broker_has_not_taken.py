"""The terminal-log republish job re-sends only what the broker has not taken, and warns once (issue #230).

It used to republish every cash and open/close log not yet ``delivered``, every
5 minutes for 24 hours, adding a copy on the topic each time. Past 15 minutes it
also marked the log ``failed`` and warned about it on every run, up to ~285
warnings per log, and the republish that followed set the status back.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.documents.terminallog_delivery_status_document import TerminallogDeliveryStatus
from tests.unit.test_terminal_service_logging import make_service


def _utc_naive(minutes_ago: float) -> datetime:
    """A time as MongoDB returns it: naive UTC."""
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).replace(tzinfo=None)


def _status(
    status: str, minutes_old: int, warning_sent_at=None, event_type="cash_in_out", **fields
) -> TerminallogDeliveryStatus:
    created = _utc_naive(minutes_old)
    event_id = f"evt-{status}-{minutes_old}"
    return TerminallogDeliveryStatus(
        event_id=event_id,
        published_at=created,
        created_at=created,
        status=status,
        tenant_id="T1",
        store_code="S1",
        terminal_no=1,
        business_date="20261022",
        open_counter=1,
        payload={"event_id": event_id, "event_type": event_type},
        services=[TerminallogDeliveryStatus.ServiceStatus(service_name="journal", status="pending")],
        last_updated_at=created,
        warning_sent_at=warning_sent_at,
        **fields,
    )


async def _run(*statuses, read_up_to=None, claimed=True, publish_ok=True):
    svc, repos = make_service()
    svc.pubsub_manager = AsyncMock()
    svc.pubsub_manager.publish_message_async.return_value = (publish_ok, None if publish_ok else "down")
    repo = repos["terminal_log_delivery_status_repo"]
    repo.find_pending_deliveries.return_value = list(statuses)
    repo.find_latest_received_published_at.return_value = read_up_to
    repo.claim_republish.return_value = claimed
    with patch("app.services.terminal_service.send_warning_notification", new_callable=AsyncMock) as warn:
        await svc.republish_undelivered_terminallog_async()
    return svc, repo, warn


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "publish_failed"])
@pytest.mark.parametrize("minutes_old", [10, 180])
@pytest.mark.parametrize("event_type", ["cash_in_out", "open"])
async def test_a_log_the_broker_has_not_taken_is_republished(status, minutes_old, event_type):
    svc, _, _ = await _run(_status(status, minutes_old, event_type=event_type))

    svc.pubsub_manager.publish_message_async.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["published", "partially_delivered", "failed"])
@pytest.mark.parametrize("minutes_old", [10, 180])
async def test_a_log_the_broker_has_taken_is_not_republished(status, minutes_old):
    svc, _, _ = await _run(_status(status, minutes_old))

    svc.pubsub_manager.publish_message_async.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "published"])
async def test_an_old_undelivered_log_is_warned_about_once(status):
    _, repo, warn = await _run(_status(status, 180))

    warn.assert_awaited_once()
    repo.mark_warning_sent.assert_awaited_once_with(event_id=f"evt-{status}-180")


@pytest.mark.asyncio
async def test_a_log_already_warned_about_is_not_warned_about_again():
    _, repo, warn = await _run(_status("published", 180, warning_sent_at=datetime.now()))

    warn.assert_not_awaited()
    repo.mark_warning_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_status_of_an_old_log_is_not_overwritten_with_failed():
    _, repo, _ = await _run(_status("published", 180))

    assert not any(call.kwargs.get("status") == "failed" for call in repo.update_delivery_status.await_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "publish", ["_publish_cash_in_out_log_async", "_publish_open_close_log"], ids=["cashlog", "opencloselog"]
)
async def test_a_publish_the_broker_takes_records_the_hand_off(publish):
    svc, repos = make_service()
    svc.pubsub_manager = AsyncMock()
    svc.pubsub_manager.publish_message_async.return_value = (True, None)

    await getattr(svc, publish)({"event_id": "evt-1"})

    repos["terminal_log_delivery_status_repo"].mark_handed_off.assert_awaited_once_with(event_id="evt-1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "publish", ["_publish_cash_in_out_log_async", "_publish_open_close_log"], ids=["cashlog", "opencloselog"]
)
async def test_a_publish_the_broker_refuses_is_recorded_as_publish_failed(publish):
    svc, repos = make_service()
    svc.pubsub_manager = AsyncMock()
    svc.pubsub_manager.publish_message_async.return_value = (False, "broker down")

    await getattr(svc, publish)({"event_id": "evt-1"})

    repos["terminal_log_delivery_status_repo"].update_delivery_status.assert_awaited_once_with(
        event_id="evt-1", status="publish_failed"
    )


# ---------------------------------------------------------------------------
# A log a consumer has read past is sent once more
# ---------------------------------------------------------------------------
# The broker took it, but a consumer has since acknowledged a log handed off later
# and still not this one. It is most likely not in the queue: the open log is the
# first publish after a start, before the subscriber's queue may exist.

READ_PAST = datetime.now(timezone.utc) - timedelta(minutes=10)


def _taken(status="published", event_type="cash_in_out", **fields):
    # Handed off 30 minutes ago, past the 15-minute wait.
    return _status(status, 30, event_type=event_type, handed_off_at=_utc_naive(30), **fields)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_type,topic",
    [("cash_in_out", "topic-cashlog"), ("open", "topic-opencloselog"), ("close", "topic-opencloselog")],
)
async def test_a_log_a_consumer_read_past_is_sent_once_more_to_its_topic(event_type, topic):
    svc, repo, _ = await _run(_taken(event_type=event_type), read_up_to=READ_PAST)

    svc.pubsub_manager.publish_message_async.assert_awaited_once()
    assert svc.pubsub_manager.publish_message_async.await_args.kwargs["topic_name"] == topic
    repo.mark_republished.assert_awaited_once_with(event_id="evt-published-30")
    repo.update_delivery_status.assert_not_awaited()
    repo.mark_handed_off.assert_not_awaited()


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
    status.services = [TerminallogDeliveryStatus.ServiceStatus(service_name="journal", status="failed")]

    svc, _, _ = await _run(status, read_up_to=READ_PAST)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        _taken(republished_at=_utc_naive(5)),
        _taken("failed"),
        _taken(event_type="unknown"),
        _status("published", 120, handed_off_at=_utc_naive(5)),
    ],
    ids=["already-sent-once-more", "all-consumers-failed", "unknown-type", "handed-off-within-the-wait"],
)
async def test_a_log_that_does_not_qualify_is_not_sent_once_more(status):
    svc, _, _ = await _run(status, read_up_to=READ_PAST)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_only_the_worker_holding_the_claim_sends_it():
    svc, repo, _ = await _run(_taken(), read_up_to=READ_PAST, claimed=False)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()
    repo.mark_republished.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_send_the_broker_refuses_is_left_for_the_next_run():
    _, repo, _ = await _run(_taken(), read_up_to=READ_PAST, publish_ok=False)

    repo.mark_republished.assert_not_awaited()
    repo.update_delivery_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_each_consumer_position_is_looked_up_once_per_run_across_both_topics():
    _, repo, _ = await _run(_taken(), _taken("partially_delivered", event_type="open"), read_up_to=READ_PAST)

    repo.find_latest_received_published_at.assert_awaited_once()
