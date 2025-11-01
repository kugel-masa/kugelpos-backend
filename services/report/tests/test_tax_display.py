# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Test cases for sales report tax display improvements (Issue #76).

This module tests the new tax display logic that shows:
- Gross sales as tax-inclusive (with external tax)
- New "税額" line showing total tax as negative
- Net sales as tax-exclusive (without internal tax)
- Tax breakdown section with all taxes without parentheses
"""

import pytest
from app.models.documents.sales_report_document import SalesReportDocument, SalesReportTemplate, TaxReportTemplate, PaymentReportTemplate, CashReportTemplate, CashInOutReportTemplate
from app.services.plugins.sales_report_receipt_data import SalesReportReceiptData
from kugel_common.receipt.receipt_data_model import Page


class TestTaxDisplayLogic:
    """Test suite for tax display logic improvements."""

    def create_sample_report(
        self,
        gross_amount: float,
        net_amount: float,
        taxes: list[dict],
        returns_amount: float = 0.0,
        discount_lineitem: float = 0.0,
        discount_subtotal: float = 0.0,
    ) -> SalesReportDocument:
        """
        Create a sample sales report document for testing.

        Args:
            gross_amount: Gross sales amount (before tax adjustments)
            net_amount: Net sales amount (before tax adjustments)
            taxes: List of tax dictionaries with tax_name, tax_amount, tax_type
            returns_amount: Return amount
            discount_lineitem: Line item discount amount
            discount_subtotal: Subtotal discount amount

        Returns:
            SalesReportDocument: Sample report document
        """
        tax_templates = [
            TaxReportTemplate(
                tax_name=tax["tax_name"],
                tax_amount=tax["tax_amount"],
                target_amount=tax.get("target_amount", 1000.0),
                target_quantity=tax.get("target_quantity", 1),
                tax_type=tax["tax_type"]
            )
            for tax in taxes
        ]

        return SalesReportDocument(
            tenant_id="test_tenant",
            store_code="STORE001",
            store_name="Test Store",
            terminal_no=1,
            business_counter=1,
            business_date="20251101",
            open_counter=1,
            report_scope="daily",
            report_type="sales",
            sales_gross=SalesReportTemplate(amount=gross_amount, quantity=10, count=2),
            sales_net=SalesReportTemplate(amount=net_amount, quantity=10, count=2),
            returns=SalesReportTemplate(amount=returns_amount, quantity=0, count=0),
            discount_for_lineitems=SalesReportTemplate(amount=discount_lineitem, quantity=0, count=0),
            discount_for_subtotal=SalesReportTemplate(amount=discount_subtotal, quantity=0, count=0),
            taxes=tax_templates,
            payments=[
                PaymentReportTemplate(payment_name="Cash", amount=net_amount + sum(t["tax_amount"] for t in taxes), count=1)
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

    def extract_receipt_lines(self, receipt_text: str) -> dict:
        """
        Extract key values from receipt XML text for verification.

        Args:
            receipt_text: XML receipt text

        Returns:
            dict: Extracted values (gross_sales, tax_line, net_sales, tax_breakdown, etc.)
        """
        import re

        result = {}

        # Extract gross sales amount
        gross_match = re.search(r'総売上.*?<Item2>([0-9,]+)円</Item2>', receipt_text, re.DOTALL)
        if gross_match:
            result["gross_sales"] = float(gross_match.group(1).replace(',', ''))

        # Extract tax line amount
        tax_line_match = re.search(r'税額.*?<Item2>([0-9,-]+)円</Item2>', receipt_text, re.DOTALL)
        if tax_line_match:
            result["tax_line"] = float(tax_line_match.group(1).replace(',', ''))

        # Extract net sales amount
        net_match = re.search(r'純売上.*?<Item2>([0-9,]+)円</Item2>', receipt_text, re.DOTALL)
        if net_match:
            result["net_sales"] = float(net_match.group(1).replace(',', ''))

        # Extract tax breakdown amounts
        tax_breakdown = []
        tax_section = re.search(r'税 額（内訳）</Line>(.*?)</Page>', receipt_text, re.DOTALL)
        if tax_section:
            # Find all tax lines that come after "税 額（内訳）" and before the next section
            tax_content = tax_section.group(1)
            # Stop at the first Line type="Line" after tax section starts
            next_section = re.search(r'<Line type="Line"/>', tax_content)
            if next_section:
                tax_content = tax_content[:next_section.start()]

            tax_items = re.findall(r'<Line type="Text" align="Split">.*?<Item1>\s*([^<]+?)\s*</Item1>.*?<Item2>([0-9,]+)円</Item2>', tax_content, re.DOTALL)
            for tax_name, tax_amount in tax_items:
                tax_breakdown.append({
                    "name": tax_name.strip(),
                    "amount": float(tax_amount.replace(',', ''))
                })
        result["tax_breakdown"] = tax_breakdown

        # Check for parentheses in tax breakdown
        result["has_parentheses"] = '(' in tax_content if tax_section and 'tax_content' in locals() else False

        return result

    def test_external_tax_only(self):
        """Test display with external tax only (外税のみ)."""
        # Setup: 1,000 yen product with 10% external tax (100 yen)
        report = self.create_sample_report(
            gross_amount=1000.0,
            net_amount=1000.0,
            taxes=[
                {"tax_name": "消費税10%", "tax_amount": 100.0, "tax_type": "External"}
            ]
        )

        # Generate receipt
        receipt_gen = SalesReportReceiptData("Test Receipt", 32)
        receipt_data = receipt_gen.make_receipt_data(report)

        # Verify
        lines = self.extract_receipt_lines(receipt_data.receipt_text)

        # Gross sales should include external tax
        assert lines["gross_sales"] == 1100.0, f"Expected 1100 (1000 + 100), got {lines['gross_sales']}"

        # Tax line should be negative total tax
        assert lines["tax_line"] == -100.0, f"Expected -100, got {lines['tax_line']}"

        # Net sales should remain unchanged (no internal tax)
        assert lines["net_sales"] == 1000.0, f"Expected 1000, got {lines['net_sales']}"

        # Verify calculation: gross - tax = net
        assert lines["gross_sales"] + lines["tax_line"] == lines["net_sales"]

        # Tax breakdown should not have parentheses
        assert not lines["has_parentheses"], "Tax amounts should not have parentheses"

    def test_internal_tax_only(self):
        """Test display with internal tax only (内税のみ)."""
        # Setup: 1,100 yen product with 10% internal tax (100 yen included)
        report = self.create_sample_report(
            gross_amount=1100.0,
            net_amount=1100.0,
            taxes=[
                {"tax_name": "内消費税10%", "tax_amount": 100.0, "tax_type": "Internal"}
            ]
        )

        # Generate receipt
        receipt_gen = SalesReportReceiptData("Test Receipt", 32)
        receipt_data = receipt_gen.make_receipt_data(report)

        # Verify
        lines = self.extract_receipt_lines(receipt_data.receipt_text)

        # Gross sales should remain unchanged (no external tax to add)
        assert lines["gross_sales"] == 1100.0, f"Expected 1100, got {lines['gross_sales']}"

        # Tax line should be negative total tax
        assert lines["tax_line"] == -100.0, f"Expected -100, got {lines['tax_line']}"

        # Net sales should subtract internal tax
        assert lines["net_sales"] == 1000.0, f"Expected 1000 (1100 - 100), got {lines['net_sales']}"

        # Verify calculation: gross - tax = net
        assert lines["gross_sales"] + lines["tax_line"] == lines["net_sales"]

        # Tax breakdown should not have parentheses (even for internal tax)
        assert not lines["has_parentheses"], "Internal tax should not have parentheses"

    def test_mixed_tax_types(self):
        """Test display with mixed external and internal taxes (外税・内税混在)."""
        # Setup:
        # - External tax product: 1,000 yen + 100 yen tax
        # - Internal tax product: 1,100 yen (includes 100 yen tax)
        report = self.create_sample_report(
            gross_amount=2100.0,  # 1000 (external base) + 1100 (internal total)
            net_amount=2100.0,
            taxes=[
                {"tax_name": "消費税10%", "tax_amount": 100.0, "tax_type": "External"},
                {"tax_name": "内消費税10%", "tax_amount": 100.0, "tax_type": "Internal"}
            ]
        )

        # Generate receipt
        receipt_gen = SalesReportReceiptData("Test Receipt", 32)
        receipt_data = receipt_gen.make_receipt_data(report)

        # Verify
        lines = self.extract_receipt_lines(receipt_data.receipt_text)

        # Gross sales should add external tax
        assert lines["gross_sales"] == 2200.0, f"Expected 2200 (2100 + 100), got {lines['gross_sales']}"

        # Tax line should be negative total of both taxes
        assert lines["tax_line"] == -200.0, f"Expected -200, got {lines['tax_line']}"

        # Net sales should subtract internal tax
        assert lines["net_sales"] == 2000.0, f"Expected 2000 (2100 - 100), got {lines['net_sales']}"

        # Verify calculation: gross - tax = net
        assert lines["gross_sales"] + lines["tax_line"] == lines["net_sales"]

        # Verify both taxes are in breakdown
        assert len(lines["tax_breakdown"]) == 2, "Should have 2 tax entries"
        assert any(t["name"] == "消費税10%" and t["amount"] == 100.0 for t in lines["tax_breakdown"])
        assert any(t["name"] == "内消費税10%" and t["amount"] == 100.0 for t in lines["tax_breakdown"])

    def test_multiple_tax_rates(self):
        """Test display with multiple tax rates (複数税率)."""
        # Setup:
        # - 10% external: 70 yen
        # - 8% external: 80 yen
        # - 10% internal: 90 yen
        # - 8% internal: 40 yen
        report = self.create_sample_report(
            gross_amount=2000.0,
            net_amount=2000.0,
            taxes=[
                {"tax_name": "消費税10%", "tax_amount": 70.0, "tax_type": "External"},
                {"tax_name": "消費税8%", "tax_amount": 80.0, "tax_type": "External"},
                {"tax_name": "内消費税10%", "tax_amount": 90.0, "tax_type": "Internal"},
                {"tax_name": "内消費税8%", "tax_amount": 40.0, "tax_type": "Internal"}
            ]
        )

        # Generate receipt
        receipt_gen = SalesReportReceiptData("Test Receipt", 32)
        receipt_data = receipt_gen.make_receipt_data(report)

        # Verify
        lines = self.extract_receipt_lines(receipt_data.receipt_text)

        # Calculate expected values
        external_tax_total = 70.0 + 80.0  # 150
        internal_tax_total = 90.0 + 40.0  # 130
        total_tax = external_tax_total + internal_tax_total  # 280

        # Gross sales should add all external taxes
        assert lines["gross_sales"] == 2150.0, f"Expected 2150 (2000 + 150), got {lines['gross_sales']}"

        # Tax line should be negative total of all taxes
        assert lines["tax_line"] == -280.0, f"Expected -280, got {lines['tax_line']}"

        # Net sales should subtract all internal taxes
        assert lines["net_sales"] == 1870.0, f"Expected 1870 (2000 - 130), got {lines['net_sales']}"

        # Verify calculation: gross - tax = net
        assert lines["gross_sales"] + lines["tax_line"] == lines["net_sales"]

        # Verify all 4 taxes are in breakdown
        assert len(lines["tax_breakdown"]) == 4, "Should have 4 tax entries"

    def test_with_discounts(self):
        """Test display with discounts (値引きあり)."""
        # Setup: Product with discounts and taxes
        report = self.create_sample_report(
            gross_amount=1000.0,
            net_amount=800.0,  # After 200 yen discount
            taxes=[
                {"tax_name": "消費税10%", "tax_amount": 80.0, "tax_type": "External"}
            ],
            discount_lineitem=100.0,
            discount_subtotal=100.0
        )

        # Generate receipt
        receipt_gen = SalesReportReceiptData("Test Receipt", 32)
        receipt_data = receipt_gen.make_receipt_data(report)

        # Verify
        lines = self.extract_receipt_lines(receipt_data.receipt_text)

        # Gross sales should add external tax
        assert lines["gross_sales"] == 1080.0, f"Expected 1080 (1000 + 80), got {lines['gross_sales']}"

        # Tax line should be negative
        assert lines["tax_line"] == -80.0, f"Expected -80, got {lines['tax_line']}"

        # Net sales should remain as is (discounts already applied in net_amount)
        assert lines["net_sales"] == 800.0, f"Expected 800, got {lines['net_sales']}"

        # Manual verification: gross - returns - discount_lineitem - discount_subtotal - tax = net
        # 1080 - 0 - 100 - 100 - 80 = 800 ✓

    def test_with_returns(self):
        """Test display with returns (返品あり)."""
        # Setup: Sales with returns
        report = self.create_sample_report(
            gross_amount=1000.0,
            net_amount=500.0,  # After 500 yen return
            taxes=[
                {"tax_name": "消費税10%", "tax_amount": 50.0, "tax_type": "External"}
            ],
            returns_amount=500.0
        )

        # Generate receipt
        receipt_gen = SalesReportReceiptData("Test Receipt", 32)
        receipt_data = receipt_gen.make_receipt_data(report)

        # Verify
        lines = self.extract_receipt_lines(receipt_data.receipt_text)

        # Gross sales should add external tax
        assert lines["gross_sales"] == 1050.0, f"Expected 1050 (1000 + 50), got {lines['gross_sales']}"

        # Tax line should be negative
        assert lines["tax_line"] == -50.0, f"Expected -50, got {lines['tax_line']}"

        # Net sales should remain as is
        assert lines["net_sales"] == 500.0, f"Expected 500, got {lines['net_sales']}"

    def test_zero_taxes(self):
        """Test display with no taxes (税額ゼロ)."""
        # Setup: Tax-exempt product
        report = self.create_sample_report(
            gross_amount=1000.0,
            net_amount=1000.0,
            taxes=[]
        )

        # Generate receipt
        receipt_gen = SalesReportReceiptData("Test Receipt", 32)
        receipt_data = receipt_gen.make_receipt_data(report)

        # Verify
        lines = self.extract_receipt_lines(receipt_data.receipt_text)

        # All amounts should remain unchanged when no taxes
        assert lines["gross_sales"] == 1000.0, f"Expected 1000, got {lines['gross_sales']}"
        assert lines["tax_line"] == 0.0, f"Expected 0, got {lines['tax_line']}"
        assert lines["net_sales"] == 1000.0, f"Expected 1000, got {lines['net_sales']}"

    def test_tax_breakdown_label(self):
        """Test that tax breakdown section has correct label (税 額（内訳）)."""
        report = self.create_sample_report(
            gross_amount=1000.0,
            net_amount=1000.0,
            taxes=[
                {"tax_name": "消費税10%", "tax_amount": 100.0, "tax_type": "External"}
            ]
        )

        # Generate receipt
        receipt_gen = SalesReportReceiptData("Test Receipt", 32)
        receipt_data = receipt_gen.make_receipt_data(report)

        # Verify label exists
        assert "税 額（内訳）" in receipt_data.receipt_text, "Tax breakdown section should have label '税 額（内訳）'"

    def test_payment_amount_calculation(self):
        """Test that payment amount calculation is consistent with report data."""
        # Setup: Mixed taxes
        external_tax = 70.0
        internal_tax = 30.0
        net_amount = 1100.0  # Original net amount before display adjustments

        report = self.create_sample_report(
            gross_amount=1100.0,
            net_amount=net_amount,
            taxes=[
                {"tax_name": "消費税10%", "tax_amount": external_tax, "tax_type": "External"},
                {"tax_name": "内消費税8%", "tax_amount": internal_tax, "tax_type": "Internal"}
            ]
        )

        # Payment amount is based on original net_amount + all taxes
        # This is set in create_sample_report: net_amount + sum(taxes)
        expected_payment = net_amount + external_tax + internal_tax  # 1100 + 70 + 30 = 1200

        # Generate receipt
        receipt_gen = SalesReportReceiptData("Test Receipt", 32)
        receipt_data = receipt_gen.make_receipt_data(report)

        # Extract payment amount from receipt
        import re
        payment_match = re.search(r'支 払.*?Cash.*?<Item2>([0-9,]+)円</Item2>', receipt_data.receipt_text, re.DOTALL)
        assert payment_match, "Should find payment amount"

        payment_amount = float(payment_match.group(1).replace(',', ''))

        # Verify payment = original net amount + all taxes
        assert payment_amount == expected_payment, \
            f"Payment {payment_amount} should equal net_amount {net_amount} + taxes {external_tax + internal_tax} = {expected_payment}"

        # Also verify the receipt calculation consistency:
        # Displayed net sales should equal original net amount minus internal tax
        lines = self.extract_receipt_lines(receipt_data.receipt_text)
        expected_net_sales_display = net_amount - internal_tax  # 1100 - 30 = 1070

        assert lines["net_sales"] == expected_net_sales_display, \
            f"Displayed net sales {lines['net_sales']} should equal net_amount {net_amount} - internal_tax {internal_tax} = {expected_net_sales_display}"
