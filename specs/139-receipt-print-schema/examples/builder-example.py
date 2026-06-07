# Copyright 2026 TRIAL Company, Inc.
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
#316 印字データ JSON（Level 1）— アプリ側コードの例示（設計用・未実装）

本ファイルは「サンプル印字データ（examples/normal-sale.json）を、どのような
アプリコードで生成するか」を示す**設計例示**であり、製品コードではない。

Level 1 のポイント:
  - 複数カラム行は columns 要素（left/mid/right）で**意味のまま**出力する
    （空白を焼き込まない）。桁揃えは DeviceGW が metadata.charsPerLine を
    基準に実施する（ADR-0003）。
  - mid は startCol（左からの固定オフセット）。桁衝突時は mid.startCol で left を切詰め。
  - style は text=行単位 / columns=カラム単位。

構成:
  A. JSON モデル（pydantic v2）       … kugel_common/receipt/print_document_model.py 相当
  B. ビルダ（意味カラムをそのまま積む）
  C. 戦略 build_print_document()      … normal-sale.json を 1:1 で生成
  D. 既存フローへの差し込み（make_receipt_data の XML 経路を JSON へ置換）
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

_camel = ConfigDict(populate_by_name=True)


# =====================================================================
# A. JSON モデル（pydantic v2）— 出力は model_dump_json(by_alias=True) で camelCase
# =====================================================================
class Style(BaseModel):
    # 各フィールドは省略可（未指定＝既定をレンダラ/DeviceGW が適用）。
    model_config = _camel
    bold: Optional[bool] = None
    underline: Optional[int] = Field(None, ge=0, le=2)
    reverse: Optional[bool] = None
    scale_width: Optional[int] = Field(None, ge=1, le=8, alias="scaleWidth")
    scale_height: Optional[int] = Field(None, ge=1, le=8, alias="scaleHeight")
    font: Optional[Literal["A", "B"]] = None


class TextElement(BaseModel):
    model_config = _camel
    type: Literal["text"] = "text"
    value: str
    align: Literal["left", "center", "right"] = "left"
    style: Optional[Style] = None


class Column(BaseModel):
    model_config = _camel
    slot: Literal["left", "mid", "right"]
    value: str
    start_col: Optional[int] = Field(None, alias="startCol")  # mid のみ必須
    align: Optional[Literal["left", "center", "right"]] = None  # 既定: left/mid=left, right=right
    style: Optional[Style] = None


class ColumnsElement(BaseModel):
    type: Literal["columns"] = "columns"
    columns: list[Column]


class RuledLineElement(BaseModel):
    type: Literal["ruledLine"] = "ruledLine"
    char: str = "-"


class FeedElement(BaseModel):
    type: Literal["feed"] = "feed"
    lines: int


class CutElement(BaseModel):
    type: Literal["cut"] = "cut"
    mode: Literal["full", "partial"] = "full"


class BarcodeElement(BaseModel):
    model_config = _camel
    type: Literal["barcode"] = "barcode"
    symbology: str
    data: str
    height: Optional[int] = None
    module_width: Optional[int] = Field(None, alias="moduleWidth")
    hri: Literal["none", "above", "below"] = "none"
    align: Literal["left", "center", "right"] = "center"


class QrcodeElement(BaseModel):
    model_config = _camel
    type: Literal["qrcode"] = "qrcode"
    data: str
    error_correction: Literal["L", "M", "Q", "H"] = Field("M", alias="errorCorrection")
    module_size: Optional[int] = Field(None, alias="moduleSize")
    align: Literal["left", "center", "right"] = "center"


class LogoElement(BaseModel):
    model_config = _camel
    type: Literal["logo"] = "logo"
    logo_id: str = Field(alias="logoId")
    align: Literal["left", "center", "right"] = "center"


Element = Annotated[
    Union[
        TextElement, ColumnsElement, RuledLineElement, FeedElement,
        CutElement, BarcodeElement, QrcodeElement, LogoElement,
    ],
    Field(discriminator="type"),
]


class Metadata(BaseModel):
    model_config = _camel
    document_type: str = Field("receipt", alias="documentType")
    tenant_id: str = Field(alias="tenantId")
    store_code: str = Field(alias="storeCode")
    terminal_no: int = Field(alias="terminalNo")
    transaction_no: Optional[int] = Field(None, alias="transactionNo")
    receipt_no: Optional[int] = Field(None, alias="receiptNo")
    business_date: Optional[str] = Field(None, alias="businessDate")
    generated_at: str = Field(alias="generatedAt")
    locale: str = "ja-JP"
    chars_per_line: int = Field(48, alias="charsPerLine")  # 設計基準桁数（DeviceGW がこの基準で配置）


class PrintDocument(BaseModel):
    model_config = _camel
    schema_version: str = Field("1.0", alias="schemaVersion")
    metadata: Metadata
    elements: list[Element] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, exclude_none=True, indent=2)


# =====================================================================
# B. ビルダ（意味カラムをそのまま積む。空白の焼き込みはしない）
# =====================================================================
def L(value, style=None):                     # left カラム
    return Column(slot="left", value=value, style=style)


def M(value, start_col, style=None):          # mid カラム（開始位置指定）
    return Column(slot="mid", value=value, start_col=start_col, style=style)


def R(value, style=None):                     # right カラム
    return Column(slot="right", value=value, style=style)


class ReceiptDocBuilder:
    """戦略から使う組み立てヘルパ（_add_* と同じ発想で要素を積む）。"""

    def __init__(self):
        self.elements: list[Element] = []

    def text(self, value, align="left", style=None):
        self.elements.append(TextElement(value=value, align=align, style=style))

    def columns(self, *cols: Column):
        self.elements.append(ColumnsElement(columns=list(cols)))

    def rule(self, char="-"):
        self.elements.append(RuledLineElement(char=char))

    def feed(self, lines):
        self.elements.append(FeedElement(lines=lines))

    def cut(self, mode="full"):
        self.elements.append(CutElement(mode=mode))

    def logo(self, logo_id, align="center"):
        self.elements.append(LogoElement(logo_id=logo_id, align=align))

    def barcode(self, symbology, data, height=None, hri="none", align="center"):
        self.elements.append(
            BarcodeElement(symbology=symbology, data=data, height=height, hri=hri, align=align)
        )

    def qrcode(self, data, error_correction="M", module_size=None, align="center"):
        self.elements.append(
            QrcodeElement(data=data, error_correction=error_correction,
                          module_size=module_size, align=align)
        )


# =====================================================================
# C. 戦略：normal-sale.json を 1:1 で生成する build_print_document()
#    現行 _add_* の「内容ロジック」は不変。line_split(a, b) を columns(L(a), R(b))
#    に置換し、必要なら mid（M）や カラム単位 style を足すだけ。
# =====================================================================
def build_print_document_example() -> PrintDocument:
    b = ReceiptDocBuilder()
    emph = Style(bold=True, scale_height=2)

    # ===== ヘッダ =====
    b.logo("store-top-logo")
    b.text("【 領 収 証 】", align="center", style=Style(scale_width=2, scale_height=2))
    b.columns(L("レジNo. 1"), R("責# S001"))
    b.text("2026年04月30日(木) 14:30")

    # ===== ボディ =====
    b.rule()
    b.columns(L("おにぎり(鮭)"), R("150外"))
    b.columns(L("お茶 500ml"), M("@108 x1", start_col=14), R("108外"))
    b.rule()
    b.columns(L("小計"), M("2点", start_col=10), R("258"))
    b.columns(L("  消費税(外税8%)"), R("20"))
    b.columns(L("合計", style=emph), R("\\278", style=emph))     # 合計はカラム単位で強調＋縦倍角
    b.columns(L("お預り"), R("\\300"))
    b.columns(L("お釣り"), R("\\22"))

    # ===== フッタ＋新要素 =====
    b.rule()
    b.text("レシートNo. 100")
    b.barcode("code128", "0012320260430000100", height=60, hri="below")
    b.feed(1)
    b.text("毎度ありがとうございます", align="center")
    b.qrcode("https://survey.example.com/r/0012320260430000100")
    b.feed(2)
    b.cut("partial")

    return PrintDocument(
        metadata=Metadata(
            tenant_id="tenant001", store_code="00123", terminal_no=1,
            transaction_no=12345, receipt_no=100, business_date="2026-04-30",
            generated_at="2026-04-30T14:30:00+09:00", chars_per_line=48,
        ),
        elements=b.elements,
    )


# =====================================================================
# D. 既存フローへの差し込み（イメージ）
#    AbstractReceiptData.make_receipt_data の XML 経路を JSON へ置換する。
#
#   def make_receipt_data(self, model) -> ReceiptData:
#       print_document = self.build_print_document(model)         # ← make_receipt_text(XML) を置換
#       journal_text   = self.make_journal_text(                  # 電子ジャーナルは維持
#           self.generate_print_data(model))
#       return ReceiptData(print_document=print_document, journal_text=journal_text)
# =====================================================================
if __name__ == "__main__":
    print(build_print_document_example().to_json())
