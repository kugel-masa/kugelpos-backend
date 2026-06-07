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
Device-agnostic print-data JSON model (`print_document`).

This module defines the OPOS/printer-independent print-data schema produced by
the backend (cart/terminal/report) and consumed downstream (frontend/device)
for receipt rendering. See specs/139-receipt-print-schema/contracts.

Key points:
  - Output is camelCase JSON via ``model_dump(by_alias=True, exclude_none=True)``.
  - Multi-column lines (`columns`) are emitted as *semantic* columns (no baked
    spaces); column alignment / spacing is the consumer's responsibility based
    on ``metadata.charsPerLine``.
  - Styling (`style`) applies at line level for `text` and at column level for
    `columns` entries.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# camelCase aliasing; allow construction by either python or alias name.
_camel = ConfigDict(populate_by_name=True)


class Style(BaseModel):
    """Character styling. Unset fields fall back to renderer/consumer defaults."""

    model_config = _camel
    bold: Optional[bool] = None
    underline: Optional[int] = Field(None, ge=0, le=2)
    reverse: Optional[bool] = None
    scale_width: Optional[int] = Field(None, ge=1, le=8, alias="scaleWidth")
    scale_height: Optional[int] = Field(None, ge=1, le=8, alias="scaleHeight")
    font: Optional[Literal["A", "B"]] = None


class PrintElement(BaseModel):
    """Base for all print elements.

    Carries the internal routing channel (R=receipt only, J=journal only,
    RJ=both). The backend uses it to split content between ``print_document``
    (R/RJ) and ``journal_text`` (J/RJ). It is an internal routing attribute and
    is excluded from the serialized print document (the consumer receives the
    receipt view only, with no per-element station)."""

    model_config = _camel
    channel: Literal["R", "J", "RJ"] = Field("RJ", exclude=True)


class TextElement(PrintElement):
    """A single-content text line (styling applies at line level)."""

    model_config = _camel
    type: Literal["text"] = "text"
    value: str
    align: Literal["left", "center", "right"] = "left"
    style: Optional[Style] = None


class Column(BaseModel):
    """One column within a `columns` line (styling applies at column level)."""

    model_config = _camel
    slot: Literal["left", "mid", "right"]
    value: str
    # Required only for the `mid` slot: fixed offset from the left (half-width
    # columns, 0-based, based on metadata.charsPerLine).
    start_col: Optional[int] = Field(None, alias="startCol")
    # Default per slot: left/mid -> left, right -> right (resolved by consumer).
    align: Optional[Literal["left", "center", "right"]] = None
    style: Optional[Style] = None


class ColumnsElement(PrintElement):
    """A multi-column line emitted as semantic columns (no baked spaces)."""

    type: Literal["columns"] = "columns"
    columns: list[Column]


class RuledLineElement(PrintElement):
    """A horizontal separator drawn across the full printer width."""

    type: Literal["ruledLine"] = "ruledLine"
    char: str = "-"


class FeedElement(PrintElement):
    """Vertical line feed."""

    type: Literal["feed"] = "feed"
    lines: int = Field(ge=1, le=255)


class CutElement(PrintElement):
    """Paper cut."""

    type: Literal["cut"] = "cut"
    mode: Literal["full", "partial"] = "full"


class BarcodeElement(PrintElement):
    """Barcode element (symbology is a logical name resolved by the consumer)."""

    model_config = _camel
    type: Literal["barcode"] = "barcode"
    symbology: str
    data: str
    height: Optional[int] = None
    module_width: Optional[int] = Field(None, alias="moduleWidth")
    hri: Literal["none", "above", "below"] = "none"
    align: Literal["left", "center", "right"] = "center"


class QrcodeElement(PrintElement):
    """QR code element."""

    model_config = _camel
    type: Literal["qrcode"] = "qrcode"
    data: str
    error_correction: Literal["L", "M", "Q", "H"] = Field("M", alias="errorCorrection")
    module_size: Optional[int] = Field(None, alias="moduleSize")
    align: Literal["left", "center", "right"] = "center"


class ImageSource(BaseModel):
    """Image source: base64-embedded data or a URL reference."""

    model_config = _camel
    kind: Literal["base64", "url"]
    data: str
    format: Optional[str] = None


class ImageElement(PrintElement):
    """Ad-hoc bitmap image element."""

    model_config = _camel
    type: Literal["image"] = "image"
    source: ImageSource
    align: Literal["left", "center", "right"] = "center"
    # Width in dots, or "auto" for native size.
    width: Union[int, Literal["auto"]] = "auto"


class LogoElement(PrintElement):
    """Pre-registered logo element (referenced by identifier)."""

    model_config = _camel
    type: Literal["logo"] = "logo"
    logo_id: str = Field(alias="logoId")
    align: Literal["left", "center", "right"] = "center"


# Discriminated union of all print elements, ordered as they appear on output.
Element = Annotated[
    Union[
        TextElement,
        ColumnsElement,
        RuledLineElement,
        FeedElement,
        CutElement,
        BarcodeElement,
        QrcodeElement,
        ImageElement,
        LogoElement,
    ],
    Field(discriminator="type"),
]


class Metadata(BaseModel):
    """Document metadata. ``charsPerLine`` is the design-reference width that the
    consumer uses as the basis to adapt to the actual printer width."""

    model_config = _camel
    document_type: str = Field("receipt", alias="documentType")
    tenant_id: Optional[str] = Field(None, alias="tenantId")
    store_code: Optional[str] = Field(None, alias="storeCode")
    terminal_no: Optional[int] = Field(None, alias="terminalNo")
    transaction_no: Optional[int] = Field(None, alias="transactionNo")
    receipt_no: Optional[int] = Field(None, alias="receiptNo")
    business_date: Optional[str] = Field(None, alias="businessDate")
    generated_at: Optional[str] = Field(None, alias="generatedAt")
    locale: str = "ja-JP"
    chars_per_line: int = Field(32, alias="charsPerLine")


class PrintDocument(BaseModel):
    """Root print-data document. Serialize with :meth:`to_dict` for storage and
    transport (camelCase, omitting unset fields)."""

    model_config = _camel
    schema_version: str = Field("1.0", alias="schemaVersion")
    metadata: Metadata
    elements: list[Element] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a camelCase dict suitable for MongoDB / pub-sub / API."""
        return self.model_dump(by_alias=True, exclude_none=True)
