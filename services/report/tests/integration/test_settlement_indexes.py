# Copyright 2026 masa@kugel
"""The indexes settlements need, on new tenants and on existing ones (#343, R-10, R-18, SC-006)."""

import os

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper
from kugel_common.database.index_startup import ensure_declared_indexes_async

from app.config.settings import settings
from app.database import database_setup

TENANT = "T343INDEX"
SESSION_SCAN = [("tenant_id", 1), ("store_code", 1), ("business_date", 1), ("terminal_no", 1), ("business_counter", 1), ("open_counter", 1)]


@pytest_asyncio.fixture
async def db():
    database = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}")
    await database.client.drop_database(database.name)
    yield database
    await database.client.drop_database(database.name)


async def _keys(db, collection):
    return [list(i["key"]) for i in (await db[collection].index_information()).values()]


async def _assert_settlement_indexes(db):
    record = await _keys(db, settings.DB_COLLECTION_NAME_SETTLEMENT_RECORD)
    assert [("tenant_id", 1), ("store_code", 1), ("terminal_no", 1), ("business_counter", 1)] in record
    info = await db[settings.DB_COLLECTION_NAME_SETTLEMENT_RECORD].index_information()
    unique = [list(i["key"]) for i in info.values() if i.get("unique")]
    assert [("tenant_id", 1), ("store_code", 1), ("terminal_no", 1), ("business_counter", 1)] in unique
    reports = await _keys(db, settings.DB_COLLECTION_NAME_SETTLEMENT_DAILY_REPORT)
    assert [("tenant_id", 1), ("settlement_id", 1), ("report_type", 1)] in reports
    for collection in (
        settings.DB_COLLECTION_NAME_TRAN,
        settings.DB_COLLECTION_NAME_CASH_IN_OUT_LOG,
        settings.DB_COLLECTION_NAME_OPEN_CLOSE_LOG,
    ):
        assert SESSION_SCAN in await _keys(db, collection), collection
    cash = await _keys(db, settings.DB_COLLECTION_NAME_CASH_IN_OUT_LOG)
    assert [("tenant_id", 1), ("store_code", 1), ("terminal_no", 1), ("business_counter", 1)] in cash


@pytest.mark.asyncio
async def test_a_new_tenant_gets_them(db):
    await database_setup.execute(TENANT)
    await _assert_settlement_indexes(db)


@pytest.mark.asyncio
async def test_startup_ensure_adds_them_to_an_existing_tenant(db):
    # An existing tenant from before #343: its log collections exist without the new indexes.
    await db.create_collection(settings.DB_COLLECTION_NAME_TRAN)
    await db.create_collection(settings.DB_COLLECTION_NAME_CASH_IN_OUT_LOG)
    await db.create_collection(settings.DB_COLLECTION_NAME_OPEN_CLOSE_LOG)

    class _OnlyThisTenant:
        """The shared MongoDB holds other tests' tenants; walk only this one."""

        async def list_database_names(self):
            return [db.name]

    async def _client():
        return _OnlyThisTenant()

    done = await ensure_declared_indexes_async(
        service_name="report",
        db_name_prefix=os.environ.get("DB_NAME_PREFIX"),
        execute=database_setup.execute,
        client_getter=_client,
    )

    assert done == 1

    await _assert_settlement_indexes(db)
