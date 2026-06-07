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
from datetime import datetime
from logging import getLogger
from typing import Any, Generic, Optional, TypeVar
import json
import locale

import wcwidth
from pydantic import BaseModel

from kugel_common.receipt.print_document_model import (
    Column,
    ColumnsElement,
    Metadata,
    PrintDocument,
    RuledLineElement,
    TextElement,
)
from kugel_common.receipt.receipt_data_model import Line, Page
from kugel_common.utils.text_helper import TextHelper

logger = getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ReceiptData(BaseModel):
    """Result of a receipt strategy: ``receipt_text`` holds the device-agnostic
    print document serialized as a JSON string; ``journal_text`` is the
    plain-text electronic journal."""

    receipt_text: str
    journal_text: str


class AbstractReceiptData(ABC, Generic[T]):

    def __init__(self, name: str, width: int = 32) -> None:
        self.name = name
        self.width = width
        # Subclasses may override to emit a different documentType (e.g. "report").
        self.document_type = "receipt"

    def make_receipt_data(self, model: T) -> ReceiptData:
        page = self.generate_print_data(model)
        # The print document (a structured dict) is serialized to a JSON string
        # and carried in the ``receipt_text`` field (same field/type as before;
        # only the content changed from XML to JSON).
        print_document = self.build_print_document(model, page.lines)
        receipt_text = json.dumps(print_document, ensure_ascii=False)
        journal_text = self.render_journal_text(page.lines)
        return ReceiptData(receipt_text=receipt_text, journal_text=journal_text)

    def generate_print_data(self, model: T) -> Page:
        page = Page()
        self.make_receipt_header(model, page)
        self.make_receipt_body(model, page)
        self.make_receipt_footer(model, page)
        return page

    #
    # print_document (JSON) generation
    #
    def build_print_document(self, model: T, elements: list[Line]) -> dict[str, Any]:
        """Build the device-agnostic print document (camelCase dict) from the
        ordered print elements produced by the strategy.

        Only elements routed to the receipt (channel R or RJ) are included; the
        channel attribute itself is excluded from the serialized output."""
        metadata = self._build_metadata(model)
        receipt_elements = [e for e in elements if getattr(e, "channel", "RJ") in ("R", "RJ")]
        document = PrintDocument(metadata=metadata, elements=receipt_elements)
        doc_dict = document.to_dict()
        logger.debug(f"print_document: {doc_dict}")
        return doc_dict

    def _build_metadata(self, model: T) -> Metadata:
        """Extract document metadata from the source model via common attributes."""
        generated_at = getattr(model, "generate_date_time", None)
        return Metadata(
            document_type=self.document_type,
            tenant_id=getattr(model, "tenant_id", None),
            store_code=getattr(model, "store_code", None),
            terminal_no=getattr(model, "terminal_no", None),
            transaction_no=getattr(model, "transaction_no", None),
            receipt_no=getattr(model, "receipt_no", None),
            business_date=getattr(model, "business_date", None),
            generated_at=generated_at,
            chars_per_line=self.width,
        )

    #
    # journal_text (plain text) generation — kept byte-equivalent to the
    # previous PrintData.to_text() implementation.
    #
    def render_journal_text(self, elements: list[Line]) -> str:
        width = int(self.width)
        text = ""
        for element in elements:
            # Only elements routed to the journal (channel J or RJ) are rendered.
            if getattr(element, "channel", "RJ") not in ("J", "RJ"):
                continue
            el_type = getattr(element, "type", None)
            if el_type == "text":
                text += self._render_text_element(element, width)
            elif el_type == "columns":
                text += self._render_columns_element(element, width)
            elif el_type == "ruledLine":
                # str.center requires a single fill char; take the first char.
                fill_char = (element.char or "-")[:1] or "-"
                text += "".center(width, fill_char)
            else:
                # feed/cut/barcode/qrcode/image/logo do not appear in the
                # current production strategies; skip them in the plain-text
                # journal (they carry no plain-text representation here).
                continue
            text += "\n"
        return text

    def _render_text_element(self, element: TextElement, width: int) -> str:
        value = element.value if element.value is not None else ""
        match element.align:
            case "center":
                return TextHelper.fixed_center(value, width)
            case "right":
                return TextHelper.fixed_right(value, width)
            case _:
                return TextHelper.fixed_left(value, width)

    def _render_columns_element(self, element: ColumnsElement, width: int) -> str:
        columns = element.columns
        slots = {c.slot for c in columns}
        # Production strategies always emit a left+right pair (from line_split);
        # reproduce the exact previous split formatting to avoid any regression.
        if len(columns) == 2 and slots == {"left", "right"}:
            left = next(c for c in columns if c.slot == "left").value
            right = next(c for c in columns if c.slot == "right").value
            left_max_width = max(0, width - wcwidth.wcswidth(right) - 1)
            return TextHelper.fixed_left(left, left_max_width, truncate=True) + " " + right
        # General layout (used by richer documents): place left/mid by position
        # and right-justify the right slot.
        return self._render_columns_general(columns, width)

    def _render_columns_general(self, columns: list[Column], width: int) -> str:
        line = ""
        cursor = 0
        right_value: Optional[str] = None
        for column in columns:
            if column.slot == "right":
                right_value = column.value
                continue
            if column.slot == "left":
                start = 0
            elif column.start_col is not None:
                start = column.start_col
            else:
                start = cursor
            if start > cursor:
                line += TextHelper.space(start - cursor)
                cursor = start
            line += column.value
            cursor += wcwidth.wcswidth(column.value)
        if right_value is not None:
            pad = width - cursor - wcwidth.wcswidth(right_value)
            line += TextHelper.space(max(1, pad)) + right_value
        return line

    #
    # date/format helpers
    #
    def format_datetime(self, date_time_str: str) -> str:
        locale.setlocale(locale.LC_ALL, "ja_JP.UTF-8")
        dt = datetime.fromisoformat(date_time_str)
        dt_formatted = dt.strftime("%Y年%m月%d日(%a) %H:%M")
        return dt_formatted

    def format_business_date(self, business_date_str: str) -> str:
        locale.setlocale(locale.LC_ALL, "ja_JP.UTF-8")
        if len(business_date_str) == 8 and business_date_str.isdigit():
            business_date_str = business_date_str[:4] + "-" + business_date_str[4:6] + "-" + business_date_str[6:8]
            dt = datetime.fromisoformat(business_date_str)
            dt_formatted = dt.strftime("%Y年%m月%d日(%a)")
        else:
            dt_formatted = business_date_str  # no format
        return dt_formatted

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
    # line builders (backward-compatible shims) — produce print_document
    # elements instead of XML lines. Signatures and call sites are unchanged.
    #
    # ``channel`` routes the line to the receipt (R), the journal (J), or both
    # (RJ, default). It defaults to RJ so existing call sites are unchanged.
    def line_split(self, item1: str, item2: str, channel: str = "RJ") -> Line:
        return ColumnsElement(
            channel=channel,
            columns=[
                Column(slot="left", value=item1),
                Column(slot="right", value=item2),
            ],
        )

    def line_center(self, text: str, channel: str = "RJ") -> Line:
        return TextElement(channel=channel, value=text, align="center")

    def line_left(self, text: str, channel: str = "RJ") -> Line:
        return TextElement(channel=channel, value=text, align="left")

    def line_right(self, text: str, channel: str = "RJ") -> Line:
        return TextElement(channel=channel, value=text, align="right")

    def line_boarder(self, channel: str = "RJ") -> Line:
        return RuledLineElement(channel=channel, char="-")

    #
    # text helpers
    #
    def space(self, width: int) -> str:
        return TextHelper.space(width)

    def comma(self, value: float) -> str:
        return TextHelper.comma(value)

    def yen(self, value: float, mark: str = "\\") -> str:
        return TextHelper.yen(value, mark)

    def zero_fill(self, value: int, width: int) -> str:
        return TextHelper.zero_fill(value, width)

    def fixed_left(self, text: str, width: int) -> str:
        return TextHelper.fixed_left(text, width)

    def fixed_right(self, text: str, width: int) -> str:
        return TextHelper.fixed_right(text, width)

    def fixed_center(self, text: str, width: int) -> str:
        return TextHelper.fixed_center(text, width)
