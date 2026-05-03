# Copyright 2025 masa@kugel
# Edge case tests for POS report system
#
# These tests verify system behavior with edge cases:
# 1. Zero amount transactions (full discount)
# 2. Empty tax arrays (non-taxable items)
# 3. Rounding errors (1 yen difference)
# 4. Three-way payment splits
# 5. Extreme payment splits (5-way)
#
# CRITICAL: These tests ensure the system handles unusual but valid scenarios
# that can occur in real-world POS operations.

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
async def test_zero_amount_transaction(set_env_vars, clean_test_data):
    """
    EDGE CASE TEST: Zero amount transaction (100% discount applied)

    Scenario:
    - 1 transaction with 1000 yen item
    - 100% discount applied: -1000 yen
    - Result: 0 yen sales net
    - Tax: 0 yen (no tax on 0 amount)
    - Payment: 0 yen

    This tests the system's ability to handle transactions where the customer
    pays nothing due to promotions, coupons, or employee discounts.

    Expected behavior:
    - Sales gross: 1000 yen (amount before discount)
    - Discount: 1000 yen
    - Sales net: 0 yen (amount after discount)
    - Tax: 0 yen
    - Payment total: 0 yen
    - Equation: Payment (0) = Sales Net (0) + Tax (0) ✓
    - Equation: Sales Net (0) = Sales Gross (1000) - Discount (1000) ✓
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    # Create repositories first to get correct collection name
    from app.models.repositories.tranlog_repository import TranlogRepository
    from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
    from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
    from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository
    from app.models.repositories.terminal_info_web_repository import TerminalInfoWebRepository

    tran_repo = TranlogRepository(db, tenant_id)

    # Get collection reference using the repository's collection name
    collection = db[tran_repo.collection_name]  # Use "log_tran", not "tranlogs"

    # EXPLICIT CLEANUP: Delete ALL data matching test criteria to ensure clean state
    cleanup_result = await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": "STORE001",
        "business_date": "2024-04-01",  # Match test date
        "terminal_no": 1,
        "open_counter": 1
    })
    print(f"[DEBUG] Explicit cleanup: deleted {cleanup_result.deleted_count} existing documents")

    # Create zero amount transaction
    # Use different date from test_data_integrity.py to avoid data conflicts
    transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=1,
        business_date="2024-04-01",  # Different date to avoid conflicts
        open_counter=1,
        business_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 0.0,  # Net amount AFTER discount (1000 - 1000 = 0)
            "total_amount_with_tax": 0.0,  # Net amount + tax (0 + 0 = 0)
            "tax_amount": 0.0,  # No tax on zero net amount
            "total_quantity": 1,
            "change_amount": 0.0,
            "total_discount_amount": 1000.0,  # Full discount (100% OFF on 1000 yen item)
            "is_cancelled": False,
        },
        line_items=[
            {
                "line_no": 1,
                "item_code": "ITEM001",
                "item_name": "Test Item",
                "quantity": 1,
                "unit_price": 1000.0,
                "amount": 1000.0,
                "tax_code": "01",
                "discounts": [
                    {
                        "discount_no": 1,
                        "discount_code": "DISC100",
                        "discount_name": "100% OFF",
                        "discount_amount": 1000.0,
                    }
                ],
            }
        ],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 0.0,  # No payment needed
                "description": "Cash",
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "消費税10%",
                "tax_amount": 0.0,  # Zero tax on zero amount
                "target_amount": 0.0,
                "target_quantity": 1,
            }
        ],  # Tax entry with zero amount (not empty array)
    )

    # Insert transaction (use snake_case field names, not camelCase aliases)
    insert_result = await collection.insert_one(transaction.model_dump())
    print(f"[DEBUG] Inserted document ID: {insert_result.inserted_id}")

    # Verify what was actually inserted
    inserted_docs = await collection.find({"tenant_id": tenant_id, "store_code": "STORE001"}).to_list(length=10)
    print(f"[DEBUG] Found {len(inserted_docs)} documents in database after insertion")
    for i, doc in enumerate(inserted_docs):
        print(f"[DEBUG] Doc {i+1}: transaction_no={doc.get('transaction_no')}, sales.total_amount={doc.get('sales', {}).get('total_amount')}, payments count={len(doc.get('payments', []))}")

    # Generate report
    tran_repo = TranlogRepository(db, tenant_id)
    cash_in_out_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "STORE001")
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)

    report_service = ReportService(
        tran_repo, cash_in_out_repo, open_close_repo, terminal_info_repo, daily_info_repo
    )

    report = await report_service.get_report_for_terminal_async(
        store_code="STORE001",
        terminal_no=1,
        report_scope="flash",
        report_type="sales",
        business_date="2024-04-01",
        open_counter=1,
        limit=100,
        page=1,
    )

    # Verify report
    assert report is not None, "Report should be generated"

    sales_gross = report.sales_gross
    sales_net = report.sales_net
    discount_total = report.discount_for_lineitems.amount + report.discount_for_subtotal.amount
    payments = report.payments
    taxes = report.taxes

    # Verify amounts
    # Sales Gross = amount before discounts = 1000
    # Discount = 1000
    # Sales Net = amount after discounts = 0
    assert sales_gross.amount == 1000.0, f"Expected gross 1000 (before discount), got {sales_gross.amount}"
    assert sales_net.amount == 0.0, f"Expected net 0 (after discount), got {sales_net.amount}"
    assert discount_total == 1000.0, f"Expected discount 1000, got {discount_total}"

    # Verify equation: Sales Net = Sales Gross - Discount
    assert sales_net.amount == sales_gross.amount - discount_total, \
        f"Equation failed: Sales Net ({sales_net.amount}) != Sales Gross ({sales_gross.amount}) - Discount ({discount_total})"

    # Verify payment
    assert len(payments) == 1, f"Expected 1 payment, got {len(payments)}"
    cash = next((p for p in payments if p.payment_name == "Cash"), None)
    assert cash is not None, "Cash payment should exist"
    assert cash.amount == 0.0, f"Expected payment 0, got {cash.amount}"

    # Verify tax (should have 1 tax entry with 0 amount)
    assert len(taxes) == 1, f"Expected 1 tax entry (with 0 amount), got {len(taxes)}"
    if len(taxes) > 0:
        assert taxes[0].tax_amount == 0.0, f"Expected tax amount 0, got {taxes[0].tax_amount}"

    # Verify accounting equation: Payment = Sales Net + Tax
    payment_total = sum(p.amount for p in payments)
    tax_total = sum(t.tax_amount for t in taxes)
    sales_with_tax = sales_net.amount + tax_total

    print("\n=== ZERO AMOUNT TRANSACTION TEST ===")
    print(f"Sales Gross: {sales_gross.amount}")
    print(f"Discount: {discount_total}")
    print(f"Sales Net: {sales_net.amount}")
    print(f"Tax Total: {tax_total}")
    print(f"Payment Total: {payment_total}")
    print(f"Sales + Tax: {sales_with_tax}")
    print(f"Difference: {abs(payment_total - sales_with_tax)}")
    print("✅ PASS: Zero amount transaction handled correctly")
    print(f"✅ Sales Gross ({sales_gross.amount}) - Discount ({discount_total}) = Sales Net ({sales_net.amount})")
    print(f"✅ Payment Total ({payment_total}) = Sales Net ({sales_net.amount}) + Tax ({tax_total})")
    print("=====================================\n")

    assert payment_total == sales_with_tax, \
        f"CRITICAL ERROR: Payment ({payment_total}) != Sales + Tax ({sales_with_tax})"


@pytest.mark.asyncio
async def test_empty_taxes_array(set_env_vars, clean_test_data):
    """
    EDGE CASE TEST: Transaction with empty taxes array (non-taxable items)

    Scenario:
    - 1 transaction with non-taxable item (e.g., newspaper in Japan)
    - Sales: 1000 yen
    - Tax: None (empty array)
    - Payment: 1000 yen cash

    This tests the system's handling of non-taxable items where the taxes
    array is legitimately empty.

    Expected behavior:
    - Sales net: 1000 yen
    - Tax total: 0 yen
    - Payment total: 1000 yen
    - Equation: 1000 = 1000 + 0 ✓
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    # Create repositories first to get correct collection name
    from app.models.repositories.tranlog_repository import TranlogRepository

    tran_repo = TranlogRepository(db, tenant_id)

    # Get collection reference using the repository's collection name
    collection = db[tran_repo.collection_name]  # Use "log_tran", not "tranlogs"

    # EXPLICIT CLEANUP: Delete ALL data matching test criteria to ensure clean state
    cleanup_result = await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": "STORE001",
        "business_date": "2024-04-01"
    })
    print(f"[DEBUG] Explicit cleanup: deleted {cleanup_result.deleted_count} existing documents")

    # Create transaction with no taxes (non-taxable item)
    transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=1,
        business_date="2024-04-01",
        open_counter=1,
        business_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 1000.0,
            "total_amount_with_tax": 1000.0,  # No tax added
            "tax_amount": 0.0,
            "total_quantity": 1,
            "change_amount": 0.0,
            "total_discount_amount": 0.0,
            "is_cancelled": False,
        },
        line_items=[
            {
                "line_no": 1,
                "item_code": "NEWSPAPER001",
                "item_name": "Daily Newspaper",
                "quantity": 1,
                "unit_price": 1000.0,
                "amount": 1000.0,
                "tax_code": "00",  # Non-taxable
            }
        ],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 1000.0,
                "description": "Cash",
            }
        ],
        taxes=[],  # Empty array - non-taxable item
    )

    # Insert transaction (use snake_case field names, not camelCase aliases)
    insert_result = await collection.insert_one(transaction.model_dump())
    print(f"[DEBUG] Inserted transaction with ID: {insert_result.inserted_id}")

    # Verify insertion (use snake_case for MongoDB field names)
    doc_count = await collection.count_documents({"tenant_id": tenant_id, "store_code": "STORE001"})
    print(f"[DEBUG] Total documents in STORE001 after insertion: {doc_count}")

    # Generate report
    tran_repo = TranlogRepository(db, tenant_id)
    cash_in_out_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "STORE001")
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)

    report_service = ReportService(
        tran_repo, cash_in_out_repo, open_close_repo, terminal_info_repo, daily_info_repo
    )

    report = await report_service.get_report_for_terminal_async(
        store_code="STORE001",
        terminal_no=1,
        report_scope="flash",
        report_type="sales",
        business_date="2024-04-01",
        open_counter=1,
        limit=100,
        page=1,
    )

    # Verify report
    assert report is not None, "Report should be generated"

    sales_net = report.sales_net
    payments = report.payments
    taxes = report.taxes

    # Verify amounts
    assert sales_net.amount == 1000.0, f"Expected sales 1000, got {sales_net.amount}"
    assert sales_net.count == 1, f"Expected 1 transaction, got {sales_net.count}"

    # Verify payment
    assert len(payments) == 1, f"Expected 1 payment, got {len(payments)}"
    cash = next((p for p in payments if p.payment_name == "Cash"), None)
    assert cash is not None, "Cash payment should exist"
    assert cash.amount == 1000.0, f"Expected payment 1000, got {cash.amount}"

    # Verify tax (should be empty)
    assert len(taxes) == 0, f"Expected 0 taxes (non-taxable item), got {len(taxes)}"

    # Verify accounting equation
    payment_total = sum(p.amount for p in payments)
    tax_total = sum(t.tax_amount for t in taxes)
    sales_with_tax = sales_net.amount + tax_total

    print("\n=== EMPTY TAXES ARRAY TEST ===")
    print(f"Sales Net: {sales_net.amount}")
    print(f"Tax Total: {tax_total} (empty array)")
    print(f"Payment Total: {payment_total}")
    print(f"Sales + Tax: {sales_with_tax}")
    print(f"Difference: {abs(payment_total - sales_with_tax)}")
    print("✅ PASS: Non-taxable item handled correctly")
    print("✅ Payment Total (1000) = Sales Net (1000) + Tax (0)")
    print("==============================\n")

    assert payment_total == sales_with_tax, \
        f"CRITICAL ERROR: Payment ({payment_total}) != Sales + Tax ({sales_with_tax})"


@pytest.mark.asyncio
async def test_rounding_one_yen_difference(set_env_vars, clean_test_data):
    """
    EDGE CASE TEST: Rounding error causing 1 yen difference

    Scenario:
    - Item: 333 yen × 3 = 999 yen
    - Tax 10%: 99.9 yen → rounds to 100 yen
    - Total: 999 + 100 = 1099 yen
    - Payment split with rounding: 550 + 549 = 1099 yen

    This tests the system's handling of rounding errors that can occur
    when splitting payments or calculating taxes.

    Expected behavior:
    - Sales net: 999 yen
    - Tax: 100 yen (rounded from 99.9)
    - Payment total: 1099 yen
    - Equation: 1099 = 999 + 100 ✓
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    # Create repositories first to get correct collection name
    from app.models.repositories.tranlog_repository import TranlogRepository

    tran_repo = TranlogRepository(db, tenant_id)

    # Get collection reference using the repository's collection name
    collection = db[tran_repo.collection_name]  # Use "log_tran", not "tranlogs"

    # Clean up - delete ALL data for STORE001 to ensure clean state
    delete_result = await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": "STORE001"
    })
    print(f"Deleted {delete_result.deleted_count} documents from STORE001")

    # Create transaction with rounding
    transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=1,
        business_date="2024-04-01",
        open_counter=1,
        business_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 999.0,
            "total_amount_with_tax": 1099.0,
            "tax_amount": 100.0,  # Rounded from 99.9
            "total_quantity": 3,
            "change_amount": 0.0,
            "total_discount_amount": 0.0,
            "is_cancelled": False,
        },
        line_items=[
            {
                "line_no": 1,
                "item_code": "ITEM333",
                "item_name": "333 Yen Item",
                "quantity": 3,
                "unit_price": 333.0,
                "amount": 999.0,
                "tax_code": "01",
            }
        ],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 550.0,
                "description": "Cash",
            },
            {
                "payment_no": 2,
                "payment_code": "11",
                "amount": 549.0,  # 1 yen less due to rounding
                "description": "Credit",
            },
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "消費税10%",
                "tax_amount": 100.0,  # Rounded from 99.9
                "target_amount": 999.0,
                "target_quantity": 3,
            }
        ],
    )

    # Insert transaction (use snake_case field names, not camelCase aliases)
    await collection.insert_one(transaction.model_dump())

    # Generate report
    tran_repo = TranlogRepository(db, tenant_id)
    cash_in_out_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "STORE001")
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)

    report_service = ReportService(
        tran_repo, cash_in_out_repo, open_close_repo, terminal_info_repo, daily_info_repo
    )

    report = await report_service.get_report_for_terminal_async(
        store_code="STORE001",
        terminal_no=1,
        report_scope="flash",
        report_type="sales",
        business_date="2024-04-01",
        open_counter=1,
        limit=100,
        page=1,
    )

    # Verify report
    assert report is not None, "Report should be generated"

    sales_net = report.sales_net
    payments = report.payments
    taxes = report.taxes

    # Verify amounts
    assert sales_net.amount == 999.0, f"Expected sales 999, got {sales_net.amount}"

    # Verify payments
    cash = next((p for p in payments if p.payment_name == "Cash"), None)
    credit = next((p for p in payments if p.payment_name == "Credit"), None)

    assert cash is not None, "Cash payment should exist"
    assert credit is not None, "Credit payment should exist"
    assert cash.amount == 550.0, f"Expected cash 550, got {cash.amount}"
    assert credit.amount == 549.0, f"Expected credit 549, got {credit.amount}"

    # Verify tax
    assert len(taxes) == 1, f"Expected 1 tax, got {len(taxes)}"
    tax = taxes[0]
    assert tax.tax_amount == 100.0, f"Expected tax 100 (rounded), got {tax.tax_amount}"

    # Verify accounting equation
    payment_total = sum(p.amount for p in payments)
    tax_total = sum(t.tax_amount for t in taxes)
    sales_with_tax = sales_net.amount + tax_total

    print("\n=== ROUNDING ERROR TEST ===")
    print(f"Sales Net: {sales_net.amount} (333 × 3)")
    print(f"Tax: {tax_total} (rounded from 99.9)")
    print(f"Cash: {cash.amount}")
    print(f"Credit: {credit.amount}")
    print(f"Payment Total: {payment_total}")
    print(f"Sales + Tax: {sales_with_tax}")
    print(f"Difference: {abs(payment_total - sales_with_tax)}")
    print("✅ PASS: Rounding handled correctly")
    print("✅ Payment Total (1099) = Sales Net (999) + Tax (100)")
    print("===========================\n")

    assert payment_total == sales_with_tax, \
        f"CRITICAL ERROR: Payment ({payment_total}) != Sales + Tax ({sales_with_tax})"


@pytest.mark.asyncio
async def test_three_way_payment_split(set_env_vars, clean_test_data):
    """
    EDGE CASE TEST: Three-way payment split

    Scenario:
    - Transaction: 3300 yen (3000 + 300 tax)
    - Payment split 3 ways:
      - Cash: 1100 yen
      - Credit: 1100 yen
      - E-money: 1100 yen
    - Total: 3300 yen

    This tests the system's ability to handle complex payment splits
    that are common in real POS scenarios (e.g., using points + cash + credit).

    Expected behavior:
    - Sales net: 3000 yen
    - Tax: 300 yen
    - Payment total: 3300 yen (3-way split)
    - Equation: 3300 = 3000 + 300 ✓
    - No Cartesian product: count should be 1, not 3
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    # Create repositories first to get correct collection name
    from app.models.repositories.tranlog_repository import TranlogRepository

    tran_repo = TranlogRepository(db, tenant_id)

    # Get collection reference using the repository's collection name
    collection = db[tran_repo.collection_name]  # Use "log_tran", not "tranlogs"

    # Clean up - delete ALL data for STORE001 to ensure clean state
    delete_result = await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": "STORE001"
    })
    print(f"Deleted {delete_result.deleted_count} documents from STORE001")

    # Create transaction with 3-way payment split
    transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=1,
        business_date="2024-04-01",
        open_counter=1,
        business_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 3000.0,
            "total_amount_with_tax": 3300.0,
            "tax_amount": 300.0,
            "total_quantity": 3,
            "change_amount": 0.0,
            "total_discount_amount": 0.0,
            "is_cancelled": False,
        },
        line_items=[
            {
                "line_no": 1,
                "item_code": "ITEM001",
                "item_name": "Item 1000",
                "quantity": 3,
                "unit_price": 1000.0,
                "amount": 3000.0,
                "tax_code": "01",
            }
        ],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 1100.0,
                "description": "Cash",
            },
            {
                "payment_no": 2,
                "payment_code": "11",
                "amount": 1100.0,
                "description": "Credit",
            },
            {
                "payment_no": 3,
                "payment_code": "21",
                "amount": 1100.0,
                "description": "E-money",
            },
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "消費税10%",
                "tax_amount": 300.0,
                "target_amount": 3000.0,
                "target_quantity": 3,
            }
        ],
    )

    # Insert transaction (use snake_case field names, not camelCase aliases)
    await collection.insert_one(transaction.model_dump())

    # Generate report
    tran_repo = TranlogRepository(db, tenant_id)
    cash_in_out_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "STORE001")
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)

    report_service = ReportService(
        tran_repo, cash_in_out_repo, open_close_repo, terminal_info_repo, daily_info_repo
    )

    report = await report_service.get_report_for_terminal_async(
        store_code="STORE001",
        terminal_no=1,
        report_scope="flash",
        report_type="sales",
        business_date="2024-04-01",
        open_counter=1,
        limit=100,
        page=1,
    )

    # Verify report
    assert report is not None, "Report should be generated"

    sales_net = report.sales_net
    payments = report.payments
    taxes = report.taxes

    # CRITICAL: Verify no Cartesian product multiplication
    assert sales_net.amount == 3000.0, f"Expected sales 3000, got {sales_net.amount}"
    assert sales_net.count == 1, f"Expected 1 transaction, got {sales_net.count} (Cartesian product!)"

    # Verify all 3 payments exist
    assert len(payments) == 3, f"Expected 3 payments, got {len(payments)}"

    cash = next((p for p in payments if p.payment_name == "Cash"), None)
    credit = next((p for p in payments if p.payment_name == "Credit"), None)
    emoney = next((p for p in payments if p.payment_name == "E-money"), None)

    assert cash is not None, "Cash payment should exist"
    assert credit is not None, "Credit payment should exist"
    assert emoney is not None, "E-money payment should exist"

    assert cash.amount == 1100.0, f"Expected cash 1100, got {cash.amount}"
    assert credit.amount == 1100.0, f"Expected credit 1100, got {credit.amount}"
    assert emoney.amount == 1100.0, f"Expected e-money 1100, got {emoney.amount}"

    # Verify tax
    assert len(taxes) == 1, f"Expected 1 tax, got {len(taxes)}"
    tax = taxes[0]
    assert tax.tax_amount == 300.0, f"Expected tax 300, got {tax.tax_amount}"

    # Verify accounting equation
    payment_total = sum(p.amount for p in payments)
    tax_total = sum(t.tax_amount for t in taxes)
    sales_with_tax = sales_net.amount + tax_total

    print("\n=== THREE-WAY PAYMENT SPLIT TEST ===")
    print(f"Sales Net: {sales_net.amount}")
    print(f"Tax: {tax_total}")
    print(f"Cash: {cash.amount}")
    print(f"Credit: {credit.amount}")
    print(f"E-money: {emoney.amount}")
    print(f"Payment Total: {payment_total} (3-way split)")
    print(f"Sales + Tax: {sales_with_tax}")
    print(f"Transaction Count: {sales_net.count} (should be 1, not 3!)")
    print(f"Difference: {abs(payment_total - sales_with_tax)}")
    print("✅ PASS: 3-way payment split handled correctly")
    print("✅ No Cartesian product: count = 1")
    print("✅ Payment Total (3300) = Sales Net (3000) + Tax (300)")
    print("====================================\n")

    assert payment_total == sales_with_tax, \
        f"CRITICAL ERROR: Payment ({payment_total}) != Sales + Tax ({sales_with_tax})"


@pytest.mark.asyncio
async def test_five_way_payment_split(set_env_vars, clean_test_data):
    """
    EDGE CASE TEST: Extreme five-way payment split

    Scenario:
    - Transaction: 5500 yen (5000 + 500 tax)
    - Payment split 5 ways:
      - Cash: 1100 yen
      - Credit: 1100 yen
      - E-money: 1100 yen
      - Gift card: 1100 yen
      - Points: 1100 yen
    - Total: 5500 yen

    This is an extreme but possible scenario (e.g., customer using multiple
    gift cards, points, and payment methods to utilize various balances).

    Expected behavior:
    - Sales net: 5000 yen
    - Tax: 500 yen
    - Payment total: 5500 yen (5-way split)
    - Equation: 5500 = 5000 + 500 ✓
    - No Cartesian product: count should be 1, not 5
    """
    from kugel_common.database import database as local_db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    # Create repositories first to get correct collection name
    from app.models.repositories.tranlog_repository import TranlogRepository

    tran_repo = TranlogRepository(db, tenant_id)

    # Get collection reference using the repository's collection name
    collection = db[tran_repo.collection_name]  # Use "log_tran", not "tranlogs"

    # Clean up - delete ALL data for STORE001 to ensure clean state
    delete_result = await collection.delete_many({
        "tenant_id": tenant_id,
        "store_code": "STORE001"
    })
    print(f"Deleted {delete_result.deleted_count} documents from STORE001")

    # Create transaction with 5-way payment split
    transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="STORE001",
        terminal_no=1,
        business_date="2024-04-01",
        open_counter=1,
        business_counter=1,
        transaction_no=1,
        transaction_type=TransactionType.NormalSales.value,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sales={
            "total_amount": 5000.0,
            "total_amount_with_tax": 5500.0,
            "tax_amount": 500.0,
            "total_quantity": 5,
            "change_amount": 0.0,
            "total_discount_amount": 0.0,
            "is_cancelled": False,
        },
        line_items=[
            {
                "line_no": 1,
                "item_code": "ITEM001",
                "item_name": "Item 1000",
                "quantity": 5,
                "unit_price": 1000.0,
                "amount": 5000.0,
                "tax_code": "01",
            }
        ],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 1100.0,
                "description": "Cash",
            },
            {
                "payment_no": 2,
                "payment_code": "11",
                "amount": 1100.0,
                "description": "Credit",
            },
            {
                "payment_no": 3,
                "payment_code": "21",
                "amount": 1100.0,
                "description": "E-money",
            },
            {
                "payment_no": 4,
                "payment_code": "31",
                "amount": 1100.0,
                "description": "Gift Card",
            },
            {
                "payment_no": 5,
                "payment_code": "41",
                "amount": 1100.0,
                "description": "Points",
            },
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "消費税10%",
                "tax_amount": 500.0,
                "target_amount": 5000.0,
                "target_quantity": 5,
            }
        ],
    )

    # Insert transaction (use snake_case field names, not camelCase aliases)
    await collection.insert_one(transaction.model_dump())

    # Generate report
    tran_repo = TranlogRepository(db, tenant_id)
    cash_in_out_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "STORE001")
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)

    report_service = ReportService(
        tran_repo, cash_in_out_repo, open_close_repo, terminal_info_repo, daily_info_repo
    )

    report = await report_service.get_report_for_terminal_async(
        store_code="STORE001",
        terminal_no=1,
        report_scope="flash",
        report_type="sales",
        business_date="2024-04-01",
        open_counter=1,
        limit=100,
        page=1,
    )

    # Verify report
    assert report is not None, "Report should be generated"

    sales_net = report.sales_net
    payments = report.payments
    taxes = report.taxes

    # CRITICAL: Verify no Cartesian product multiplication
    assert sales_net.amount == 5000.0, f"Expected sales 5000, got {sales_net.amount}"
    assert sales_net.count == 1, f"Expected 1 transaction, got {sales_net.count} (Cartesian product!)"

    # Verify all 5 payments exist
    assert len(payments) == 5, f"Expected 5 payments, got {len(payments)}"

    cash = next((p for p in payments if p.payment_name == "Cash"), None)
    credit = next((p for p in payments if p.payment_name == "Credit"), None)
    emoney = next((p for p in payments if p.payment_name == "E-money"), None)
    gift = next((p for p in payments if p.payment_name == "Gift Card"), None)
    points = next((p for p in payments if p.payment_name == "Points"), None)

    assert cash is not None, "Cash payment should exist"
    assert credit is not None, "Credit payment should exist"
    assert emoney is not None, "E-money payment should exist"
    assert gift is not None, "Gift card payment should exist"
    assert points is not None, "Points payment should exist"

    # Verify each payment amount
    for payment in [cash, credit, emoney, gift, points]:
        assert payment.amount == 1100.0, f"Expected {payment.payment_name} 1100, got {payment.amount}"

    # Verify tax
    assert len(taxes) == 1, f"Expected 1 tax, got {len(taxes)}"
    tax = taxes[0]
    assert tax.tax_amount == 500.0, f"Expected tax 500, got {tax.tax_amount}"

    # Verify accounting equation
    payment_total = sum(p.amount for p in payments)
    tax_total = sum(t.tax_amount for t in taxes)
    sales_with_tax = sales_net.amount + tax_total

    print("\n=== FIVE-WAY PAYMENT SPLIT TEST ===")
    print(f"Sales Net: {sales_net.amount}")
    print(f"Tax: {tax_total}")
    print(f"Cash: {cash.amount}")
    print(f"Credit: {credit.amount}")
    print(f"E-money: {emoney.amount}")
    print(f"Gift Card: {gift.amount}")
    print(f"Points: {points.amount}")
    print(f"Payment Total: {payment_total} (5-way split!)")
    print(f"Sales + Tax: {sales_with_tax}")
    print(f"Transaction Count: {sales_net.count} (should be 1, not 5!)")
    print(f"Difference: {abs(payment_total - sales_with_tax)}")
    print("✅ PASS: 5-way payment split handled correctly")
    print("✅ No Cartesian product: count = 1")
    print("✅ Payment Total (5500) = Sales Net (5000) + Tax (500)")
    print("===================================\n")

    assert payment_total == sales_with_tax, \
        f"CRITICAL ERROR: Payment ({payment_total}) != Sales + Tax ({sales_with_tax})"
