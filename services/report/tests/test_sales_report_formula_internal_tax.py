"""
Test for sales report formula with internal tax (内税).
Tests the correct implementation of the formula:
純売上 = 総売上 - 返品 - 値引 - 税額

Issue #85: https://github.com/kugel-masa/kugelpos-backend-private/issues/85
"""

import asyncio
import os
from datetime import datetime, timezone

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository
from app.models.repositories.terminal_info_web_repository import TerminalInfoWebRepository


@pytest.mark.asyncio
async def test_internal_tax_with_discount_and_return(set_env_vars):
    """
    Test sales report formula with internal tax scenario.

    Scenario:
    - Sale: Product 3,500 yen (税込), discount 500 yen, tax 273 yen (included), total 3,000 yen (税込)
    - Return: Same item returned

    Expected results:
    - 総売上 (sales_gross) = 3,000 + 500 = 3,500円
    - 返品 (returns) = 3,000円
    - 明細値引 (discount_for_lineitems) = 500 (sale) - 500 (return) = 0円
    - 小計値引 (discount_for_subtotal) = 0円
    - 税額 (tax) = 273 - 273 = 0円
    - 純売上 (sales_net) = 3,500 - 3,000 - 0 - 0 = 500円
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
    terminal_info_repo = TerminalInfoWebRepository(tenant_id, "TEST_STORE_INT")

    collection = db[tran_repo.collection_name]

    # Clean up existing test data
    await collection.delete_many({
        "store_code": "TEST_STORE_INT",
        "terminal_no": 88,
        "business_date": "20251107"
    })

    # Create sale transaction (internal tax)
    # For internal tax: total_amount = total_amount_with_tax (both are tax-inclusive)
    # Tax amount is calculated as: amount / 1.1 * 0.1 = amount * 0.10 / 1.10
    from datetime import datetime

    sale_transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="TEST_STORE_INT",
        terminal_no=88,
        transaction_no=600,
        transaction_type=101,  # NormalSales
        business_date="20251107",
        open_counter=1,
        business_counter=1,
        line_items=[
            {
                "line_no": 1,
                "item_code": "PROD002",
                "description": "Test Product Internal Tax",
                "unit_price": 3500.0,  # Tax-inclusive price
                "quantity": 1,
                "amount": 3500.0,  # Tax-inclusive
                "tax_code": "01",
                "is_cancelled": False,
                "discounts": [
                    {
                        "discount_amount": 500.0
                    }
                ]
            }
        ],
        subtotal_discounts=[],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 3000.0,  # Tax-inclusive amount after discount
                "deposit_amount": 3000.0,
                "description": "Cash"
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "消費税10%",
                "tax_amount": 273.0,
                "target_amount": 2727.0,  # Net amount: 3000 / 1.1 ≒ 2727
                "target_quantity": 1
            }
        ],
        sales={
            "total_quantity": 1,
            "total_amount": 3000.0,  # For internal tax: this is tax-inclusive
            "total_amount_with_tax": 3000.0,  # Same as total_amount for internal tax
            "tax_amount": 0.0,  # Internal tax is stored in taxes array, not here (Cart service spec)
            "total_discount_amount": 500.0,
            "change_amount": 0.0,
            "is_cancelled": False
        },
        transaction_time=datetime.now().isoformat()
    )

    # Create return transaction (internal tax)
    return_transaction = BaseTransaction(
        tenant_id=tenant_id,
        store_code="TEST_STORE_INT",
        terminal_no=88,
        transaction_no=601,
        transaction_type=102,  # ReturnSales
        business_date="20251107",
        open_counter=1,
        business_counter=1,
        line_items=[
            {
                "line_no": 1,
                "item_code": "PROD002",
                "description": "Test Product Internal Tax",
                "unit_price": 3500.0,
                "quantity": 1,
                "amount": 3500.0,
                "tax_code": "01",
                "is_cancelled": False,
                "discounts": [
                    {
                        "discount_amount": 500.0
                    }
                ]
            }
        ],
        subtotal_discounts=[],
        payments=[
            {
                "payment_no": 1,
                "payment_code": "01",
                "amount": 3000.0,
                "deposit_amount": 3000.0,
                "description": "Cash"
            }
        ],
        taxes=[
            {
                "tax_no": 1,
                "tax_code": "01",
                "tax_name": "消費税10%",
                "tax_amount": 273.0,
                "target_amount": 2727.0,
                "target_quantity": 1
            }
        ],
        sales={
            "total_quantity": 1,
            "total_amount": 3000.0,
            "total_amount_with_tax": 3000.0,
            "tax_amount": 0.0,  # Internal tax is stored in taxes array, not here (Cart service spec)
            "total_discount_amount": 500.0,
            "change_amount": 0.0,
            "is_cancelled": False
        },
        transaction_time=datetime.now().isoformat()
    )

    # Insert test data
    # Note: Use model_dump() without by_alias to store in snake_case format
    # which matches the aggregation pipeline expectations
    await collection.insert_one(sale_transaction.model_dump())
    await collection.insert_one(return_transaction.model_dump())

    # Generate report through ReportService (like working tests)
    from app.services.report_service import ReportService
    service = ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo
    )

    report = await service.get_report_for_terminal_async(
        store_code="TEST_STORE_INT",
        terminal_no=88,
        report_scope="flash",
        report_type="sales",
        business_date="20251107",
        open_counter=1,
        limit=100,
        page=1
    )

    # Verify report
    assert report is not None, "No report generated"
    report_doc = report

    print("\n=== Internal Tax Test Results ===")
    print(f"総売上 (sales_gross): {report_doc.sales_gross.amount} yen (count: {report_doc.sales_gross.count})")
    print(f"返品 (returns): {report_doc.returns.amount} yen (count: {report_doc.returns.count})")
    print(f"明細値引 (discount_for_lineitems): {report_doc.discount_for_lineitems.amount} yen")
    print(f"小計値引 (discount_for_subtotal): {report_doc.discount_for_subtotal.amount} yen")
    print(f"純売上 (sales_net): {report_doc.sales_net.amount} yen")
    tax_amount = sum(t.tax_amount for t in report_doc.taxes) if report_doc.taxes else 0.0
    print(f"税額 (tax): {tax_amount} yen")

    # Assertions based on Issue #85 specification
    sales_gross_amount = report_doc.sales_gross.amount
    returns_amount = report_doc.returns.amount
    discount_for_lineitems_amount = report_doc.discount_for_lineitems.amount
    discount_for_subtotal_amount = report_doc.discount_for_subtotal.amount
    sales_net_amount = report_doc.sales_net.amount

    # 総売上 = 3,000 (税込) + 500 (値引) = 3,500円
    assert sales_gross_amount == 3500.0, \
        f"Expected sales_gross.amount = 3500.0, got {sales_gross_amount}"

    # 返品 = 3,000円 (税込)
    assert returns_amount == 3000.0, \
        f"Expected returns.amount = 3000.0, got {returns_amount}"

    # 明細値引 = 0円 (sale discount 500 - return discount 500)
    assert discount_for_lineitems_amount == 0.0, \
        f"Expected discount_for_lineitems.amount = 0.0, got {discount_for_lineitems_amount}"

    # 小計値引 = 0円
    assert discount_for_subtotal_amount == 0.0, \
        f"Expected discount_for_subtotal.amount = 0.0, got {discount_for_subtotal_amount}"

    # 純売上 = 3,500 - 3,000 - 0 - 0 (net_tax) = 500円
    expected_sales_net = 500.0
    assert sales_net_amount == expected_sales_net, \
        f"Expected sales_net.amount = {expected_sales_net}, got {sales_net_amount}"

    # Verify the formula holds
    print(f"\n✅ Formula verification:")
    print(f"   純売上 ({sales_net_amount}) = 総売上 ({sales_gross_amount}) - 返品 ({returns_amount}) - 明細値引 ({discount_for_lineitems_amount}) - 小計値引 ({discount_for_subtotal_amount}) - 税額 (0)")
    print(f"   {sales_net_amount} = {sales_gross_amount} - {returns_amount} - {discount_for_lineitems_amount} - {discount_for_subtotal_amount} - 0")
    print(f"   {sales_net_amount} = {sales_gross_amount - returns_amount - discount_for_lineitems_amount - discount_for_subtotal_amount}")

    # Cleanup
    await collection.delete_many({
        "store_code": "TEST_STORE_INT",
        "terminal_no": 88,
        "business_date": "20251107"
    })

    print("\n✅ All internal tax test assertions passed!")


if __name__ == "__main__":
    asyncio.run(test_internal_tax_with_discount_and_return(lambda: None))
