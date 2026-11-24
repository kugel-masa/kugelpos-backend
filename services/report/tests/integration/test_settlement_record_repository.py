# Copyright 2026 masa@kugel
"""Settlement records: provisional, replaced, made final, never rewritten (#343, R-6, R-17)."""

import asyncio
import os
import uuid

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper
from kugel_common.utils.misc import get_app_time

from app.database import database_setup
from app.models.documents.settlement_record_document import STATE_FINAL, STATE_PROVISIONAL, SettlementRecordDocument
from app.models.repositories.settlement_record_repository import SettlementRecordRepository

TENANT = "T343RECORD"
STORE = "S343"


@pytest_asyncio.fixture
async def repo():
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}")
    await db.client.drop_database(db.name)
    await database_setup.create_settlement_record_collection(TENANT)
    await database_setup.create_settlement_daily_report_collection(TENANT)
    yield SettlementRecordRepository(db, TENANT)
    await db.client.drop_database(db.name)


def _record(business_counter=5, terminal_no=1, **overrides) -> SettlementRecordDocument:
    values = dict(
        tenant_id=TENANT,
        store_code=STORE,
        terminal_no=terminal_no,
        business_counter=business_counter,
        business_date="20261124",
        open_counter=1,
        settlement_id=str(uuid.uuid4()),
        settled_at="2026-11-24T21:00:00+09:00",
        recorded_at="2026-11-24T21:00:01+09:00",
        cutoff=get_app_time(),
        included_count=3,
    )
    values.update(overrides)
    return SettlementRecordDocument(**values)


REPORTS = {"sales": {"report_type": "sales", "n": 1}, "item": {"report_type": "item", "n": 2}}


@pytest.mark.asyncio
async def test_first_save_is_provisional_with_its_reports(repo):
    record = _record()
    stored = await repo.save_provisional_async(record, REPORTS)

    assert stored.state == STATE_PROVISIONAL
    got = await repo.get_async(STORE, 1, 5)
    assert got.settlement_id == record.settlement_id
    assert await repo.get_daily_reports_async([record.settlement_id], "item") == {record.settlement_id: REPORTS["item"]}


@pytest.mark.asyncio
async def test_a_provisional_record_is_replaced_with_its_reports(repo):
    first = _record(included_count=3)
    await repo.save_provisional_async(first, REPORTS)
    second = _record(included_count=4)
    await repo.save_provisional_async(second, {"sales": {"n": 9}})

    got = await repo.get_async(STORE, 1, 5)
    assert got.settlement_id == second.settlement_id
    assert got.included_count == 4
    assert await repo.get_daily_reports_async([first.settlement_id], "sales") == {}
    assert await repo.get_daily_reports_async([second.settlement_id], "sales") == {second.settlement_id: {"n": 9}}
    assert await repo.reports.count_documents({}) == 1


@pytest.mark.asyncio
async def test_finalize_needs_the_same_settlement(repo):
    record = _record()
    await repo.save_provisional_async(record, REPORTS)

    assert await repo.finalize_async(STORE, 1, 5, "another-id", "t") is False
    assert (await repo.get_async(STORE, 1, 5)).state == STATE_PROVISIONAL
    assert await repo.finalize_async(STORE, 1, 5, record.settlement_id, "t") is True
    assert (await repo.get_async(STORE, 1, 5)).state == STATE_FINAL


@pytest.mark.asyncio
async def test_a_final_record_is_never_rewritten(repo):
    record = _record(included_count=3)
    await repo.save_provisional_async(record, REPORTS)
    await repo.finalize_async(STORE, 1, 5, record.settlement_id, "t")

    returned = await repo.save_provisional_async(_record(included_count=99), {"sales": {"n": 0}})

    assert returned.settlement_id == record.settlement_id
    assert returned.state == STATE_FINAL
    got = await repo.get_async(STORE, 1, 5)
    assert got.included_count == 3
    assert await repo.get_daily_reports_async([record.settlement_id], "sales") == {record.settlement_id: REPORTS["sales"]}


@pytest.mark.asyncio
async def test_concurrent_saves_leave_one_record_and_one_set_of_reports(repo):
    records = [_record(included_count=n) for n in range(5)]
    results = await asyncio.gather(
        *(repo.save_provisional_async(r, {"sales": {"n": r.included_count}}) for r in records), return_exceptions=True
    )

    assert await repo.dbcollection.count_documents({}) == 1
    stored = await repo.get_async(STORE, 1, 5)
    assert await repo.get_daily_reports_async([stored.settlement_id], "sales") == {stored.settlement_id: {"n": stored.included_count}}
    assert await repo.reports.count_documents({}) == 1
    # Losers of a write conflict raise; the caller (terminal) retries the close.
    assert any(not isinstance(r, Exception) for r in results)


@pytest.mark.asyncio
async def test_find_final_and_list(repo):
    for bc, terminal in [(5, 1), (6, 1), (7, 2)]:
        r = _record(business_counter=bc, terminal_no=terminal)
        await repo.save_provisional_async(r, {})
        if bc != 6:
            await repo.finalize_async(STORE, terminal, bc, r.settlement_id, "t")

    finals = await repo.find_final_async(STORE, business_date="20261124")
    assert [(r.terminal_no, r.business_counter) for r in finals] == [(1, 5), (2, 7)]
    listed = await repo.list_async(STORE, limit=2, page=1)
    assert listed.metadata.total == 3
    assert [(r.terminal_no, r.business_counter) for r in listed.data] == [(1, 5), (1, 6)]
    assert (await repo.list_async(STORE, state=STATE_PROVISIONAL)).metadata.total == 1
