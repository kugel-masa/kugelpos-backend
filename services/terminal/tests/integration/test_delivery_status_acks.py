# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Service ACKs and the overall delivery status, against real MongoDB.

journal and report each acknowledge a terminal log. Each ACK updates its service,
reads the record back, and writes the overall status it derives. Should one ACK
stall between its read and its write while the other completes, the older
decision lands last and the overall status is left behind with every service
acknowledged. The republish job heals such a record before any warning, as the
stpos fork does, instead of reporting a delivered log as not acknowledged.
"""

import asyncio
import os
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from kugel_common.utils.misc import get_app_time
from motor.motor_asyncio import AsyncIOMotorClient

from app.config.settings import settings
from app.models.repositories.terminallog_delivery_status_repository import TerminallogDeliveryStatusRepository
from app.services.terminal_service import TerminalService

TENANT = "TEST_TENANT_ACKS"


@pytest_asyncio.fixture
async def db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0&directConnection=true")
    client = AsyncIOMotorClient(uri)
    database = client[f"{settings.DB_NAME_PREFIX}_{TENANT}"]
    yield database
    await client.drop_database(database.name)
    client.close()


def _service(db):
    info = MagicMock(tenant_id=TENANT, store_code="S1", terminal_no=1, business_date="20261108", open_counter=1)
    repo = TerminallogDeliveryStatusRepository(db=db, terminal_info=info)
    svc = TerminalService(
        terminal_id=f"{TENANT}-S1-1",
        terminal_info_repo=AsyncMock(),
        staff_master_repo=AsyncMock(),
        store_info_repo=AsyncMock(),
        cash_in_out_log_repo=AsyncMock(),
        open_close_log_repo=AsyncMock(),
        tran_log_repo=AsyncMock(),
        terminal_log_delivery_status_repo=repo,
    )
    svc.pubsub_manager = AsyncMock()
    svc.pubsub_manager.publish_message_async.return_value = (True, None)
    return svc, repo


async def _published_open_log(repo) -> str:
    await repo.initialize()
    event_id = str(uuid.uuid4())
    await repo.create_status_async(
        event_id=event_id,
        payload={"event_id": event_id, "event_type": "open"},
        services=[{"service_name": "journal", "status": "pending"}, {"service_name": "report", "status": "pending"}],
    )
    await repo.mark_handed_off(event_id=event_id)
    return event_id


@pytest.mark.asyncio
async def test_two_acks_at_once_leave_the_log_delivered(db):
    a, repo = _service(db)
    b, _ = _service(db)
    for _ in range(20):
        event_id = await _published_open_log(repo)

        await asyncio.gather(
            a.update_delivery_status_async(event_id, "received", "journal", None),
            b.update_delivery_status_async(event_id, "received", "report", None),
        )

        assert (await repo.find_by_event_id(event_id)).status == "delivered"


@pytest.mark.asyncio
async def test_a_log_left_behind_by_crossed_acks_is_healed_without_a_warning(db):
    """Force the crossing: A reads the record before B's ACK and derives
    "partially_delivered", then stalls; B records the second ACK and writes
    "delivered"; A's write lands last."""
    a, repo = _service(db)
    b, _ = _service(db)
    event_id = await _published_open_log(repo)

    a_has_read, b_done = asyncio.Event(), asyncio.Event()
    a_repo = a.terminal_log_delivery_status_repo
    read_back, write_overall = a_repo.find_by_event_id, a_repo.update_delivery_status

    async def a_read_back(*args, **kwargs):
        result = await read_back(*args, **kwargs)
        a_has_read.set()
        return result

    async def a_write_overall(*args, **kwargs):
        await b_done.wait()
        return await write_overall(*args, **kwargs)

    a_repo.find_by_event_id, a_repo.update_delivery_status = a_read_back, a_write_overall

    async def b_ack():
        await a_has_read.wait()
        await b.update_delivery_status_async(event_id, "received", "report", None)
        b_done.set()

    await asyncio.gather(a.update_delivery_status_async(event_id, "received", "journal", None), b_ack())
    left = await repo.find_by_event_id(event_id)
    assert left.status == "partially_delivered"
    assert all(s.status == "received" for s in left.services)

    old = get_app_time() - timedelta(hours=3)
    await db[settings.DB_COLLECTION_NAME_TERMINALLOG_DELIVERY_STATUS].update_one(
        {"event_id": event_id}, {"$set": {"created_at": old, "published_at": old, "handed_off_at": old}}
    )
    a_repo.find_by_event_id, a_repo.update_delivery_status = read_back, write_overall
    with patch("app.services.terminal_service.send_warning_notification", new_callable=AsyncMock) as warn:
        await a.republish_undelivered_terminallog_async()

    assert (await repo.find_by_event_id(event_id)).status == "delivered"
    warn.assert_not_awaited()
    a.pubsub_manager.publish_message_async.assert_not_awaited()
