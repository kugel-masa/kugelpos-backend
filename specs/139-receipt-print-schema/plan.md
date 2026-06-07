# Implementation Plan: device-agnostic な印字データスキーマ（XML 撤去・JSON 化）

**Branch**: `139-receipt-print-schema` | **Date**: 2026-06-07 | **Spec**: [spec.md](./spec.md)
**Related Issue**: [#139](https://github.com/kugel-masa/kugelpos-backend/issues/139)
**派生元**: stpos-backend `316-device-print-schema`

## Summary

`AbstractReceiptData`（kugel_common）が `receipt_text` に入れている印字データの中身を XML→device-agnostic な JSON 文字列（`print_document` スキーマ）へ移行する。**フィールド名 `receipt_text`・`str` 型は据え置き**、中身のみ変更。`journal_text` は維持。変更は kugel_common に閉じ、cart/terminal/journal/report のコードは無改変。

`AbstractReceiptData` を継承する印字生成器は 7 つ（cart 取引×1、terminal 開閉店/現金×2、report 帳票 sales/item/payment/category×4）。**いずれも `line_split`/`line_center`/`line_left`/`line_right`/`line_boarder` と整形ヘルパ（fixed_*/comma/yen 等）のみで Page を組み立てており、`Line()`/`Page()` の直接構築や `tables` は使っていない**（調査で確認）。この事実を利用し、基底のヘルパを**後方互換シム**として再実装することで、**7 生成器のレシート内容を一切変えずに**出力形式だけを XML→JSON へ移行する。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, Pydantic v2, Motor（async MongoDB）, Dapr（pub/sub）
**撤去する依存**: `pydantic-xml`（`receipt_data_model.py` の XML モデルでのみ使用）
**Storage**: MongoDB（`tranlog`/`journal_document`/`open_close_log`/`cash_in_out_log`/report 各 document）。`receipt_text:str`（不変）の中身を XML→JSON 文字列へ
**Testing**: pytest + pytest-asyncio（unit / integration / e2e）
**Project Type**: Microservices（kugel_common 共通 + cart/terminal/journal/report）

## 設計方針（Converter + 後方互換シム）

### 1. 新規モデル `kugel_common/receipt/print_document_model.py`
[contracts/print-document.schema.md](./contracts/print-document.schema.md) を pydantic v2 で実装（`examples/builder-example.py` のモデル定義を流用）。
- `Style`（bold/underline/reverse/scaleWidth/scaleHeight/font）
- `Column`（slot/value/startCol/align/style）
- 要素: `TextElement`/`ColumnsElement`/`RuledLineElement`/`FeedElement`/`CutElement`/`BarcodeElement`/`QrcodeElement`/`ImageElement`/`LogoElement`（`type` discriminator のユニオン）
- `Metadata`（documentType/tenantId/storeCode/terminalNo/transactionNo/receiptNo/businessDate/generatedAt/locale/charsPerLine）
- `PrintDocument`（schemaVersion/metadata/elements）。出力は `model_dump(by_alias=True, exclude_none=True)`（camelCase dict）

### 2. `receipt_data_model.py` の作り替え（XML 撤去）
- `pydantic-xml`（`BaseXmlModel`/`to_xml`/`PrintData`）を撤去。
- `Page`（`lines: list[Element]`）と `Line`（= Element 型エイリアス、型注釈の後方互換用）、`Constants`（既存定数）を残す。
- `tables` は誰も使っていないため廃止。

### 3. `AbstractReceiptData` の改修（基底）
- `make_receipt_data(model) -> ReceiptData`:
  1. `page = generate_print_data(model)`（既存どおり header/body/footer が Page.lines に Element を積む）
  2. `print_document = build_print_document(model, page.lines)`（Metadata 構築 + camelCase dict 化）
  3. `journal_text = render_journal_text(page.lines, self.width)`（**現行 `to_text` と同一出力**）
  4. `return ReceiptData(print_document=print_document, journal_text=journal_text)`
- **`make_receipt_text`（XML）と `to_xml` 経路を削除**。
- 後方互換シム（戻り値を Element に変更、引数・呼び出し側は不変）:
  - `line_left/center/right(text)` → `TextElement(value=text, align=...)`
  - `line_split(a, b)` → `ColumnsElement(columns=[Column(left, a), Column(right, b)])`
  - `line_boarder()` → `RuledLineElement(char="-")`
- Metadata は共通属性を `getattr` で抽出（documentType 既定 "receipt"、`charsPerLine = self.width`、generatedAt = `generate_date_time` か app time）。report 生成器は将来 documentType を上書き可能にする（任意）。

### 4. `journal_text` 無回帰の担保
`render_journal_text` は現行 `to_text` を Element 入力に移植し、**バイト等価**を保つ:
- `TextElement` center/left/right → `TextHelper.fixed_center/left/right(value, width)`
- `ColumnsElement[left,right]` → 現行 SPLIT と同じく `fixed_left(left, width - wcswidth(right) - 1, truncate=True) + " " + right`
- `RuledLineElement` → `"".center(width, char)`
- 新要素（feed/cut/barcode/qrcode/image/logo）は本フィーチャーの production 生成器では使用しないため journal 出力に現れない（showcase は examples/ のみ）。将来 production で使う場合の journal 表現は別途定義。

> **重要な判断**: production の 7 生成器のレシート**内容は変更しない**（行・文言・順序・桁を維持）。ロゴ/倍角/バーコード/QR 等の拡張表現は **スキーマと examples/（normal-sale.json・builder-example.py）で実証**する。これにより SC-002（論理等価）/SC-005（journal 無回帰）を確実に満たす。各生成器を意味カラム（mid 利用）へ深掘り改修するのは、スキーマ変更を伴わない後続作業として generator 単位で実施可能。

### 5. フィールド据え置き（`receipt_text:str`・名前/型不変）
- `BaseTransaction`（kugel_common）: `receipt_text: Optional[str]` は**不変**。`ReceiptData.receipt_text` も `str`。`make_receipt_data` が `json.dumps(build_print_document(...), ensure_ascii=False)` で **JSON 文字列**を入れる。
- cart / terminal / journal / report: **コード無改変**。`receipt_text`（`str`）の中身が XML→JSON 文字列に変わるだけ。document・schema・transformer・戦略・テストは元のまま。
- pub/sub: cart の tranlog ペイロードはフィールド構成不変。`receipt_text` の中身のみ JSON 文字列に。

### 6. R/J/RJ チャネル（ステーション）— 追補 2026-06-07
- `print_document_model.py` に共通基底 `PrintElement` を導入し、`channel: Literal["R","J","RJ"] = Field("RJ", exclude=True)` を全要素へ付与（**JSON 出力からは除外**＝内部ルーティング属性）。
- `AbstractReceiptData`: `build_print_document` は `channel in {R, RJ}` の要素のみを `print_document` に含め、`render_journal_text` は `channel in {J, RJ}` のみを描画。`line_split`/`line_center`/`line_left`/`line_right`/`line_boarder` に `channel` 引数を追加（既定 `RJ`）。
- 既定 RJ のため既存戦略のレシート/ジャーナル内容は不変（**機能追加のみ**）。commons に routing 単体テスト（`tests/unit/test_receipt_routing.py`）を追加。

## Constitution Check

| 項目 | 状態 | 備考 |
|---|---|---|
| 成果物（spec/plan/tasks/docs）が日本語 | PASS | 本フィーチャーの speckit 文書はすべて日本語 |
| コード内コメント・ログが英語 | 実装時遵守 | 新モデル・基底改修・各サービスで英語コメント徹底 |

## Project Structure

```text
specs/139-receipt-print-schema/
├── spec.md
├── plan.md                 # 本ファイル
├── tasks.md
├── contracts/print-document.schema.md
├── examples/normal-sale.json
├── examples/builder-example.py
└── checklists/requirements.md

services/commons/src/kugel_common/receipt/
├── print_document_model.py   # 新規（スキーマ実装）
├── receipt_data_model.py     # 改修（XML 撤去・Page/Line/Constants 維持）
└── abstract_receipt_data.py  # 改修（XML 撤去・シム・JSON+journal 生成）
```

## フェーズ（実装順）

1. **commons（唯一の変更箇所）**: `print_document_model.py` 追加 → `receipt_data_model.py` 改修（XML 撤去）→ `abstract_receipt_data.py` 改修（`make_receipt_data` が `receipt_text` に JSON 文字列を入れる・channel ルーティング）。`base_tranlog.py` は不変。commons unit テスト + routing テスト。
2. **cart / terminal / journal / report**: コード変更なし（`receipt_text` の中身が JSON 文字列に変わるのみ）。新 commons wheel を再ビルド・再インストールし、既存 unit/integration/e2e が無改変で pass することを確認。
3. **検証**: 全サービス unit/integration/e2e。XML 生成経路が残っていないことを grep で確認。

## リスクと緩和

| リスク | 緩和 |
|---|---|
| journal_text 回帰 | render_journal_text を to_text とバイト等価に移植。cart/terminal/report の既存 unit テストで確認 |
| `receipt_text` 参照漏れ（146 箇所） | grep ベースで service ごとに潰し、最後に全 grep で 0 を確認（テスト除く production コード） |
| 歴史データ（XML）の読み出し | `receipt_text` は `str` のまま。旧 XML も新 JSON も同一フィールドに入るためデシリアライズは壊れない。読み出し側は中身の format を判別（先頭が `{`=JSON / `<`=XML）すればよい |
| pub/sub 購読側の不整合 | cart 発行と journal/report 購読を同一リリースで切替（ハードカットオーバー） |

## Success Criteria 対応

- SC-001/003: `print_document_model` のスキーマ + 要素テスト
- SC-002/005: production 生成器の内容不変 + journal バイト等価
- SC-004: 実装後 `grep -r receipt_text services/*/app` が production コードで 0
- SC-006: 全 unit/integration テスト パス
