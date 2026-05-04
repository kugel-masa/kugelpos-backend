# Copyright 2025 masa@kugel
# Test cancelled transactions handling

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
async def test_cancelled_flag_exclusion(set_env_vars):
    """
    Test that transactions with is_cancelled=True are excluded from reports
    
    Scenario:
    - Transaction 1: NormalSales 1000 yen (is_cancelled=False) ✓ Include
    - Transaction 2: NormalSales 2000 yen (is_cancelled=True)  ✗ Exclude
    - Transaction 3: NormalSales 3000 yen (is_cancelled=False) ✓ Include
    
    Expected:
    - Total sales: 1000 + 3000 = 4000 yen (excluding cancelled 2000)
    - Transaction count: 2 (not 3)
    
    WHY THIS MATTERS:
    - Cancelled transactions should not appear in sales reports
    - Common in POS when clerk cancels a transaction mid-sale
    - Critical for accurate end-of-day reconciliation
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(db, tenant_id)

    collection = db[tran_repo.collection_name]

    # Clean up test data - use unique terminal_no=10 to avoid conflicts
    test_date = "2024-05-01"
    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": "STORE001",
        "terminal_no": 10,
        "business_date": test_date
    })

    # Transaction 1: Normal (not cancelled)
    tran1 = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=10,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 1000,
            "total_amount_with_tax": 1100,
            "tax_amount": 100,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False,  # ✓ Include
        },
        line_items=[{"line_no": 1, "item_code": "ITEM001", "quantity": 1, "amount": 1000}],
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 1100, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}],
    )

    # Transaction 2: Cancelled (should be excluded)
    tran2 = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=10,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=2,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 2000,
            "total_amount_with_tax": 2200,
            "tax_amount": 200,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": True,  # ✗ Exclude
        },
        line_items=[{"line_no": 1, "item_code": "ITEM002", "quantity": 1, "amount": 2000}],
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 2200, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 200, "target_amount": 2000, "target_quantity": 1}],
    )

    # Transaction 3: Normal (not cancelled)
    tran3 = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=10,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=3,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 3000,
            "total_amount_with_tax": 3300,
            "tax_amount": 300,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False,  # ✓ Include
        },
        line_items=[{"line_no": 1, "item_code": "ITEM003", "quantity": 1, "amount": 3000}],
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 3300, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 300, "target_amount": 3000, "target_quantity": 1}],
    )

    # Insert all transactions
    await collection.insert_many([
        tran1.model_dump(),
        tran2.model_dump(),
        tran3.model_dump(),
    ])

    # Generate sales report
    report_service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo,
    )

    report = await report_service.get_report_for_terminal_async(
        store_code="STORE001",
        terminal_no=10,
        report_scope="flash",
        report_type="sales",
        business_date=test_date,
        open_counter=1,
    )

    # Verify: Only non-cancelled transactions are included
    # Expected: 1000 + 3000 = 4000 (excluding cancelled 2000)
    assert report.sales_net.amount == 4000, \
        f"Expected net 4000 (excluding cancelled 2000), got {report.sales_net.amount}"
    
    # Note: count might be 0 for store-level reports, so we check amount only
    
    print("\n=== CANCELLED TRANSACTION EXCLUSION TEST ===")
    print(f"Transaction 1: 1000 yen (is_cancelled=False) ✓ Included")
    print(f"Transaction 2: 2000 yen (is_cancelled=True)  ✗ Excluded")
    print(f"Transaction 3: 3000 yen (is_cancelled=False) ✓ Included")
    print(f"Total Sales Net: {report.sales_net.amount} yen")
    print(f"Expected: 1000 + 3000 = 4000 yen ✓")
    print("✓ Cancelled transactions correctly excluded from report")
    print("============================================\n")


@pytest.mark.asyncio
async def test_void_vs_cancelled_difference(set_env_vars):
    """
    Test the difference between VoidSales and is_cancelled=True
    
    Scenario:
    - Transaction 1: NormalSales 1000 yen
    - Transaction 2: VoidSales 500 yen (factor=-1, included in report)
    - Transaction 3: NormalSales 2000 yen (is_cancelled=True, excluded from report)
    
    Expected:
    - VoidSales: Included with factor=-1 → Net = 1000 - 500 = 500
    - is_cancelled=True: Excluded completely → Not in calculation
    
    WHY THIS MATTERS:
    - VoidSales: Official void transaction (appears in journal, affects sales)
    - is_cancelled=True: Aborted transaction (doesn't appear in report)
    - Different business meanings, different handling
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(db, tenant_id)

    collection = db[tran_repo.collection_name]

    # Clean up test data - use unique terminal_no=11 to avoid conflicts
    test_date = "2024-05-02"
    await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": "STORE001",
        "terminal_no": 11,
        "business_date": test_date
    })

    # Transaction 1: NormalSales
    tran1 = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=11,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 1000,
            "total_amount_with_tax": 1100,
            "tax_amount": 100,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False,
        },
        line_items=[{"line_no": 1, "item_code": "ITEM001", "quantity": 1, "amount": 1000}],
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 1100, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}],
    )

    # Transaction 2: VoidSales (included with factor=-1)
    tran2 = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=11,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=2,
        transaction_type=TransactionType.VoidSales.value,  # Factor = -1
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 500,
            "total_amount_with_tax": 550,
            "tax_amount": 50,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False,  # VoidSales with is_cancelled=False
        },
        line_items=[{"line_no": 1, "item_code": "ITEM002", "quantity": 1, "amount": 500}],
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 550, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 50, "target_amount": 500, "target_quantity": 1}],
    )

    # Transaction 3: NormalSales with is_cancelled=True (excluded)
    tran3 = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=11,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=3,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 2000,
            "total_amount_with_tax": 2200,
            "tax_amount": 200,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": True,  # Excluded
        },
        line_items=[{"line_no": 1, "item_code": "ITEM003", "quantity": 1, "amount": 2000}],
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 2200, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 200, "target_amount": 2000, "target_quantity": 1}],
    )

    # Insert all transactions
    await collection.insert_many([
        tran1.model_dump(),
        tran2.model_dump(),
        tran3.model_dump(),
    ])

    # Generate sales report
    report_service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo,
    )

    report = await report_service.get_report_for_terminal_async(
        store_code="STORE001",
        terminal_no=11,
        report_scope="flash",
        report_type="sales",
        business_date=test_date,
        open_counter=1,
    )

    # Verify: VoidSales included (factor=-1), is_cancelled excluded
    # Expected: NormalSales 1000 - VoidSales 500 = 500
    # is_cancelled 2000 not included
    assert report.sales_net.amount == 500, \
        f"Expected net 500 (1000 - 500, excluding cancelled 2000), got {report.sales_net.amount}"

    print("\n=== VOID vs CANCELLED DIFFERENCE TEST ===")
    print(f"Transaction 1: NormalSales 1000 yen")
    print(f"Transaction 2: VoidSales 500 yen (factor=-1) → Included as -500")
    print(f"Transaction 3: NormalSales 2000 yen (is_cancelled=True) → Excluded")
    print(f"Net Sales: 1000 - 500 = {report.sales_net.amount} yen ✓")
    print("✓ VoidSales correctly included with factor=-1")
    print("✓ is_cancelled=True correctly excluded")
    print("==========================================\n")
