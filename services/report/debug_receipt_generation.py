#!/usr/bin/env python3
"""Debug script to see what receipt is actually generated"""

import sys
sys.path.insert(0, '/home/masa/proj/kugelpos-public/services/report')

from app.services.plugins.sales_report_receipt_data import SalesReportReceiptData
from app.models.documents.sales_report_document import (
    SalesReportDocument,
    TaxReportTemplate,
    SalesReportTemplate,
    PaymentReportTemplate,
    CashReportTemplate,
    CashInOutReportTemplate
)

# Create a sample report with taxes
report = SalesReportDocument(
    tenant_id="test_tenant",
    store_code="STORE001",
    store_name="Test Store",
    terminal_no=1,
    business_counter=1,
    business_date="20251101",
    open_counter=1,
    report_scope="daily",
    report_type="sales",
    sales_gross=SalesReportTemplate(amount=2100.0, quantity=10, count=2),
    sales_net=SalesReportTemplate(amount=2100.0, quantity=10, count=2),
    returns=SalesReportTemplate(amount=0.0, quantity=0, count=0),
    discount_for_lineitems=SalesReportTemplate(amount=0.0, quantity=0, count=0),
    discount_for_subtotal=SalesReportTemplate(amount=0.0, quantity=0, count=0),
    taxes=[
        TaxReportTemplate(
            tax_name="消費税10%",
            tax_amount=100.0,
            target_amount=1000.0,
            target_quantity=1,
            tax_type="External"
        ),
        TaxReportTemplate(
            tax_name="内消費税10%",
            tax_amount=100.0,
            target_amount=1000.0,
            target_quantity=1,
            tax_type="Internal"
        )
    ],
    payments=[
        PaymentReportTemplate(payment_name="Cash", amount=2200.0, count=1)
    ],
    cash=CashReportTemplate(
        logical_amount=1000.0,
        physical_amount=1000.0,
        difference_amount=0.0,
        cash_in=CashInOutReportTemplate(amount=0.0, count=0),
        cash_out=CashInOutReportTemplate(amount=0.0, count=0),
    ),
    generate_date_time="2025-11-01T12:00:00",
)

print("=" * 80)
print("Report object details:")
print(f"  report.taxes type: {type(report.taxes)}")
print(f"  report.taxes length: {len(report.taxes)}")
print(f"  report.taxes content:")
for idx, tax in enumerate(report.taxes):
    print(f"    [{idx}] {tax.tax_name}: {tax.tax_amount} ({tax.tax_type})")

print("\n" + "=" * 80)
print("Generating receipt data...")
receipt_generator = SalesReportReceiptData("Sales Report", 32)
receipt_data = receipt_generator.make_receipt_data(report)

print("\n" + "=" * 80)
print("Receipt text output:")
print(receipt_data.receipt_text)

print("\n" + "=" * 80)
print("Searching for tax breakdown in receipt:")
lines = receipt_data.receipt_text.split('\n')
tax_section_found = False
for i, line in enumerate(lines):
    if '税 額（内訳）' in line or '税' in line:
        print(f"Line {i}: {line}")
        tax_section_found = True
        # Print next 5 lines after finding tax section
        for j in range(1, 6):
            if i + j < len(lines):
                print(f"Line {i+j}: {lines[i+j]}")

if not tax_section_found:
    print("No tax section found in receipt!")

print("\n" + "=" * 80)
