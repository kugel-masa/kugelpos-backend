# Tasks: device-agnostic な印字データスキーマ（XML 撤去・JSON 化）

**Branch**: `139-receipt-print-schema` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

凡例: `[P]` = 並行可能（依存なし） / 各タスクは英語コメント・型注釈を遵守。

> **方針（spec 2026-06-07 確定・最重要）**: フィールド名 `receipt_text`・`str` 型は**据え置き**、中身を XML→JSON 文字列に変える。新フィールド `print_document` は**追加しない**（`print_document` は JSON スキーマの呼称）。変更は **kugel_common（生成ロジック）に閉じ**、cart/terminal/journal/report は **コード無改変**。したがって Phase 2–5 はフィールド改名作業ではなく、**commons 再ビルド後に既存テストが無改変で pass することの検証**である。

## Phase 1: commons（唯一の実改修）

- [ ] **T001** `services/commons/src/kugel_common/receipt/print_document_model.py` を新規作成（Style/Column/各 Element/Metadata/PrintDocument）。`examples/builder-example.py` のモデル定義を流用し、`ImageElement`/`ImageSource` を追加。共通基底 `PrintElement` を導入し `channel: Literal["R","J","RJ"] = Field("RJ", exclude=True)` を全要素へ付与（**JSON 出力からは除外**＝内部ルーティング属性）。`PrintDocument.to_dict()`（`model_dump(by_alias=True, exclude_none=True)`）を提供。
- [ ] **T002** `services/commons/src/kugel_common/receipt/receipt_data_model.py` を改修。`pydantic-xml` 依存を撤去。`Page`（`lines: list`）・`Line`（Element エイリアス）・`Constants` を維持。`PrintData`/`to_xml`/`Table`/`TableRow` を削除。
- [ ] **T003** `services/commons/src/kugel_common/receipt/abstract_receipt_data.py` を改修。`make_receipt_text`(XML) を削除。`line_*` シム（`line_left`/`line_center`/`line_right`/`line_split`/`line_boarder`）を Element 生成へ再実装し、各々に `channel="RJ"` 引数を追加（既定 RJ）。`build_print_document(model, elements)`（`channel in {R,RJ}` 要素のみ + Metadata 構築・camelCase dict）と `render_journal_text(elements, width)`（`channel in {J,RJ}` 要素のみ・現行 `to_text` とバイト等価）を追加。`make_receipt_data` が `ReceiptData(receipt_text=json.dumps(build_print_document(...), ensure_ascii=False), journal_text=render_journal_text(...))` を返すよう変更。**`ReceiptData.receipt_text` は `str` のまま据え置き（改名しない）**。
- [ ] **T004** `services/commons/src/kugel_common/models/documents/base_tranlog.py`: **無改変**。`receipt_text: Optional[str]` を維持（中身が JSON 文字列に変わるのみ）。本タスクは「base_tranlog を変更しないこと」を確認するチェック項目。
- [ ] **T005** commons 単体テスト追加: `tests/unit/test_receipt_routing.py`（R/J/RJ 振り分け＝`print_document` に R/RJ のみ／`journal_text` に J/RJ のみ／`channel` が JSON 出力に現れない）と、`render_journal_text` の出力が現行 `to_text` とバイト等価であることの回帰テスト。
- [ ] **T006** commons 検証: `pipenv run ruff check src/` + 既存 receipt 系 unit テスト + T005。commons wheel を再ビルド（後続サービスへ配布）。

## Phase 2: cart（依存: Phase 1・コード変更なし）

- [ ] **T010** 新 commons wheel を再インストール。cart は **コード無改変**。`pipenv run pytest -m unit` が無改変で pass することを確認（`tranlog`/Cart API/pub-sub のフィールドは不変、`receipt_text` の中身が XML→JSON 文字列に変わるのみ）。

## Phase 3: terminal（依存: Phase 1・コード変更なし）

- [ ] **T020** 新 commons を再インストール。terminal は **コード無改変**。`pipenv run pytest -m unit` が無改変で pass することを確認（開閉店/現金レシートの `receipt_text` 中身が JSON 文字列に変わるのみ）。

## Phase 4: journal（依存: Phase 1・コード変更なし）

- [ ] **T030** 新 commons を再インストール。journal は **コード無改変**。`pipenv run pytest -m unit` が無改変で pass することを確認（保存する `receipt_text` の中身が JSON 文字列に。歴史データ＝XML との混在を読み出し側が許容できることを確認）。

## Phase 5: report（依存: Phase 1・コード変更なし）

- [ ] **T040** 新 commons を再インストール。report は **コード無改変**。`pipenv run pytest -m unit` が無改変で pass することを確認（4 帳票生成器が基底シム経由で JSON を出力、`receipt_text` 中身のみ変化）。

## Phase 6: 統合検証

- [ ] **T050** 全サービス `ruff check`。
- [ ] **T051** XML 経路が production コードに残っていないことを確認: `grep -rn 'to_xml\|pydantic_xml\|BaseXmlModel\|PrintData' services/*/app services/commons/src` がテスト以外で 0。**`receipt_text` は全面維持するため grep 対象に含めない**。
- [ ] **T052** 全サービス unit テスト パス（commons/cart/terminal/journal/report、いずれも commons 以外は無改変）。
- [ ] **T053** 可能なら integration テスト（MongoDB 必要）。歴史データ（XML）と新規（JSON）混在の読み出しを確認。
