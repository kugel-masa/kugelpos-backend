# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
import logging

from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.receipt.receipt_data_model import Page
from app.models.documents.item_report_document import ItemReportDocument

logger = logging.getLogger(__name__)


class ItemReportReceiptData(AbstractReceiptData[ItemReportDocument]):
    """
    Class for generating receipt text from item report data.
    
    Formats item-based sales report data grouped by categories into a printer-friendly 
    receipt format with proper alignment and Japanese labels.
    """

    def __init__(self, name: str, width: int = 32) -> None:
        """
        Constructor

        Args:
            name: Name of the receipt
            width: Width of the receipt in characters (default: 32)
        """
        super().__init__(name, width)
        self.width = width

    def make_receipt_header(self, report: ItemReportDocument, page: Page):
        """
        Generate the header section of the item report receipt.

        Args:
            report: Item report document
            page: Page object to add lines to
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 店舗名 XXXXXXXXXXXX
        # レジNo. 999          責# 9999999
        # 2025年01月22日(水) 14:30
        # 
        # 【商品別売上レポート( 日報 )】
        # 
        # 営業日付 2025年01月22日(水)
        # 開設回数 999回
        # 精算通番 999,999
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
            staff_id_str += report.staff.get('id', '') if report.staff.get('id') is not None else ""
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
        page.lines.append(self.line_center("【商品別売上レポート" + subtitle + "】"))
        page.lines.append(self.line_center(" "))

        # business date info
        # Handle date range or single date
        if report.business_date_from and report.business_date_to:
            # Date range format
            date_from_str = self.format_business_date(report.business_date_from)
            date_to_str = self.format_business_date(report.business_date_to)
            business_date_str = f"期間 {date_from_str}"
            page.lines.append(self.line_left(business_date_str))
            business_date_str2 = f"     ～ {date_to_str}"
            page.lines.append(self.line_left(business_date_str2))
        elif report.business_date:
            # Single date format
            business_date_str = "営業日付 " + self.format_business_date(report.business_date)
            page.lines.append(self.line_left(business_date_str))
        else:
            # No date information available
            page.lines.append(self.line_left("営業日付 指定なし"))
        if report.open_counter is not None:
            open_counter_str = "開設回数 " + self.fixed_left(self.comma(report.open_counter) + "回", 10)
            page.lines.append(self.line_left(open_counter_str))
        if report.report_scope == "daily" and report.business_counter is not None:
            business_counter_str = "精算通番 " + self.fixed_left(self.comma(report.business_counter), 10)
            page.lines.append(self.line_left(business_counter_str))

    def make_receipt_body(self, report: ItemReportDocument, page: Page):
        """
        Generate the body section of the item report receipt.

        Args:
            report: Item report document
            page: Page object to add lines to
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # --------------------------------
        # カテゴリー名１
        #   商品名１      999点 99,999,999円
        #     値引        999点 -9,999,999円
        #   商品名２      999点    999,999円
        # 小計          9,999点 99,999,999円
        #
        # カテゴリー名２
        #   商品名３      999点    999,999円
        # 小計            999点    999,999円
        # --------------------------------
        # 合計         10,998点 99,999,999円
        #
        # 総売上: 99,999,999円
        # 値引計: 99,999,999円
        # 純売上: 99,999,999円
        # --------------------------------
        page.lines.append(self.line_boarder())
        
        # Categories with items
        for category in report.categories:
            # Category name header
            cat_display = category.category_name or category.category_code or "不明"
            page.lines.append(self.line_left(cat_display))
            
            # Items in category
            for item in category.items:
                for line in self._format_item_lines(item):
                    page.lines.append(line)
            
            # Category subtotal
            cat_quantity_str = self.fixed_right(f"{self._format_number(category.category_total_quantity)}点", 7)
            cat_amount_str = self.fixed_right(f"{self._format_amount(category.category_total_net_amount)}円", 12)
            page.lines.append(self.line_split("小計", f"{cat_quantity_str} {cat_amount_str}"))
            page.lines.append(self.line_left(""))  # Empty line after each category
        
        page.lines.append(self.line_boarder())
        
        # Grand totals
        total_quantity_str = self.fixed_right(f"{self._format_number(report.total_quantity)}点", 7)
        total_amount_str = self.fixed_right(f"{self._format_amount(report.total_net_amount)}円", 12)
        page.lines.append(self.line_split("合計", f"{total_quantity_str} {total_amount_str}"))
        
        page.lines.append(self.line_left(""))
        
        # Additional summary
        page.lines.append(self.line_left(f"総売上: {self._format_amount(report.total_gross_amount)}円"))
        page.lines.append(self.line_left(f"値引計: {self._format_amount(report.total_discount_amount)}円"))
        page.lines.append(self.line_left(f"純売上: {self._format_amount(report.total_net_amount)}円"))
        
        # --------------------------------
        page.lines.append(self.line_boarder())

    def make_receipt_footer(self, report: ItemReportDocument, page: Page):
        """
        Generate the footer section of the item report receipt.

        Args:
            report: Item report document
            page: Page object to add lines to
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # レシートNo. ------
        receipt_no_str = "レシートNo. " + "------"
        page.lines.append(self.line_left(receipt_no_str))


    def _format_item_lines(self, item: ItemReportDocument.ItemReportItem) -> list:
        """Format item lines with main line and discount line"""
        lines = []
        
        # Use item name or code
        item_display = item.item_name or item.item_code or "不明"
        # Indent item name with 2 spaces
        item_display = "  " + item_display
        
        # Truncate item name if too long (leaving room for quantity and amount)
        max_item_length = self.width - 18  # Reserve space for quantity and amount
        if len(item_display) > max_item_length:
            item_display = item_display[:max_item_length-1] + "…"
        
        # First line: item name with quantity and gross amount
        quantity_str = self.fixed_right(f"{self._format_number(item.quantity)}点", 5)
        gross_amount_str = self.fixed_right(f"{self._format_amount(item.gross_amount)}円", 12)
        lines.append(self.line_split(item_display, f"{quantity_str} {gross_amount_str}"))
        
        # Second line: discount information (only if there are discounts)
        if item.discount_amount > 0 or item.discount_quantity > 0:
            discount_qty_str = self.fixed_right(f"{self._format_number(item.discount_quantity)}点", 5)
            discount_amount_str = self.fixed_right(f"-{self._format_amount(item.discount_amount)}円", 12)
            lines.append(self.line_split("    値引", f"{discount_qty_str} {discount_amount_str}"))
        
        return lines

    def _format_amount(self, amount: float) -> str:
        """Format amount with comma separator"""
        return f"{int(amount):,}"

    def _format_number(self, number: int) -> str:
        """Format number with comma separator"""
        return f"{number:,}"