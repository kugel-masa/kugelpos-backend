---
description: "Task list for 343-settlement-snapshot"
---

# Tasks: 精算を report が確定するスナップショットにする

**Input**: `/specs/343-settlement-snapshot/` の plan.md、spec.md、research.md（R-1〜R-19）、data-model.md、contracts/、quickstart.md
**Tests**: 必要（R-19）。計算と保存の規則は、実装の前にテストを書く

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並べて進められる（別のファイル、未完了のタスクに依存しない）
- **[Story]**: US1（精算で確定）、US2（日報の固定）、US3（精算前の確認）、US4（一覧）、US5（report に届かないとき）
- パスは `services/` からの相対

---

## Phase 1: Setup

- [X] T001 現状の件数を記録する: report・terminal の unit / integration / e2e、`tests/e2e` の件数を specs/343-settlement-snapshot/test-baseline.md に残す（変更後の比較用。cart の DUAL 117・REQUIRED 66/51 も）

---

## Phase 2: Foundational（report の土台）

**⚠️ CRITICAL**: US1〜US4 はこの Phase のあと

### 計算（純粋な関数、先にテスト）

- [X] T002 [P] report/tests/unit/test_settlement_counting.py: 届いた件数（cart_id 単位、cart_id 無しは1件ずつ、番号 1 未満を除く）、番号の系列の分け方（`receipt_counter` の有無）、範囲（`first`/`last`）、未着（`seq` あり: 1〜seq、なし: 最小〜最大の飛び）、重複（違う cart_id の同じ番号）、サーバー側の番号の件数、入出金の未着（名乗り − 届いた、負は 0）（R-2・R-13）
- [X] T003 [P] report/tests/unit/test_expected_cash.py: 現金の支払（コード "01"）＋入金＋出金、内訳、釣銭準備金を二重に足さない、数えていなければ過不足 None（R-3）
- [X] T004 report/app/services/settlement_counting.py を実装して T002 を通す
- [X] T005 report/app/services/expected_cash.py を実装して T003 を通す。report/app/services/plugins/sales_report_maker.py の `_make_cash` をこれに置き換え、既存の売上レポートのテストが変わらないことを確かめる

### プラグイン

- [X] T006 report/app/services/plugins/{sales,category,item,payment,promotion}_report_maker.py: 任意の `business_counter` を、取引のパイプラインの `$match`、入出金ログ・開閉ログの取得の条件に足す。件数の区切りなし（`limit=None`）のときは `$skip`/`$limit` と取得の `limit` を外す（R-4）。名前（部門・支払）を外から渡せる入口を足す（渡されなければ今どおり master-data に問い合わせる・R-12）
- [X] T007 [P] report/tests/integration/test_plugins_business_counter.py: 端末を登録し直して同じ営業日・同じ `open_counter` の営業が2つあるとき、`business_counter` を渡せば片方の営業だけが集計される。区切りなしで大量の取引・部門・商品が切られない

### 文書・リポジトリ・索引

- [X] T008 [P] report/app/models/documents/settlement_record_document.py と settlement_daily_report_document.py（data-model §1・§2）
- [X] T009 report/app/models/repositories/settlement_record_repository.py: 「仮」の置き換え（upsert、条件 `state != final`）と確定集計の書き込みを1つのトランザクションで、確定（`settlement_id` が一致する「仮」を `final` に）、営業・営業日・期間・状態での照会、確定集計の種類ごとの読み出し（R-6・R-17）
- [X] T010 [P] report/tests/integration/test_settlement_record_repository.py: 置き換え・確定・確定のあとの不変・同時の書き込みで1件・確定集計の置き換えで古いものが残らない
- [X] T011 report/app/database/database_setup.py: `settlement_record`（3つの索引）、`settlement_daily_report`（一意の索引）、`log_cash_in_out` の `(tenant, store, terminal_no, business_counter)`、3つのログの `(tenant, store, business_date, terminal_no, business_counter)`（R-10・R-18）。report/tests/integration に索引のテストを足す。起動時の索引の整備の経路で、新しい索引の無い既存のテナントに作られることも確かめる（SC-006）

### エラーコード・例外

- [X] T012 [P] report/app/exceptions/report_error_codes.py・report_exceptions.py: `412101` の説明を「精算していない」に、`413007` SETTLEMENT_NOT_FOUND、`413008` SETTLEMENT_AGGREGATION_FAILED、`SessionNotSettledException`（未精算の一覧を持つ）。メッセージの ja/en
- [X] T013 [P] terminal/app/exceptions/terminal_error_codes.py・terminal_exceptions.py: `406016` SETTLEMENT_UNAVAILABLE（503）
- [X] T014 report/app/main.py: `SessionNotSettledException` の専用の例外の処理（`ApiResponse.data` に `unsettledSessions`）（R-16）

**Checkpoint**: 計算・プラグインの絞り込み・保存の土台ができた

---

## Phase 3: User Story 1 - 精算すると、その時点の精算実績が確定する (P1) 🎯 MVP

**Goal**: terminal の精算で report が精算実績を作り、閉設ログで確定する
**Independent Test**: 販売・入出金のあと精算し、応答・レシート・精算実績に理論在高・過不足・未着が出る。閉設ログが届くと確定する

### report の側

- [X] T015 [US1] report/tests/integration/test_settlement_confirm.py（先に書く）: 確定の計算と保存、`seq` あり・なしの未着、入出金の未着、数えていない過不足、確定集計5種類が保存され売上の現金の欄が精算実績と一致しレシートが作り直されている、「仮」の作り直し、「確定」なら計算せずに返す、集計の失敗で何も保存しない（413008）、大きすぎる確定集計で 413008、計算の途中で取引が届いても同じ時点を表す（R-12）、master-data が遅い・届かないときも精算できる（名前はコードで代わる）
- [X] T016 [US1] report/app/services/settlement_service.py: `confirm_async`（締めの時刻を決める → 名前を先に取る → 締めの時刻で絞って数値を計算 → 保存 → 返す）、確定集計の作成（5プラグインを business_counter・区切りなしで、売上の現金の欄を上書きしてレシートを作り直す、失敗で 413008、大きさの確認）、`finalize_from_close_log_async`（一致すれば確定、一致しなければ閉設ログの settlement_id で計算し直して確定）（R-4・R-6・R-12・R-15・R-17）
- [X] T017 [US1] report/app/dependencies/get_settlement_service.py: SettlementService の組み立て（テナントのデータベース、リポジトリ、プラグイン）
- [X] T018 [US1] report/app/api/v1/schemas.py・schemas_transformer.py: 確定の要求・応答（contracts §1）
- [X] T019 [US1] report/app/api/v1/settlement_internal.py: `POST /internal/tenants/{t}/stores/{s}/terminals/{n}/settlements`（サービスアカウントだけ、テナントの照合）。report/app/main.py に登録
- [X] T020 [US1] report/app/services/log_service.py: `settlement_id` を持つ閉設ログを受け取ったら `finalize_from_close_log_async`。無ければ何もしない
- [X] T021 [P] [US1] report/tests/integration/test_settlement_internal_api.py: サービスアカウントで 200、端末のトークン・利用者のトークン・API キーで拒否、別テナントで 403、閉設ログで確定（一致・不一致・settlement_id 無し）

### terminal の側

- [X] T022 [P] [US1] terminal/app/models/repositories/settlement_web_repository.py: `confirm_async`・`preview_async`（`create_service_token`、`get_service_client("report")`、タイムアウト 30 秒・再試行 1 回、200 以外を contracts/terminal-close.md の表どおりに分類）
- [X] T023 [US1] terminal/app/api/common/schemas.py・api/v1/schemas.py・schemas_transformer.py: 精算の要求に `seq`、応答に `expectedCashTotal`・`difference`・`missingCount`・`missingCashLogCount`・`settlementId`
- [X] T024 [US1] terminal と report・journal の閉設ログの型（open_close_log）に `settlement_id`・`expected_cash`・`difference`・`missing_count`・`missing_cash_log_count`
- [X] T025 [US1] terminal/app/services/terminal_service.py `close_terminal_async`: 入出金の件数を数える → report に確定を依頼 → 閉設ログ（`seq` を件数・最後の番号に）→ `physical_amount` を精算実績の値に → 条件付きの端末の更新（`Opened` のときだけ、合わなければ 406003）・閉設ログ・配信状態を1つのトランザクションで → 発行。cart への取引の問い合わせを外す（R-7）
- [X] T026 [US1] terminal/app/services/receipt_data/open_close_receipt_data.py: 理論在高・過不足（数えていれば）・`未着の取引 N件`・`未着の入出金 N件`
- [X] T027 [P] [US1] terminal/tests/unit: report の結果ごとの扱い（200・タイムアウト・5xx・404・401/403 → 406016、400/422 → 406008）、閉設ログ・レシート・応答の項目、cart への問い合わせをしない、`seq` を送らない既存の要求でも精算できる（FR-013）。既存の `tran_log_repo` の差し替えを外す（test_terminal_service_lifecycle.py ほか）
- [X] T028 [US1] terminal/tests/integration: 閉設のテスト（test_terminal_lifecycle.py、test_terminal_reregistered_reopen.py ほか）に report の確定の口の respx の差し替えを足す。同時の精算で1つだけが閉じる

**Checkpoint**: 精算で精算実績ができ、閉設ログで確定する

---

## Phase 4: User Story 5 - report に届かないときは精算しない (P1)

- [X] T029 [US5] terminal/tests/integration/test_close_report_unavailable.py: report に届かない・5xx・タイムアウト・413008 のとき 503 `406016`、端末は開設のまま、閉設ログも配信状態も無い。復旧のあと普通に精算でき、その間の販売を含む（仮の作り直し）

---

## Phase 5: User Story 2 - 日報は精算の時点の値で固定される (P1)

**Goal**: daily は確定した確定集計から返し、店舗・期間は合算、未精算は 412101
**Independent Test**: 精算のあとに取引を遅れて届けても日報が変わらない。未精算の端末があると 412101 と一覧

- [X] T030 [P] [US2] report/tests/unit/test_report_merge.py（先に書く）: 5種類の `merge` の規則（税は tax_name、支払は payment_code と variant_code、名前は最新の精算、支払の ratio の計算し直し、部門・商品・プロモーションのコード、合計の計算し直し、数えていない営業を含む現金の欄は None）、`from_saved`、合算のあとのレシートの作り直し
- [X] T031 [US2] report/app/services/plugins/*_report_maker.py: `merge`・`from_saved` を実装して T030 を通す
- [X] T032 [US2] report/app/models/documents/*_report_document.py: `missing_count`・`missing_ranges`（任意）
- [X] T033 [US2] report/app/services/report_service.py: daily（端末・店舗・期間）を、対象の営業の集め方（3つのログ）→ 確定した精算実績との照合（無ければ `SessionNotSettledException` を包まずに送り出す）→ 確定集計の読み出しと合算 → 未着の項目、に置き換える。対象が無ければ空の日報。daily では limit/page を使わない。`_check_if_terminal_closed`・`_commit_*`・DailyInfo の読み書きを外す（R-5・R-14・R-16）。report/app/dependencies/get_report_service.py の組み立てを直す
- [X] T034 [US2] report/tests/integration/test_daily_from_settlement.py: 端末の日報（open_counter・business_counter 指定・指定なしで複数の営業）、店舗の日報の合算、期間の日報、遅れて届いた取引で変わらない、「仮」だけの営業は 412101、未精算の一覧、空の範囲は 200、速報はその場で集計
- [X] T035 [US2] report の既存のテストを直す: `412102`〜`412107`・DailyInfo を前提にしたもの、`ReportService(daily_info_repository=...)` の組み立て、日報の前に確定の口を通し、さらに `settlement_id` を持つ閉設ログを pub/sub の口に入れて「確定」させる形（report/tests/unit・integration・e2e の test_setup_data.py と test_report.py ほか）

**Checkpoint**: 日報が確定集計から返る

---

## Phase 6: User Story 3 - 精算前の確認 (P2)

- [X] T036 [US3] report/app/services/settlement_service.py `preview_async`（確定集計は作らない、保存しない、確定があれば settled: true と保存済みの値）と report/app/api/v1/settlement_internal.py の `GET …/settlement-preview`
- [X] T037 [US3] terminal/app/api/v1/terminal.py と terminal_service.py: `GET /terminals/{terminal_id}/close-preview`（contracts/terminal-close.md）
- [X] T038 [P] [US3] report と terminal の統合テスト: 何も保存されない、確定済みなら settled、開設していない端末は 406003、report に届かなければ 406016

---

## Phase 7: User Story 4 - 精算実績の一覧 (P2)

- [X] T039 [US4] report/app/api/v1/settlement.py: `GET /tenants/{t}/stores/{s}/settlements`（利用者のトークンだけ、絞り込み、並び、区切り、確定集計を含めない）。main.py に登録
- [X] T040 [P] [US4] report/tests/integration/test_settlement_list_api.py: 絞り込み・並び・区切り・端末の API キーの拒否・片側だけの期間は 400

---

## Phase 8: Polish & Cross-Cutting

- [X] T041 e2e: サービス横断の e2e（tests/e2e）に精算の流れを足す（販売・入出金を `wait_for` で report に届くのを待ってから精算、精算実績の `state=final` を `wait_for` で待ってから端末と店舗の日報、遅れた取引、report を止めて 406016）。既存の journey が精算のあとに日報を読む箇所は、すべて `state=final` を待つ形に直す。tests/e2e/test_report_error_codes.py の 412101 の期待を直す
- [X] T042a 確定の口の処理時間を測る: 大きな営業（取引 2,000 件、商品 1,000 品目程度）を作り、確定の口の処理時間が terminal のタイムアウト（30 秒）より十分短い（目安 10 秒以内）ことを確かめ、test-baseline.md に記録する。超えるなら、確定集計の作り方を見直す
- [X] T042 全体の確かめ: `./scripts/build.sh` → unit / integration / e2e（cart は DUAL と REQUIRED）。T001 の件数と比べ、意図して直したテスト以外の件数が減っていないこと
- [X] T043 [P] docs: docs/{en,ja}/general/error_code_spec.md（412101 の意味、413007、413008、406016）、API の文書の生成（scripts/generate-api-docs.py）、report・terminal の api-specification に精算の流れと日報の挙動の変化（daily は limit/page を使わない、期間の日報に現金の欄）
- [X] T044 [P] 配備の手順（.claude/commands/deploy.md か docs）: report を terminal より先に配備すること、terminal に `BASE_URL_REPORT` が要ること
- [X] T045 `pipenv run ruff check` を変更した app のファイルに。下流の名前が入っていないこと（`~/.config/kugelpos-public/forbidden-patterns` で検索）
- [X] T046 PR（本文も同じ検索で確かめる）→ #345

## Phase 9: PR のレビューへの対応（R-20、R-21）

- [X] T047 内部の精算の口を terminal のサービスアカウントだけにする（services/report/app/api/v1/settlement_internal.py）とテスト
- [X] T048 計算を `_id` の集合で固定する（settlement_service.py、report_scope.py の `cash_extra_match`、sales_report_maker.py）と、書き込みの確定が遅れた取引のテスト
- [X] T049 [US2] `missingRanges` に `terminalNo`・`businessDate`（report_service.py、schemas.py）と、店舗の日報のテスト
- [X] T050 同時の精算: terminal の書き込みの衝突を 406003 に（terminal_service.py）、report のトランザクションのやり直し（settlement_record_repository.py）、テスト
- [X] T051 閉設ログの照合で確定できなければ例外（settlement_service.py）とテスト
- [X] T052 管理者の精算の口（settlement.py、settlement_service.py `settle_by_admin_async`、settlement_record_document.py）とテスト（test_settlement_admin_api.py）
- [X] T053 索引に `open_counter`、精算実績の日時、通知の文言、再試行の説明、API の文書の生成、仕様の文書の更新

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → Phase 3（US1）→ Phase 4（US5、US1 の terminal の側のあと）
- Phase 5（US2）は Phase 3 の report の側（T016）のあと。terminal の側と並べて進められる
- Phase 6（US3）・Phase 7（US4）は Phase 3 のあと、互いに独立
- Phase 8 は全部のあと
- Phase 2 の中: T002→T004、T003→T005、T006→T007、T008→T009→T010、T012→T014

## Parallel Example

```text
# Phase 2 のテストを並べて書く
T002 test_settlement_counting.py / T003 test_expected_cash.py / T007 test_plugins_business_counter.py

# US1 の report の側と terminal の側
T016〜T021（report） と T022〜T024（terminal の土台）
```

## Implementation Strategy

1. Phase 2 で計算・絞り込み・保存の土台を固める（純粋な関数は unit で網羅）
2. US1 で精算 → 精算実績 → 確定の流れを通す（MVP）。US5 を合わせて確かめる
3. US2 で日報を確定集計に切り替える（既存のテストの書き直しが多い）
4. US3・US4 を足す
5. e2e・文書・配備の手順をそろえて PR
