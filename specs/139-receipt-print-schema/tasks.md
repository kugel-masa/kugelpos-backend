# Tasks: device-agnostic な印字データスキーマ（XML 撤去・JSON 化）

**Branch**: `139-receipt-print-schema` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

凡例: `[P]` = 並行可能（依存なし） / 各タスクは英語コメント・型注釈を遵守。

## Phase 1: commons（基盤）

- [ ] **T001** `services/commons/src/kugel_common/receipt/print_document_model.py` を新規作成（Style/Column/各 Element/Metadata/PrintDocument）。`examples/builder-example.py` のモデル定義を流用し、`ImageElement`/`ImageSource` を追加。`PrintDocument.to_dict()`（`model_dump(by_alias=True, exclude_none=True)`）を提供。
- [ ] **T002** `services/commons/src/kugel_common/receipt/receipt_data_model.py` を改修。`pydantic-xml` 依存を撤去。`Page`（`lines: list`）・`Line`（Element エイリアス）・`Constants` を維持。`PrintData`/`to_xml`/`Table`/`TableRow` を削除。
- [ ] **T003** `services/commons/src/kugel_common/receipt/abstract_receipt_data.py` を改修。`make_receipt_text`(XML) を削除。`line_*` シムを Element 生成へ再実装。`build_print_document(model, elements)` と `render_journal_text(elements, width)` を追加。`make_receipt_data` が `ReceiptData(print_document, journal_text)` を返すよう変更。`ReceiptData` モデルの `receipt_text` を `print_document: dict` に置換。
- [ ] **T004** `services/commons/src/kugel_common/models/documents/base_tranlog.py`: `receipt_text` を `print_document: Optional[dict[str, Any]] = None` に置換。
- [ ] **T005** commons 検証: `pipenv run ruff check src/` + 既存 receipt 系 unit テスト。`render_journal_text` の出力が現行 `to_text` と一致することを確認。

## Phase 2: cart（依存: Phase 1）

- [ ] **T010** `services/cart/app/api/common/schemas.py`（`BaseTran`）: `receipt_text` → `print_document: Optional[dict] = None`。
- [ ] **T011** `services/cart/app/api/common/schemas_transformer.py`: `receipt_text=...` 2 箇所を `print_document=...` へ。
- [ ] **T012** `services/cart/app/models/repositories/cart_repository.py`: `cart.receipt_text = ""` を `cart.print_document = None` へ。
- [ ] **T013** `services/cart/app/services/tran_service.py`: `tranlog.receipt_text`/`cart.receipt_text`/`tran.receipt_text`（3 ブロック）を `print_document` へ。`print_data` 変数名はそのままで `make_receipt_data` の戻り値 `.print_document` を使用。
- [ ] **T014** cart テスト更新: `tests/log_maker.py`・`tests/unit/test_api_cart.py`・`test_api_tran.py`・`test_cart_repository.py` の `receipt_text` 参照を `print_document` へ。
- [ ] **T015** cart 検証: `pipenv run pytest -m unit`。

## Phase 3: terminal（依存: Phase 1）

- [ ] **T020** `services/terminal/app/models/documents/open_close_log.py`・`cash_in_out_log.py`: `receipt_text` → `print_document`。
- [ ] **T021** `services/terminal/app/services/terminal_service.py`: `*.receipt_text = receipt_data.receipt_text`（4 箇所）を `print_document` へ。
- [ ] **T022** `services/terminal/app/api/common/schemas.py`・`schemas_transformer.py`・`api/v1/schemas.py`・`api/v1/terminal.py`: `receipt_text` → `print_document`。
- [ ] **T023** terminal テスト更新: `tests/unit/test_api_terminals.py`・`test_receipt_data.py`・`test_terminal_service_lifecycle.py`・`test_terminal_service_logging.py`。
- [ ] **T024** terminal 検証: `pipenv run pytest -m unit`。

## Phase 4: journal（依存: Phase 1, 2, 3 のスキーマ整合）

- [ ] **T030** `services/journal/app/models/documents/jornal_document.py`・`open_close_log.py`・`cash_in_out_log.py`: `receipt_text: str` → `print_document: Optional[dict] = None`。
- [ ] **T031** `services/journal/app/services/log_service.py`: `receipt_text=tran.receipt_text` 等を `print_document` へ。
- [ ] **T032** `services/journal/app/api/common/schemas.py`・`schemas_transformer.py`: `receipt_text`/`receiptText` → `print_document`/`printDocument`。
- [ ] **T033** journal テスト更新: `tests/integration/conftest.py`・`tests/unit/test_api_journal.py`・`test_journal_service.py`・`test_log_service.py`・`test_repositories.py`。
- [ ] **T034** journal 検証: `pipenv run pytest -m unit`。

## Phase 5: report（依存: Phase 1）

- [ ] **T040** report 各 document: `cash_in_out_log.py`・`open_close_log.py`・`sales_report_document.py`・`item_report_document.py`・`category_report_document.py`・`payment_report_document.py`・`promotion_report_document.py`: `receipt_text` → `print_document`。
- [ ] **T041** `services/report/app/services/report_service.py`: `receipt_text`/`receiptText`（帳票→journal 連携、659-703 付近）を `print_document`/`printDocument` へ。帳票生成器の戻り値 `.print_document` を使用。
- [ ] **T042** report 帳票生成器（`sales_report_maker.py`・`item_report_maker.py`・`payment_report_maker.py`・`category_report_maker.py`・`promotion_report_maker.py` と `*_receipt_data.py`）: `make_receipt_data` の戻り値参照を `print_document` へ。生成器本体はシムで不変。
- [ ] **T043** `services/report/app/api/common/schemas.py`・`schemas_transformer.py`: `receipt_text` → `print_document`。
- [ ] **T044** report テスト・補助更新: `tests/e2e/test_*`・`tests/log_maker.py`・`tests/unit/test_journal_integration.py`・`debug_receipt_generation.py`。
- [ ] **T045** report 検証: `pipenv run pytest -m unit`。

## Phase 6: 統合検証

- [ ] **T050** 全サービス `ruff check`。
- [ ] **T051** production コードに `receipt_text` / `to_xml` / `pydantic_xml` が残っていないことを確認（`grep -rn 'receipt_text\|to_xml\|pydantic_xml' services/*/app services/commons/src` がテスト以外で 0）。
- [ ] **T052** 全サービス unit テスト パス（commons/cart/terminal/journal/report）。
- [ ] **T053** 可能なら integration テスト（MongoDB 必要）。
