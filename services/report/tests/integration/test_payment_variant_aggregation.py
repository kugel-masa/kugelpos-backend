"""Reports keep one row per payment method and break it down by variant (issue #311).

Runs the real aggregation pipelines against MongoDB. Sales T1 (VISA 1000, PAYPAY
2000) and T2 (PAYPAY 500), and T3 voiding T1, as in
specs/311-payment-variants/contracts/tranlog-and-reports.md.
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
from app.services.plugins.payment_report_maker import PaymentReportMaker
from app.services.report_service import ReportService

STORE = "STOREPV"
TERMINAL = 1
DATE = "2024-02-11"


def _tran(no, ttype, payments, when):
    total = sum(p["amount"] for p in payments)
    return BaseTransaction(
        tenant_id=os.environ.get("TENANT_ID"),
        store_code=STORE,
        terminal_no=TERMINAL,
        business_date=DATE,
        business_counter=1,
        open_counter=1,
        transaction_no=no,
        transaction_type=ttype,
        generate_date_time=when,
        sales={
            "total_amount": total,
            "total_amount_with_tax": total,
            "tax_amount": 0,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False,
        },
        payments=payments,
        taxes=[],
        line_items=[],
    ).model_dump()


def _pay(no, variant, name, amount, method_name="Cashless"):
    return {
        "payment_no": no,
        "payment_code": "11",
        "variant_code": variant,
        "description": name,
        "builtin_description": method_name,
        "amount": amount,
    }


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


async def _report(service, report_type):
    with patch.object(
        PaymentReportMaker, "_fetch_payment_master", AsyncMock(return_value=({"11": "Cashless"}, {}))
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


T1 = _tran(
    1,
    TransactionType.NormalSales.value,
    [_pay(1, "VISA", "VISA", 1000), _pay(2, "PAYPAY", "PayPay", 2000)],
    "2024-02-11T10:00:00",
)
T2 = _tran(2, TransactionType.NormalSales.value, [_pay(1, "PAYPAY", "PayPay", 500)], "2024-02-11T11:00:00")
T3 = _tran(
    3,
    TransactionType.VoidSales.value,
    [_pay(1, "VISA", "VISA", 1000), _pay(2, "PAYPAY", "PayPay", 2000)],
    "2024-02-11T12:00:00",
)


@pytest.mark.asyncio
async def test_the_sales_report_breaks_a_method_down_by_variant(set_env_vars):
    service, collection = await _service_with([T1, T2])
    try:
        report = await _report(service, "sales")
    finally:
        await collection.delete_many({"store_code": STORE})

    assert len(report.payments) == 1
    row = report.payments[0]
    assert (row.payment_code, row.payment_name, row.amount, row.count) == ("11", "Cashless", 3500, 3)
    assert [(v.variant_code, v.variant_name, v.amount, v.count) for v in row.variants] == [
        ("PAYPAY", "PayPay", 2500, 2),
        ("VISA", "VISA", 1000, 1),
    ]


@pytest.mark.asyncio
async def test_the_payment_report_counts_transactions_under_each_variant(set_env_vars):
    service, collection = await _service_with([T1, T2])
    try:
        report = await _report(service, "payment")
    finally:
        await collection.delete_many({"store_code": STORE})

    row = report.payment_summary[0]
    assert (row.payment_code, row.amount, row.count) == ("11", 3500, 2)
    assert [(v.variant_code, v.amount, v.count) for v in row.variants] == [("PAYPAY", 2500, 2), ("VISA", 1000, 1)]


@pytest.mark.asyncio
async def test_a_void_cancels_its_sale_in_the_breakdown(set_env_vars):
    service, collection = await _service_with([T1, T2, T3])
    try:
        sales = await _report(service, "sales")
        payment = await _report(service, "payment")
    finally:
        await collection.delete_many({"store_code": STORE})

    payment_row = payment.payment_summary[0]
    assert (payment_row.amount, payment_row.count) == (500, 1)
    assert [(v.variant_code, v.amount, v.count) for v in payment_row.variants] == [("PAYPAY", 500, 1), ("VISA", 0, 0)]
    sales_row = sales.payments[0]
    assert sales_row.amount == 500
    assert {v.variant_code: v.amount for v in sales_row.variants} == {"PAYPAY": 500, "VISA": 0}


@pytest.mark.asyncio
async def test_names_come_from_the_newest_sale_in_the_period(set_env_vars):
    older = _tran(
        11, TransactionType.NormalSales.value, [_pay(1, "VISA", "VISA old", 100, "Cards old")], "2024-02-11T09:00:00"
    )
    newer = _tran(
        12, TransactionType.NormalSales.value, [_pay(1, "VISA", "VISA new", 100, "Cards new")], "2024-02-11T15:00:00"
    )
    for inserted in ([older, newer], [newer, older]):
        service, collection = await _service_with(inserted)
        try:
            report = await _report(service, "sales")
        finally:
            await collection.delete_many({"store_code": STORE})
        assert report.payments[0].payment_name == "Cards new"
        assert report.payments[0].variants[0].variant_name == "VISA new"


@pytest.mark.asyncio
async def test_lines_from_before_variants_fall_under_no_variant(set_env_vars):
    legacy = _tran(
        21,
        TransactionType.NormalSales.value,
        [{"payment_no": 1, "payment_code": "11", "description": "Cashless", "amount": 700}],
        "2024-02-11T10:00:00",
    )
    service, collection = await _service_with([legacy])
    try:
        report = await _report(service, "sales")
    finally:
        await collection.delete_many({"store_code": STORE})

    row = report.payments[0]
    assert row.payment_name == "Cashless"
    assert [(v.variant_code, v.variant_name, v.amount) for v in row.variants] == [(None, "Cashless", 700)]


# ---------------------------------------------------------------------------
# Review follow-ups (PR #313)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_sales_report_response_answers_the_breakdown_in_camel_case(set_env_vars):
    from app.api.v1.schemas_transformer import SchemasTransformerV1

    service, collection = await _service_with([T1, T2])
    try:
        report = await _report(service, "sales")
    finally:
        await collection.delete_many({"store_code": STORE})

    answered = SchemasTransformerV1().transform_sales_report_response(report).model_dump(by_alias=True)

    payment = answered["payments"][0]
    assert (payment["paymentCode"], payment["paymentName"], payment["amount"], payment["count"]) == (
        "11",
        "Cashless",
        3500,
        3,
    )
    assert payment["variants"] == [
        {"variantCode": "PAYPAY", "variantName": "PayPay", "amount": 2500, "count": 2},
        {"variantCode": "VISA", "variantName": "VISA", "amount": 1000, "count": 1},
    ]


@pytest.mark.asyncio
async def test_a_missing_variant_and_an_explicit_null_are_one_line_without_a_variant(set_env_vars):
    # A log written before the field existed has no variant_code at all; one written
    # since has it as null. MongoDB groups the two apart; the report must not.
    legacy = _tran(
        31,
        TransactionType.NormalSales.value,
        [{"payment_no": 1, "payment_code": "11", "description": "Cashless", "amount": 700}],
        "2024-02-11T10:00:00",
    )
    for key in ("variant_code", "builtin_description"):
        legacy["payments"][0].pop(key, None)
    recent = _tran(
        32,
        TransactionType.NormalSales.value,
        [_pay(1, None, "Cashless", 300), _pay(2, None, "Cashless", 100)],
        "2024-02-11T11:00:00",
    )
    service, collection = await _service_with([legacy, recent])
    try:
        sales = await _report(service, "sales")
        payment = await _report(service, "payment")
    finally:
        await collection.delete_many({"store_code": STORE})

    assert [(v.variant_code, v.amount, v.count) for v in sales.payments[0].variants] == [(None, 1100, 3)]
    assert [(v.variant_code, v.amount, v.count) for v in payment.payment_summary[0].variants] == [(None, 1100, 2)]


@pytest.mark.asyncio
async def test_two_taxes_and_two_variants_count_each_payment_once(set_env_vars):
    # The taxes and payments are unwound together; the per-transaction $addToSet must
    # still see each payment line once (issue #78), variant fields included.
    tran = _tran(
        41,
        TransactionType.NormalSales.value,
        [_pay(1, "VISA", "VISA", 1000), _pay(2, "PAYPAY", "PayPay", 2000)],
        "2024-02-11T10:00:00",
    )
    tran["taxes"] = [
        {"tax_no": 1, "tax_code": "01", "tax_name": "Tax 10%", "tax_amount": 200, "target_amount": 2000, "target_quantity": 1},
        {"tax_no": 2, "tax_code": "02", "tax_name": "Tax 8%", "tax_amount": 80, "target_amount": 1000, "target_quantity": 1},
    ]
    service, collection = await _service_with([tran])
    try:
        sales = await _report(service, "sales")
    finally:
        await collection.delete_many({"store_code": STORE})

    row = sales.payments[0]
    assert (row.amount, row.count) == (3000, 2)
    assert [(v.variant_code, v.amount, v.count) for v in row.variants] == [("PAYPAY", 2000, 1), ("VISA", 1000, 1)]


@pytest.mark.asyncio
async def test_one_variant_split_over_two_lines_counts_lines_in_sales_and_one_transaction_in_payments(set_env_vars):
    tran = _tran(
        51,
        TransactionType.NormalSales.value,
        [_pay(1, "VISA", "VISA", 400), _pay(2, "VISA", "VISA", 600)],
        "2024-02-11T10:00:00",
    )
    service, collection = await _service_with([tran])
    try:
        sales = await _report(service, "sales")
        payment = await _report(service, "payment")
    finally:
        await collection.delete_many({"store_code": STORE})

    assert [(v.variant_code, v.amount, v.count) for v in sales.payments[0].variants] == [("VISA", 1000, 2)]
    assert [(v.variant_code, v.amount, v.count) for v in payment.payment_summary[0].variants] == [("VISA", 1000, 1)]


@pytest.mark.asyncio
async def test_a_return_and_its_void_take_their_signs_in_the_breakdown(set_env_vars):
    returned = _tran(
        61, TransactionType.ReturnSales.value, [_pay(1, "PAYPAY", "PayPay", 2000)], "2024-02-11T13:00:00"
    )
    void_of_return = _tran(
        62, TransactionType.VoidReturn.value, [_pay(1, "PAYPAY", "PayPay", 2000)], "2024-02-11T14:00:00"
    )

    for trans, paypay in (([T1, T2, returned], (500, 1)), ([T1, T2, returned, void_of_return], (2500, 2))):
        service, collection = await _service_with(trans)
        try:
            sales = await _report(service, "sales")
            payment = await _report(service, "payment")
        finally:
            await collection.delete_many({"store_code": STORE})

        sales_variants = {v.variant_code: (v.amount, v.count) for v in sales.payments[0].variants}
        payment_variants = {v.variant_code: (v.amount, v.count) for v in payment.payment_summary[0].variants}
        assert sales_variants["PAYPAY"] == paypay
        assert payment_variants["PAYPAY"] == paypay
        assert sales_variants["VISA"] == payment_variants["VISA"] == (1000, 1)
