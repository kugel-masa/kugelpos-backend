# Copyright 2026 masa@kugel
"""The open/close log is written without relying on E11000, keyed on business_counter.

Open and close write the log inside a transaction. MongoDB aborts a transaction on
E11000, so the previous replace-on-duplicate "recovery" always failed (code 251).
The log is now inserted only if absent: the same business written again overwrites
its own log, and a different business holding the same business_counter is refused
rather than overwritten.
"""

import os

import pytest
import pytest_asyncio
from kugel_common.exceptions import CannotCreateException

from app.models.documents.open_close_log import OpenCloseLog
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository

TENANT = "OCLOGW1"


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


def _log(business_counter=7, business_date="20261112", open_counter=1, operation="open", amount=1000.0):
    return OpenCloseLog(
        tenant_id=TENANT,
        store_code="S1",
        terminal_no=1,
        business_date=business_date,
        open_counter=open_counter,
        business_counter=business_counter,
        operation=operation,
        generate_date_time="2026-11-12T09:00:00",
        terminal_info=None,
    )


async def _count(repo):
    return await repo.dbcollection.count_documents({"tenant_id": TENANT})


@pytest.mark.asyncio
async def test_a_new_business_is_inserted(repo):
    await repo.create_open_close_log(_log())

    assert await _count(repo) == 1


@pytest.mark.asyncio
async def test_the_same_business_again_inside_a_transaction_commits(repo):
    await repo.create_open_close_log(_log())

    async with await repo.start_transaction():
        await repo.create_open_close_log(_log())
        await repo.commit_transaction()

    assert await _count(repo) == 1


@pytest.mark.asyncio
async def test_a_different_business_with_the_same_counter_is_refused_not_overwritten(repo):
    await repo.create_open_close_log(_log(business_date="20261111", open_counter=3))

    with pytest.raises(CannotCreateException):
        await repo.create_open_close_log(_log(business_date="20261112", open_counter=1))

    stored = await repo.dbcollection.find_one({"tenant_id": TENANT})
    assert (stored["business_date"], stored["open_counter"]) == ("20261111", 3)


@pytest.mark.asyncio
async def test_the_same_day_and_open_counter_in_another_business_is_stored(repo):
    # A terminal registered again restarts open_counter; its business_counter does not.
    await repo.create_open_close_log(_log(business_counter=7, open_counter=1))
    await repo.create_open_close_log(_log(business_counter=8, open_counter=1))

    assert await _count(repo) == 2
