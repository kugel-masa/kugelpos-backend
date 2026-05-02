# Copyright 2025 masa@kugel
# Regression tests for sales/item/category report aggregation:
#   1. Period sales report only returns 1 day of data (final_group_id had business_date)
#   2. Item/Category reports include cancelled line_items (no is_cancelled filter)
#   3. Sales report discount aggregation leaks discounts from cancelled lines

import os
import pytest
from datetime import datetime

from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository
from app.models.repositories.terminal_info_web_repository import TerminalInfoWebRepository
from app.services.report_service import ReportService


def _make_normal_sale(
    *,
    tenant_id: str,
    store_code: str,
    terminal_no: int,
    transaction_no: int,
    business_date: str,
    base_amount: int,
    line_items: list,
    total_discount_amount: float = 0,
    subtotal_discounts: list = None,
) -> BaseTransaction:
    """Build a NormalSales transaction. Caller supplies pre-computed line_items.

    Optional:
      total_discount_amount: cart-side sum of subtotal_discounts + non-cancelled line discounts.
      subtotal_discounts: cart-level subtotal discount entries (mirror of cart_doc.subtotal_discounts).
    """
    tax_amount = int(round(base_amount * 0.1 / 1.1))  # internal 10% tax
    return BaseTransaction(
        tenant_id=tenant_id,
        store_code=store_code,
        terminal_no=terminal_no,
        business_date=business_date,
        business_counter=1,
        open_counter=1,
        transaction_no=transaction_no,
        transaction_type=TransactionType.NormalSales.value,
        sales={
            "total_amount": base_amount,
            "total_amount_with_tax": base_amount,
            "tax_amount": 0,
            "total_quantity": sum(li.get("quantity", 0) for li in line_items if not li.get("is_cancelled", False)),
            "change_amount": 0,
            "total_discount_amount": total_discount_amount,
            "is_cancelled": False,
        },
        payments=[
            {"payment_no": 1, "payment_code": "01", "amount": base_amount, "description": "Cash"},
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "内税10%",
                "tax_amount": tax_amount,
                "target_amount": base_amount,
                "target_quantity": 1,
            }
        ],
        line_items=line_items,
        subtotal_discounts=subtotal_discounts or [],
        transaction_time=datetime.now().isoformat(),
    )


@pytest.mark.asyncio
async def test_period_sales_report_aggregates_all_days(set_env_vars):
    """
    Period sales report previously only included 1 day's data because
    final_group_id contained business_date, splitting transaction_type into multiple rows;
    _get_result_by_transaction_type then took only the first row (non-deterministic).

    Scenario: 3 transactions across 3 different business dates, 1000 yen each.
    Expected (after fix): sales_gross.amount = 3000 yen, count = 3.
    Buggy behavior: ~1000 yen, count = 1.
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "STORE115A")

    collection = db[tran_repo.collection_name]

    test_store = "STORE115A"
    test_terminal = 70
    business_dates = ["20260414", "20260415", "20260416"]

    # Clean up any prior test data
    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": test_store,
        "terminal_no": test_terminal,
    })

    # Insert one NormalSales per business_date, 1000 yen each
    for idx, bdate in enumerate(business_dates, start=1):
        tran = _make_normal_sale(
            tenant_id=tenant_id,
            store_code=test_store,
            terminal_no=test_terminal,
            transaction_no=idx,
            business_date=bdate,
            base_amount=1000,
            line_items=[
                {
                    "line_no": 1,
                    "item_code": "G115A",
                    "category_code": "C1",
                    "quantity": 1,
                    "unit_price": 1000,
                    "amount": 1000,
                    "tax_code": "01",
                    "is_cancelled": False,
                }
            ],
        )
        await collection.insert_one(tran.model_dump())

    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo,
    )

    # Run the same period query multiple times — non-determinism would surface here
    observed_amounts = set()
    last_report = None
    for _ in range(3):
        report = await service.get_report_for_terminal_async(
            store_code=test_store,
            terminal_no=test_terminal,
            report_scope="daily",
            report_type="sales",
            business_date_from=business_dates[0],
            business_date_to=business_dates[-1],
            limit=100,
            page=1,
        )
        observed_amounts.add(report.sales_gross.amount)
        last_report = report

    # Cleanup
    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": test_store,
        "terminal_no": test_terminal,
    })

    assert observed_amounts == {3000.0}, (
        f"Period sales report must aggregate all 3 days deterministically. "
        f"Observed gross amounts across repeated calls: {observed_amounts}. "
        f"If the set has multiple values, results are non-deterministic."
    )

    # gross count is NormalSales count; we have 3 NormalSales
    assert last_report.sales_gross.count == 3, \
        f"Expected 3 transactions across 3 days, got {last_report.sales_gross.count}"


@pytest.mark.asyncio
async def test_item_report_excludes_cancelled_line_items(set_env_vars):
    """
    Item/category report previously included line_items with
    is_cancelled=True, causing item totals to exceed sales totals.

    Scenario: 1 transaction with 2 line_items — one active (500 yen), one cancelled (500 yen).
    Sales totals (computed by Cart) reflect only the active item: 500 yen.
    Item/category report should also reflect only the active item, not 1000 yen.
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "STORE115B")

    collection = db[tran_repo.collection_name]

    test_store = "STORE115B"
    test_terminal = 71
    test_date = "20260420"

    # Clean up any prior test data
    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": test_store,
        "terminal_no": test_terminal,
    })

    tran = _make_normal_sale(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        transaction_no=1,
        business_date=test_date,
        base_amount=500,  # only the active line item is in totals
        line_items=[
            {
                "line_no": 1,
                "item_code": "G5011",
                "category_code": "CAT1",
                "quantity": 1,
                "unit_price": 500,
                "amount": 500,
                "tax_code": "01",
                "is_cancelled": False,  # active
            },
            {
                "line_no": 2,
                "item_code": "G5011",
                "category_code": "CAT1",
                "quantity": 1,
                "unit_price": 500,
                "amount": 500,
                "tax_code": "01",
                "is_cancelled": True,  # cancelled, must not be counted
            },
        ],
    )
    await collection.insert_one(tran.model_dump())

    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo,
    )

    # 1) Sales report — used as the source of truth
    sales_report = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=test_terminal,
        report_scope="flash",
        report_type="sales",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1,
    )

    # 2) Item report
    item_report = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=test_terminal,
        report_scope="flash",
        report_type="item",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1,
    )

    # 3) Category report
    category_report = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=test_terminal,
        report_scope="flash",
        report_type="category",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1,
    )

    # Cleanup
    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": test_store,
        "terminal_no": test_terminal,
    })

    # Sales total should be 500 (only active line)
    assert sales_report.sales_gross.amount == 500.0, \
        f"Sales gross should reflect only active line item. Expected 500, got {sales_report.sales_gross.amount}"

    # Item report total must equal sales total (no over-count from cancelled lines)
    assert item_report.total_gross_amount == 500.0, (
        f"Item report total_gross_amount must equal sales_gross.amount (500). "
        f"Got {item_report.total_gross_amount}. If 1000, cancelled line_items are leaking into item aggregation."
    )
    assert item_report.total_quantity == 1, \
        f"Item report total_quantity should be 1 (cancelled line excluded), got {item_report.total_quantity}"

    # Category report total must also equal sales total
    assert category_report.total_gross_amount == 500.0, (
        f"Category report total_gross_amount must equal sales_gross.amount (500). "
        f"Got {category_report.total_gross_amount}. If 1000, cancelled line_items are leaking into category aggregation."
    )
    assert category_report.total_quantity == 1, \
        f"Category report total_quantity should be 1 (cancelled line excluded), got {category_report.total_quantity}"

    # Within item report, G5011 should appear with quantity 1 only
    g5011_items = [
        item for cat in item_report.categories for item in cat.items if item.item_code == "G5011"
    ]
    assert len(g5011_items) == 1, f"G5011 should appear exactly once, got {len(g5011_items)}"
    assert g5011_items[0].quantity == 1, \
        f"G5011 quantity should be 1 (cancelled excluded), got {g5011_items[0].quantity}"
    assert g5011_items[0].gross_amount == 500.0, \
        f"G5011 gross_amount should be 500 (cancelled excluded), got {g5011_items[0].gross_amount}"


@pytest.mark.asyncio
async def test_sales_report_excludes_cancelled_line_item_discounts(set_env_vars):
    """
    sales_report_maker's $project iterated $line_items without filtering
    is_cancelled, so a cancelled line item that still carries discounts (Cart sets
    is_cancelled=True without clearing line_item.discounts) inflated the report's
    discount_for_lineitems totals and depressed sales_net.amount via _make_sales_net.

    Scenario: 1 NormalSales transaction with 2 line items.
      - Item 1: active, post-discount 900 yen (1000 - 100 line discount). Must be counted.
      - Item 2: cancelled, originally 500 yen, with a 200 yen line discount dangling. Must NOT be counted.

    Both items have line discounts; the active discount must be retained in the report and
    the cancelled discount must be filtered out. This shape distinguishes "filter is doing
    its job" from "everything is zero anyway".

    Cart-side calc_subtotal_logic computes:
      total_amount = 900 (only active line)
      total_discount_amount = 100 (only active line discount counted)
    The report must agree:
      discount_for_lineitems = (amount=100, count=1, quantity=1)
      sales_net = sales_gross(1000) - returns(0) - discount_lineitem(100) - discount_subtotal(0) - net_tax
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "STORE115C")

    collection = db[tran_repo.collection_name]

    test_store = "STORE115C"
    test_terminal = 72
    test_date = "20260421"

    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": test_store,
        "terminal_no": test_terminal,
    })

    tran = _make_normal_sale(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        transaction_no=1,
        business_date=test_date,
        base_amount=900,  # cart-side total_amount = sum of non-cancelled line.amount = 900
        total_discount_amount=100,  # cart-side counts only active line's discount
        line_items=[
            {
                "line_no": 1,
                "item_code": "G115C-A",
                "category_code": "CAT1",
                "quantity": 1,
                "unit_price": 1000,
                "amount": 900,  # post-discount line amount = unit_price - line discount
                "tax_code": "01",
                "is_cancelled": False,
                "discounts": [
                    {
                        "seq_no": 1,
                        "discount_type": "DiscountAmount",
                        "discount_value": 100,
                        "discount_amount": 100,
                        "detail": "active-must-count",
                    }
                ],
                "discounts_allocated": [],
            },
            {
                "line_no": 2,
                "item_code": "G115C-B",
                "category_code": "CAT1",
                "quantity": 1,
                "unit_price": 500,
                "amount": 300,
                "tax_code": "01",
                "is_cancelled": True,  # cancelled but still has a dangling discount
                "discounts": [
                    {
                        "seq_no": 1,
                        "discount_type": "DiscountAmount",
                        "discount_value": 200,
                        "discount_amount": 200,
                        "detail": "cancelled-must-not-leak",
                    }
                ],
                "discounts_allocated": [],
            },
        ],
    )
    await collection.insert_one(tran.model_dump())

    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo,
    )

    sales_report = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=test_terminal,
        report_scope="flash",
        report_type="sales",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1,
    )

    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": test_store,
        "terminal_no": test_terminal,
    })

    # Active line's 100 yen discount must be counted; cancelled line's 200 yen must NOT leak.
    assert sales_report.discount_for_lineitems.amount == 100.0, (
        f"discount_for_lineitems.amount must equal the active line's discount (100). "
        f"Got {sales_report.discount_for_lineitems.amount}. "
        f"If 300, both active+cancelled discounts are aggregated (filter not effective). "
        f"If 0, the active discount was also dropped (filter too aggressive)."
    )
    assert sales_report.discount_for_lineitems.count == 1, (
        f"discount_for_lineitems.count must equal 1 (only the active line). "
        f"Got {sales_report.discount_for_lineitems.count}. "
        f"If 2, the cancelled line is leaking; if 0, the active line was also dropped."
    )
    assert sales_report.discount_for_lineitems.quantity == 1, (
        f"discount_for_lineitems.quantity must equal 1 (only the active line). "
        f"Got {sales_report.discount_for_lineitems.quantity}. "
        f"If 2, cancelled is leaking; if 0, active was dropped."
    )

    # sales_net must reflect the active discount (100) only, not the leaked 200.
    # gross = total_amount_with_tax(=900) + total_discount_amount(=100) = 1000.
    # net = gross - returns(0) - discount_lineitem(100) - discount_subtotal(0) - net_tax.
    expected_net = (
        sales_report.sales_gross.amount
        - sales_report.discount_for_lineitems.amount
        - sum(t.tax_amount for t in sales_report.taxes)
    )
    assert sales_report.sales_net.amount == expected_net, (
        f"sales_net.amount must equal sales_gross - discount_lineitem - net_tax. "
        f"Expected {expected_net}, got {sales_report.sales_net.amount}. "
        f"A 200 yen extra subtraction here would mean _make_sales_net is using the leaked discount."
    )


@pytest.mark.asyncio
async def test_sales_report_excludes_cancelled_line_from_subtotal_discount_quantity(set_env_vars):
    """
    The same $line_items-without-filter bug affects sub_total_discount_quantity.
    sub_total_discount_quantity sums the quantity of every line item whose discounts_allocated is
    non-empty. When a subtotal discount is applied (which populates discounts_allocated for all
    eligible lines) and a line is then cancelled, Cart's __subtotal_async re-runs but does NOT
    re-run add_discount_to_cart_logic, so the cancelled line keeps its discounts_allocated.

    Without the filter, that cancelled line's quantity gets counted in discount_for_subtotal.quantity.
    Note: amount and count come from $subtotal_discounts directly and are not affected; only quantity
    is buggy. Still worth covering — this is the only path that exercises the discounts_allocated
    branch of the fix.

    Scenario: subtotal discount of 300 yen, then Item B cancelled.
      - Item A (active): amount=1000, discounts_allocated=[200]
      - Item B (cancelled): amount=500, discounts_allocated=[100] (dangling)
    Expected: discount_for_subtotal.quantity == 1 (only A counted), not 2.
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "STORE115D")

    collection = db[tran_repo.collection_name]

    test_store = "STORE115D"
    test_terminal = 73
    test_date = "20260422"

    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": test_store,
        "terminal_no": test_terminal,
    })

    tran = _make_normal_sale(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        transaction_no=1,
        business_date=test_date,
        base_amount=700,  # subtotal_amount(1000, only active) - subtotal_discount(300) = 700
        total_discount_amount=300,  # subtotal_discounts sum + non-cancelled line discounts (0) = 300
        subtotal_discounts=[
            {
                "seq_no": 1,
                "discount_type": "DiscountAmount",
                "discount_value": 300,
                "discount_amount": 300,
                "detail": "subtotal-discount",
            }
        ],
        line_items=[
            {
                "line_no": 1,
                "item_code": "G115D-A",
                "category_code": "CAT1",
                "quantity": 1,
                "unit_price": 1000,
                "amount": 1000,
                "tax_code": "01",
                "is_cancelled": False,
                "discounts": [],
                "discounts_allocated": [
                    {
                        "seq_no": 1,
                        "discount_type": "DiscountAmount",
                        "discount_value": 300,
                        "discount_amount": 200,
                        "detail": "active-allocation",
                    }
                ],
            },
            {
                "line_no": 2,
                "item_code": "G115D-B",
                "category_code": "CAT1",
                "quantity": 1,
                "unit_price": 500,
                "amount": 500,
                "tax_code": "01",
                "is_cancelled": True,  # cancelled, but discounts_allocated was not cleared
                "discounts": [],
                "discounts_allocated": [
                    {
                        "seq_no": 1,
                        "discount_type": "DiscountAmount",
                        "discount_value": 300,
                        "discount_amount": 100,
                        "detail": "cancelled-allocation-dangling",
                    }
                ],
            },
        ],
    )
    await collection.insert_one(tran.model_dump())

    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo,
    )

    sales_report = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=test_terminal,
        report_scope="flash",
        report_type="sales",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1,
    )

    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": test_store,
        "terminal_no": test_terminal,
    })

    # amount and count come from $subtotal_discounts directly — sanity-check they are right.
    assert sales_report.discount_for_subtotal.amount == 300.0, (
        f"discount_for_subtotal.amount should equal the subtotal discount (300). "
        f"Got {sales_report.discount_for_subtotal.amount}."
    )
    assert sales_report.discount_for_subtotal.count == 1, (
        f"discount_for_subtotal.count should equal 1 (one subtotal_discounts entry). "
        f"Got {sales_report.discount_for_subtotal.count}."
    )

    # The buggy field: quantity must count only the active line whose discounts_allocated is non-empty.
    assert sales_report.discount_for_subtotal.quantity == 1, (
        f"discount_for_subtotal.quantity must exclude cancelled line items with dangling "
        f"discounts_allocated. Expected 1 (only active line A), got {sales_report.discount_for_subtotal.quantity}. "
        f"If 2, the cancelled line's allocation is leaking into the report."
    )
