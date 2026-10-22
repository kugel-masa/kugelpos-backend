"""The republish job against real MongoDB (issue #230).

A tranlog the broker has taken is not republished, however long it stays
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
from app.models.repositories.tranlog_delivery_status_repository import TranlogDeliveryStatusRepository
from app.services.tran_service import TranService

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
    info.business_counter = 1
    return info


async def _service(db, publish_ok: bool):
    repo = TranlogDeliveryStatusRepository(db=db, terminal_info=_terminal_info())
    await repo.initialize()
    with patch("app.services.tran_service.CartStrategyManager") as strategies, patch(
        "app.services.tran_service.PubsubManager"
    ) as pubsub:
        receipt = MagicMock()
        receipt.name = "default"
        strategies.return_value.load_strategies.return_value = [receipt]
        pubsub.return_value.publish_message_async = AsyncMock(return_value=(publish_ok, None if publish_ok else "down"))
        svc = TranService(
            terminal_info=_terminal_info(),
            terminal_counter_repo=MagicMock(),
            tranlog_repo=MagicMock(),
            tranlog_delivery_status_repo=repo,
            settings_master_repo=MagicMock(),
            payment_master_repo=MagicMock(),
            transaction_status_repo=MagicMock(),
        )
    return svc, repo


async def _finalize_and_age(db, svc, repo) -> str:
    """Create the delivery status as finalize does, publish it, and age it past the warning threshold."""
    event_id = str(uuid.uuid4())
    await repo.create_status_async(
        event_id=event_id,
        transaction_no=1,
        payload={"event_id": event_id},
        services=[{"service_name": "journal", "status": "pending"}],
    )
    stored = await repo.find_by_event_id(event_id)
    assert stored.status == "pending"

    await svc._publish_tranlog_async({"event_id": event_id})

    old = get_app_time() - timedelta(hours=3)
    await db[settings.DB_COLLECTION_NAME_TRAN_LOG_DELIVERY_STATUS].update_one(
        {"event_id": event_id}, {"$set": {"created_at": old, "published_at": old}}
    )
    return event_id


async def _republish_twice(svc):
    with patch("app.services.tran_service.send_warning_notification", new_callable=AsyncMock) as warn:
        svc.pubsub_manager.publish_message_async.reset_mock()
        await svc.republish_undelivered_tranlog_async()
        await svc.republish_undelivered_tranlog_async()
    return warn


@pytest.mark.asyncio
async def test_a_tranlog_the_broker_took_is_warned_about_once_and_not_republished(db):
    svc, repo = await _service(db, publish_ok=True)
    event_id = await _finalize_and_age(db, svc, repo)

    warn = await _republish_twice(svc)

    svc.pubsub_manager.publish_message_async.assert_not_awaited()
    assert warn.await_count == 1
    stored = await repo.find_by_event_id(event_id)
    assert stored.status == "published"
    assert stored.warning_sent_at is not None


@pytest.mark.asyncio
async def test_a_tranlog_the_broker_refused_keeps_being_republished_and_is_warned_about_once(db):
    svc, repo = await _service(db, publish_ok=False)
    event_id = await _finalize_and_age(db, svc, repo)
    assert (await repo.find_by_event_id(event_id)).status == "publish_failed"

    warn = await _republish_twice(svc)

    assert svc.pubsub_manager.publish_message_async.await_count == 2
    assert warn.await_count == 1
    assert (await repo.find_by_event_id(event_id)).status == "publish_failed"
