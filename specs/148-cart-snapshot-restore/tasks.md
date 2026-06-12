# Tasks: 署名付きカートスナップショットのレスポンス付加と restore API（client-carried cart phase 1）

**Input**: Design documents from `/specs/148-cart-snapshot-restore/`
**Prerequisites**: plan.md, spec.md（Clarifications 3 件確定済み）, research.md（R-001〜R-010）, data-model.md, contracts/restore-api.yaml, quickstart.md

**Tests**: テスト 3 層（unit / integration / e2e）の規約に従いテストタスクを含める（spec の受け入れシナリオ・Success Criteria が実測検証を要求するため）。

**Organization**: ユーザーストーリー単位でフェーズ化。ただし US1（restore）はスナップショットが存在しないと検証できないため、**US2（付加）→ US1（restore）の順**で実装する（spec の「US2 は US1 の前提」に整合）。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並列実行可（異なるファイル・未完了タスクへの依存なし）
- **[Story]**: 対応するユーザーストーリー（US1〜US4）

## Path Conventions

マイクロサービス構成（plan.md の Source Code 構成に従う）。cart = `services/cart/`、commons = `services/commons/src/kugel_common/`。

---

## Phase 1: Setup（設定・エラーコード）

**Purpose**: 全ストーリーが参照する設定とエラーコードの土台

- [X] T001 `services/cart/app/config/settings_cart.py` に `SNAPSHOT_HMAC_KEYS`（既定 `""`）と `SNAPSHOT_SIZE_WARN_BYTES`（既定 262144）を追加（data-model.md §4）
- [X] T002 [P] `services/cart/app/exceptions/cart_error_codes.py` にサブカテゴリ 4015xx（401501〜401507、data-model.md §5）を追加し、`ErrorMessage` に ja/en メッセージを定義
- [X] T003 [P] `services/cart/app/exceptions/cart_exceptions.py` に 4015xx に対応する例外クラス（署名不一致・検証不能・未知 kid・バージョン非対応・スコープ違反・終端状態）を既存例外のパターンで追加

---

## Phase 2: Foundational（署名基盤・エンベロープ・監査基盤）

**Purpose**: 全ストーリーが依存するブロッキング前提。**このフェーズ完了までストーリー実装に着手しない**

- [X] T004 `services/commons/src/kugel_common/utils/hmac_signer.py` を新規作成: canonical JSON 生成（`sort_keys=True, separators=(",", ":"), ensure_ascii=True`）、kid→鍵マップによる HMAC-SHA256 署名/検証（`hmac.compare_digest`）、`"<kid>:<base64>[,...]"` 形式のパーサ（R-003/R-004。コメント・ログは英語）
- [X] T005 [P] `services/commons/tests/unit/test_hmac_signer.py` を新規作成: 正規化の安定性（キー順・Unicode・往復一致）、署名/検証、kid 世代（前世代で検証可・未知 kid 拒否）、鍵文字列パース異常系
- [X] T006 `services/cart/app/api/common/schemas.py` に `SnapshotEnvelope` スキーマ（schema_version / issued_at / kid / tenant_id / store_code / terminal_no / cart_document / signature、data-model.md §1）を追加
- [X] T007 cart 起動時の鍵ロード検証を追加（`services/cart/app/main.py` の lifespan）: `SNAPSHOT_HMAC_KEYS` をパースし、未設定なら縮退モードの warning、パース不能なら明示エラーをログ（R-006 の fail-fast。ログは英語）
- [X] T008 [P] `services/cart/app/models/documents/cart_restore_log_document.py` を新規作成: 監査レコード文書（data-model.md §3 のフィールド）
- [X] T009 `services/cart/app/models/repositories/cart_restore_log_repository.py` を新規作成し、`services/cart/app/config/settings_database.py` に `DB_COLLECTION_NAME_LOG_CART_RESTORE = "log_cart_restore"` を追加、`services/cart/app/database/database_setup.py` にコレクション作成 + インデックス（`cart_id`, `event_datetime`）を登録

**Checkpoint**: 署名ユーティリティ・エンベロープ・監査基盤が単体で動作。以降のストーリーを開始できる

---

## Phase 3: User Story 2 - すべてのカート変更レスポンスで最新の復元コピーを受け取る (Priority: P1)

**Goal**: カート変更系 12 エンドポイント（contracts/restore-api.yaml のコメント一覧）のレスポンスに `signedSnapshot` を付加。GET には付加しない。生成失敗は縮退

**Independent Test**: 変更系の全エンドポイントを順に呼び、全レスポンスにスナップショット（masters 同梱・署名つき）が含まれ、内容がサーバ側の正のデータと一致することを確認（spec User Story 2）

- [X] T010 [US2] `services/cart/app/services/snapshot_service.py` を新規作成: `build_envelope(cart_doc, terminal_info)`（`model_dump(mode="json")` → エンベロープ組み立て → 署名）、生成失敗時は None を返して warning ログ（縮退、R-006）、raw サイズが `SNAPSHOT_SIZE_WARN_BYTES` 超なら warning（R-008）
- [X] T011 [P] [US2] `services/cart/tests/unit/test_snapshot_service.py` を新規作成: エンベロープ組み立て・署名対象の安定性・縮退（鍵未設定で None + 例外を漏らさない）・サイズ warning
- [X] T012 [US2] `services/cart/app/api/common/schemas.py` の `BaseCart` に Optional フィールド `signed_snapshot` / `restored` / `diverged` を追加（data-model.md §2。既存フィールド不変）
- [X] T013 [US2] `services/cart/app/api/v1/schemas_transformer.py` の `transform_cart` に optional の snapshot 引数を追加し、渡されたら `signed_snapshot` に詰める
- [X] T014 [US2] `services/cart/app/api/v1/cart.py` の変更系 12 ハンドラ（create/cancel/lineItems/明細 cancel/unitPrice/quantity/明細 discounts/subtotal/discounts/payments/bill/resume-item-entry）で `snapshot_service.build_envelope` を呼び transformer に渡す。GET 系は変更しない（R-005）
- [X] T015 [US2] `services/cart/tests/integration/test_cart_snapshot_attach.py` を新規作成: (1) 変更系全エンドポイントのレスポンスに `signedSnapshot` が含まれ署名が自己検証できる、(2) `cartDocument.masters.items` にスキャン済み商品が同梱、(3) GET には含まれない、(4) 鍵未設定時は null + 操作自体は成功（縮退）

**Checkpoint**: クライアントは常に最新の復元コピーを受け取れる（MVP の前半）

---

## Phase 4: User Story 1 - 別バックエンドへの切替後に取引を継続できる (Priority: P1)

**Goal**: restore API でカートを再構築し、後続操作（追加〜確定）を継続できる。同一 cart_id 衝突時は既存サーバ優先（FR-006 の基本形。差分通知は US4）

**Independent Test**: バックエンド A 相当でスナップショット取得 → キャッシュからカートを削除（quickstart.md §3 の手順）→ restore → 商品追加〜bill まで通ることを確認

- [X] T016 [US1] `services/cart/app/api/v1/schemas.py` に restore リクエスト（SnapshotEnvelope ボディ）/レスポンス（`ApiResponse[Cart]`）スキーマを追加（contracts/restore-api.yaml）
- [X] T017 [US1] `services/cart/app/services/snapshot_service.py` に `verify_envelope(envelope)` を追加: signature を除いた canonical 再直列化 → kid 解決 → HMAC 検証 → `CartDocument(**cart_document)` 再構築を返す（拒否系の詳細マッピングは US3 で拡充）
- [X] T018 [US1] `services/cart/app/services/cart_service.py` に `restore_cart_async(envelope)` を追加: 検証（T017）→ テナント/店舗スコープ確認 → 既存カート確認（存在すれば既存を返し `restored=False` — 上書きしない、FR-006）→ 非存在なら再構築してキャッシュ書き込み（既存 `__cache_cart_async` / resume の `set_*_master_documents` パターンを流用）→ 監査レコード書き込み（T009、result=`restored`/`existing_returned`）→ 復元後カートの新スナップショットを返却
- [X] T019 [US1] `services/cart/app/api/v1/cart.py` に `POST /carts/restore?terminal_id=` エンドポイントを追加（既存の `get_terminal_info_with_jwt_or_apikey` 認証・`ApiResponse[Cart]` 規約、R-009）
- [X] T020 [US1] `services/cart/tests/integration/test_cart_restore.py` を新規作成: (1) キャッシュ削除後の restore 成功（`restored=true`・状態/明細/masters が一致・新スナップショット同梱）、(2) restore 後に商品追加→小計→支払い→bill が成功し tranlog が正常生成、(3) カート存在時の restore は既存を返す（`restored=false`）、(4) 復元可能状態は idle/entering_item/paying のみ、(5) restore 後に master-data 側の価格を変更しても明細単価が変わらない（取引開始時点のマスタ文脈の維持 — spec Edge Case「マスタ乖離」）

**Checkpoint**: バックエンド切替の取引継続（SC-001/SC-002 の機能面）が成立 — **ここまでが MVP**

---

## Phase 5: User Story 3 - 改ざん・偽造されたスナップショットは復元できない (Priority: P1)

**Goal**: 不正スナップショットを 4015xx で区別可能に拒否し、セキュリティイベントとして記録する

**Independent Test**: 正当なスナップショットを 1 バイト改ざんして restore に提示 → 401501 で拒否され、カートが作成されず、監査/ログから追跡できる

- [X] T021 [US3] `services/cart/app/services/snapshot_service.py` の `verify_envelope` に拒否系の詳細マッピングを実装: 署名不一致→401501、署名欠落/形式不正/パース不能→401502、未知 kid→401503、schema_version 非対応→401504（T003 の例外を送出。security warning ログは英語）
- [X] T022 [US3] `services/cart/app/services/cart_service.py` の `restore_cart_async` にスコープ違反→401505（エンベロープ側の tenant_id/store_code と認証コンテキストを比較、FR-005/FR-012）と、**全拒否パターンの監査レコード書き込み**（result=`rejected` + reject_reason、FR-007/NFR-003）を実装
- [X] T023 [P] [US3] `services/cart/tests/unit/test_snapshot_verify.py` を新規作成: 改ざん 1 バイト・署名欠落・未知 kid・前世代鍵での検証成功・バージョン非対応の各ケースが正しい例外になる
- [X] T024 [US3] `services/cart/tests/integration/test_cart_restore_reject.py` を新規作成: 改ざん（401501）・署名欠落（401502）・未知 kid（401503）・非対応バージョン（401504）・他テナント/他店舗（401505、HTTP 403）の各拒否でカートが作成されず、`log_cart_restore` に rejected レコードが残る

**Checkpoint**: 不正スナップショットは 100% 拒否 + 追跡可能（SC-003）

---

## Phase 6: User Story 4 - リプレイは受け入れつつ検知できる (Priority: P2)

**Goal**: 差分通知（diverged）・終端状態の冪等拒否・二重計上防止・監査追跡の完成（FR-006 差分通知 + FR-007）

**Independent Test**: 古いスナップショットの restore →確定を 2 系統で実施し、取引が二重計上されず、監査証跡から再提示を追跡できる

- [X] T025 [US4] `services/cart/app/services/cart_service.py` の衝突パスに差分判定を実装: 提示エンベロープの `cart_document` と既存カートの canonical JSON 比較（data-model.md §2）→ `diverged` フラグをレスポンスと監査レコードに設定
- [X] T026 [US4] 終端状態（completed/cancelled）スナップショットの restore を 401506 で冪等拒否し監査記録（FR-007・Edge Case。`services/cart/app/services/cart_service.py`）
- [X] T027 [US4] `services/cart/tests/integration/test_cart_restore_replay.py` を新規作成: (1) 操作を進めた後に古いスナップショットを restore → `restored=false` + `diverged=true` + 監査記録、(2) 終端状態（completed/cancelled）スナップショットの restore → 401506 で冪等拒否・カート作成なし・監査記録、(3) `log_cart_restore` を cart_id で引くと発行端末・要求端末・発行時刻・結果の全履歴が追跡できる（発行端末 ≠ 要求端末のケース含む、FR-012）。※確定済み取引の**終端前**スナップショットによる二重計上の防止は別 issue #152（tranlog への cart_id 追加、spec Clarifications 2026-06-12）のスコープであり、本タスクでは監査証跡から検知可能であることのみ検証する

**Checkpoint**: 全ユーザーストーリーの受け入れシナリオが integration レベルで充足

---

## Phase 7: Polish & 計測・横断事項

**Purpose**: e2e 実証・Success Criteria の実測・運用文書

- [X] T028 `services/cart/tests/e2e/test_cart_restore.py` を新規作成: quickstart.md §2〜§4 のフルシナリオ（カート作成→商品追加→スナップショット捕捉→Redis キー削除→restore→継続→bill→改ざん拒否→衝突）を実スタックで検証。既存 `tests/e2e/test_cart.py` のセットアップパターンを流用。**restore は JWT 認証で実施**（フェイルオーバー前提の検証 — terminal info が JWT クレームから再構築されることを含めて確認。既存 `test_cart_jwt_auth.py` 参照）
- [ ] T029 [P] サイズ/レイテンシ計測（SC-005/SC-006）: `/perf-test` 標準手順で 40 商品カートの gzip 後レスポンスサイズと変更系 API の p95 増分を計測し、結果を issue #148 にコメントで記録（R-008 の判断基準と突き合わせ。gzip は #147 完了が前提）
- [X] T030 [P] `docs/ja/cart-snapshot-key-rotation.md` を新規作成: 鍵ローテーション手順（通常: 新 kid 追加→24h 後に旧鍵削除 / 緊急: 即時差し替え＝進行中取引の復元コピー犠牲の明記、FR-011）
- [X] T031 `cd services/cart && pipenv run ruff check --fix app/ && pipenv run ruff format app/`（commons も同様）+ quickstart.md の手順を通しで実行して成立を確認

---

## Dependencies & Execution Order

```text
Phase 1 (Setup) ─→ Phase 2 (Foundational) ─→ Phase 3 (US2: 付加)
                                                  │
                                                  ▼
                                          Phase 4 (US1: restore) ─→ Phase 5 (US3: 拒否系)
                                                                          │
                                                                          ▼
                                                                  Phase 6 (US4: リプレイ/差分)
                                                                          │
                                                                          ▼
                                                                  Phase 7 (e2e + 計測)
```

- **US2 → US1 の順序**は意図的（restore の検証にはスナップショットの取得が必要）。spec の「US2 は US1 の前提」に整合
- US3 は US1 のエンドポイントに拒否パスを足す形なので US1 後。US4 は US1/US3 の上に差分・冪等を足す
- ストーリー単位の独立テスト基準は各 Phase 冒頭の Independent Test を参照

## Parallel Opportunities

- Phase 1: T002, T003 は T001 と並列可
- Phase 2: T005（commons unit テスト）、T008（監査文書）は他と並列可
- Phase 3: T011（unit テスト）は T012〜T014 と並列可
- Phase 5: T023（unit テスト）は T022 と並列可
- Phase 7: T029（計測）、T030（運用文書）は T028 と並列可

## Implementation Strategy

- **MVP = Phase 1〜4**（US2 + US1）: 「全変更レスポンスにスナップショット + restore で取引継続」が成立した時点で phase 1 の核心価値（SC-001/SC-002）をデモできる
- **セキュリティ完成 = Phase 5**（US3）: 本番投入の最低ライン（SC-003）
- **整合性完成 = Phase 6**（US4）: 差分通知・終端状態の冪等拒否・監査。**SC-004（二重計上ゼロ）の完全達成は別 issue #152（取引確定の cart_id 冪等化）に依存**
- **リリース判定 = Phase 7**: 実測（SC-005/SC-006）が R-008 の基準内であることを確認して有効化（#147 完了が前提）

**Total**: 31 タスク（US2: 6 / US1: 5 / US3: 4 / US4: 3 / Setup+Foundational: 9 / Polish: 4）
