"""The republish job re-sends only what the broker has not taken, and warns once (issue #230).

It used to republish every tranlog not yet ``delivered``, every 5 minutes for 24
hours. Each copy was redelivered on its own, so a tranlog a consumer could not
process was multiplied on the topic. Past 15 minutes it was also marked
``failed`` and warned about on every run, and the republish that followed set
the status back to ``published``.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models.documents.tranlog_delivery_status_document import TranlogDeliveryStatus
from tests.unit.test_tran_service import _make_tran_service


def _status(status: str, minutes_old: int, warning_sent_at=None) -> TranlogDeliveryStatus:
    created = datetime.now() - timedelta(minutes=minutes_old)
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
    )


async def _run(*statuses):
    svc = _make_tran_service()
    repo = svc.tranlog_delivery_status_repo
    repo.find_pending_deliveries = AsyncMock(return_value=list(statuses))
    repo.update_delivery_status = AsyncMock(return_value=True)
    repo.mark_warning_sent = AsyncMock(return_value=True)
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
async def test_a_publish_the_broker_refuses_is_recorded_as_publish_failed():
    svc = _make_tran_service()
    svc.pubsub_manager.publish_message_async = AsyncMock(return_value=(False, "broker down"))
    svc.tranlog_delivery_status_repo.update_delivery_status = AsyncMock(return_value=True)

    await svc._publish_tranlog_async({"event_id": "evt-1"})

    svc.tranlog_delivery_status_repo.update_delivery_status.assert_awaited_once_with(
        event_id="evt-1", status="publish_failed"
    )
