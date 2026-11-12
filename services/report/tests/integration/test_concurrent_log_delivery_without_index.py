# Copyright 2026 masa@kugel
"""Concurrent deliveries of one log store it once, even before the index exists.

The writers read and then inserted. That only deduplicated while the
collection's unique index existed. A delivery that arrives before tenant setup,
or after the tenant database was dropped, makes MongoDB create the collection
with no index; concurrent deliveries all saw "not present" and all inserted.
From then on the index could never be built, so tenant setup kept failing
(#185), and the report counted the sale more than once.

Measured with the read-then-insert writers: 4 concurrent deliveries, no index,
duplicates in 100 of 100 trials. The inserted document's _id is now derived from
the natural key, and _id is unique from the moment the collection exists, so a
concurrent second insert is refused rather than stored.
"""

import asyncio
import os

import pytest
import pytest_asyncio

TENANT = "LOGRACEREPORT"
DELIVERIES = 16
TRIALS = 10


@pytest_asyncio.fixture
async def db():
    from kugel_common.database import database as db_helper

    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}"
    client = await db_helper.get_client_async()
    await client.drop_database(db_name)
    try:
        yield await db_helper.get_db_async(db_name)
    finally:
        await client.drop_database(db_name)


def _writer(kind, db, i):
    """A fresh repository and document for one delivery of log number i."""
    stamp = f"2026-11-12T09:00:00.{i:06d}"
    if kind == "tranlog":
        from kugel_common.models.documents.base_tranlog import BaseTransaction

        from app.models.repositories.tranlog_repository import TranlogRepository

        doc = BaseTransaction(
            tenant_id=TENANT, store_code="S1", terminal_no=1, cart_id=f"cart-{i}",
            business_counter=1, transaction_no=i + 1, business_date="20261112", generate_date_time=stamp,
        )
        return "log_tran", TranlogRepository(db, TENANT).create_tranlog_async(doc)
    if kind == "journal":
        from app.models.documents.jornal_document import JournalDocument
        from app.models.repositories.journal_repository import JournalRepository

        doc = JournalDocument(
            tenant_id=TENANT, store_code="S1", terminal_no=1, transaction_type=101,
            business_date="20261112", generate_date_time=stamp,
        )
        return "journal", JournalRepository(db, TENANT).create_journal_async(doc)
    if kind == "cash":
        from app.models.documents.cash_in_out_log import CashInOutLog
        from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository

        doc = CashInOutLog(
            tenant_id=TENANT, store_code="S1", terminal_no=1, business_date="20261112",
            open_counter=1, generate_date_time=stamp, amount=100.0,
        )
        return "log_cash_in_out", CashInOutLogRepository(db, TENANT).create_cash_in_out_log(doc)
    from app.models.documents.open_close_log import OpenCloseLog
    from app.models.repositories.open_close_log_repository import OpenCloseLogRepository

    doc = OpenCloseLog(
        tenant_id=TENANT, store_code="S1", terminal_no=1, business_date="20261112",
        open_counter=1, business_counter=i + 1, operation="open", generate_date_time=stamp,
    )
    return "log_open_close", OpenCloseLogRepository(db, TENANT).create_open_close_log(doc)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ("tranlog", "cash", "open_close"))
async def test_concurrent_deliveries_store_one_document_without_an_index(db, kind):
    for i in range(TRIALS):
        writers = [_writer(kind, db, i) for _ in range(DELIVERIES)]
        collection = writers[0][0]
        await db[collection].drop()  # no unique index: the window the issue is about
        results = await asyncio.gather(*(coro for _, coro in writers), return_exceptions=True)

        assert not [r for r in results if isinstance(r, Exception)], results
        assert await db[collection].count_documents({}) == 1, f"trial {i}: a delivery was stored twice"
        stored = await db[collection].find_one({})
        assert isinstance(stored["_id"], str), "stored under the id derived from its natural key"


@pytest.mark.asyncio
async def test_a_log_stored_before_the_derived_id_is_still_found(db):
    """A log stored by the old writers has a generated ObjectId; a redelivery must match it."""
    collection, coro = _writer("cash", db, 0)
    coro.close()
    _, again = _writer("cash", db, 0)
    from app.models.documents.cash_in_out_log import CashInOutLog

    legacy = CashInOutLog(
        tenant_id=TENANT, store_code="S1", terminal_no=1, business_date="20261112",
        open_counter=1, generate_date_time="2026-11-12T09:00:00.000000", amount=100.0,
    )
    await db[collection].insert_one(legacy.model_dump())

    await again

    assert await db[collection].count_documents({}) == 1
