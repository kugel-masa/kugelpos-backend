# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.receipt.receipt_data_model import Page
from app.models.documents.sales_report_document import SalesReportDocument

logger = getLogger(__name__)


class SalesReportReceiptData(AbstractReceiptData[SalesReportDocument]):
    """
    Class for generating receipt data for sales reports.

    This class extends AbstractReceiptData to provide specialized formatting
    for sales report receipts. It handles the generation of receipt text that
    will be printed or displayed to the user.
    """

    def __init__(self, name: str, width: int = 32) -> None:
        """
        Initialize the receipt data generator.

        Args:
            name: Name of the receipt
            width: Width of the receipt in characters (default: 32)
        """
        super().__init__(name, width)
        self.width = width

    def make_receipt_header(self, report: SalesReportDocument, page: Page):
        """
        Generate the header section of the sales report receipt.

        This includes store information, terminal number, staff ID, date/time,
        report title, and business date information.

        Args:
            report: Sales report document containing the data to format
            page: Page object to add lines to
        """

        # store_name
        store_name_str = "店舗名 " + report.store_name if report.store_name is not None else ""
        page.lines.append(self.line_left(store_name_str))

        # terminal_no and staff_id
        if report.terminal_no is None:
            terminal_no_str = "店舗合計"
        else:
            terminal_no_str = "レジNo. " + f"{report.terminal_no}"
        staff_id_str = "責# "
        if report.staff is not None:
            staff_id_str += report.staff.id if report.staff.id is not None else ""
        page.lines.append(self.line_split(terminal_no_str, staff_id_str))

        # datetime
        date_time_str = self.format_datetime(report.generate_date_time)
        page.lines.append(self.line_left(date_time_str))

        # title
        page.lines.append(self.line_center(" "))
        if report.report_scope == "daily":
            subtitle = "( 日報 )"
        else:
            subtitle = "( 速報 )"
        page.lines.append(self.line_center("【 売 上 レ ポ ー ト " + subtitle + " 】"))
        page.lines.append(self.line_center(" "))

        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 営業日付 2021年01月01日(木)
        # 開設回数 999回
        # 精算通番 999,999
        business_date_str = "営業日付 " + self.format_business_date(report.business_date)
        page.lines.append(self.line_left(business_date_str))
        if report.open_counter is not None:
            open_counter_str = "開設回数 " + self.fixed_left(self.comma(report.open_counter) + "回", 10)
            page.lines.append(self.line_left(open_counter_str))
        if report.report_scope == "daily" and report.business_counter is not None:
            business_counter_str = "精算通番 " + self.fixed_left(self.comma(report.business_counter), 10)
            page.lines.append(self.line_left(business_counter_str))

    def make_receipt_body(self, report: SalesReportDocument, page: Page):
        """
        Generate the body section of the sales report receipt.

        This includes sales totals, tax amounts, payment methods,
        cash in/out operations, and cash drawer information.

        Args:
            report: Sales report document containing the data to format
            page: Page object to add lines to
        """

        # Calculate tax amounts for display adjustments
        # External tax: added to gross sales
        exclusive_tax_amount = sum(
            tax.tax_amount for tax in report.taxes
            if tax.tax_type == "External"
        )

        # Internal tax: subtracted from net sales
        inclusive_tax_amount = sum(
            tax.tax_amount for tax in report.taxes
            if tax.tax_type == "Internal"
        )

        # Total tax: displayed as negative line item
        total_tax_amount = sum(tax.tax_amount for tax in report.taxes)

        # --------------------------------
        page.lines.append(self.line_boarder())

        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 売 上 合 計
        #  総売上      999件   99,999,999円  ← Tax-inclusive (with external tax)
        # 　　　       999点
        #  返　品      999件   99,999,999円
        # 　　　       999点
        #  明細値引    999件   99,999,999円
        # 　　　       999点
        #  小計値引    999件   99,999,999円
        # 　　　       999点
        #  税額                -9,999,999円  ← New line (negative)
        #  純売上      999件   99,999,999円  ← Tax-exclusive (without internal tax)
        # 　　　       999点
        page.lines.append(self.line_left("売 上 合 計"))
        # Gross sales: add external tax to display as tax-inclusive
        gross_amount_with_tax = report.sales_gross.amount + exclusive_tax_amount
        self._make_line_for_sales(
            "総売上", gross_amount_with_tax, report.sales_gross.quantity, report.sales_gross.count, page
        )
        self._make_line_for_sales("返品", report.returns.amount, report.returns.quantity, report.returns.count, page)
        self._make_line_for_sales(
            "明細値引",
            report.discount_for_lineitems.amount,
            report.discount_for_lineitems.quantity,
            report.discount_for_lineitems.count,
            page,
        )
        self._make_line_for_sales(
            "小計値引",
            report.discount_for_subtotal.amount,
            report.discount_for_subtotal.quantity,
            report.discount_for_subtotal.count,
            page,
        )
        # Tax amount line: display as negative (no count/quantity)
        self._make_line("税額", -total_tax_amount, page)
        # Net sales: subtract internal tax to display as tax-exclusive
        net_amount_pretax = report.sales_net.amount - inclusive_tax_amount
        self._make_line_for_sales(
            "純売上", net_amount_pretax, report.sales_net.quantity, report.sales_net.count, page
        )

        # --------------------------------
        page.lines.append(self.line_boarder())

        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 税 額（内訳）
        #  税名称      　      99,999,999円
        #  税名称      　      99,999,999円
        page.lines.append(self.line_left("税 額（内訳）"))
        for tax in report.taxes:
            # Display all taxes without parentheses
            self._make_line(tax.tax_name, tax.tax_amount, page)

        # --------------------------------
        page.lines.append(self.line_boarder())

        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 支　払
        #  支払名称    　      99,999,999円
        #  支払名称    　      99,999,999円
        page.lines.append(self.line_left("支 払"))
        for payment in report.payments:
            self._make_line(payment.payment_name, payment.amount, page)

        # --------------------------------
        page.lines.append(self.line_boarder())

        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 入出金
        #  入金        999件   99,999,999円
        #  出金        999件   99,999,999円
        page.lines.append(self.line_left("入出金"))
        self._make_line_with_count("入金", report.cash.cash_in.amount, report.cash.cash_in.count, page)
        self._make_line_with_count("出金", report.cash.cash_out.amount, report.cash.cash_out.count, page)

        # --------------------------------
        page.lines.append(self.line_boarder())

        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 現　金
        #  ドロア内現金　　     99,999,999円
        #  あるべき現金　　     99,999,999円
        #  過不足 　           99,999,999円
        page.lines.append(self.line_left("現 金"))
        self._make_line("ドロア内現金", report.cash.physical_amount, page)
        self._make_line("あるべき現金", report.cash.logical_amount, page)
        self._make_line("過不足", report.cash.difference_amount, page)

        # --------------------------------
        page.lines.append(self.line_boarder())

    def make_receipt_footer(self, report: SalesReportDocument, page: Page):
        """
        Generate the footer section of the sales report receipt.

        This includes the receipt number.

        Args:
            report: Sales report document containing the data to format
            page: Page object to add lines to
        """
        # receipt_no
        receipt_no_str = "レシートNo. " + "------"
        page.lines.append(self.line_left(receipt_no_str))

    def _make_line_for_sales(self, title: str, amount: float, quantity: int, count: int, page: Page):
        """
        Format a sales line with amount, quantity, and count.

        Args:
            title: Title of the sales line (e.g., "総売上")
            amount: Sales amount
            quantity: Item quantity
            count: Transaction count
            page: Page object to add lines to
        """
        self._make_line_with_count(title, amount, count, page)
        quantity_str = self.comma(quantity) + "点"
        page.lines.append(self.line_left(self.space(12) + self.fixed_right(quantity_str, 5)))
        return

    def _make_line(self, title: str, amount: float, page: Page):
        """
        Format a simple line with title and amount.

        Args:
            title: Line title
            amount: Amount to display
            page: Page object to add lines to
        """
        amount_str = self.comma(amount) + "円"
        page.lines.append(self.line_split((self.space(1) + title), amount_str))
        return

    def _make_line_with_count(self, title: str, amount: float, count: int, page: Page):
        """
        Format a line with title, amount, and count.

        Args:
            title: Line title
            amount: Amount to display
            count: Count to display
            page: Page object to add lines to
        """
        amount_str = self.comma(amount) + "円"
        count_str = self.comma(count) + "件"
        page.lines.append(
            self.line_split(self.fixed_left(self.space(1) + title, 12) + self.fixed_right(count_str, 5), amount_str)
        )
        return

    def _make_line_with_parentheses(self, title: str, amount: float, page: Page):
        """
        Format a line with title and amount in parentheses.
        Used for inclusive tax display.

        Args:
            title: Line title
            amount: Amount to display
            page: Page object to add lines to
        """
        amount_str = self.comma(amount) + "円"
        page.lines.append(self.line_split((self.space(1) + "(" + title), amount_str + ")"))
        return
