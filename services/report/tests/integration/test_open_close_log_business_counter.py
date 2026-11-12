# Copyright 2026 masa@kugel
"""A new business's open/close log is stored even when the day and open_counter repeat.

The log was looked up, and unique, on (business_date, open_counter, operation).
open_counter restarts at 1 when a terminal is deleted and registered again, so the
new business's open log looked "already created" and was skipped. The key is now
(business_counter, operation): business_counter is carried across the
re-registration and never reused. A redelivery of the same business is still
kept once.
"""

import os

import pytest
import pytest_asyncio

from app.models.documents.open_close_log import OpenCloseLog
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository

TENANT = "OCLOGREPORT1"


@pytest_asyncio.fixture
async def repo():
    from kugel_common.database import database as db_helper

    from app.database import database_setup

    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}"
    client = await db_helper.get_client_async()
    await client.drop_database(db_name)
    await database_setup.create_open_close_log_collection(TENANT)
    db = await db_helper.get_db_async(db_name)
    try:
        yield OpenCloseLogRepository(db, TENANT)
    finally:
        await client.drop_database(db_name)


def _log(business_counter, open_counter=1, operation="open"):
    return OpenCloseLog(
        tenant_id=TENANT,
        store_code="S1",
        terminal_no=1,
        business_date="20261112",
        open_counter=open_counter,
        business_counter=business_counter,
        operation=operation,
        generate_date_time=f"2026-11-12T09:00:0{business_counter % 10}",
    )


async def _stored(repo):
    return [d["business_counter"] async for d in repo.dbcollection.find({"tenant_id": TENANT})]


@pytest.mark.asyncio
async def test_same_day_and_open_counter_in_another_business_is_stored(repo):
    await repo.create_open_close_log(_log(business_counter=7))
    await repo.create_open_close_log(_log(business_counter=8))

    assert sorted(await _stored(repo)) == [7, 8]


@pytest.mark.asyncio
async def test_a_redelivery_of_the_same_business_is_kept_once(repo):
    await repo.create_open_close_log(_log(business_counter=7))
    await repo.create_open_close_log(_log(business_counter=7))

    assert await _stored(repo) == [7]
