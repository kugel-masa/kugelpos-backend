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
Internal intermediate representation used while a receipt strategy builds its
content. A strategy appends print elements to ``Page.lines`` via the
``line_*`` helpers on ``AbstractReceiptData``; the base then renders the page
into the device-agnostic ``print_document`` (JSON) and the plain-text
``journal_text``.

The XML representation (previously ``PrintData`` / pydantic-xml) has been
removed; the canonical print-data format is now JSON (see
``print_document_model``).
"""
from logging import getLogger
from typing import List

from pydantic import BaseModel, Field

from kugel_common.receipt.print_document_model import Element

logger = getLogger(__name__)


class Constants:
    """Constants used while building receipt content (alignment, element kinds)."""

    TYPE_TEXT = "Text"
    TYPE_LINE = "Line"

    ALIGN_CENTER = "Center"
    ALIGN_LEFT = "Left"
    ALIGN_RIGHT = "Right"
    ALIGN_SPLIT = "Split"


# Backward-compatible alias: strategies type-annotate built elements as ``Line``.
# Elements are now ``print_document`` elements (TextElement/ColumnsElement/...).
Line = Element


class Page(BaseModel):
    """A page accumulates ordered print elements appended by a strategy."""

    lines: List[Element] = Field(default_factory=list)
