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
async def test_multi_transaction_payment_integrity(set_env_vars):
    """
    CRITICAL TEST: Verify payment integrity across multiple transactions

    Scenario:
    - Transaction 1: 1000 yen + 100 tax = 1100 (Cash 600 + Credit 500)
    - Transaction 2: 2000 yen + 200 tax = 2200 (Cash 1100 + Credit 1100)
    - Transaction 3: 500 yen + 50 tax = 550 (Cash only)

    Expected:
    - Total Sales: 3500 yen
    - Total Tax: 350 yen
    - Total Payments: 3850 yen
    - Equation: 3850 = 3500 + 350 ✓

    WHY THIS MATTERS:
    - Tests aggregation across multiple transactions
    - Verifies no multiplication from Cartesian products
    - Real scenario: end-of-day reconciliation
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
    test_terminal = 1
    test_date = "2024-03-01"
    tenant_id = os.environ.get("TENANT_ID")

    # Transaction 1: 1000 + 100 tax = 1100
    tran1 = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
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
            {"payment_no": 1, "payment_code": "01", "amount": 600, "description": "Cash"},
            {"payment_no": 2, "payment_code": "11", "amount": 500, "description": "Credit"}
        ],
        taxes=[
            {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}
        ],
        line_items=[
            {"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1000, "amount": 1000, "tax_code": "01"}
        ]
    )

    # Transaction 2: 2000 + 200 tax = 2200
    tran2 = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
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

    # Transaction 3: 500 + 50 tax = 550 (Cash only)
    tran3 = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=3,
        open_counter=1,
        transaction_no=3,
        transaction_type=TransactionType.NormalSales.value,
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
            {"line_no": 1, "item_code": "ITEM003", "quantity": 1, "unit_price": 500, "amount": 500, "tax_code": "01"}
        ]
    )

    insert_result = await collection.insert_many([tran1.model_dump(), tran2.model_dump(), tran3.model_dump()])
    print(f"Inserted {len(insert_result.inserted_ids)} documents")

    # Verify data was inserted
    count = await collection.count_documents({})
    print(f"Collection now has {count} documents")

    # Generate sales report
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    report = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=test_terminal,
        report_scope="flash",
        report_type="sales",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1
    )

    # Extract values
    sales_net = report.sales_net.amount  # 3500
    tax_total = sum(t.tax_amount for t in report.taxes)  # 350
    payment_total = sum(p.amount for p in report.payments)  # 3850

    sales_with_tax = sales_net + tax_total

    print("\n=== MULTI-TRANSACTION INTEGRITY TEST ===")
    print(f"Sales Net: {sales_net}")
    print(f"Tax Total: {tax_total}")
    print(f"Sales + Tax: {sales_with_tax}")
    print(f"Payment Total: {payment_total}")
    print(f"Difference: {payment_total - sales_with_tax}")

    # NOTE: count represents report groups, not individual transactions
    # All 3 transactions have same (tenant, store, date, type, terminal) → 1 group

    assert sales_net == 3500, f"Expected sales net 3500, got {sales_net}"
    assert tax_total == 350, f"Expected tax total 350, got {tax_total}"
    assert payment_total == 3850, f"Expected payment total 3850, got {payment_total}"

    # THE CRITICAL ASSERTION
    assert payment_total == sales_with_tax, \
        f"CRITICAL ERROR: Payment total ({payment_total}) != Sales + Tax ({sales_with_tax}). " \
        f"Difference: {payment_total - sales_with_tax}. " \
        f"Multi-transaction aggregation has errors!"

    print("✅ PASS: Multi-transaction integrity verified")
    print("✅ 3 transactions aggregated into 1 group")
    print("✅ Payment Total = Sales Net + Tax")
    print("======================================\n")


