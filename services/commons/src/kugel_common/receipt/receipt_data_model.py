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
from pydantic_xml import BaseXmlModel, attr, element
from typing import List, Optional
from logging import getLogger
import wcwidth

from kugel_common.utils.text_helper import TextHelper

logger = getLogger(__name__)

# constants
class Constants:
    """
    Constants class
    
    Defines constants used for receipt printing, including text display types,
    alignment options, border settings, and frame types.
    """
    TYPE_TEXT = "Text"
    TYPE_LINE = "Line"
    TYPE_BYTE = "Byte"

    ALIGN_CENTER = "Center"
    ALIGN_LEFT = "Left"
    ALIGN_RIGHT = "Right"
    ALIGN_SPLIT = "Split"

    BORADER_OFF = "0"
    BORADER_ON = "1"

    FRAME_BOARDER = "boarder"
    FRAME_HSIDES = "hsides"

    DIMENSION_QR_CODE = "QR_CODE"

# Line model
class Line(BaseXmlModel, tag="Line"):
    """
    Line element model
    
    Represents a single line on a receipt.
    Defines the type, alignment, and content of text lines.
    """
    type: str = attr()
    align: Optional[str] = attr(default=None)
    description: Optional[str] = element(tag="Description", default=None)
    item1: Optional[str] = element(tag="Item1", default=None)
    item2: Optional[str] = element(tag="Item2", default=None)
    
    def __init__(self, **data):
        # Store original item1 value
        item1_original = data.get('item1')
        item2 = data.get('item2')
        
        # Adjust item1 if both item1 and item2 are present
        if item1_original is not None and item2 is not None:
            max_width = 32
            item2_width = wcwidth.wcswidth(item2)
            item1_max_width = max(0, max_width - item2_width - 1)
            data['item1'] = TextHelper.fixed_left(item1_original, item1_max_width, truncate=True)
        
        super().__init__(**data)

# TableRow model
class TableRow(BaseXmlModel, tag="tr"):
    """
    Table row model
    
    Represents a single row in a table.
    Contains multiple columns.
    """
    columns: List[str] = element(tag="td", default=[])

# Table model
class Table(BaseXmlModel, tag="Table"):
    """
    Table model
    
    Represents a table on a receipt.
    Contains border, frame, alignment specifications, and multiple rows.
    """
    border: str = attr()
    frame: str = attr()
    align: Optional[str] = attr(default=None)
    rows: List[TableRow] = element(default=[])

# Page model
class Page(BaseXmlModel, tag="Page"):
    """
    Page model
    
    Represents a single page of a receipt.
    Contains multiple lines and tables.
    """
    lines: List[Line] = element(default=[])
    tables: List[Table] = element(default=[])

# PrintData model 
class PrintData(BaseXmlModel, tag="PrintData"):
    """
    Print data model
    
    Root model representing the complete print data for a receipt.
    Contains multiple pages and can be converted to XML format.
    """
    pages: List[Page] = element(default=[])

    def to_text(self, width: int = 32) -> str:
        text = ""
        for page in self.pages:
            for line in page.lines:
                if line.type == Constants.TYPE_TEXT:
                    if line.align is None:
                        logger.warning(f"Align is None. line->{line}")
                        continue
                    desc = line.description if line.description is not None else ""
                    item1 = line.item1 if line.item1 is not None else ""
                    item2 = line.item2 if line.item2 is not None else ""
                    match line.align:
                        case Constants.ALIGN_CENTER:
                            text += TextHelper.fixed_center(desc, int(width))
                        case Constants.ALIGN_LEFT:
                            text += TextHelper.fixed_left(desc, int(width))
                        case Constants.ALIGN_RIGHT:
                            text += TextHelper.fixed_right(desc, int(width))
                        case Constants.ALIGN_SPLIT:
                            # item1は既に調整済みなので、スペースを追加
                            text += item1 + " " + item2
                elif line.type == Constants.TYPE_LINE:
                    text += "".center(int(width), "-")
                elif line.type == Constants.TYPE_BYTE:
                    logger.debug(f"Byte: {line}")
                    raise ValueError("Not supported type: Byte")
                text += "\n"
        return text