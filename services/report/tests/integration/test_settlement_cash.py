# Copyright 2026 masa@kugel
"""The expected cash a settlement records, case by case (#343, FR-006, FR-007, SC-005).

Each case states its expected cash by hand. The settlement must record that
amount, the frozen sales report's cash column must equal it, and so must the
live (flash) sales report of the same session: the three never disagree.
"""

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
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.settlement_record_repository import SettlementRecordRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.services.report_service import ReportService
from app.services.settlement_service import SettlementRequest

TENANT = "T343CASH"
STORE = "S343CASH"
TERMINAL = 4
DATE = "20261124"
BC = 21
FLOAT = 10000

SALE = TransactionType.NormalSales.value
VOID = TransactionType.VoidSales.value
RETURN = TransactionType.ReturnSales.value
VOID_RETURN = TransactionType.VoidReturn.value


@pytest_asyncio.fixture
async def db():
    database = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}")
    await database.client.drop_database(database.name)
    await database_setup.execute(TENANT)
    yield database
    await database.client.drop_database(database.name)


_numbers = iter(range(1, 10_000))


def _tran(
    total_with_tax: int,
    payments: list[tuple[str, int]],
    transaction_type: int = SALE,
    change: int = 0,
    cancelled: bool = False,
) -> BaseTransaction:
    """A transaction log as cart writes it: amounts positive, the type gives the sign."""
    total = round(total_with_tax / 1.1)
    tax = total_with_tax - total
    no = next(_numbers)
    return BaseTransaction(
        tenant_id=TENANT,
        store_code=STORE,
        terminal_no=TERMINAL,
        business_date=DATE,
        business_counter=BC,
        open_counter=1,
        transaction_no=no,
        receipt_counter=no,
        transaction_type=transaction_type,
        generate_date_time=f"{DATE}T10:00:00",
        cart_id=str(uuid.uuid4()),
        sales={
            "total_amount": total,
            "total_amount_with_tax": total_with_tax,
            "tax_amount": tax,
            "total_quantity": 1,
            "change_amount": change,
            "total_discount_amount": 0,
            "is_cancelled": cancelled,
        },
        payments=[
            # cart records the amount applied to the sale; with change, the
            # deposit is larger (abstract_payment.py: payment.amount = balance)
            {"payment_no": i + 1, "payment_code": code, "amount": amount,
             "deposit_amount": amount + (change if code == "01" else 0), "description": code}
            for i, (code, amount) in enumerate(payments)
        ],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "10%", "tax_amount": tax, "target_amount": total, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "I1", "category_code": "C1", "quantity": 1, "unit_price": total, "amount": total, "tax_code": "01"}],
    )


def _cash(amount: float, n: int) -> CashInOutLog:
    return CashInOutLog(
        tenant_id=TENANT, store_code=STORE, terminal_no=TERMINAL, business_date=DATE, open_counter=1,
        business_counter=BC, generate_date_time=f"{DATE}T09:{n:02d}:00", amount=amount,
    )


async def _settle(db, trans: list[BaseTransaction], cash: list[float], counted=None):
    tran_repo = TranlogRepository(db, TENANT)
    for t in trans:
        await tran_repo.create_tranlog_async(t)
    cash_repo = CashInOutLogRepository(db, TENANT)
    for n, amount in enumerate(cash):
        await cash_repo.create_cash_in_out_log(_cash(amount, n))

    service = await get_settlement_service_async(TENANT)
    with patch.object(service, "_names_async", return_value={"category_names": {}, "payment_names": ({}, {})}):
        record, _ = await service.confirm_async(
            SettlementRequest(
                store_code=STORE, terminal_no=TERMINAL, business_counter=BC, business_date=DATE, open_counter=1,
                settled_at="t", cash_log_count=len(cash), physical_amount=counted,
            )
        )
    frozen = (await SettlementRecordRepository(db, TENANT).get_daily_reports_async([record.settlement_id], "sales"))[
        record.settlement_id
    ]
    flash = await ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=OpenCloseLogRepository(db, TENANT),
    ).get_report_for_terminal_async(
        store_code=STORE, terminal_no=TERMINAL, report_scope="flash", report_type="sales",
        business_date=DATE, open_counter=1, limit=100, page=1,
    )
    return record, frozen, flash


def _assert_cash(record, frozen, flash, expected_total, cash_sales):
    assert record.expected_cash.total == expected_total
    assert record.expected_cash.cash_sales == cash_sales
    assert frozen["cash"]["logical_amount"] == expected_total, "frozen sales report disagrees with the settlement"
    assert flash.cash.logical_amount == expected_total, "live sales report disagrees with the settlement"


CASES = [
    pytest.param(
        # Paid 1,000 for a 220 sale: 780 change goes back, only 220 stays
        [_tran(220, [("01", 220)], change=780)], [FLOAT], FLOAT + 220, 220,
        id="cash-with-change",
    ),
    pytest.param(
        # A sale and its void cancel out
        [_tran(1100, [("01", 1100)]), _tran(1100, [("01", 1100)], transaction_type=VOID)], [FLOAT], FLOAT, 0,
        id="void",
    ),
    pytest.param(
        # 550 refunded in cash
        [_tran(1100, [("01", 1100)]), _tran(550, [("01", 550)], transaction_type=RETURN)], [FLOAT], FLOAT + 550, 550,
        id="return",
    ),
    pytest.param(
        # The return is voided: the refund comes back
        [
            _tran(1100, [("01", 1100)]),
            _tran(550, [("01", 550)], transaction_type=RETURN),
            _tran(550, [("01", 550)], transaction_type=VOID_RETURN),
        ],
        [FLOAT], FLOAT + 1100, 1100,
        id="void-of-a-return",
    ),
    pytest.param(
        # Only the cash part of a split payment is in the drawer
        [_tran(3300, [("01", 1000), ("11", 2300)])], [FLOAT], FLOAT + 1000, 1000,
        id="split-cash-and-card",
    ),
    pytest.param(
        # Card only: nothing in the drawer
        [_tran(2200, [("11", 2200)])], [FLOAT], FLOAT, 0,
        id="card-only",
    ),
    pytest.param(
        # A pickup of 2,000 and a cash-in of 300
        [_tran(1100, [("01", 1100)])], [FLOAT, -2000, 300], FLOAT + 1100 - 2000 + 300, 1100,
        id="cash-out-and-in",
    ),
    pytest.param(
        # A cart cancelled before payment completed is not a sale
        [_tran(1100, [("01", 1100)]), _tran(500, [("01", 500)], cancelled=True)], [FLOAT], FLOAT + 1100, 1100,
        id="cancelled-cart",
    ),
    pytest.param(
        # Opened without a float: no cash-in log at open
        [_tran(1100, [("01", 1100)])], [], 1100, 1100,
        id="no-float",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("trans,cash,expected_total,cash_sales", CASES)
async def test_expected_cash_case_by_case(db, trans, cash, expected_total, cash_sales):
    record, frozen, flash = await _settle(db, trans, cash)
    _assert_cash(record, frozen, flash, expected_total, cash_sales)
    assert record.difference is None  # nothing counted


@pytest.mark.asyncio
async def test_everything_in_one_session(db):
    trans = [
        _tran(220, [("01", 220)], change=780),                  # +220
        _tran(1100, [("01", 1100)]),                            # +1100
        _tran(1100, [("01", 1100)], transaction_type=VOID),     # -1100
        _tran(2200, [("01", 2200)]),                            # +2200
        _tran(550, [("01", 550)], transaction_type=RETURN),     # -550
        _tran(3300, [("01", 1000), ("11", 2300)]),              # +1000 (card 2300 not cash)
        _tran(500, [("01", 500)], cancelled=True),              # 0
    ]
    cash = [FLOAT, -2000, 300]
    cash_sales = 220 + 1100 - 1100 + 2200 - 550 + 1000
    expected = FLOAT + cash_sales - 2000 + 300

    record, frozen, flash = await _settle(db, trans, cash, counted=expected - 30)

    _assert_cash(record, frozen, flash, expected, cash_sales)
    assert record.physical_amount == expected - 30
    assert record.difference == -30
    assert frozen["cash"]["physical_amount"] == expected - 30
    assert frozen["cash"]["difference_amount"] == -30
    assert record.expected_cash.cash_in.model_dump() == {"amount": FLOAT + 300, "count": 2}
    assert record.expected_cash.cash_out.model_dump() == {"amount": -2000, "count": 1}
    assert record.cash_log_count == 3 and record.missing_cash_log_count == 0
    # The cancelled cart carries a number, so it is counted as arrived
    assert record.included_count == len(trans)
    assert record.missing_count == 0
