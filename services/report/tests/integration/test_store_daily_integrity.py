# Copyright 2025 masa@kugel
# Data integrity tests for POS accounting equations
#
# These tests verify fundamental POS accounting principles:
# 1. Payment total = Sales total (with tax)
# 2. Multi-transaction aggregation maintains integrity
# 3. Store-wide daily totals are accurate
#
# CRITICAL: These tests detect Cartesian product bugs and other aggregation errors
# by verifying the fundamental equation: Total Payments = Sales Net + Tax

import os
import pytest
from datetime import datetime

from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.services.report_service import ReportService
from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository
from app.models.repositories.terminal_info_web_repository import TerminalInfoWebRepository


@pytest.mark.asyncio
async def test_store_wide_daily_integrity(set_env_vars):
    """
    CRITICAL TEST: Verify store-wide daily integrity across multiple terminals
    INCLUDING return transactions (factor = -1)

    Scenario:
    - Terminal 1: 2 NormalSales, total 3300 yen (3000 + 300 tax)
    - Terminal 2: 3 NormalSales, total 4950 yen (4500 + 450 tax)
    - Terminal 3: 2 transactions
      - 1 NormalSales: 1100 yen (1000 + 100 tax)
      - 1 ReturnSales: -550 yen (-500 - 50 tax) [factor = -1]
      - Net: 550 yen

    Store-wide daily total (terminal_no=None):
    - Expected Sales: 8000 yen (3000 + 4500 + 500)
    - Expected Tax: 800 yen (300 + 450 + 50)
    - Expected Payments: 8800 yen
    - Equation: 8800 = 8000 + 800 ✓

    WHY THIS MATTERS:
    - Store-wide reports are used for daily business reconciliation
    - Tests the most complex aggregation scenario
    - Verifies composite key (tenant, store, terminal, transaction_no) works correctly
    - Verifies return transactions correctly subtract from totals (factor = -1)
    - Real impact: Daily cash reconciliation for entire store
    """
    from kugel_common.database import database as local_db_helper

    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    db = await local_db_helper.get_db_async(db_name)

    tran_repo = TranlogRepository(db, os.environ.get("TENANT_ID"))
    cash_repo = CashInOutLogRepository(db, os.environ.get("TENANT_ID"))
    open_close_repo = OpenCloseLogRepository(db, os.environ.get("TENANT_ID"))
    daily_info_repo = DailyInfoDocumentRepository(db, os.environ.get("TENANT_ID"))
    terminal_info_repo = TerminalInfoWebRepository(db, os.environ.get("TENANT_ID"))

    collection = db[tran_repo.collection_name]
    await collection.delete_many({})

    test_store = "STORE001"
    test_date = "2024-03-01"
    tenant_id = os.environ.get("TENANT_ID")

    transactions = []

    # Terminal 1: 2 transactions
    # T1-1: 1000 + 100 tax = 1100
    transactions.append(BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=1,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        sales={
            "total_amount": 1000,
            "total_amount_with_tax": 1100,
            "tax_amount": 100,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[
            {"payment_no": 1, "payment_code": "01", "amount": 1100, "description": "Cash"}
        ],
        taxes=[
            {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}
        ],
        line_items=[
            {"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1000, "amount": 1000, "tax_code": "01"}
        ]
    ))

    # T1-2: 2000 + 200 tax = 2200
    transactions.append(BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=1,
        business_date=test_date,
        business_counter=2,
        open_counter=1,
        transaction_no=2,
        transaction_type=TransactionType.NormalSales.value,
        sales={
            "total_amount": 2000,
            "total_amount_with_tax": 2200,
            "tax_amount": 200,
            "total_quantity": 2,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[
            {"payment_no": 1, "payment_code": "01", "amount": 1100, "description": "Cash"},
            {"payment_no": 2, "payment_code": "11", "amount": 1100, "description": "Credit"}
        ],
        taxes=[
            {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 200, "target_amount": 2000, "target_quantity": 2}
        ],
        line_items=[
            {"line_no": 1, "item_code": "ITEM002", "quantity": 2, "unit_price": 1000, "amount": 2000, "tax_code": "01"}
        ]
    ))

    # Terminal 2: 3 transactions
    for i in range(3):
        transactions.append(BaseTransaction(
            tenant_id=tenant_id,
            store_code=test_store,
            terminal_no=2,
            business_date=test_date,
            business_counter=i+1,
            open_counter=1,
            transaction_no=i+1,
            transaction_type=TransactionType.NormalSales.value,
            sales={
                "total_amount": 1500,
                "total_amount_with_tax": 1650,
                "tax_amount": 150,
                "total_quantity": 1,
                "change_amount": 0,
                "total_discount_amount": 0,
                "is_cancelled": False
            },
            payments=[
                {"payment_no": 1, "payment_code": "01", "amount": 825, "description": "Cash"},
                {"payment_no": 2, "payment_code": "11", "amount": 825, "description": "Credit"}
            ],
            taxes=[
                {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 150, "target_amount": 1500, "target_quantity": 1}
            ],
            line_items=[
                {"line_no": 1, "item_code": f"ITEM00{i+3}", "quantity": 1, "unit_price": 1500, "amount": 1500, "tax_code": "01"}
            ]
        ))

    # Terminal 3: 2 transactions (1 NormalSales + 1 ReturnSales)
    # T3-1: NormalSales 1000 + 100 tax = 1100
    transactions.append(BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=3,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        sales={
            "total_amount": 1000,
            "total_amount_with_tax": 1100,
            "tax_amount": 100,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[
            {"payment_no": 1, "payment_code": "01", "amount": 550, "description": "Cash"},
            {"payment_no": 2, "payment_code": "11", "amount": 550, "description": "Credit"}
        ],
        taxes=[
            {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}
        ],
        line_items=[
            {"line_no": 1, "item_code": "ITEM006", "quantity": 1, "unit_price": 1000, "amount": 1000, "tax_code": "01"}
        ]
    ))

    # T3-2: ReturnSales (返品) 500 + 50 tax = 550 (factor = -1)
    # This should SUBTRACT from the totals
    transactions.append(BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=3,
        business_date=test_date,
        business_counter=2,
        open_counter=1,
        transaction_no=2,
        transaction_type=TransactionType.ReturnSales.value,
        sales={
            "total_amount": 500,
            "total_amount_with_tax": 550,
            "tax_amount": 50,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[
            {"payment_no": 1, "payment_code": "01", "amount": 550, "description": "Cash"}
        ],
        taxes=[
            {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 50, "target_amount": 500, "target_quantity": 1}
        ],
        line_items=[
            {"line_no": 1, "item_code": "ITEM007", "quantity": 1, "unit_price": 500, "amount": 500, "tax_code": "01"}
        ]
    ))

    await collection.insert_many([t.model_dump() for t in transactions])

    # Generate STORE-WIDE report (terminal_no=None)
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    report = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=None,  # Store-wide report!
        report_scope="flash",
        report_type="sales",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1
    )

    # Extract values
    sales_net = report.sales_net.amount
    tax_total = sum(t.tax_amount for t in report.taxes)
    payment_total = sum(p.amount for p in report.payments)

    # Expected values
    # Terminal 1: 1000 + 2000 = 3000 + 300 tax = 3300
    # Terminal 2: 1500 × 3 = 4500 + 450 tax = 4950
    # Terminal 3:
    #   - NormalSales: 1000 + 100 tax = 1100
    #   - ReturnSales: -500 - 50 tax = -550 (factor = -1)
    #   - Net: 500 + 50 tax = 550
    # Total: 8000 + 800 tax = 8800

    expected_sales = 8000  # 3000 + 4500 + 500 (1000 - 500 return)
    expected_tax = 800     # 300 + 450 + 50 (100 - 50 return)
    expected_payment = 8800

    sales_with_tax = sales_net + tax_total

    print("\n=== STORE-WIDE DAILY INTEGRITY TEST ===")
    print(f"Terminals: 3 (T1: 2 trans, T2: 3 trans, T3: 2 trans [1 sale + 1 return])")
    print(f"Total Transactions: 7 (6 NormalSales + 1 ReturnSales)")
    print(f"Sales Net: {sales_net}")
    print(f"Tax Total: {tax_total}")
    print(f"Sales + Tax: {sales_with_tax}")
    print(f"Payment Total: {payment_total}")
    print(f"Difference: {payment_total - sales_with_tax}")

    # NOTE: count represents report groups, not individual transactions
    # Store-wide groups by (tenant, store, date, type) → 2 groups: NormalSales + ReturnSales

    assert sales_net == expected_sales, f"Expected sales net {expected_sales}, got {sales_net}"
    assert tax_total == expected_tax, f"Expected tax total {expected_tax}, got {tax_total}"
    assert payment_total == expected_payment, f"Expected payment total {expected_payment}, got {payment_total}"

    # THE CRITICAL ASSERTION FOR STORE-WIDE DAILY
    assert payment_total == sales_with_tax, \
        f"CRITICAL ERROR: Store-wide payment total ({payment_total}) != Sales + Tax ({sales_with_tax}). " \
        f"Difference: {payment_total - sales_with_tax}. " \
        f"Store-wide aggregation has errors!"

    print("✅ PASS: Store-wide daily integrity verified")
    print("✅ 3 terminals, 7 transactions (including 1 return) aggregate correctly")
    print("✅ Return transaction correctly subtracts from totals (factor = -1)")
    print("✅ Payment Total = Sales Net + Tax")
    print("=========================================\n")


