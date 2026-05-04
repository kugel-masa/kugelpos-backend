# Copyright 2025 masa@kugel
# Test void transaction aggregation and factoring

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
async def test_void_sales_basic(set_env_vars):
    """
    Test basic void sales transaction.

    Scenario:
    - Normal Sale: 1000 yen
    - Void Sales: 1000 yen (cancels the sale)

    Expected:
    - Sales Net: 0 (1000 - 1000)
    - Payment: 0 (1100 - 1100)
    - Transaction count for payment: 0 (1 sale - 1 void)
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
    test_date = "2024-01-31"
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

    # Void Sales (cancels the above)
    tran_void = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=2,
        open_counter=1,
        transaction_no=2,
        transaction_type=TransactionType.VoidSales.value,
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

    await collection.insert_one(tran_sale.model_dump())
    await collection.insert_one(tran_void.model_dump())

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

    # Verify void cancellation
    assert report.sales_net.amount == 0, f"Expected sales net 0, got {report.sales_net.amount}"

    # Verify payment (should be 0 after void)
    cash_payment = next((p for p in report.payments if p.payment_name == "Cash"), None)
    assert cash_payment is not None, "Cash payment should exist"
    assert cash_payment.amount == 0, f"Expected payment 0, got {cash_payment.amount}"
    assert cash_payment.count == 0, f"Expected net count 0 (1 sale - 1 void), got {cash_payment.count}"

    print("\n=== VOID SALES BASIC TEST ===")
    print(f"Sales Net: {report.sales_net.amount} (voided)")
    print(f"Payment: {cash_payment.amount} (voided)")
    print("✓ Void sales correctly cancels normal sales")
    print("=============================\n")


@pytest.mark.asyncio
async def test_void_return_basic(set_env_vars):
    """
    Test basic void return transaction.

    Scenario:
    - Return Sale: 500 yen
    - Void Return: 500 yen (cancels the return)

    Expected:
    - Returns: 0 (500 - 500)
    - Sales Net: 0
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
    test_date = "2024-01-31"
    tenant_id = os.environ.get("TENANT_ID")

    # Return Sale
    tran_return = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=1,
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

    # Void Return (cancels the above)
    tran_void_return = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=2,
        open_counter=1,
        transaction_no=2,
        transaction_type=TransactionType.VoidReturn.value,
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

    await collection.insert_one(tran_return.model_dump())
    await collection.insert_one(tran_void_return.model_dump())

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

    # Verify void return cancellation
    assert report.returns.amount == 0, f"Expected returns 0, got {report.returns.amount}"
    assert report.sales_net.amount == 0, f"Expected sales net 0, got {report.sales_net.amount}"

    # Verify payment
    cash_payment = next((p for p in report.payments if p.payment_name == "Cash"), None)
    assert cash_payment is not None, "Cash payment should exist"
    assert cash_payment.amount == 0, f"Expected payment 0, got {cash_payment.amount}"
    assert cash_payment.count == 0, f"Expected net count 0 (1 return - 1 void return), got {cash_payment.count}"

    print("\n=== VOID RETURN BASIC TEST ===")
    print(f"Returns: {report.returns.amount} (voided)")
    print(f"Sales Net: {report.sales_net.amount}")
    print("✓ Void return correctly cancels return sale")
    print("==============================\n")


@pytest.mark.asyncio
async def test_complex_void_scenario(set_env_vars):
    """
    Test complex scenario with multiple voids.

    Scenario:
    - Sale 1: 1000 yen
    - Sale 2: 2000 yen
    - Void Sale 1: 1000 yen (cancels Sale 1)
    - Return 1: 500 yen
    - Void Return 1: 500 yen (cancels Return 1)
    - Sale 3: 3000 yen

    Expected:
    - Sales Net: 5000 (2000 + 3000, Sale 1 voided)
    - Returns: 0 (return voided)
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
    test_date = "2024-01-31"
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

    # Void Sale 1
    transactions.append(BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=3,
        open_counter=1,
        transaction_no=3,
        transaction_type=TransactionType.VoidSales.value,
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

    # Return 1: 500 yen
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
        line_items=[{"line_no": 1, "item_code": "ITEM003", "quantity": 1, "unit_price": 500, "amount": 500}]
    ))

    # Void Return 1
    transactions.append(BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=5,
        open_counter=1,
        transaction_no=5,
        transaction_type=TransactionType.VoidReturn.value,
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
        line_items=[{"line_no": 1, "item_code": "ITEM003", "quantity": 1, "unit_price": 500, "amount": 500}]
    ))

    # Sale 3: 3000 yen
    transactions.append(BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=6,
        open_counter=1,
        transaction_no=6,
        transaction_type=TransactionType.NormalSales.value,
        sales={
            "total_amount": 3000,
            "total_amount_with_tax": 3300,
            "tax_amount": 300,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[{"payment_no": 1, "payment_code": "01", "amount": 3300, "description": "Cash"}],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 300, "target_amount": 3000, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM004", "quantity": 1, "unit_price": 3000, "amount": 3000}]
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

    # Verify complex void scenario
    # Sales: 1000 + 2000 - 1000 + 3000 = 5000
    assert report.sales_net.amount == 5000, f"Expected sales net 5000, got {report.sales_net.amount}"

    # Returns: 500 - 500 = 0
    assert report.returns.amount == 0, f"Expected returns 0, got {report.returns.amount}"

    # Payment: 1100 + 2200 - 1100 - 550 + 550 + 3300 = 5500
    # Net count: Sale1(1) + Sale2(1) + VoidSale1(-1) + Return(-1) + VoidReturn(+1) + Sale3(1) = 2
    cash_payment = next((p for p in report.payments if p.payment_name == "Cash"), None)
    assert cash_payment is not None, "Cash payment should exist"
    assert cash_payment.amount == 5500, f"Expected payment 5500, got {cash_payment.amount}"
    assert cash_payment.count == 2, f"Expected net count 2, got {cash_payment.count}"

    print("\n=== COMPLEX VOID SCENARIO TEST ===")
    print(f"Sales Net: {report.sales_net.amount}")
    print(f"Returns: {report.returns.amount}")
    print(f"Payment: {cash_payment.amount}")
    print(f"Transaction Count: {cash_payment.count}")
    print("✓ Complex void scenario handled correctly")
    print("==================================\n")


@pytest.mark.asyncio
async def test_multiple_voids_same_transaction_type(set_env_vars):
    """
    Test multiple void transactions of the same type.

    Scenario:
    - Sale 1: 1000 yen
    - Sale 2: 2000 yen
    - Sale 3: 3000 yen
    - Void Sale (1st): 1000 yen
    - Void Sale (2nd): 2000 yen

    Expected:
    - Sales Net: 3000 (only Sale 3 remains)
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
    test_date = "2024-01-31"
    tenant_id = os.environ.get("TENANT_ID")

    transactions = []

    # Create 3 sales
    for i in range(1, 4):
        transactions.append(BaseTransaction(
            tenant_id=tenant_id,
            store_code=test_store,
            terminal_no=test_terminal,
            business_date=test_date,
            business_counter=i,
            open_counter=1,
            transaction_no=i,
            transaction_type=TransactionType.NormalSales.value,
            sales={
                "total_amount": i * 1000,
                "total_amount_with_tax": i * 1100,
                "tax_amount": i * 100,
                "total_quantity": 1,
                "change_amount": 0,
                "total_discount_amount": 0,
                "is_cancelled": False
            },
            payments=[{"payment_no": 1, "payment_code": "01", "amount": i * 1100, "description": "Cash"}],
            taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": i * 100, "target_amount": i * 1000, "target_quantity": 1}],
            line_items=[{"line_no": 1, "item_code": f"ITEM00{i}", "quantity": 1, "unit_price": i * 1000, "amount": i * 1000}]
        ))

    # Void first two sales
    for i in range(1, 3):
        transactions.append(BaseTransaction(
            tenant_id=tenant_id,
            store_code=test_store,
            terminal_no=test_terminal,
            business_date=test_date,
            business_counter=i + 3,
            open_counter=1,
            transaction_no=i + 3,
            transaction_type=TransactionType.VoidSales.value,
            sales={
                "total_amount": i * 1000,
                "total_amount_with_tax": i * 1100,
                "tax_amount": i * 100,
                "total_quantity": 1,
                "change_amount": 0,
                "total_discount_amount": 0,
                "is_cancelled": False
            },
            payments=[{"payment_no": 1, "payment_code": "01", "amount": i * 1100, "description": "Cash"}],
            taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": i * 100, "target_amount": i * 1000, "target_quantity": 1}],
            line_items=[{"line_no": 1, "item_code": f"ITEM00{i}", "quantity": 1, "unit_price": i * 1000, "amount": i * 1000}]
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

    # Verify only Sale 3 remains
    # Sales: 1000 + 2000 + 3000 - 1000 - 2000 = 3000
    assert report.sales_net.amount == 3000, f"Expected sales net 3000, got {report.sales_net.amount}"

    # Payment: 1100 + 2200 + 3300 - 1100 - 2200 = 3300
    # Net count: Sale1(1) + Sale2(1) + Sale3(1) + VoidSale1(-1) + VoidSale2(-1) = 1
    cash_payment = next((p for p in report.payments if p.payment_name == "Cash"), None)
    assert cash_payment is not None, "Cash payment should exist"
    assert cash_payment.amount == 3300, f"Expected payment 3300, got {cash_payment.amount}"
    assert cash_payment.count == 1, f"Expected net count 1, got {cash_payment.count}"

    print("\n=== MULTIPLE VOIDS SAME TYPE TEST ===")
    print(f"Sales Net: {report.sales_net.amount} (only Sale 3)")
    print(f"Payment: {cash_payment.amount}")
    print(f"Transaction Count: {cash_payment.count}")
    print("✓ Multiple voids correctly processed")
    print("=====================================\n")
