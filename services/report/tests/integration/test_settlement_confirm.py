# Copyright 2026 masa@kugel
"""Confirming a session's settlement (#343, R-2, R-4, R-6, R-12, R-15)."""

import asyncio
import os
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper
from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction

from app.database import database_setup
from app.dependencies.get_settlement_service import get_settlement_service_async
from app.exceptions.report_exceptions import SettlementAggregationException
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.models.documents.settlement_record_document import STATE_FINAL, STATE_PROVISIONAL
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.settlement_record_repository import SettlementRecordRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.settlement_service import SettlementRequest

TENANT = "T343CONFIRM"
STORE = "S343C"
TERMINAL = 3
DATE = "20261124"
BC = 11


@pytest_asyncio.fixture
async def db():
    database = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}")
    await database.client.drop_database(database.name)
    await database_setup.execute(TENANT)
    yield database
    await database.client.drop_database(database.name)


@pytest_asyncio.fixture
async def service(db):
    svc = await get_settlement_service_async(TENANT)
    # Master-data is not running; the names fall back to codes.
    with patch.object(svc, "_names_async", return_value={"category_names": {}, "payment_names": ({}, {})}):
        yield svc


def _sale(no: int, amount: int = 1000, business_counter: int = BC, carried: bool = True, payment="01") -> BaseTransaction:
    tax = amount // 10
    return BaseTransaction(
        tenant_id=TENANT,
        store_code=STORE,
        terminal_no=TERMINAL,
        business_date=DATE,
        business_counter=business_counter,
        open_counter=1,
        transaction_no=no,
        receipt_counter=no if carried else None,
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
        payments=[{"payment_no": 1, "payment_code": payment, "amount": amount + tax, "description": "Pay"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "10%", "tax_amount": tax, "target_amount": amount, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "I1", "category_code": "C1", "quantity": 1, "unit_price": amount, "amount": amount, "tax_code": "01"}],
    )


def _cash(amount: float, n: int) -> CashInOutLog:
    return CashInOutLog(
        tenant_id=TENANT,
        store_code=STORE,
        terminal_no=TERMINAL,
        business_date=DATE,
        open_counter=1,
        business_counter=BC,
        generate_date_time=f"{DATE}T09:00:0{n}",
        amount=amount,
    )


def _request(**overrides) -> SettlementRequest:
    values = dict(
        store_code=STORE,
        terminal_no=TERMINAL,
        business_counter=BC,
        business_date=DATE,
        open_counter=1,
        settled_at=f"{DATE}T21:00:00",
    )
    values.update(overrides)
    return SettlementRequest(**values)


async def _seed(db, sales=(1, 2), cash=(10000, 500)):
    tran = TranlogRepository(db, TENANT)
    for no in sales:
        await tran.create_tranlog_async(_sale(no))
    cash_repo = CashInOutLogRepository(db, TENANT)
    for n, amount in enumerate(cash):
        await cash_repo.create_cash_in_out_log(_cash(amount, n))


@pytest.mark.asyncio
async def test_confirm_records_the_figures_and_freezes_five_reports(db, service):
    await _seed(db)

    record, created = await service.confirm_async(_request(seq=3, cash_log_count=2, physical_amount=12700))

    assert created is True
    assert record.state == STATE_PROVISIONAL
    assert record.included_count == 2
    assert [r.model_dump() for r in record.included_ranges] == [{"first": 1, "last": 2}]
    assert record.missing_count == 1
    assert [r.model_dump() for r in record.missing_ranges] == [{"first": 3, "last": 3}]
    assert record.cash_log_count == 2 and record.missing_cash_log_count == 0
    # Two cash sales of 1,100 plus the float 10,000 and a cash-in of 500
    assert record.expected_cash.cash_sales == 2200
    assert record.expected_cash.total == 12700
    assert record.difference == 0

    repo = SettlementRecordRepository(db, TENANT)
    for report_type in ("sales", "category", "item", "payment", "promotion"):
        reports = await repo.get_daily_reports_async([record.settlement_id], report_type)
        assert record.settlement_id in reports, report_type
    sales = (await repo.get_daily_reports_async([record.settlement_id], "sales"))[record.settlement_id]
    # The frozen sales report's cash is the settlement's (SC-005), and printed so
    assert sales["cash"]["logical_amount"] == record.expected_cash.total
    assert sales["cash"]["physical_amount"] == 12700
    assert sales["cash"]["difference_amount"] == 0
    assert "12,700" in sales["receipt_text"]


@pytest.mark.asyncio
async def test_without_seq_only_gaps_count_and_uncounted_has_no_difference(db, service):
    await _seed(db, sales=(1, 3))

    record, _ = await service.confirm_async(_request(cash_log_count=3))

    assert record.declared_source == "none"
    assert [r.model_dump() for r in record.missing_ranges] == [{"first": 2, "last": 2}]
    assert record.missing_cash_log_count == 1
    assert record.physical_amount is None and record.difference is None


@pytest.mark.asyncio
async def test_server_numbered_sales_are_counted_not_analysed(db, service):
    tran = TranlogRepository(db, TENANT)
    await tran.create_tranlog_async(_sale(1))
    await tran.create_tranlog_async(_sale(1041, carried=False))

    record, _ = await service.confirm_async(_request(seq=1))

    assert record.included_count == 2
    assert record.server_numbered_count == 1
    assert record.missing_count == 0 and record.duplicate_numbers == []


@pytest.mark.asyncio
async def test_a_provisional_settlement_is_recomputed_with_later_sales(db, service):
    await _seed(db, sales=(1,))
    first, _ = await service.confirm_async(_request(seq=1))
    # The close failed after report stored it; the terminal sold again and closes again.
    await TranlogRepository(db, TENANT).create_tranlog_async(_sale(2))

    second, created = await service.confirm_async(_request(seq=2))

    assert created is True
    assert second.settlement_id != first.settlement_id
    assert second.included_count == 2


@pytest.mark.asyncio
async def test_a_final_settlement_is_returned_as_stored(db, service):
    await _seed(db, sales=(1,))
    record, _ = await service.confirm_async(_request(seq=1))
    await SettlementRecordRepository(db, TENANT).finalize_async(STORE, TERMINAL, BC, record.settlement_id, "t")
    await TranlogRepository(db, TENANT).create_tranlog_async(_sale(2))

    again, created = await service.confirm_async(_request(seq=2))

    assert created is False
    assert again.settlement_id == record.settlement_id
    assert again.included_count == 1


@pytest.mark.asyncio
async def test_close_log_finalizes_and_a_mismatched_one_recomputes(db, service):
    await _seed(db, sales=(1,))
    record, _ = await service.confirm_async(_request(seq=1))

    close = OpenCloseLog(
        tenant_id=TENANT, store_code=STORE, terminal_no=TERMINAL, business_date=DATE, open_counter=1,
        business_counter=BC, operation="close", generate_date_time=f"{DATE}T21:00:05",
        cart_transaction_last_no=1, cash_in_out_count=2, settlement_id="the-terminals-id",
    )
    await service.finalize_from_close_log_async(close)

    stored = await SettlementRecordRepository(db, TENANT).get_async(STORE, TERMINAL, BC)
    assert stored.state == STATE_FINAL
    assert stored.settlement_id == "the-terminals-id"
    assert stored.settlement_id != record.settlement_id


@pytest.mark.asyncio
async def test_a_failed_report_stores_nothing(db, service):
    await _seed(db, sales=(1,))
    item = service.report_makers["item"]
    with patch.object(item, "generate_report", side_effect=RuntimeError("boom")):
        with pytest.raises(SettlementAggregationException):
            await service.confirm_async(_request(seq=1))

    assert await SettlementRecordRepository(db, TENANT).get_async(STORE, TERMINAL, BC) is None


@pytest.mark.asyncio
async def test_a_frozen_report_over_the_size_limit_stores_nothing(db, service):
    await _seed(db, sales=(1,))
    with patch("app.services.settlement_service.MAX_DAILY_REPORT_BYTES", 10):
        with pytest.raises(SettlementAggregationException):
            await service.confirm_async(_request(seq=1))

    assert await SettlementRecordRepository(db, TENANT).get_async(STORE, TERMINAL, BC) is None


@pytest.mark.asyncio
async def test_a_sale_arriving_during_the_computation_is_in_nothing(db, service):
    """Every query reads the same cutoff (R-12)."""
    await _seed(db, sales=(1,))
    original = service._report_async
    tran = TranlogRepository(db, TENANT)

    async def arrive_midway(report_type, *args, **kwargs):
        if report_type == "category":
            await asyncio.sleep(0.01)
            await tran.create_tranlog_async(_sale(2))
        return await original(report_type, *args, **kwargs)

    with patch.object(service, "_report_async", side_effect=arrive_midway):
        record, _ = await service.confirm_async(_request(seq=1))

    repo = SettlementRecordRepository(db, TENANT)
    sales = (await repo.get_daily_reports_async([record.settlement_id], "sales"))[record.settlement_id]
    item = (await repo.get_daily_reports_async([record.settlement_id], "item"))[record.settlement_id]
    assert record.included_count == 1
    assert sales["sales_gross"]["count"] == 1
    assert item["total_quantity"] == 1


@pytest.mark.asyncio
async def test_names_unavailable_still_settles(db):
    """A slow master-data costs at most the name timeout; codes stand in (R-12)."""
    await _seed(db, sales=(1,))
    svc = await get_settlement_service_async(TENANT)

    async def never():
        await asyncio.sleep(60)

    with patch("app.services.settlement_service.NAME_FETCH_TIMEOUT_SECONDS", 0.05):
        with patch.object(svc.report_makers["category"].category_repository, "get_categories", side_effect=never):
            with patch.object(svc.report_makers["payment"], "_fetch_payment_master", side_effect=never):
                record, created = await asyncio.wait_for(svc.confirm_async(_request(seq=1)), timeout=10)

    assert created is True


@pytest.mark.asyncio
async def test_a_sale_stamped_early_but_committed_late_is_in_nothing(db, service):
    """created_at is stamped before the insert commits; a clock is no fence (R-12).

    A sale stamped a second ago lands while the reports are being frozen. The
    figures come from the documents read at the start, so it is in none of them
    - not counted as arrived, not in the cash, not in any frozen report.
    """
    from datetime import timedelta

    from kugel_common.utils.misc import get_app_time

    await _seed(db, sales=(1,))
    original = service._names_async

    async def land_midway(store_code):
        late = _sale(2).model_dump()
        late["created_at"] = get_app_time() - timedelta(seconds=1)
        await db["log_tran"].insert_one(late)
        return await original(store_code)

    with patch.object(service, "_names_async", side_effect=land_midway):
        record, _ = await service.confirm_async(_request(seq=2))

    repo = SettlementRecordRepository(db, TENANT)
    sales = (await repo.get_daily_reports_async([record.settlement_id], "sales"))[record.settlement_id]
    item = (await repo.get_daily_reports_async([record.settlement_id], "item"))[record.settlement_id]
    assert record.included_count == 1
    assert [r.model_dump() for r in record.missing_ranges] == [{"first": 2, "last": 2}]
    assert record.expected_cash.cash_sales == 1100
    assert sales["sales_gross"]["count"] == 1
    assert item["total_quantity"] == 1


@pytest.mark.asyncio
async def test_a_mismatched_close_log_that_cannot_finalize_fails_the_delivery(db, service):
    """S5: replaced again before it could be made final - the delivery must fail
    so the close log comes again, never leave the record provisional and consumed."""
    await _seed(db, sales=(1,))
    await service.confirm_async(_request(seq=1))
    close = OpenCloseLog(
        tenant_id=TENANT, store_code=STORE, terminal_no=TERMINAL, business_date=DATE, open_counter=1,
        business_counter=BC, operation="close", generate_date_time=f"{DATE}T21:00:05", settlement_id="the-terminals-id",
    )

    with patch.object(service.settlement_repository, "finalize_async", return_value=False):
        with pytest.raises(RuntimeError):
            await service.finalize_from_close_log_async(close)

    # Delivered again, it goes through
    await service.finalize_from_close_log_async(close)
    stored = await SettlementRecordRepository(db, TENANT).get_async(STORE, TERMINAL, BC)
    assert stored.state == STATE_FINAL and stored.settlement_id == "the-terminals-id"


@pytest.mark.asyncio
async def test_two_confirms_at_once_both_answer_and_leave_one_record(db, service):
    """S4 (report side): colliding transactions are retried, not answered 500."""
    await _seed(db, sales=(1, 2))

    results = await asyncio.gather(*(service.confirm_async(_request(seq=2)) for _ in range(4)))

    stored = await SettlementRecordRepository(db, TENANT).get_async(STORE, TERMINAL, BC)
    assert stored.settlement_id in {r.settlement_id for r, _ in results}
    assert await db["settlement_record"].count_documents({}) == 1
    assert await db["settlement_daily_report"].count_documents({"settlement_id": stored.settlement_id}) == 5
    assert await db["settlement_daily_report"].count_documents({}) == 5
    assert stored.created_at is not None and stored.updated_at is not None

