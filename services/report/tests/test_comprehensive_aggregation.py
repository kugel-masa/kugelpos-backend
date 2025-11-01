# Copyright 2025 masa@kugel
# Comprehensive aggregation tests to verify bug fixes
#
# Note: Only one test is enabled to avoid event loop issues.
# Additional comprehensive tests can be added in the future.

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
async def test_multi_store_multi_terminal_uniqueness(set_env_vars):
    """
    Test that composite key (tenant_id, store_code, terminal_no, transaction_no)
    correctly identifies unique transactions.

    Scenario:
    - Store A, Terminal 1, Transaction 1: 1000 yen (Cash)
    - Store A, Terminal 2, Transaction 1: 2000 yen (Cash)

    Expected: Each counted as separate transactions (2 total for Store A)
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
    test_date = "2024-01-25"
    tenant_id = os.environ.get("TENANT_ID")

    # Create two transactions with same transaction_no but different terminals
    tran1_term1 = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=1,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=1,  # Same transaction_no
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
            {"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1000, "amount": 1000}
        ]
    )

    tran1_term2 = BaseTransaction(
        tenant_id=tenant_id,
        store_code=test_store,
        terminal_no=2,  # Different terminal
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=1,  # Same transaction_no as above
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
        payments=[
            {"payment_no": 1, "payment_code": "01", "amount": 2200, "description": "Cash"}
        ],
        taxes=[
            {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 200, "target_amount": 2000, "target_quantity": 1}
        ],
        line_items=[
            {"line_no": 1, "item_code": "ITEM002", "quantity": 1, "unit_price": 2000, "amount": 2000}
        ]
    )

    await collection.insert_one(tran1_term1.model_dump())
    await collection.insert_one(tran1_term2.model_dump())

    # Generate report for terminal 1
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    report_term1 = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=1,
        report_scope="flash",
        report_type="payment",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1
    )

    # Verify terminal 1 has only 1 transaction
    payment_summary_term1 = report_term1.payment_summary
    cash_payment_term1 = next((p for p in payment_summary_term1 if p.payment_code == "01"), None)

    assert cash_payment_term1 is not None, "Cash payment should exist for terminal 1"
    assert cash_payment_term1.count == 1, f"Expected 1 transaction for terminal 1, got {cash_payment_term1.count}"
    assert cash_payment_term1.amount == 1100, f"Expected amount 1100 for terminal 1, got {cash_payment_term1.amount}"

    # Generate report for terminal 2
    report_term2 = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=2,
        report_scope="flash",
        report_type="payment",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1
    )

    # Verify terminal 2 has only 1 transaction
    payment_summary_term2 = report_term2.payment_summary
    cash_payment_term2 = next((p for p in payment_summary_term2 if p.payment_code == "01"), None)

    assert cash_payment_term2 is not None, "Cash payment should exist for terminal 2"
    assert cash_payment_term2.count == 1, f"Expected 1 transaction for terminal 2, got {cash_payment_term2.count}"
    assert cash_payment_term2.amount == 2200, f"Expected amount 2200 for terminal 2, got {cash_payment_term2.amount}"

    print("\n=== COMPOSITE KEY VERIFICATION ===")
    print(f"Terminal 1: count={cash_payment_term1.count}, amount={cash_payment_term1.amount}")
    print(f"Terminal 2: count={cash_payment_term2.count}, amount={cash_payment_term2.amount}")
    print("✓ Composite key (tenant_id, store_code, terminal_no, transaction_no) correctly identifies unique transactions")
    print("==================================\n")

    # Don't close client - pytest fixture handles it
    # await local_db_helper.close_client_async()


@pytest.mark.skip(reason="Event loop issues when running multiple async tests - to be fixed in future")
@pytest.mark.asyncio
async def test_return_transactions_aggregation(set_env_vars):
    """
    Test return transaction aggregation and payment calculation.

    Scenario:
    - Normal Sale: 1000 yen (1100 with tax)
    - Return Sale: 500 yen (550 with tax)

    Expected:
    - Net sales: 500 (1000 - 500)
    - Payment: 550 (1100 - 550)
    - Returns: -500
    - Verifies the fix in check_report_data.py for handling returns
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
    test_date = "2024-01-25"
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

    # Verify sales calculations
    sales_gross = report.sales_gross
    sales_net = report.sales_net
    returns = report.returns
    payments = report.payments
    taxes = report.taxes

    # Net sales: 1000 - 500 = 500
    assert sales_net.amount == 500, f"Expected sales net 500, got {sales_net.amount}"

    # Returns: 500 (stored as positive value, factored during aggregation)
    assert returns.amount == 500, f"Expected returns 500, got {returns.amount}"

    # Payment: 1100 - 550 = 550
    cash_payment = next((p for p in payments if p.payment_code == "01"), None)
    assert cash_payment is not None, "Cash payment should exist"
    assert cash_payment.amount == 550, f"Expected payment 550, got {cash_payment.amount}"
    assert cash_payment.count == 2, f"Expected 2 transactions (1 sale + 1 return), got {cash_payment.count}"

    # Tax: 100 - 50 = 50
    tax = next((t for t in taxes if t.tax_code == "01"), None)
    assert tax is not None, "Tax should exist"
    assert tax.tax_amount == 50, f"Expected tax 50, got {tax.tax_amount}"

    print("\n=== RETURN TRANSACTION TEST ===")
    print(f"Sales Gross: {sales_gross.amount}")
    print(f"Sales Net: {sales_net.amount} (1000 - 500)")
    print(f"Returns: {returns.amount}")
    print(f"Payment: {cash_payment.amount} (1100 - 550)")
    print(f"Tax: {tax.tax_amount} (100 - 50)")
    print("✓ Return transactions correctly aggregated")
    print("✓ Payment formula verified: payment = abs(net) + tax for returns")
    print("===============================\n")

    # Don't close client - pytest fixture handles it
    # await local_db_helper.close_client_async()


@pytest.mark.skip(reason="Event loop issues when running multiple async tests - to be fixed in future")
@pytest.mark.asyncio
async def test_multiple_tax_rates_no_cartesian_product(set_env_vars):
    """
    Test that multiple tax rates don't cause Cartesian product.

    Scenario:
    - 1 transaction with 10% tax item (1000 yen) and 8% tax item (1000 yen)
    - 2 payment methods: Cash (1090) + Credit (1090)

    Expected:
    - Sales net: 2000 (NOT 8000 from 2 taxes × 2 payments × 2000)
    - Payment count: 1 (NOT 4 from Cartesian product)
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
    test_date = "2024-01-25"
    tenant_id = os.environ.get("TENANT_ID")

    # Transaction with 2 tax rates and 2 payment methods
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
            "total_amount": 2000,
            "total_amount_with_tax": 2180,  # 1100 (10%) + 1080 (8%)
            "tax_amount": 180,  # 100 + 80
            "total_quantity": 2,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[
            {"payment_no": 1, "payment_code": "01", "amount": 1090, "description": "Cash"},
            {"payment_no": 2, "payment_code": "11", "amount": 1090, "description": "Credit"}
        ],
        taxes=[
            {"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 100, "target_amount": 1000, "target_quantity": 1},
            {"tax_no": 2, "tax_code": "02", "tax_name": "軽減税率8%", "tax_amount": 80, "target_amount": 1000, "target_quantity": 1}
        ],
        line_items=[
            {"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1000, "amount": 1000, "tax_code": "01"},
            {"line_no": 2, "item_code": "ITEM002", "quantity": 1, "unit_price": 1000, "amount": 1000, "tax_code": "02"}
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

    # Verify no Cartesian product
    sales_net = report.sales_net
    payments = report.payments
    taxes = report.taxes

    # Sales amount should be 2000, NOT multiplied by number of taxes/payments
    assert sales_net.amount == 2000, f"Expected sales net 2000, got {sales_net.amount} (Cartesian product detected!)"
    assert sales_net.count == 1, f"Expected 1 transaction, got {sales_net.count}"

    # Each payment method should count as 1 transaction
    cash = next((p for p in payments if p.payment_code == "01"), None)
    credit = next((p for p in payments if p.payment_code == "11"), None)

    assert cash is not None, "Cash payment should exist"
    assert cash.count == 1, f"Expected 1 cash transaction, got {cash.count}"
    assert cash.amount == 1090, f"Expected cash amount 1090, got {cash.amount}"

    assert credit is not None, "Credit payment should exist"
    assert credit.count == 1, f"Expected 1 credit transaction, got {credit.count}"
    assert credit.amount == 1090, f"Expected credit amount 1090, got {credit.amount}"

    # Verify tax breakdown
    tax_10 = next((t for t in taxes if t.tax_code == "01"), None)
    tax_8 = next((t for t in taxes if t.tax_code == "02"), None)

    assert tax_10 is not None, "10% tax should exist"
    assert tax_10.tax_amount == 100, f"Expected 10% tax 100, got {tax_10.tax_amount}"

    assert tax_8 is not None, "8% tax should exist"
    assert tax_8.tax_amount == 80, f"Expected 8% tax 80, got {tax_8.tax_amount}"

    print("\n=== MULTIPLE TAX RATES TEST ===")
    print(f"Sales Net: {sales_net.amount} (should be 2000, not 8000)")
    print(f"Transaction Count: {sales_net.count} (should be 1, not 4)")
    print(f"Cash: count={cash.count}, amount={cash.amount}")
    print(f"Credit: count={credit.count}, amount={credit.amount}")
    print(f"Tax 10%: {tax_10.tax_amount}")
    print(f"Tax 8%: {tax_8.tax_amount}")
    print("✓ No Cartesian product between taxes and payments")
    print("✓ Amounts correctly calculated with multiple tax rates")
    print("===============================\n")

    # Don't close client - pytest fixture handles it
    # await local_db_helper.close_client_async()


@pytest.mark.skip(reason="Event loop issues when running multiple async tests - to be fixed in future")
@pytest.mark.asyncio
async def test_multiple_payment_methods_mixed(set_env_vars):
    """
    Test mixed payment methods in a single transaction.

    Scenario:
    - Transaction 1: Cash (500) + Credit (500) + E-money (500) = 1500 + tax
    - Transaction 2: Cash only (1000) + tax

    Expected:
    - Cash: count=2, amount=1650 (550+1100)
    - Credit: count=1, amount=550
    - E-money: count=1, amount=550
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
    test_date = "2024-01-25"
    tenant_id = os.environ.get("TENANT_ID")

    # Transaction 1: Mixed payments
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
            "total_amount": 1500,
            "total_amount_with_tax": 1650,
            "tax_amount": 150,
            "total_quantity": 1,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[
            {"payment_no": 1, "payment_code": "01", "amount": 550, "description": "Cash"},
            {"payment_no": 2, "payment_code": "11", "amount": 550, "description": "Credit"},
            {"payment_no": 3, "payment_code": "21", "amount": 550, "description": "E-money"}
        ],
        taxes=[{"tax_no": 1, "tax_code": "01", "tax_name": "消費税10%", "tax_amount": 150, "target_amount": 1500, "target_quantity": 1}],
        line_items=[{"line_no": 1, "item_code": "ITEM001", "quantity": 1, "unit_price": 1500, "amount": 1500}]
    )

    # Transaction 2: Cash only
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
        line_items=[{"line_no": 1, "item_code": "ITEM002", "quantity": 1, "unit_price": 1000, "amount": 1000}]
    )

    await collection.insert_one(tran1.model_dump())
    await collection.insert_one(tran2.model_dump())

    # Generate payment report
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
        report_type="payment",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1
    )

    payment_summary = report.payment_summary

    # Verify Cash payment (appears in both transactions)
    cash = next((p for p in payment_summary if p.payment_code == "01"), None)
    assert cash is not None, "Cash payment should exist"
    assert cash.count == 2, f"Expected 2 cash transactions, got {cash.count}"
    assert cash.amount == 1650, f"Expected cash amount 1650 (550+1100), got {cash.amount}"

    # Verify Credit payment (only in transaction 1)
    credit = next((p for p in payment_summary if p.payment_code == "11"), None)
    assert credit is not None, "Credit payment should exist"
    assert credit.count == 1, f"Expected 1 credit transaction, got {credit.count}"
    assert credit.amount == 550, f"Expected credit amount 550, got {credit.amount}"

    # Verify E-money payment (only in transaction 1)
    emoney = next((p for p in payment_summary if p.payment_code == "21"), None)
    assert emoney is not None, "E-money payment should exist"
    assert emoney.count == 1, f"Expected 1 e-money transaction, got {emoney.count}"
    assert emoney.amount == 550, f"Expected e-money amount 550, got {emoney.amount}"

    # Verify total
    total = next((p for p in payment_summary if p.payment_code == "total"), None)
    assert total is not None, "Total should exist"
    assert total.count == 2, f"Expected 2 total transactions, got {total.count}"
    assert total.amount == 2750, f"Expected total amount 2750 (1650+1100), got {total.amount}"

    print("\n=== MULTIPLE PAYMENT METHODS TEST ===")
    print(f"Cash: count={cash.count}, amount={cash.amount} (from 2 transactions)")
    print(f"Credit: count={credit.count}, amount={credit.amount} (from 1 transaction)")
    print(f"E-money: count={emoney.count}, amount={emoney.amount} (from 1 transaction)")
    print(f"Total: count={total.count}, amount={total.amount}")
    print("✓ Mixed payment methods correctly aggregated")
    print("✓ Each payment method counted separately")
    print("=====================================\n")

    # Don't close client - pytest fixture handles it
    # await local_db_helper.close_client_async()
