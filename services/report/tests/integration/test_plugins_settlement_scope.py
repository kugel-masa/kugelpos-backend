# Copyright 2026 masa@kugel
"""The report makers narrowed to one settled session (#343, R-4, R-12).

A settlement freezes the daily reports of one session. Selecting by business
date and open counter is not enough: re-registering a terminal starts its open
counter at 1 again, so two sessions can share both. And the paging the makers
apply must not cut a frozen report short.
"""

import asyncio
import os
import uuid

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper
from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.utils.misc import get_app_time

from app.database import database_setup
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.report_plugin_manager import ReportPluginManager

TENANT = "T343SCOPE"
STORE = "STORE343"
TERMINAL = 34
DATE = "2026-11-24"
NO_NAMES = {"category_names": {}, "payment_names": ({}, {})}


@pytest_asyncio.fixture
async def db():
    database = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}")
    await database.client.drop_database(database.name)
    await database_setup.create_tran_collection(TENANT)
    yield database
    await database.client.drop_database(database.name)


def _sale(amount: int, business_counter: int, transaction_no: int, category: str = "C1") -> BaseTransaction:
    tax = amount // 10
    return BaseTransaction(
        tenant_id=TENANT,
        store_code=STORE,
        terminal_no=TERMINAL,
        business_date=DATE,
        business_counter=business_counter,
        open_counter=1,
        transaction_no=transaction_no,
        transaction_type=TransactionType.NormalSales.value,
        generate_date_time=f"{DATE}T10:00:00",
        cart_id=str(uuid.uuid4()),
        sales={
            "total_amount": amount,
            "total_amount_with_tax": amount + tax,
            "tax_amount": tax,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False,
        },
        payments=[{"payment_no": 1, "payment_code": "01", "amount": amount + tax, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "10%", "tax_amount": tax, "target_amount": amount, "target_quantity": 1}],
        line_items=[
            {
                "line_no": 1,
                "item_code": f"I-{category}",
                "category_code": category,
                "quantity": 1,
                "unit_price": amount,
                "amount": amount,
                "tax_code": "01",
            }
        ],
    )


def _makers(db):
    return ReportPluginManager().load_plugins(
        "report_makers",
        tran_repository=TranlogRepository(db, TENANT),
        cash_in_out_log_repository=CashInOutLogRepository(db, TENANT),
        open_close_log_repository=OpenCloseLogRepository(db, TENANT),
    )


async def _daily(db, report_type, **scope):
    return await _makers(db)[report_type].generate_report(
        store_code=STORE,
        terminal_no=TERMINAL,
        business_counter=None,
        business_date=DATE,
        open_counter=1,
        report_scope="daily",
        report_type=report_type,
        limit=100,
        page=1,
        sort=None,
        **NO_NAMES,
        **scope,
    )


@pytest.mark.asyncio
async def test_business_counter_keeps_a_re_registered_terminals_sessions_apart(db):
    repo = TranlogRepository(db, TENANT)
    # Same date, same open counter 1: the terminal was registered again in between.
    await repo.create_tranlog_async(_sale(1000, business_counter=7, transaction_no=1))
    await repo.create_tranlog_async(_sale(5000, business_counter=8, transaction_no=1))

    unscoped = await _daily(db, "sales")
    scoped = await _daily(db, "sales", extra_match={"business_counter": 8})

    # Gross sales include tax.
    assert unscoped.sales_gross.amount == 6600
    assert scoped.sales_gross.amount == 5500
    assert scoped.sales_gross.count == 1
    for report_type in ("category", "item", "payment", "promotion"):
        report = await _daily(db, report_type, extra_match={"business_counter": 8})
        assert report is not None


@pytest.mark.asyncio
async def test_cutoff_leaves_out_what_arrived_after_it(db):
    repo = TranlogRepository(db, TENANT)
    await repo.create_tranlog_async(_sale(1000, business_counter=7, transaction_no=1))
    cutoff = get_app_time()
    # Stored datetimes have millisecond precision; a log in the same millisecond
    # as the cutoff counts as arrived before it - in every query alike.
    await asyncio.sleep(0.01)
    await repo.create_tranlog_async(_sale(2000, business_counter=7, transaction_no=2))

    scoped = await _daily(
        db, "sales", extra_match={"business_counter": 7, "created_at": {"$not": {"$gt": cutoff}}}
    )

    assert scoped.sales_gross.amount == 1100


@pytest.mark.asyncio
async def test_unbounded_keeps_every_category(db):
    repo = TranlogRepository(db, TENANT)
    for n in range(1, 121):
        await repo.create_tranlog_async(_sale(100, business_counter=7, transaction_no=n, category=f"C{n:03d}"))

    paged = await _daily(db, "category", extra_match={"business_counter": 7})
    whole = await _daily(db, "category", extra_match={"business_counter": 7}, unbounded=True)

    assert len(paged.categories) == 100
    assert len(whole.categories) == 120
