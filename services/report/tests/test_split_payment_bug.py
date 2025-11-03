# Copyright 2025 masa@kugel
# Test case to demonstrate the split payment counting bug

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
async def test_split_payment_count_bug(set_env_vars):
    """
    Test to demonstrate the split payment counting bug.

    Bug: When a transaction has multiple payments of the same payment_code,
    the transaction count is incorrectly multiplied by the number of payments.

    Expected: 1 transaction with 3 split payments should count as 1 transaction
    Actual (buggy): Counts as 3 transactions
    """

    # Import here to avoid issues with event loop
    from kugel_common.database import database as local_db_helper

    # Get fresh database connection
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    db = await local_db_helper.get_db_async(db_name)

    # Initialize repositories
    tran_repo = TranlogRepository(db, os.environ.get("TENANT_ID"))
    cash_repo = CashInOutLogRepository(db, os.environ.get("TENANT_ID"))
    open_close_repo = OpenCloseLogRepository(db, os.environ.get("TENANT_ID"))

    # Clean all data
    collection = db[tran_repo.collection_name]
    await collection.delete_many({})

    test_store = "STORE001"
    test_terminal = 1
    test_date = "2024-01-20"

    # Create ONE transaction with THREE split payments (all same payment code)
    tran1 = BaseTransaction(
        tenant_id=os.environ.get("TENANT_ID"),
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=1,
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
        payments=[
            {
                "payment_no": 1,
                "payment_code": "11",  # Credit card
                "amount": 1000,
                "description": "Credit Card"
            },
            {
                "payment_no": 2,
                "payment_code": "11",  # Credit card (split payment)
                "amount": 1000,
                "description": "Credit Card"
            },
            {
                "payment_no": 3,
                "payment_code": "11",  # Credit card (split payment)
                "amount": 1300,
                "description": "Credit Card"
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "消費税10%",
                "tax_amount": 300,
                "target_amount": 3000,
                "target_quantity": 1
            }
        ],
        line_items=[
            {
                "line_no": 1,
                "item_code": "ITEM001",
                "item_name": "テスト商品",
                "quantity": 1,
                "unit_price": 3000,
                "amount": 3000,
                "tax_code": "01",
                "discounts": []
            }
        ],
        transaction_time=datetime.now().isoformat()
    )
    await collection.insert_one(tran1.model_dump())

    # Initialize service
    daily_info_repo = DailyInfoDocumentRepository(db, os.environ.get("TENANT_ID"))
    terminal_info_repo = TerminalInfoWebRepository(os.environ.get("TENANT_ID"), test_store)
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    # Generate payment report
    report = await service.get_report_for_terminal_async(
        store_code=test_store,
        terminal_no=test_terminal,
        report_scope="flash",  # Flash report doesn't require terminal close
        report_type="payment",
        business_date=test_date,
        open_counter=1,
        limit=100,
        page=1
    )

    # Verify results
    payment_summary = report.payment_summary
    assert len(payment_summary) == 1  # Only credit card

    # Check credit payment
    credit_payment = payment_summary[0]
    assert credit_payment.payment_code == "11"
    assert credit_payment.amount == 3300  # Total amount with tax

    # THIS IS THE BUG CHECK
    # Expected: count == 1 (one transaction with three split payments)
    # Actual (buggy): count == 3 (counts each payment separately)
    print(f"\n=== BUG DEMONSTRATION ===")
    print(f"Transaction count: {credit_payment.count}")
    print(f"Expected: 1 (one transaction)")
    print(f"Actual: {credit_payment.count} (BUG: counting each split payment as a transaction)")
    print(f"=======================\n")

    assert credit_payment.count == 1, \
        f"Expected 1 transaction, but got {credit_payment.count}. " \
        f"This is the split payment counting bug!"

    # Close database connection
    await local_db_helper.close_client_async()


@pytest.mark.asyncio
async def test_sales_report_amount_bug(set_env_vars):
    """
    Test to demonstrate the sales report amount doubling bug.

    Bug: When a transaction has multiple payments and multiple taxes,
    the Cartesian product causes amounts to be multiplied.

    Expected: 1 transaction with 2 taxes × 2 payments should have amount counted once
    Actual (buggy): Amount is counted 2×2=4 times
    """

    # Import here to avoid issues with event loop
    from kugel_common.database import database as local_db_helper

    # Get fresh database connection
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    db = await local_db_helper.get_db_async(db_name)

    # Initialize repositories
    tran_repo = TranlogRepository(db, os.environ.get("TENANT_ID"))
    cash_repo = CashInOutLogRepository(db, os.environ.get("TENANT_ID"))
    open_close_repo = OpenCloseLogRepository(db, os.environ.get("TENANT_ID"))

    # Clean all data
    collection = db[tran_repo.collection_name]
    await collection.delete_many({})

    test_store = "STORE001"
    test_terminal = 1
    test_date = "2024-01-21"

    # Create ONE transaction with 2 taxes and 2 payments
    tran1 = BaseTransaction(
        tenant_id=os.environ.get("TENANT_ID"),
        store_code=test_store,
        terminal_no=test_terminal,
        business_date=test_date,
        business_counter=1,
        open_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        sales={
            "total_amount": 1000,  # IMPORTANT: Total is 1000
            "total_amount_with_tax": 1100,
            "tax_amount": 100,
            "total_quantity": 2,
            "change_amount": 0,
            "total_discount_amount": 0,
            "is_cancelled": False
        },
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",  # Cash
                "amount": 600,
                "description": "Cash"
            },
            {
                "payment_no": 2,
                "payment_code": "11",  # Credit
                "amount": 500,
                "description": "Credit Card"
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "消費税8%",
                "tax_amount": 40,
                "target_amount": 500,
                "target_quantity": 1
            },
            {
                "tax_no": 2,
                "tax_code": "02",
                "tax_name": "消費税10%",
                "tax_amount": 60,
                "target_amount": 600,
                "target_quantity": 1
            }
        ],
        line_items=[
            {
                "line_no": 1,
                "item_code": "ITEM001",
                "item_name": "軽減税率商品",
                "quantity": 1,
                "unit_price": 500,
                "amount": 500,
                "tax_code": "01",
                "discounts": []
            },
            {
                "line_no": 2,
                "item_code": "ITEM002",
                "item_name": "通常税率商品",
                "quantity": 1,
                "unit_price": 600,
                "amount": 600,
                "tax_code": "02",
                "discounts": []
            }
        ],
        transaction_time=datetime.now().isoformat()
    )
    await collection.insert_one(tran1.model_dump())

    # Initialize service
    daily_info_repo = DailyInfoDocumentRepository(db, os.environ.get("TENANT_ID"))
    terminal_info_repo = TerminalInfoWebRepository(os.environ.get("TENANT_ID"), test_store)
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    # Generate sales report
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

    # Verify results
    sales_net = report.sales_net

    # THIS IS THE BUG CHECK
    # Expected: amount == 1000 (total_amount from the single transaction)
    # Actual (buggy): amount == 4000 (1000 × 2 taxes × 2 payments = 4000)
    print(f"\n=== BUG DEMONSTRATION ===")
    print(f"Sales amount: {sales_net.amount}")
    print(f"Expected: 1000 (one transaction)")
    print(f"Actual: {sales_net.amount} (BUG: Cartesian product multiplication)")
    print(f"Multiplier: 2 taxes × 2 payments = 4x")
    print(f"=======================\n")

    assert sales_net.amount == 1000, \
        f"Expected amount 1000, but got {sales_net.amount}. " \
        f"This is the Cartesian product bug (2 taxes × 2 payments = 4x multiplication)!"

    # Also check transaction count
    assert sales_net.count == 1, \
        f"Expected 1 transaction, but got {sales_net.count}"

    # Close database connection
    await local_db_helper.close_client_async()
