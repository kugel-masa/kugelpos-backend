# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.receipt.receipt_data_model import Page

from app.models.documents.open_close_log import OpenCloseLog

logger = getLogger(__name__)


class OpenCloseReceiptData(AbstractReceiptData[OpenCloseLog]):
    """
    Open/Close Receipt Data Generator

    This class is responsible for generating formatted receipt data for terminal open and close operations.
    It formats the terminal status details in a structured format suitable for printing
    on a receipt or displaying in a journal.
    """

    def __init__(self, name: str, width: int = 32) -> None:
        """
        Initialize a new open/close receipt data generator

        Args:
            name: Name identifier for this receipt generator
            width: Width of the receipt in characters (default: 32)
        """
        super().__init__(name, width)
        self.width = width

    def make_receipt_header(self, open_close_log: OpenCloseLog, page: Page):
        """
        Generate the header section of the open/close receipt

        Creates the top part of the receipt including:
        - Store name and information
        - Terminal number
        - Staff information
        - Date and time
        - Operation type title (Open or Close)
        - Business date and session information

        Args:
            open_close_log: Open/close log data to format
            page: Receipt page to add content to
        """
        # store_name
        store_name_str = (
            "店舗名 " + open_close_log.store_name
            if open_close_log.store_name is not None
            else open_close_log.store_code
        )
        page.lines.append(self.line_left(store_name_str))

        # terminal_no and staff_id
        if open_close_log.terminal_no is None:
            terminal_no_str = "店舗合計"
        else:
            terminal_no_str = "レジNo. " + f"{open_close_log.terminal_no}"
        terminal_info = open_close_log.terminal_info
        if terminal_info is not None and terminal_info.staff is not None:
            staff_id_str = "責# " + self.zero_fill(open_close_log.staff_id, 6)
        else:
            staff_id_str = "責# ------"
        page.lines.append(self.line_split(terminal_no_str, staff_id_str))

        # datetime
        date_time_str = self.format_datetime(open_close_log.generate_date_time)
        page.lines.append(self.line_left(date_time_str))

        # title
        page.lines.append(self.line_center(" "))
        if open_close_log.operation == "open":
            title = "開 設"  # Open terminal
        else:
            title = "精 算"  # Close terminal
        page.lines.append(self.line_center(f"【 {title}  レ ポ ー ト 】"))
        page.lines.append(self.line_center(" "))

        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 営業日付 2021年01月01日(木)
        # 開設回数 999,999回
        # 精算通番 999,999回
        business_date_str = "営業日付 " + self.format_business_date(open_close_log.business_date)
        page.lines.append(self.line_left(business_date_str))
        if open_close_log.open_counter is not None:
            open_counter_str = "開設回数 " + self.fixed_left(self.comma(open_close_log.open_counter) + "回", 10)
            page.lines.append(self.line_left(open_counter_str))

        if open_close_log.open_counter == "close":
            if open_close_log.business_counter is not None:
                business_counter_str = "精算通番 " + self.fixed_left(
                    self.comma(open_close_log.business_counter) + "回", 10
                )
                page.lines.append(self.line_left(business_counter_str))

    def make_receipt_body(self, open_close_log: OpenCloseLog, page: Page):
        """
        Generate the body section of the open/close receipt

        Creates the main part of the receipt showing different details based on
        whether this is an open or close operation.

        Args:
            open_close_log: Open/close log data to format
            page: Receipt page to add content to
        """
        # --------------------------------
        page.lines.append(self.line_boarder())

        if open_close_log.operation == "open":
            self._make_open_receipt_body(open_close_log, page)
        else:
            self._make_close_receipt_body(open_close_log, page)

        # --------------------------------
        page.lines.append(self.line_boarder())

    def _make_open_receipt_body(self, open_close_log: OpenCloseLog, page: Page):
        """
        Generate the body section for terminal opening receipts

        Shows the initial cash amount (float) in the terminal at opening

        Args:
            open_close_log: Open log data to format
            page: Receipt page to add content to
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 釣銭準備金　　       99,999,999円
        terminal_info = open_close_log.terminal_info
        if terminal_info is not None and terminal_info.initial_amount is not None:
            initial_amount = terminal_info.initial_amount
        else:
            initial_amount = 0
        amount_str = self.comma(initial_amount) + "円"
        page.lines.append(self.line_split("釣銭準備金", amount_str))

    def _make_close_receipt_body(self, open_close_log: OpenCloseLog, page: Page):
        """
        Generate the body section for terminal closing receipts

        Shows the counted physical cash amount in the terminal at closing

        Args:
            open_close_log: Close log data to format
            page: Receipt page to add content to
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # ドロア内現金　　     99,999,999円
        terminal_info = open_close_log.terminal_info
        if terminal_info is not None and terminal_info.physical_amount is not None:
            pysical_amount = terminal_info.physical_amount
        else:
            pysical_amount = 0
        amount_str = self.comma(pysical_amount) + "円"
        page.lines.append(self.line_split("ドロア内現金", amount_str))

    def make_receipt_footer(self, open_close_log: OpenCloseLog, page: Page):
        """
        Generate the footer section of the open/close receipt

        Creates the bottom part of the receipt showing:
        - Receipt number

        Args:
            open_close_log: Open/close log data to format
            page: Receipt page to add content to
        """
        # receipt_no
        receipt_no_str = "レシートNo. " + "------"
        page.lines.append(self.line_left(receipt_no_str))
