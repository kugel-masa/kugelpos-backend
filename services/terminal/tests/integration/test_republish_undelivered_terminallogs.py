"""The terminal-log republish job against real MongoDB (issue #230).

A log the broker has taken is not republished, however long it stays
undelivered; one the broker refused keeps being republished. Each raises one
warning, and its status is not overwritten.
"""

import os
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from kugel_common.utils.misc import get_app_time

from app.config.settings import settings
from app.models.repositories.terminallog_delivery_status_repository import TerminallogDeliveryStatusRepository
from app.services.terminal_service import TerminalService

TENANT = "TEST_TENANT_230"


@pytest_asyncio.fixture
async def db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0&directConnection=true")
    client = AsyncIOMotorClient(uri)
    database = client[f"{settings.DB_NAME_PREFIX}_{TENANT}"]
    yield database
    await client.drop_database(database.name)
    client.close()


def _terminal_info():
    info = MagicMock()
    info.tenant_id = TENANT
    info.store_code = "S230"
    info.terminal_no = 1
    info.business_date = "20261022"
    info.open_counter = 1
    return info


async def _service(db, publish_ok: bool):
    repo = TerminallogDeliveryStatusRepository(db=db, terminal_info=_terminal_info())
    await repo.initialize()
    svc = TerminalService(
        terminal_id=f"{TENANT}-S230-1",
        terminal_info_repo=AsyncMock(),
        staff_master_repo=AsyncMock(),
        store_info_repo=AsyncMock(),
        cash_in_out_log_repo=AsyncMock(),
        open_close_log_repo=AsyncMock(),
        tran_log_repo=AsyncMock(),
        terminal_log_delivery_status_repo=repo,
    )
    svc.pubsub_manager = AsyncMock()
    svc.pubsub_manager.publish_message_async.return_value = (publish_ok, None if publish_ok else "down")
    return svc, repo


async def _cash_in_and_age(db, svc, repo) -> str:
    """Create the delivery status as a cash in does, publish it, and age it past the warning threshold."""
    event_id = str(uuid.uuid4())
    payload = {"event_id": event_id, "event_type": "cash_in_out", "amount": 100}
    await repo.create_status_async(
        event_id=event_id, payload=payload, services=[{"service_name": "journal", "status": "pending"}]
    )
    stored = await repo.find_by_event_id(event_id)
    assert stored.status == "pending"

    await svc._publish_cash_in_out_log_async(payload)

    old = get_app_time() - timedelta(hours=3)
    await db[settings.DB_COLLECTION_NAME_TERMINALLOG_DELIVERY_STATUS].update_one(
        {"event_id": event_id}, {"$set": {"created_at": old, "published_at": old}}
    )
    return event_id


async def _republish_twice(svc):
    with patch("app.services.terminal_service.send_warning_notification", new_callable=AsyncMock) as warn:
        svc.pubsub_manager.publish_message_async.reset_mock()
        await svc.republish_undelivered_terminallog_async()
        await svc.republish_undelivered_terminallog_async()
    return warn


@pytest.mark.asyncio
async def test_a_log_the_broker_took_is_warned_about_once_and_not_republished(db):
    svc, repo = await _service(db, publish_ok=True)
    event_id = await _cash_in_and_age(db, svc, repo)

    warn = await _republish_twice(svc)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()
    assert warn.await_count == 1
    stored = await repo.find_by_event_id(event_id)
    assert stored.status == "published"
    assert stored.warning_sent_at is not None


@pytest.mark.asyncio
async def test_a_log_the_broker_refused_keeps_being_republished_and_is_warned_about_once(db):
    svc, repo = await _service(db, publish_ok=False)
    event_id = await _cash_in_and_age(db, svc, repo)
    assert (await repo.find_by_event_id(event_id)).status == "publish_failed"

    warn = await _republish_twice(svc)

    assert svc.pubsub_manager.publish_message_async.await_count == 2
    assert warn.await_count == 1
    assert (await repo.find_by_event_id(event_id)).status == "publish_failed"
