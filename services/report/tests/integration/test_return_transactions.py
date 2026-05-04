# Copyright 2025 masa@kugel
# Test return transaction aggregation and processing

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
async def test_return_transaction_basic(set_env_vars):
    """
    Test basic return transaction aggregation.

    Scenario:
    - Normal Sale: 1000 yen (1100 with tax)
    - Return Sale: 500 yen (550 with tax)

    Expected:
    - Sales Gross: 1000
    - Returns: 500 (stored as positive, factored during aggregation)
    - Sales Net: 500 (1000 - 500)
    - Payment: 550 (1100 - 550)
    - Tax: 50 (100 - 50)
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
    test_date = "2024-01-30"
    tenant_id = os.environ.get("TENANT_ID")

    # Normal Sale
    tran_sale = BaseTransaction(
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
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 1100, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1000, "amount": 1000}]
    )

    # Return Sale
    tran_return = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
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
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 550, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 50, "target_amount": 500, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 500, "amount": 500}]
    )

    await collection.insert_one(tran_sale.model_dump())
    await collection.insert_one(tran_return.model_dump())

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

    # Verify sales calculations (Issue #85: now uses tax-inclusive amounts)
    # Sales gross: 1100 (tax-inclusive)
    # Returns: 550 (tax-inclusive)
    # Net tax: 100 - 50 = 50
    # Sales net: 1100 - 550 - 0 - 0 - 50 = 500
    assert report.sales_gross.amount == 1100, f"Expected sales gross 1100, got {report.sales_gross.amount}"
    assert report.sales_net.amount == 500, f"Expected sales net 500, got {report.sales_net.amount}"
    assert report.returns.amount == 550, f"Expected returns 550, got {report.returns.amount}"

    # Verify payment
    cash_payment = next((p for p in report.payments if p.payment_name == "Cash"), None)
    assert cash_payment is not None, "Cash payment should exist"
    assert cash_payment.amount == 550, f"Expected payment 550, got {cash_payment.amount}"
    assert cash_payment.count == 0, f"Expected net count 0 (1 sale - 1 return), got {cash_payment.count}"

    # Verify tax
    tax = next((t for t in report.taxes if t.tax_name == "消費税10%"), None)
    assert tax is not None, "Tax should exist"
    assert tax.tax_amount == 50, f"Expected tax 50, got {tax.tax_amount}"

    print("\n=== RETURN TRANSACTION BASIC TEST ===")
    print(f"Sales Gross: {report.sales_gross.amount}")
    print(f"Returns: {report.returns.amount}")
    print(f"Sales Net: {report.sales_net.amount}")
    print(f"Payment: {cash_payment.amount}")
    print(f"Tax: {tax.tax_amount}")
    print("✓ Return transactions correctly aggregated")
    print("=====================================\n")


@pytest.mark.asyncio
async def test_return_exceeds_sales(set_env_vars):
    """
    Test when return amount exceeds sales amount (negative net sales).

    Scenario:
    - Normal Sale: 1000 yen (1100 with tax)
    - Return Sale: 1500 yen (1650 with tax)

    Expected:
    - Sales Net: -500 (1000 - 1500)
    - check_report_data.py should handle negative net sales correctly
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
    test_date = "2024-01-30"
    tenant_id = os.environ.get("TENANT_ID")

    # Normal Sale
    tran_sale = BaseTransaction(
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
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 1100, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1000, "amount": 1000}]
    )

    # Return Sale (exceeds sales)
    tran_return = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=2,
        open_counter=1,
        transaction_no=2,
        transaction_type=TransactionType.ReturnSales.value,
        sales={
            "total_amount": 1500,
            "total_amount_with_tax": 1650,
            "tax_amount": 150,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 1650, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 150, "target_amount": 1500, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1500, "amount": 1500}]
    )

    await collection.insert_one(tran_sale.model_dump())
    await collection.insert_one(tran_return.model_dump())

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

    # Verify negative net sales (Issue #85: now uses tax-inclusive amounts)
    # Sales gross: 1100 (tax-inclusive)
    # Returns: 1650 (tax-inclusive)
    # Net tax: 100 - 150 = -50
    # Sales net: 1100 - 1650 - 0 - 0 - (-50) = -500
    assert report.sales_net.amount == -500, f"Expected sales net -500, got {report.sales_net.amount}"
    assert report.returns.amount == 1650, f"Expected returns 1650, got {report.returns.amount}"

    # Verify payment (1100 - 1650 = -550)
    cash_payment = next((p for p in report.payments if p.payment_name == "Cash"), None)
    assert cash_payment is not None, "Cash payment should exist"
    assert cash_payment.amount == -550, f"Expected payment -550, got {cash_payment.amount}"
    assert cash_payment.count == 0, f"Expected net count 0 (1 sale - 1 return), got {cash_payment.count}"

    print("\n=== RETURN EXCEEDS SALES TEST ===")
    print(f"Sales Net: {report.sales_net.amount} (negative)")
    print(f"Returns: {report.returns.amount}")
    print(f"Payment: {cash_payment.amount} (negative)")
    print("✓ Negative net sales handled correctly")
    print("=====================================\n")


@pytest.mark.asyncio
async def test_multiple_returns_same_day(set_env_vars):
    """
    Test multiple return transactions in a single day.

    Scenario:
    - Sale 1: 1000 yen
    - Sale 2: 2000 yen
    - Return 1: 300 yen
    - Return 2: 500 yen

    Expected:
    - Sales Gross: 3000
    - Returns: 800 (300 + 500)
    - Sales Net: 2200 (3000 - 800)
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
    test_date = "2024-01-30"
    tenant_id = os.environ.get("TENANT_ID")

    transactions = []

    # Sale 1: 1000 yen
    transactions.append(BaseTransaction(
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
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 1100, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1000, "amount": 1000}]
    ))

    # Sale 2: 2000 yen
    transactions.append(BaseTransaction(
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
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 2200, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 200, "target_amount": 2000, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM002", "quantity": 1, "unit_price": 2000, "amount": 2000}]
    ))

    # Return 1: 300 yen
    transactions.append(BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=3,
        open_counter=1,
        transaction_no=3,
        transaction_type=TransactionType.ReturnSales.value,
        sales={
            "total_amount": 300,
            "total_amount_with_tax": 330,
            "tax_amount": 30,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 330, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 30, "target_amount": 300, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 300, "amount": 300}]
    ))

    # Return 2: 500 yen
    transactions.append(BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=4,
        open_counter=1,
        transaction_no=4,
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
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 550, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 50, "target_amount": 500, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM002", "quantity": 1, "unit_price": 500, "amount": 500}]
    ))

    for tran in transactions:
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

    # Verify aggregation (Issue #85: now uses tax-inclusive amounts)
    # Sales gross: 1100 + 2200 = 3300 (tax-inclusive)
    # Returns: 330 + 550 = 880 (tax-inclusive)
    # Net tax: (100 + 200) - (30 + 50) = 220
    # Sales net: 3300 - 880 - 0 - 0 - 220 = 2200
    assert report.sales_gross.amount == 3300, f"Expected sales gross 3300, got {report.sales_gross.amount}"
    assert report.returns.amount == 880, f"Expected returns 880, got {report.returns.amount}"
    assert report.sales_net.amount == 2200, f"Expected sales net 2200, got {report.sales_net.amount}"

    # Verify payment (1100 + 2200 - 330 - 550 = 2420)
    cash_payment = next((p for p in report.payments if p.payment_name == "Cash"), None)
    assert cash_payment is not None, "Cash payment should exist"
    assert cash_payment.amount == 2420, f"Expected payment 2420, got {cash_payment.amount}"
    assert cash_payment.count == 0, f"Expected net count 0 (2 sales - 2 returns), got {cash_payment.count}"

    print("\n=== MULTIPLE RETURNS TEST ===")
    print(f"Sales Gross: {report.sales_gross.amount}")
    print(f"Returns: {report.returns.amount}")
    print(f"Sales Net: {report.sales_net.amount}")
    print(f"Payment Count: {cash_payment.count}")
    print("✓ Multiple returns correctly aggregated")
    print("=============================\n")
