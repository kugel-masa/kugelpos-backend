# Copyright 2026 masa@kugel
"""Daily reports answer from the settled sessions' frozen reports (#343, US2)."""

import os
from unittest.mock import patch

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper

from app.database import database_setup
from app.dependencies.get_settlement_service import get_settlement_service_async
from app.config.settings import settings
from app.exceptions.report_exceptions import SessionNotSettledException
from kugel_common.exceptions import ServiceException
from app.models.documents.open_close_log import OpenCloseLog
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.report_service import ReportService
from app.services.settlement_service import SettlementRequest

from .test_settlement_confirm import _sale as _confirm_sale

TENANT = "T343DAILY"
STORE = "S343D"
DATE = "20261124"


@pytest_asyncio.fixture
async def db():
    database = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}")
    await database.client.drop_database(database.name)
    await database_setup.execute(TENANT)
    yield database
    await database.client.drop_database(database.name)


def _sale(terminal_no, business_counter, no, amount=1000, business_date=DATE):
    sale = _confirm_sale(no, amount=amount, business_counter=business_counter)
    sale.tenant_id = TENANT
    sale.store_code = STORE
    sale.terminal_no = terminal_no
    sale.business_date = business_date
    return sale


async def _open(db, terminal_no, business_counter, business_date=DATE):
    await OpenCloseLogRepository(db, TENANT).create_open_close_log(
        OpenCloseLog(
            tenant_id=TENANT, store_code=STORE, terminal_no=terminal_no, business_date=business_date,
            open_counter=1, business_counter=business_counter, operation="open",
            generate_date_time=f"{business_date}T09:00:00",
        )
    )


async def _settle(db, terminal_no, business_counter, business_date=DATE, seq=None):
    service = await get_settlement_service_async(TENANT)
    with patch.object(service, "_names_async", return_value={"category_names": {}, "payment_names": ({}, {})}):
        record, _ = await service.confirm_async(
            SettlementRequest(
                store_code=STORE, terminal_no=terminal_no, business_counter=business_counter,
                business_date=business_date, open_counter=1, settled_at=f"{business_date}T21:0{terminal_no}:00", seq=seq,
            )
        )
        close = OpenCloseLog(
            tenant_id=TENANT, store_code=STORE, terminal_no=terminal_no, business_date=business_date, open_counter=1,
            business_counter=business_counter, operation="close", generate_date_time=f"{business_date}T21:00:00",
            settlement_id=record.settlement_id,
        )
        await OpenCloseLogRepository(db, TENANT).create_open_close_log(close)
        await service.finalize_from_close_log_async(close)
    return record


def _service(db):
    return ReportService(
        tran_repository=TranlogRepository(db, TENANT),
        cash_in_out_log_repository=CashInOutLogRepository(db, TENANT),
        open_close_log_repository=OpenCloseLogRepository(db, TENANT),
    )


async def _terminal_daily(db, terminal_no, report_type="sales", **kwargs):
    return await _service(db).get_report_for_terminal_async(
        store_code=STORE, terminal_no=terminal_no, report_scope="daily", report_type=report_type,
        business_date=kwargs.pop("business_date", DATE), limit=100, page=1, **kwargs,
    )


async def _store_daily(db, report_type="sales", **kwargs):
    return await _service(db).get_report_for_store_async(
        store_code=STORE, report_scope="daily", report_type=report_type, limit=100, page=1, **kwargs
    )


@pytest.mark.asyncio
async def test_a_terminal_daily_is_the_frozen_report_and_ignores_late_sales(db):
    tran = TranlogRepository(db, TENANT)
    await _open(db, 1, 5)
    await tran.create_tranlog_async(_sale(1, 5, 1))
    await _settle(db, 1, 5, seq=2)

    before = await _terminal_daily(db, 1)
    # A sale of the session arrives after it was settled
    await tran.create_tranlog_async(_sale(1, 5, 2, amount=5000))
    after = await _terminal_daily(db, 1)

    assert before.sales_gross.amount == 1100
    assert after.sales_gross.amount == 1100
    assert after.missing_count == 1
    assert after.missing_ranges == [{"terminal_no": 1, "business_date": DATE, "business_counter": 5, "first": 2, "last": 2}]
    flash = await _service(db).get_report_for_terminal_async(
        store_code=STORE, terminal_no=1, report_scope="flash", report_type="sales", business_date=DATE, limit=100, page=1
    )
    assert flash.sales_gross.amount == 6600  # flash stays live


@pytest.mark.asyncio
async def test_a_store_daily_merges_every_terminal(db):
    tran = TranlogRepository(db, TENANT)
    for terminal_no, bc, amount in [(1, 5, 1000), (2, 9, 3000)]:
        await _open(db, terminal_no, bc)
        await tran.create_tranlog_async(_sale(terminal_no, bc, 1, amount=amount))
        await _settle(db, terminal_no, bc)

    sales = await _store_daily(db, business_date=DATE)
    payment = await _store_daily(db, report_type="payment", business_date=DATE)

    assert sales.sales_gross.amount == 4400
    assert sales.terminal_no is None
    assert payment.total.amount == 4400
    category = await _store_daily(db, report_type="category", business_date=DATE)
    item = await _store_daily(db, report_type="item", business_date=DATE)
    promotion = await _store_daily(db, report_type="promotion", business_date=DATE)
    # Both terminals sold one I1 of category C1: the store's rows add them up
    assert [(c.category_code, c.quantity, c.gross_amount) for c in category.categories] == [("C1", 2, 4000)]
    assert [(i.item_code, i.quantity) for c in item.categories for i in c.items] == [("I1", 2)]
    assert item.total_quantity == 2
    assert promotion.terminal_no is None and promotion.business_date == DATE


@pytest.mark.asyncio
async def test_a_store_daily_says_which_terminal_is_missing_what(db):
    """S3: business counters are per terminal, so each missing range names its terminal."""
    tran = TranlogRepository(db, TENANT)
    for terminal_no in (1, 2):
        await _open(db, terminal_no, 11)
        await tran.create_tranlog_async(_sale(terminal_no, 11, 1))
        await _settle(db, terminal_no, 11, seq=2)

    report = await _store_daily(db, business_date=DATE)

    assert report.missing_count == 2
    assert report.missing_ranges == [
        {"terminal_no": 1, "business_date": DATE, "business_counter": 11, "first": 2, "last": 2},
        {"terminal_no": 2, "business_date": DATE, "business_counter": 11, "first": 2, "last": 2},
    ]


@pytest.mark.asyncio
async def test_an_unsettled_terminal_refuses_the_store_daily(db):
    tran = TranlogRepository(db, TENANT)
    await _open(db, 1, 5)
    await tran.create_tranlog_async(_sale(1, 5, 1))
    await _settle(db, 1, 5)
    await _open(db, 2, 9)
    await tran.create_tranlog_async(_sale(2, 9, 1))

    with pytest.raises(SessionNotSettledException) as exc_info:
        await _store_daily(db, business_date=DATE)

    assert exc_info.value.unsettled_sessions == [
        {"terminalNo": 2, "businessCounter": 9, "businessDate": DATE, "openCounter": 1}
    ]


@pytest.mark.asyncio
async def test_a_provisional_settlement_is_not_settled_yet(db):
    await _open(db, 1, 5)
    service = await get_settlement_service_async(TENANT)
    with patch.object(service, "_names_async", return_value={"category_names": {}, "payment_names": ({}, {})}):
        await service.confirm_async(
            SettlementRequest(store_code=STORE, terminal_no=1, business_counter=5, business_date=DATE, open_counter=1, settled_at="t")
        )

    with pytest.raises(SessionNotSettledException):
        await _terminal_daily(db, 1)


@pytest.mark.asyncio
async def test_a_date_range_merges_settlements_and_refuses_an_unsettled_day(db):
    tran = TranlogRepository(db, TENANT)
    await _open(db, 1, 5, business_date="20261123")
    await tran.create_tranlog_async(_sale(1, 5, 1, business_date="20261123"))
    await _settle(db, 1, 5, business_date="20261123")
    await _open(db, 1, 6, business_date=DATE)
    await tran.create_tranlog_async(_sale(1, 6, 1, amount=2000, business_date=DATE))
    await _settle(db, 1, 6, business_date=DATE)

    report = await _store_daily(db, business_date_from="20261123", business_date_to=DATE)
    assert report.sales_gross.amount == 3300
    assert report.business_date is None

    await _open(db, 1, 7, business_date="20261125")
    with pytest.raises(SessionNotSettledException):
        await _store_daily(db, business_date_from="20261123", business_date_to="20261125")


@pytest.mark.asyncio
async def test_nothing_in_scope_is_the_empty_report(db):
    report = await _store_daily(db, business_date="20200101")
    assert report.sales_gross.amount == 0


@pytest.mark.asyncio
async def test_a_terminal_with_two_sessions_on_the_day(db):
    """A re-registered terminal: two sessions on one day, open counter 1 both times."""
    tran = TranlogRepository(db, TENANT)
    for bc, amount in [(5, 1000), (12, 2000)]:
        await _open(db, 1, bc)
        await tran.create_tranlog_async(_sale(1, bc, 1, amount=amount))
        await _settle(db, 1, bc)

    both = await _terminal_daily(db, 1)
    second = await _terminal_daily(db, 1, business_counter=12)

    assert both.sales_gross.amount == 3300
    assert second.sales_gross.amount == 2200


@pytest.mark.asyncio
async def test_more_sessions_than_one_batch_are_all_in_the_store_daily(db):
    """R-22: the frozen reports are read 20 at a time; 23 sessions cross a batch boundary."""
    tran = TranlogRepository(db, TENANT)
    terminals = range(1, 24)
    for terminal_no in terminals:
        await _open(db, terminal_no, 7)
        await tran.create_tranlog_async(_sale(terminal_no, 7, 1, amount=100 * terminal_no))
        await _settle(db, terminal_no, 7, seq=2)

    sales = await _store_daily(db, business_date=DATE)
    item = await _store_daily(db, report_type="item", business_date=DATE)

    assert sales.sales_gross.amount == sum(110 * t for t in terminals)
    assert sales.sales_gross.count == len(terminals)
    assert item.total_quantity == len(terminals)
    assert sales.missing_count == len(terminals)
    # In the order the sessions were settled; every terminal is named once
    assert sorted(r["terminal_no"] for r in sales.missing_ranges) == list(terminals)


@pytest.mark.asyncio
async def test_a_frozen_report_gone_missing_is_an_error_not_a_smaller_report(db):
    tran = TranlogRepository(db, TENANT)
    for terminal_no in (1, 2):
        await _open(db, terminal_no, 5)
        await tran.create_tranlog_async(_sale(terminal_no, 5, 1))
        await _settle(db, terminal_no, 5)
    await db.get_collection(settings.DB_COLLECTION_NAME_SETTLEMENT_DAILY_REPORT).delete_one(
        {"terminal_no": 2, "report_type": "sales"}
    )

    with pytest.raises(ServiceException) as exc_info:
        await _store_daily(db, business_date=DATE)

    causes, e = [], exc_info.value
    while e is not None:
        causes.append(e)
        e = e.__cause__ or getattr(e, "original_exception", None)
    assert any(isinstance(c, LookupError) for c in causes)
