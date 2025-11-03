# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.receipt.receipt_data_model import Page
from app.models.documents.payment_report_document import PaymentReportDocument

logger = getLogger(__name__)


class PaymentReportReceiptData(AbstractReceiptData[PaymentReportDocument]):
    """
    Class for generating receipt data for payment reports.

    This class extends AbstractReceiptData to provide specialized formatting
    for payment method reports. It handles the generation of receipt text that
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

    def make_receipt_header(self, report: PaymentReportDocument, page: Page):
        """
        Generate the header section of the payment report receipt.

        This includes store information, terminal number, staff ID, date/time,
        report title, and business date information.

        Args:
            report: Payment report document containing the data to format
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
            staff_id_str += report.staff.get("id", "") if isinstance(report.staff, dict) else (report.staff.id if hasattr(report.staff, "id") else "")
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
        page.lines.append(self.line_center("【 決済別レポート " + subtitle + " 】"))
        page.lines.append(self.line_center(" "))

        # Business date or date range
        if report.business_date_from and report.business_date_to:
            # Date range report
            date_from_str = self.format_business_date(report.business_date_from)
            date_to_str = self.format_business_date(report.business_date_to)
            page.lines.append(self.line_left("期間"))
            page.lines.append(self.line_left(f"  {date_from_str}"))
            page.lines.append(self.line_left(f"  ～ {date_to_str}"))
        elif report.business_date:
            # Single date report
            business_date_str = "営業日付 " + self.format_business_date(report.business_date)
            page.lines.append(self.line_left(business_date_str))
        
        if report.open_counter is not None:
            open_counter_str = "開設回数 " + self.fixed_left(self.comma(report.open_counter) + "回", 10)
            page.lines.append(self.line_left(open_counter_str))
        if report.report_scope == "daily" and report.business_counter is not None:
            business_counter_str = "精算通番 " + self.fixed_left(self.comma(report.business_counter), 10)
            page.lines.append(self.line_left(business_counter_str))

    def make_receipt_body(self, report: PaymentReportDocument, page: Page):
        """
        Generate the body section of the payment report receipt.

        This includes payment method breakdowns with counts, amounts,
        and composition ratios.

        Args:
            report: Payment report document containing the data to format
            page: Page object to add lines to
        """

        # --------------------------------
        page.lines.append(self.line_boarder())

        # Payment methods header
        page.lines.append(self.line_left("決 済 方 法 別 集 計"))
        page.lines.append(self.line_boarder())

        # Payment summary details
        # Format:
        # 決済方法名
        #   件数:     999件  構成比: 99.99%
        #   金額: 9,999,999円
        
        for payment in report.payment_summary:
            # Payment method name
            page.lines.append(self.line_left(payment.payment_name))
            
            # Count and ratio on same line
            count_str = f"件数: {self.fixed_right(self.comma(payment.count) + '件', 8)}"
            ratio_str = f"構成比: {self.fixed_right(f'{payment.ratio:.2f}%', 7)}"
            page.lines.append(self.line_left(f"  {count_str} {ratio_str}"))
            
            # Amount
            amount_str = f"金額: {self.fixed_right(self.comma(payment.amount) + '円', 12)}"
            page.lines.append(self.line_left(f"  {amount_str}"))
            
            # Separator between payment methods
            if payment != report.payment_summary[-1]:
                page.lines.append(self.line_left(" "))

        # --------------------------------
        page.lines.append(self.line_boarder())

        # Total section
        page.lines.append(self.line_left("合 計"))
        
        # Total count
        total_count_str = f"総件数: {self.fixed_right(self.comma(report.total.count) + '件', 10)}"
        page.lines.append(self.line_left(f"  {total_count_str}"))
        
        # Total amount
        total_amount_str = f"総金額: {self.fixed_right(self.comma(report.total.amount) + '円', 12)}"
        page.lines.append(self.line_left(f"  {total_amount_str}"))
        
        # --------------------------------
        page.lines.append(self.line_boarder())

    def make_receipt_footer(self, report: PaymentReportDocument, page: Page):
        """
        Generate the footer section of the payment report receipt.

        Args:
            report: Payment report document containing the data to format
            page: Page object to add lines to
        """
        # Add spacing
        page.lines.append(self.line_center(" "))
        page.lines.append(self.line_center(" "))
        
        # End marker
        page.lines.append(self.line_center("*** END ***"))

    def _make_line_for_payment(self, name: str, amount: float, count: int, ratio: float, page: Page):
        """
        Helper method to format a payment method line.

        Args:
            name: Payment method name
            amount: Total amount for this payment method
            count: Number of transactions
            ratio: Composition ratio percentage
            page: Page object to add lines to
        """
        # Format the payment information across multiple lines
        page.lines.append(self.line_left(name))
        
        # Count and ratio
        count_str = f"件数: {self.comma(count)}件"
        ratio_str = f"構成比: {ratio:.2f}%"
        page.lines.append(self.line_left(f"  {count_str}"))
        page.lines.append(self.line_left(f"  {ratio_str}"))
        
        # Amount
        amount_str = f"金額: {self.comma(amount)}円"
        page.lines.append(self.line_left(f"  {amount_str}"))