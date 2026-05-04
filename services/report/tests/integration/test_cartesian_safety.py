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
async def test_mixed_transaction_types_with_cartesian_risk(set_env_vars):
    """
    CRITICAL TEST: Verify payment integrity with mixed transaction types
    (NormalSales, ReturnSales, VoidSales) with Cartesian product risk

    Scenario:
    - Terminal 1:
      - NormalSales 1: 1000 + 100 tax = 1100 (Cash 550 + Credit 550)
      - NormalSales 2: 2000 + 200 tax = 2200 (Cash 1100 + Credit 1100)
    - Terminal 2:
      - NormalSales: 1500 + 150 tax = 1650 (Cash 825 + Credit 825)
      - ReturnSales: -500 - 50 tax = -550 (Cash only)
      - VoidSales: -800 - 80 tax = -880 (Cash 440 + Credit 440)
    - Terminal 3:
      - NormalSales: 3000 + 300 tax = 3300 (2 payments × 2 taxes = 4x Cartesian)
      - VoidSales: -1000 - 100 tax = -1100 (2 payments × 2 taxes = 4x Cartesian)

    Store-wide total:
    - NormalSales: 7500 + 750 tax = 8250
    - ReturnSales: -500 - 50 tax = -550 (factor = -1)
    - VoidSales: -1800 - 180 tax = -1980 (factor = -1)
    - Net: 5200 + 520 tax = 5720
    - Equation: 5720 = 5200 + 520 ✓

    WHY THIS MATTERS:
    - Tests all transaction types (NormalSales, ReturnSales, VoidSales)
    - Tests factoring logic (factor = 1 or -1)
    - Tests Cartesian product scenarios with void transactions
    - Most complex real-world scenario
    - Real impact: End-of-day reconciliation with returns and voids
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
    delete_result = await collection.delete_many({})
    print(f"Deleted {delete_result.deleted_count} documents")

    test_store = "STORE001"
    test_date = "2024-03-01"
    tenant_id = os.environ.get("TENANT_ID")

    transactions = []

    # Terminal 1: 2 NormalSales
    transactions.extend([
        BaseTransaction(
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
                {"payment_no": 1, "payment_code": "01", "amount": 550, "description": "Cash"},
                {"payment_no": 2, "payment_code": "11", "amount": 550, "description": "Credit"}
            ],
            taxes=[
                {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}
            ],
            line_items=[
                {"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1000, "amount": 1000, "tax_code": "01"}
            ]
        ),
        BaseTransaction(
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
        )
    ])

    # Terminal 2: 1 NormalSales + 1 ReturnSales + 1 VoidSales
    transactions.extend([
        BaseTransaction(
            tenant_id=tenant_id,
            store_code=test_store,
            terminal_no=2,
            business_date=test_date,
            business_counter=1,
            open_counter=1,
            transaction_no=1,
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
                {"line_no": 1, "item_code": "ITEM003", "quantity": 1, "unit_price": 1500, "amount": 1500, "tax_code": "01"}
            ]
        ),
        BaseTransaction(
            tenant_id=tenant_id,
            store_code=test_store,
            terminal_no=2,
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
                {"line_no": 1, "item_code": "ITEM004", "quantity": 1, "unit_price": 500, "amount": 500, "tax_code": "01"}
            ]
        ),
        BaseTransaction(
            tenant_id=tenant_id,
            store_code=test_store,
            terminal_no=2,
            business_date=test_date,
            business_counter=3,
            open_counter=1,
            transaction_no=3,
            transaction_type=TransactionType.VoidSales.value,
            sales={
                "total_amount": 800,
                "total_amount_with_tax": 880,
                "tax_amount": 80,
                "total_quantity": 1,
                "change_amount": 0,
                "total_discount_amount": 0,
                "is_cancelled": False
            },
            payments=[
                {"payment_no": 1, "payment_code": "01", "amount": 440, "description": "Cash"},
                {"payment_no": 2, "payment_code": "11", "amount": 440, "description": "Credit"}
            ],
            taxes=[
                {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 80, "target_amount": 800, "target_quantity": 1}
            ],
            line_items=[
                {"line_no": 1, "item_code": "ITEM005", "quantity": 1, "unit_price": 800, "amount": 800, "tax_code": "01"}
            ]
        )
    ])

    # Terminal 3: 1 NormalSales + 1 VoidSales (both with Cartesian product risk)
    transactions.extend([
        BaseTransaction(
            tenant_id=tenant_id,
            store_code=test_store,
            terminal_no=3,
            business_date=test_date,
            business_counter=1,
            open_counter=1,
            transaction_no=1,
            transaction_type=TransactionType.NormalSales.value,
            sales={
                "total_amount": 3000,
                "total_amount_with_tax": 3300,
                "tax_amount": 300,
                "total_quantity": 2,
                "change_amount": 0,
                "total_discount_amount": 0,
                "is_cancelled": False
            },
            payments=[
                {"payment_no": 1, "payment_code": "01", "amount": 1650, "description": "Cash"},
                {"payment_no": 2, "payment_code": "11", "amount": 1650, "description": "Credit"}
            ],
            taxes=[
                {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 200, "target_amount": 2000, "target_quantity": 1},
                {"tax_no": 2, "tax_code": "02", "tax_name": "軽減税率8%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}
            ],
            line_items=[
                {"line_no": 1, "item_code": "ITEM006", "quantity": 1, "unit_price": 2000, "amount": 2000, "tax_code": "01"},
                {"line_no": 2, "item_code": "ITEM007", "quantity": 1, "unit_price": 1000, "amount": 1000, "tax_code": "02"}
            ]
        ),
        BaseTransaction(
            tenant_id=tenant_id,
            store_code=test_store,
            terminal_no=3,
            business_date=test_date,
            business_counter=2,
            open_counter=1,
            transaction_no=2,
            transaction_type=TransactionType.VoidSales.value,
            sales={
                "total_amount": 1000,
                "total_amount_with_tax": 1100,
                "tax_amount": 100,
                "total_quantity": 2,
                "change_amount": 0,
                "total_discount_amount": 0,
                "is_cancelled": False
            },
            payments=[
                {"payment_no": 1, "payment_code": "01", "amount": 550, "description": "Cash"},
                {"payment_no": 2, "payment_code": "11", "amount": 550, "description": "Credit"}
            ],
            taxes=[
                {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 60, "target_amount": 600, "target_quantity": 1},
                {"tax_no": 2, "tax_code": "02", "tax_name": "軽減税率8%", "tax_amount": 40, "target_amount": 400, "target_quantity": 1}
            ],
            line_items=[
                {"line_no": 1, "item_code": "ITEM008", "quantity": 1, "unit_price": 600, "amount": 600, "tax_code": "01"},
                {"line_no": 2, "item_code": "ITEM009", "quantity": 1, "unit_price": 400, "amount": 400, "tax_code": "02"}
            ]
        )
    ])

    insert_result = await collection.insert_many([t.model_dump() for t in transactions])
    print(f"Inserted {len(insert_result.inserted_ids)} documents")

    # Verify data was inserted
    count = await collection.count_documents({})
    print(f"Collection now has {count} documents")

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
    # NormalSales: 1000 + 2000 + 1500 + 3000 = 7500 + 750 tax = 8250
    # ReturnSales: -500 - 50 tax = -550 (factor = -1)
    # VoidSales: -800 - 1000 = -1800 - 180 tax = -1980 (factor = -1)
    # Net: 7500 - 500 - 1800 = 5200 + (750 - 50 - 180) = 520 tax
    # Total: 5200 + 520 = 5720

    expected_sales = 5200  # 7500 - 500 - 1800
    expected_tax = 520     # 750 - 50 - 180
    expected_payment = 5720

    sales_with_tax = sales_net + tax_total

    print("\n=== MIXED TRANSACTION TYPES TEST ===")
    print(f"Transaction Types:")
    print(f"  - NormalSales: 4 transactions (T1: 2, T2: 1, T3: 1)")
    print(f"  - ReturnSales: 1 transaction (T2: 1)")
    print(f"  - VoidSales: 2 transactions (T2: 1, T3: 1)")
    print(f"  - Total: 7 transactions")
    print(f"Cartesian Product Risk:")
    print(f"  - T3-1 (NormalSales): 2 payments × 2 taxes = 4x")
    print(f"  - T3-2 (VoidSales): 2 payments × 2 taxes = 4x")
    print(f"Sales Net: {sales_net}")
    print(f"Tax Total: {tax_total}")
    print(f"Sales + Tax: {sales_with_tax}")
    print(f"Payment Total: {payment_total}")
    print(f"Difference: {payment_total - sales_with_tax}")

    assert sales_net == expected_sales, f"Expected sales net {expected_sales}, got {sales_net}"
    assert tax_total == expected_tax, f"Expected tax total {expected_tax}, got {tax_total}"
    assert payment_total == expected_payment, f"Expected payment total {expected_payment}, got {payment_total}"

    # THE CRITICAL ASSERTION
    assert payment_total == sales_with_tax, \
        f"CRITICAL ERROR: Payment total ({payment_total}) != Sales + Tax ({sales_with_tax}). " \
        f"Difference: {payment_total - sales_with_tax}. " \
        f"Mixed transaction types aggregation has errors!"

    print("✅ PASS: Mixed transaction types integrity verified")
    print("✅ All 3 transaction types (Normal, Return, Void) aggregate correctly")
    print("✅ Factoring (factor = 1 or -1) works correctly")
    print("✅ Cartesian product eliminated even with void transactions")
    print("✅ Payment Total = Sales Net + Tax")
    print("=====================================\n")
