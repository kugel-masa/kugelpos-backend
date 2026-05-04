"""
Test for Issue #90: Internal tax not deducted from sales_net

https://github.com/kugel-masa/kugelpos-backend-private/issues/90

Problem: Sales report shows incorrect net sales amount when transactions include
internal tax items. The internal tax is not being deducted from net sales.

Expected behavior:
純売上 = 総売上 - 返品 - 値引 - 全税額（外税 + 内税）

Current (buggy) behavior:
純売上 = 総売上 - 返品 - 値引 - 外税のみ  ← 内税が引かれていない
"""

import asyncio
import os
from datetime import datetime

import pytest

from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository
from app.models.repositories.terminal_info_web_repository import TerminalInfoWebRepository


@pytest.mark.asyncio
async def test_internal_tax_not_deducted_from_sales_net(set_env_vars):
    """
    Test that internal tax IS deducted from sales_net.

    This test SHOULD FAIL before the fix and PASS after the fix.

    Scenario: Sale with internal tax only (no returns, no discounts)
    - Product: 1,100円 (税込、内税10% = 100円含む)
    - Expected net sales (税抜): 1,000円
    - Current buggy behavior: 1,100円 (internal tax NOT deducted)
    """
    from kugel_common.database import database as local_db_helper

    # Setup
    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    # Create repositories
    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "TEST_ISSUE90")

    collection = db[tran_repo.collection_name]

    # Clean up existing test data
    await collection.delete_many({
        "store_code": "TEST_ISSUE90",
        "terminal_no": 90,
        "business_date": "20251107"
    })

    # Create sale transaction with INTERNAL TAX ONLY
    # Product: 1,100円 (tax-inclusive, internal tax 10%)
    # Internal tax calculation: 1100 / 1.1 * 0.1 = 100円
    # Net amount (tax-exclusive): 1100 / 1.1 = 1000円

    # IMPORTANT: Based on cart service spec:
    # For internal tax items:
    #   - sales.total_amount = 1100 (tax-INCLUSIVE)
    #   - sales.tax_amount = 0 (no external tax)
    #   - sales.total_amount_with_tax = 1100 (same as total_amount)
    #   - taxes array contains: [{"tax_type": "Internal", "tax_amount": 100}]

    sale_transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="TEST_ISSUE90",
        terminal_no=90,
        transaction_no=900,
        transaction_type=101,  # NormalSales
        business_date="20251107",
        open_counter=1,
        business_counter=1,
        line_items=[
            {
                "line_no": 1,
                "item_code": "INTERNAL_TAX_ITEM",
                "description": "Internal Tax Product",
                "unit_price": 1100.0,  # Tax-inclusive price
                "quantity": 1,
                "amount": 1100.0,  # Tax-inclusive
                "tax_code": "02",  # Internal tax code
                "is_cancelled": False,
                "discounts": []
            }
        ],
        subtotal_discounts=[],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 1100.0,  # Customer pays tax-inclusive
                "deposit_amount": 1100.0,
                "description": "Cash"
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "02",
                "tax_type": "Internal",  # CRITICAL: Internal tax
                "tax_name": "内税10%",
                "tax_amount": 100.0,  # 1100 / 1.1 * 0.1 = 100
                "target_amount": 1100.0,  # Tax-inclusive amount
                "target_quantity": 1
            }
        ],
        sales={
            "total_quantity": 1,
            "total_amount": 1100.0,  # Tax-INCLUSIVE (cart service spec)
            "total_amount_with_tax": 1100.0,  # Same for internal tax
            "tax_amount": 0.0,  # ZERO! (cart service only stores external tax here)
            "total_discount_amount": 0.0,
            "change_amount": 0.0,
            "is_cancelled": False
        },
        transaction_time=datetime.now().isoformat()
    )

    # Insert test data
    await collection.insert_one(sale_transaction.model_dump())

    # Generate report
    from app.services.report_service import ReportService
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    report = await service.get_report_for_terminal_async(
        store_code="TEST_ISSUE90",
        terminal_no=90,
        report_scope="flash",
        report_type="sales",
        business_date="20251107",
        open_counter=1,
        limit=100,
        page=1
    )

    # Verify report
    assert report is not None, "No report generated"

    print("\n=== Issue #90 Test Results ===")
    print(f"Transaction: 1,100円 (税込、内税100円含む)")
    print(f"総売上 (sales_gross): {report.sales_gross.amount}円")
    print(f"返品 (returns): {report.returns.amount}円")
    print(f"値引 (discounts): {report.discount_for_lineitems.amount}円")
    print(f"税額合計: {sum(t.tax_amount for t in report.taxes) if report.taxes else 0}円")
    print(f"  - 内税: 100円")
    print(f"  - 外税: 0円")
    print(f"純売上 (sales_net): {report.sales_net.amount}円")

    # Expected values
    expected_sales_gross = 1100.0
    expected_returns = 0.0
    expected_discounts = 0.0
    expected_internal_tax = 100.0
    expected_external_tax = 0.0
    expected_total_tax = 100.0

    # Expected sales_net (tax-exclusive):
    # sales_net = sales_gross - returns - discounts - total_tax
    #           = 1100 - 0 - 0 - 100
    #           = 1000円 (tax-exclusive)
    expected_sales_net = 1000.0

    # Assertions
    assert report.sales_gross.amount == expected_sales_gross, \
        f"Expected sales_gross = {expected_sales_gross}, got {report.sales_gross.amount}"

    assert report.returns.amount == expected_returns, \
        f"Expected returns = {expected_returns}, got {report.returns.amount}"

    assert report.discount_for_lineitems.amount == expected_discounts, \
        f"Expected discounts = {expected_discounts}, got {report.discount_for_lineitems.amount}"

    # THIS IS THE CRITICAL ASSERTION - It will FAIL before the fix
    assert report.sales_net.amount == expected_sales_net, \
        f"Expected sales_net = {expected_sales_net}円 (税抜), but got {report.sales_net.amount}円\n" \
        f"❌ FAILED: Internal tax (100円) is NOT being deducted!\n" \
        f"   Current: {report.sales_net.amount}円 (税込)\n" \
        f"   Expected: {expected_sales_net}円 (税抜)\n" \
        f"   Difference: {report.sales_net.amount - expected_sales_net}円 = Internal tax amount"

    # Verify the formula
    print(f"\n✅ Formula verification:")
    print(f"   純売上 = 総売上 - 返品 - 値引 - 全税額")
    print(f"   {report.sales_net.amount} = {report.sales_gross.amount} - {report.returns.amount} - {report.discount_for_lineitems.amount} - {expected_total_tax}")
    print(f"   {report.sales_net.amount} = {expected_sales_net}")

    # Cleanup
    await collection.delete_many({
        "store_code": "TEST_ISSUE90",
        "terminal_no": 90,
        "business_date": "20251107"
    })

    print("\n✅ Issue #90 test passed! Internal tax is correctly deducted from sales_net.")


@pytest.mark.asyncio
async def test_mixed_tax_scenario(set_env_vars):
    """
    Test with mixed tax scenario (both internal and external tax).

    Scenario:
    - Product A: 1,000円 + 外税10% (100円) = 1,100円
    - Product B: 1,100円 (税込、内税10% = 100円含む)
    - Total: 2,200円
    - Expected net sales (税抜): 2,000円 (1000 + 1000)
    """
    from kugel_common.database import database as local_db_helper

    # Setup
    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    # Create repositories
    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "TEST_ISSUE90")

    collection = db[tran_repo.collection_name]

    # Clean up
    await collection.delete_many({
        "store_code": "TEST_ISSUE90",
        "terminal_no": 91,
        "business_date": "20251107"
    })

    # Create transaction with BOTH external and internal tax
    # Cart service spec for mixed tax:
    #   - sales.total_amount = 2100 (1000 pretax + 1100 tax-inc)
    #   - sales.tax_amount = 100 (external tax only)
    #   - sales.total_amount_with_tax = 2200 (2100 + 100)
    #   - taxes array: [External 100, Internal 100]

    sale_transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="TEST_ISSUE90",
        terminal_no=91,
        transaction_no=910,
        transaction_type=101,  # NormalSales
        business_date="20251107",
        open_counter=1,
        business_counter=1,
        line_items=[
            {
                "line_no": 1,
                "item_code": "EXTERNAL_TAX_ITEM",
                "description": "External Tax Product",
                "unit_price": 1000.0,  # Pre-tax
                "quantity": 1,
                "amount": 1000.0,  # Pre-tax
                "tax_code": "01",  # External tax
                "is_cancelled": False,
                "discounts": []
            },
            {
                "line_no": 2,
                "item_code": "INTERNAL_TAX_ITEM",
                "description": "Internal Tax Product",
                "unit_price": 1100.0,  # Tax-inclusive
                "quantity": 1,
                "amount": 1100.0,  # Tax-inclusive
                "tax_code": "02",  # Internal tax
                "is_cancelled": False,
                "discounts": []
            }
        ],
        subtotal_discounts=[],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 2200.0,
                "deposit_amount": 2200.0,
                "description": "Cash"
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_type": "External",
                "tax_name": "外税10%",
                "tax_amount": 100.0,  # 1000 * 10%
                "target_amount": 1000.0,
                "target_quantity": 1
            },
            {
                "tax_no": 2,
                "tax_code": "02",
                "tax_type": "Internal",
                "tax_name": "内税10%",
                "tax_amount": 100.0,  # 1100 / 1.1 * 0.1
                "target_amount": 1100.0,
                "target_quantity": 1
            }
        ],
        sales={
            "total_quantity": 2,
            "total_amount": 2100.0,  # 1000 (pretax) + 1100 (tax-inc)
            "total_amount_with_tax": 2200.0,  # 2100 + 100 (external)
            "tax_amount": 100.0,  # External tax ONLY
            "total_discount_amount": 0.0,
            "change_amount": 0.0,
            "is_cancelled": False
        },
        transaction_time=datetime.now().isoformat()
    )

    await collection.insert_one(sale_transaction.model_dump())

    # Generate report
    from app.services.report_service import ReportService
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    report = await service.get_report_for_terminal_async(
        store_code="TEST_ISSUE90",
        terminal_no=91,
        report_scope="flash",
        report_type="sales",
        business_date="20251107",
        open_counter=1,
        limit=100,
        page=1
    )

    assert report is not None

    print("\n=== Mixed Tax Test Results ===")
    print(f"Product A: 1,000円 + 外税100円 = 1,100円")
    print(f"Product B: 1,100円 (内税100円含む)")
    print(f"Total: 2,200円")
    print(f"総売上 (sales_gross): {report.sales_gross.amount}円")
    print(f"税額合計: {sum(t.tax_amount for t in report.taxes) if report.taxes else 0}円")
    print(f"  - 外税: 100円")
    print(f"  - 内税: 100円")
    print(f"純売上 (sales_net): {report.sales_net.amount}円")

    expected_sales_gross = 2200.0
    expected_total_tax = 200.0  # 100 external + 100 internal
    expected_sales_net = 2000.0  # 2200 - 200

    assert report.sales_gross.amount == expected_sales_gross
    assert report.sales_net.amount == expected_sales_net, \
        f"Expected sales_net = {expected_sales_net}円, got {report.sales_net.amount}円\n" \
        f"Difference: {report.sales_net.amount - expected_sales_net}円"

    # Cleanup
    await collection.delete_many({
        "store_code": "TEST_ISSUE90",
        "terminal_no": 91,
        "business_date": "20251107"
    })

    print("\n✅ Mixed tax test passed!")


@pytest.mark.asyncio
async def test_internal_tax_with_return(set_env_vars):
    """
    Test internal tax handling with return transactions.

    Scenario:
    - Sale: 1,100円 (税込、内税10% = 100円含む)
    - Return: -1,100円 (税込、内税10% = -100円)
    - Expected net sales: 0円 (sale and return cancel out)
    """
    from kugel_common.database import database as local_db_helper

    # Setup
    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    # Create repositories
    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "TEST_ISSUE90")

    collection = db[tran_repo.collection_name]

    # Clean up
    await collection.delete_many({
        "store_code": "TEST_ISSUE90",
        "terminal_no": 92,
        "business_date": "20251107"
    })

    # Create sale transaction (internal tax)
    sale_transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="TEST_ISSUE90",
        terminal_no=92,
        transaction_no=920,
        transaction_type=101,  # NormalSales
        business_date="20251107",
        open_counter=1,
        business_counter=1,
        line_items=[
            {
                "line_no": 1,
                "item_code": "INTERNAL_TAX_ITEM",
                "description": "Internal Tax Product",
                "unit_price": 1100.0,
                "quantity": 1,
                "amount": 1100.0,
                "tax_code": "02",
                "is_cancelled": False,
                "discounts": []
            }
        ],
        subtotal_discounts=[],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 1100.0,
                "deposit_amount": 1100.0,
                "description": "Cash"
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "02",
                "tax_type": "Internal",
                "tax_name": "内税10%",
                "tax_amount": 100.0,
                "target_amount": 1100.0,
                "target_quantity": 1
            }
        ],
        sales={
            "total_quantity": 1,
            "total_amount": 1100.0,
            "total_amount_with_tax": 1100.0,
            "tax_amount": 0.0,  # Internal tax stored in taxes array
            "total_discount_amount": 0.0,
            "change_amount": 0.0,
            "is_cancelled": False
        },
        transaction_time=datetime.now().isoformat()
    )

    # Create return transaction (internal tax)
    return_transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="TEST_ISSUE90",
        terminal_no=92,
        transaction_no=921,
        transaction_type=102,  # ReturnSales
        business_date="20251107",
        open_counter=1,
        business_counter=1,
        line_items=[
            {
                "line_no": 1,
                "item_code": "INTERNAL_TAX_ITEM",
                "description": "Internal Tax Product",
                "unit_price": 1100.0,
                "quantity": 1,
                "amount": 1100.0,
                "tax_code": "02",
                "is_cancelled": False,
                "discounts": []
            }
        ],
        subtotal_discounts=[],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 1100.0,
                "deposit_amount": 1100.0,
                "description": "Cash"
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "02",
                "tax_type": "Internal",
                "tax_name": "内税10%",
                "tax_amount": 100.0,
                "target_amount": 1100.0,
                "target_quantity": 1
            }
        ],
        sales={
            "total_quantity": 1,
            "total_amount": 1100.0,
            "total_amount_with_tax": 1100.0,
            "tax_amount": 0.0,  # Internal tax stored in taxes array
            "total_discount_amount": 0.0,
            "change_amount": 0.0,
            "is_cancelled": False
        },
        transaction_time=datetime.now().isoformat()
    )

    # Insert test data
    await collection.insert_many([
        sale_transaction.model_dump(),
        return_transaction.model_dump()
    ])

    # Generate report
    from app.services.report_service import ReportService
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    report = await service.get_report_for_terminal_async(
        store_code="TEST_ISSUE90",
        terminal_no=92,
        report_scope="flash",
        report_type="sales",
        business_date="20251107",
        open_counter=1,
        limit=100,
        page=1
    )

    assert report is not None

    print("\n=== Internal Tax + Return Test ===")
    print(f"Sale: 1,100円 (税込、内税100円)")
    print(f"Return: 1,100円 (税込、内税100円)")
    print(f"総売上 (sales_gross): {report.sales_gross.amount}円")
    print(f"返品 (returns): {report.returns.amount}円")
    print(f"税額合計: {sum(t.tax_amount for t in report.taxes) if report.taxes else 0}円")
    print(f"純売上 (sales_net): {report.sales_net.amount}円")

    # Sale 1,100 - Return 1,100 = 0
    # Tax: Sale 100 - Return 100 = 0
    # Net: 0 (sale and return cancel out)
    assert report.sales_gross.amount == 1100.0
    assert report.returns.amount == 1100.0
    assert report.sales_net.amount == 0.0

    # Cleanup
    await collection.delete_many({
        "store_code": "TEST_ISSUE90",
        "terminal_no": 92,
        "business_date": "20251107"
    })

    print("\n✅ Internal tax + return test passed!")


@pytest.mark.asyncio
async def test_multiple_internal_tax_rates(set_env_vars):
    """
    Test with multiple internal tax rates (8% and 10%).

    Scenario:
    - Product A: 1,080円 (税込、内税8% = 80円含む)
    - Product B: 1,100円 (税込、内税10% = 100円含む)
    - Expected net sales: 2,000円 (1000 + 1000)
    """
    from kugel_common.database import database as local_db_helper

    # Setup
    tenant_id = os.environ.get("TENANT_ID")
    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    db = await local_db_helper.get_db_async(db_name)

    # Create repositories
    tran_repo = TranlogRepository(db, tenant_id)
    cash_repo = CashInOutLogRepository(db, tenant_id)
    open_close_repo = OpenCloseLogRepository(db, tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db, tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "TEST_ISSUE90")

    collection = db[tran_repo.collection_name]

    # Clean up
    await collection.delete_many({
        "store_code": "TEST_ISSUE90",
        "terminal_no": 93,
        "business_date": "20251107"
    })

    # Create transaction with multiple internal tax rates
    sale_transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="TEST_ISSUE90",
        terminal_no=93,
        transaction_no=930,
        transaction_type=101,  # NormalSales
        business_date="20251107",
        open_counter=1,
        business_counter=1,
        line_items=[
            {
                "line_no": 1,
                "item_code": "INTERNAL_TAX_8",
                "description": "Internal Tax 8% Product",
                "unit_price": 1080.0,  # 1000 + 8% = 1080
                "quantity": 1,
                "amount": 1080.0,
                "tax_code": "03",  # 8% internal tax
                "is_cancelled": False,
                "discounts": []
            },
            {
                "line_no": 2,
                "item_code": "INTERNAL_TAX_10",
                "description": "Internal Tax 10% Product",
                "unit_price": 1100.0,  # 1000 + 10% = 1100
                "quantity": 1,
                "amount": 1100.0,
                "tax_code": "02",  # 10% internal tax
                "is_cancelled": False,
                "discounts": []
            }
        ],
        subtotal_discounts=[],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 2180.0,
                "deposit_amount": 2180.0,
                "description": "Cash"
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "03",
                "tax_type": "Internal",
                "tax_name": "軽減税率8%",
                "tax_amount": 80.0,  # 1080 / 1.08 * 0.08
                "target_amount": 1080.0,
                "target_quantity": 1
            },
            {
                "tax_no": 2,
                "tax_code": "02",
                "tax_type": "Internal",
                "tax_name": "内税10%",
                "tax_amount": 100.0,  # 1100 / 1.1 * 0.1
                "target_amount": 1100.0,
                "target_quantity": 1
            }
        ],
        sales={
            "total_quantity": 2,
            "total_amount": 2180.0,  # Tax-inclusive total
            "total_amount_with_tax": 2180.0,
            "tax_amount": 0.0,  # Internal tax stored in taxes array
            "total_discount_amount": 0.0,
            "change_amount": 0.0,
            "is_cancelled": False
        },
        transaction_time=datetime.now().isoformat()
    )

    await collection.insert_one(sale_transaction.model_dump())

    # Generate report
    from app.services.report_service import ReportService
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    report = await service.get_report_for_terminal_async(
        store_code="TEST_ISSUE90",
        terminal_no=93,
        report_scope="flash",
        report_type="sales",
        business_date="20251107",
        open_counter=1,
        limit=100,
        page=1
    )

    assert report is not None

    print("\n=== Multiple Internal Tax Rates Test ===")
    print(f"Product A: 1,080円 (内税8% = 80円)")
    print(f"Product B: 1,100円 (内税10% = 100円)")
    print(f"Total: 2,180円")
    print(f"総売上 (sales_gross): {report.sales_gross.amount}円")
    print(f"税額合計: {sum(t.tax_amount for t in report.taxes) if report.taxes else 0}円")
    for tax in report.taxes:
        print(f"  - {tax.tax_name}: {tax.tax_amount}円")
    print(f"純売上 (sales_net): {report.sales_net.amount}円")

    expected_sales_gross = 2180.0
    expected_total_tax = 180.0  # 80 + 100
    expected_sales_net = 2000.0  # 2180 - 180

    assert report.sales_gross.amount == expected_sales_gross
    assert report.sales_net.amount == expected_sales_net, \
        f"Expected sales_net = {expected_sales_net}円, got {report.sales_net.amount}円"

    # Verify both tax rates are present
    tax_amounts = {tax.tax_name: tax.tax_amount for tax in report.taxes}
    assert "軽減税率8%" in tax_amounts
    assert "内税10%" in tax_amounts
    assert tax_amounts["軽減税率8%"] == 80.0
    assert tax_amounts["内税10%"] == 100.0

    # Cleanup
    await collection.delete_many({
        "store_code": "TEST_ISSUE90",
        "terminal_no": 93,
        "business_date": "20251107"
    })

    print("\n✅ Multiple internal tax rates test passed!")


if __name__ == "__main__":
    asyncio.run(test_internal_tax_not_deducted_from_sales_net(lambda: None))
