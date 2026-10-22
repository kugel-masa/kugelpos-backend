"""The terminal-log republish job re-sends only what the broker has not taken, and warns once (issue #230).

It used to republish every cash and open/close log not yet ``delivered``, every
5 minutes for 24 hours, adding a copy on the topic each time. Past 15 minutes it
also marked the log ``failed`` and warned about it on every run, up to ~285
warnings per log, and the republish that followed set the status back.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models.documents.terminallog_delivery_status_document import TerminallogDeliveryStatus
from tests.unit.test_terminal_service_logging import make_service


def _status(status: str, minutes_old: int, warning_sent_at=None, event_type="cash_in_out") -> TerminallogDeliveryStatus:
    created = datetime.now() - timedelta(minutes=minutes_old)
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
    )


async def _run(*statuses):
    svc, repos = make_service()
    svc.pubsub_manager = AsyncMock()
    svc.pubsub_manager.publish_message_async.return_value = (True, None)
    repo = repos["terminal_log_delivery_status_repo"]
    repo.find_pending_deliveries.return_value = list(statuses)
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
async def test_a_publish_the_broker_refuses_is_recorded_as_publish_failed(publish):
    svc, repos = make_service()
    svc.pubsub_manager = AsyncMock()
    svc.pubsub_manager.publish_message_async.return_value = (False, "broker down")

    await getattr(svc, publish)({"event_id": "evt-1"})

    repos["terminal_log_delivery_status_repo"].update_delivery_status.assert_awaited_once_with(
        event_id="evt-1", status="publish_failed"
    )
