"""Reports name items and payment methods from the transaction log (issue #326).

Runs the real aggregation pipelines against MongoDB. An item is named by the
newest name it was sold under in the period, whatever master-data holds now.
A payment method keeps its current master name first, then the newest name it
was paid under, so a method deleted or renamed since keeps its name.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository
from app.models.repositories.terminal_info_web_repository import TerminalInfoWebRepository
from app.models.repositories.category_master_web_repository import CategoryMasterWebRepository
from app.services.plugins.payment_report_maker import PaymentReportMaker
from app.services.report_service import ReportService

STORE = "STORENM"
TERMINAL = 1
DATE = "2024-03-05"


def _line(no, code, description, amount=100.0, category="001"):
    line = {
        "line_no": no,
        "item_code": code,
        "category_code": category,
        "unit_price": amount,
        "quantity": 1,
        "amount": amount,
        "tax_code": "01",
        "is_cancelled": False,
    }
    if description is not None:
        line["description"] = description
    return line


def _tran(no, when, line_items=(), payments=()):
    total = sum(p["amount"] for p in payments) or sum(li["amount"] for li in line_items)
    return BaseTransaction(
        tenant_id=os.environ.get("TENANT_ID"),
        store_code=STORE,
        terminal_no=TERMINAL,
        business_date=DATE,
        business_counter=1,
        open_counter=1,
        transaction_no=no,
        transaction_type=TransactionType.NormalSales.value,
        generate_date_time=when,
        sales={
            "total_amount": total,
            "total_amount_with_tax": total,
            "tax_amount": 0,
            "total_quantity": len(line_items),
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False,
        },
        payments=list(payments),
        taxes=[],
        line_items=list(line_items),
    ).model_dump()


def _pay(code, amount, builtin=None):
    payment = {"payment_no": 1, "payment_code": code, "description": builtin or "", "amount": amount}
    if builtin is not None:
        payment["builtin_description"] = builtin
    return payment


async def _service_with(trans):
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}")
    tran_repo = TranlogRepository(db, tenant_id)
    collection = db[tran_repo.collection_name]
    await collection.delete_many({"store_code": STORE})
    if trans:
        await collection.insert_many(trans)
    return ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=CashInOutLogRepository(db, tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db, tenant_id),
        daily_info_repository=DailyInfoDocumentRepository(db, tenant_id),
        terminal_info_repository=TerminalInfoWebRepository(tenant_id, STORE),
    ), collection


async def _report(trans, report_type, payment_master=None):
    service, collection = await _service_with(trans)
    try:
        with patch.object(
            CategoryMasterWebRepository, "get_categories", AsyncMock(return_value={"001": "Food"})
        ), patch.object(
            PaymentReportMaker, "_fetch_payment_master", AsyncMock(return_value=(payment_master or {}, {}))
        ):
            return await service.get_report_for_terminal_async(
                store_code=STORE,
                terminal_no=TERMINAL,
                report_scope="flash",
                report_type=report_type,
                business_date=DATE,
                open_counter=1,
                limit=100,
                page=1,
            )
    finally:
        await collection.delete_many({"store_code": STORE})


def _item_names(report):
    return {item.item_code: item.item_name for category in report.categories for item in category.items}


@pytest.mark.asyncio
async def test_an_item_is_named_as_it_was_sold_without_asking_master_data(set_env_vars, mock_outbound):
    report = await _report([_tran(1, "2024-03-05T10:00:00", [_line(1, "A1", "Apple")])], "item")

    assert _item_names(report) == {"A1": "Apple"}
    assert not [c for c in mock_outbound.calls if "/items" in str(c.request.url)]


@pytest.mark.asyncio
async def test_an_item_renamed_in_the_period_takes_its_newest_name(set_env_vars):
    older = _tran(1, "2024-03-05T09:00:00", [_line(1, "A1", "Apple")])
    newer = _tran(2, "2024-03-05T15:00:00", [_line(1, "A1", "Green apple")])
    for inserted in ([older, newer], [newer, older]):
        report = await _report(inserted, "item")
        assert _item_names(report) == {"A1": "Green apple"}


@pytest.mark.asyncio
async def test_a_line_without_a_name_neither_wins_nor_hides_one(set_env_vars):
    named = _tran(1, "2024-03-05T09:00:00", [_line(1, "A1", "Apple")])
    unnamed = _tran(2, "2024-03-05T15:00:00", [_line(1, "A1", None), _line(2, "B1", "")])

    report = await _report([named, unnamed], "item")

    assert _item_names(report) == {"A1": "Apple", "B1": "B1"}


@pytest.mark.asyncio
async def test_a_payment_method_takes_its_master_name_first(set_env_vars):
    report = await _report([_tran(1, "2024-03-05T10:00:00", payments=[_pay("11", 300, "Cards then")])], "payment",
                           payment_master={"11": "Cards now"})

    assert report.payment_summary[0].payment_name == "Cards now"


@pytest.mark.asyncio
async def test_a_method_gone_from_master_data_keeps_the_newest_name_it_was_paid_under(set_env_vars):
    older = _tran(1, "2024-03-05T09:00:00", payments=[_pay("41", 300, "Gift old")])
    newer = _tran(2, "2024-03-05T15:00:00", payments=[_pay("41", 200, "Gift new")])
    unnamed = _tran(3, "2024-03-05T18:00:00", payments=[_pay("41", 100)])
    for inserted in ([older, newer, unnamed], [unnamed, newer, older]):
        report = await _report(inserted, "payment")
        assert report.payment_summary[0].payment_name == "Gift new"


@pytest.mark.asyncio
async def test_a_method_named_nowhere_falls_back_as_before(set_env_vars):
    report = await _report(
        [_tran(1, "2024-03-05T10:00:00", payments=[_pay("41", 300), _pay("01", 100)])], "payment"
    )

    assert {p.payment_code: p.payment_name for p in report.payment_summary} == {"41": "Payment 41", "01": "Cash"}
