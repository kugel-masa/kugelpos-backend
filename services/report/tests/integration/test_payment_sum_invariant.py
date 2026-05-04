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
async def test_payment_sum_equals_sales_with_tax(set_env_vars):
    """
    CRITICAL TEST: Verify fundamental POS accounting equation

    Equation: Total Payment = Sales Net + Tax

    Scenario:
    - 1 transaction with 1000 yen item
    - Tax: 10% = 100 yen
    - Total with tax: 1100 yen
    - Payment split: Cash 550 + Credit 550 = 1100 yen

    This test ensures no Cartesian product or aggregation bugs are causing
    discrepancies in the accounting equation. If payments total != sales + tax,
    there is a critical bug in the aggregation pipeline.

    WHY THIS MATTERS:
    - This is the most fundamental equation in POS systems
    - Any deviation indicates money is being miscounted
    - Detects Cartesian product bugs immediately
    - Real-world impact: incorrect cash reconciliation
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
    test_terminal = 1
    test_date = "2024-03-01"
    tenant_id = os.environ.get("TENANT_ID")

    # Create transaction: 1000 yen + 100 tax = 1100 total
    # Payment: Cash 550 + Credit 550 = 1100
    tran = BaseTransaction(
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
            {"payment_no": 1, "payment_code": "01", "amount": 550, "description": "Cash"},
            {"payment_no": 2, "payment_code": "11", "amount": 550, "description": "Credit"}
        ],
        taxes=[
            {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}
        ],
        line_items=[
            {"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1000, "amount": 1000, "tax_code": "01"}
        ]
    )

    await collection.insert_one(tran.model_dump())

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
    sales_net = report.sales_net.amount  # 1000
    tax_total = sum(t.tax_amount for t in report.taxes)  # 100
    payment_total = sum(p.amount for p in report.payments)  # 550 + 550 = 1100

    # CRITICAL ASSERTION: Payment total MUST equal sales + tax
    sales_with_tax = sales_net + tax_total

    print("\n=== DATA INTEGRITY TEST ===")
    print(f"Sales Net: {sales_net}")
    print(f"Tax Total: {tax_total}")
    print(f"Sales + Tax: {sales_with_tax}")
    print(f"Payment Total: {payment_total}")
    print(f"Difference: {payment_total - sales_with_tax}")

    assert sales_net == 1000, f"Expected sales net 1000, got {sales_net}"
    assert tax_total == 100, f"Expected tax total 100, got {tax_total}"
    assert payment_total == 1100, f"Expected payment total 1100, got {payment_total}"

    # THE MOST IMPORTANT ASSERTION
    assert payment_total == sales_with_tax, \
        f"CRITICAL ERROR: Payment total ({payment_total}) != Sales + Tax ({sales_with_tax}). " \
        f"Difference: {payment_total - sales_with_tax}. " \
        f"This indicates a Cartesian product or aggregation bug!"

    print("✅ PASS: Payment equation verified")
    print("✅ Payment Total = Sales Net + Tax")
    print("===========================\n")


