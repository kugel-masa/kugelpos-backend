# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.receipt.receipt_data_model import Page

from app.models.documents.cash_in_out_log import CashInOutLog

logger = getLogger(__name__)


class CashInOutReceiptData(AbstractReceiptData[CashInOutLog]):
    """
    Cash In/Out Receipt Data Generator

    This class is responsible for generating formatted receipt data for cash in/out operations.
    It formats the cash transaction details in a structured format suitable for printing
    on a receipt or displaying in a journal.
    """

    def __init__(self, name: str, width: int = 32) -> None:
        """
        Initialize a new cash in/out receipt data generator

        Args:
            name: Name identifier for this receipt generator
            width: Width of the receipt in characters (default: 32)
        """
        super().__init__(name, width)
        self.width = width

    def make_receipt_header(self, cash_log: CashInOutLog, page: Page):
        """
        Generate the header section of the cash in/out receipt

        Creates the top part of the receipt including:
        - Store name and information
        - Terminal number
        - Staff information
        - Date and time
        - Transaction type title
        - Business date and session information

        Args:
            cash_log: Cash in/out log data to format
            page: Receipt page to add content to
        """
        # store_name
        store_name_str = "店舗名 " + cash_log.store_name if cash_log.store_name is not None else cash_log.store_code
        page.lines.append(self.line_left(store_name_str))

        # terminal_no
        if cash_log.terminal_no is None:
            terminal_no_str = "店舗合計"
        else:
            terminal_no_str = "レジNo. " + f"{cash_log.terminal_no}"

        # staff info
        if cash_log.staff_id is not None:
            staff_id_str = "責# " + self.zero_fill(cash_log.staff_id, 6)
        else:
            staff_id_str = "責# ------"
        page.lines.append(self.line_split(terminal_no_str, staff_id_str))

        # datetime
        date_time_str = self.format_datetime(cash_log.generate_date_time)
        page.lines.append(self.line_left(date_time_str))

        # title
        page.lines.append(self.line_center(" "))
        if cash_log.amount < 0:
            title = "出 金"  # Cash out
        else:
            title = "入 金"  # Cash in
        page.lines.append(self.line_center(f"【 {title}  レ ポ ー ト 】"))
        page.lines.append(self.line_center(" "))

        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 営業日付 2021年01月01日(木)
        # 開設回数 999回
        business_date_str = "営業日付 " + self.format_business_date(cash_log.business_date)
        page.lines.append(self.line_left(business_date_str))
        if cash_log.open_counter is not None:
            open_counter_str = "開設回数 " + self.fixed_left(self.comma(cash_log.open_counter) + "回", 10)
            page.lines.append(self.line_left(open_counter_str))

    def make_receipt_body(self, cash_log: CashInOutLog, page: Page):
        """
        Generate the body section of the cash in/out receipt

        Creates the main part of the receipt showing:
        - Transaction amount
        - Transaction description

        Args:
            cash_log: Cash in/out log data to format
            page: Receipt page to add content to
        """
        # --------------------------------
        page.lines.append(self.line_boarder())

        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 入出金科目            9,999,999円
        desc = cash_log.description if cash_log.description is not None else ""
        amt_str = self.comma(cash_log.amount) + "円"
        page.lines.append(self.line_split(desc, amt_str))

        # --------------------------------
        page.lines.append(self.line_boarder())

    def make_receipt_footer(self, cash_log: CashInOutLog, page: Page):
        """
        Generate the footer section of the cash in/out receipt

        Creates the bottom part of the receipt showing:
        - Receipt number

        Args:
            cash_log: Cash in/out log data to format
            page: Receipt page to add content to
        """
        # receipt_no
        receipt_no_str = "レシートNo. " + "------"
        page.lines.append(self.line_left(receipt_no_str))
