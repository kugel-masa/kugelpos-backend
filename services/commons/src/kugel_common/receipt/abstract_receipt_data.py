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
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Generic, TypeVar
from xml.dom.minidom import parseString
from logging import getLogger
from datetime import datetime
import locale


logger = getLogger(__name__)

from kugel_common.receipt.receipt_data_model import Page, Line, PrintData, Constants as const
from kugel_common.utils.text_helper import TextHelper

T = TypeVar('T', bound=BaseModel)

class ReceiptData(BaseModel):
    receipt_text: str
    journal_text: str

class AbstractReceiptData(ABC, Generic[T]):

    def __init__(self, name: str, width: int = 32) -> None:
        self.name = name
        self.width = width

    def make_receipt_data(self, model: T) -> ReceiptData:
        print_data = self.generate_print_data(model)
        receipt_text = self.make_receipt_text(print_data)
        journal_text = self.make_journal_text(print_data)
        return ReceiptData(receipt_text=receipt_text, journal_text=journal_text)
    
    def generate_print_data(self, model: T) -> PrintData:
        page  = Page()
        self.make_receipt_header(model, page)
        self.make_receipt_body(model, page)
        self.make_receipt_footer(model, page)
        print_data = PrintData(pages=[page])
        return print_data

    def make_receipt_text(self, print_data: PrintData) -> str:
        print_str = parseString(print_data.to_xml())
        print_xml_str = print_str.toprettyxml(indent="\t")
        print_xml_str = print_xml_str.encode('utf-8').decode('utf-8')
        logger.debug(f"receipt_text: {print_xml_str}")
        return print_xml_str

    def format_datetime(self, date_time_str: str) -> str:
        locale.setlocale(locale.LC_ALL, 'ja_JP.UTF-8')
        dt = datetime.fromisoformat(date_time_str)
        dt_formatted = dt.strftime("%Y年%m月%d日(%a) %H:%M")
        return dt_formatted
    
    def format_business_date(self, business_date_str: str) -> str:
        locale.setlocale(locale.LC_ALL, 'ja_JP.UTF-8')
        if len(business_date_str) == 8 and business_date_str.isdigit():
            business_date_str = business_date_str[:4] + "-" + business_date_str[4:6] + "-" + business_date_str[6:8]
            dt = datetime.fromisoformat(business_date_str)
            dt_formatted = dt.strftime("%Y年%m月%d日(%a)")
        else:
            dt_formatted = business_date_str # no format
        return dt_formatted

    def make_journal_text(self, print_data: PrintData) -> str:
        journal_text = print_data.to_text(width=self.width)
        logger.debug(f"journal_text: {journal_text}")
        return journal_text

    @abstractmethod
    def make_receipt_header(self, model: T, page: Page):
        pass

    @abstractmethod
    def make_receipt_body(self, model: T, page: Page):
        pass

    @abstractmethod
    def make_receipt_footer(self, model: T, page: Page):
        pass

    #
    # make line data for receipt
    #
    def line_split(self, item1: str, item2: str) -> Line:
        return Line(type=const.TYPE_TEXT, align=const.ALIGN_SPLIT, item1=item1, item2=item2)
    
    def line_center(self, text: str) -> Line:
        return Line(type=const.TYPE_TEXT, align=const.ALIGN_CENTER, description=text, item1=None, item2=None)

    def line_left(self, text: str) -> Line:
        return Line(type=const.TYPE_TEXT, align=const.ALIGN_LEFT, description=text, item1=None, item2=None)
    
    def line_right(self, text: str) -> Line:
        return Line(type=const.TYPE_TEXT, align=const.ALIGN_RIGHT, description=text, item1=None, item2=None)
    
    def line_boarder(self) -> Line:
        return Line(type=const.TYPE_LINE, align=None, description=None, item1=None, item2=None)

    def space(self, width: int) -> str:
        return TextHelper.space(width)

    def comma(self, value: float) -> str:
        return TextHelper.comma(value) 

    def yen(self, value: float, mark: str = '\\') -> str:
        return TextHelper.yen(value, mark)

    def zero_fill(self, value: int, width: int) -> str:
        return TextHelper.zero_fill(value, width)

    def fixed_left(self, text: str, width: int) -> str:
        return TextHelper.fixed_left(text, width)

    def fixed_right(self, text: str, width: int) -> str:
        return TextHelper.fixed_right(text, width)

    def fixed_center(self, text: str, width: int) -> str:
        return TextHelper.fixed_center(text, width)