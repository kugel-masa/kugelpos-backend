# Tasks: 毎リクエストでのカートスナップショット提示とサーバ側キャッシュの権威降格（client-carried cart phase 2）

**Input**: Design documents from `/specs/156-stateless-cart/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/request-snapshot.yaml, quickstart.md

**Tests**: 含める（kugelpos の 3 層テスト規約 unit / integration / e2e に従う。phase 1 #148 と同じ）。

**Organization**: ユーザーストーリー単位。ただし本フィーチャーは共有のステートレス中核（モデル変更・DI 分岐・検証・再構成）が大きく、Foundational 層が厚い。各ストーリーはその上の増分 + 固有の検証で構成する。

## 重要な依存・制約（実装前に必読）

- **採番 seq 再定義と下流 cart_id 化は同時適用が必須**（research R-005）。`transaction_no` を seq に変える変更と、report/journal/stock のスキップ判定を cart_id へ差し替える変更は、片方だけ入れると「別セッションの同一 seq を誤スキップ」する。両者は US4 内で同一の deliverable として扱う。
- **確定はあり経路で決定論的であること**（FR-012）: 連番（business_counter, seq）+ 取引時刻（generate_date_time）+ レシートを carried 値から生成。サーバ時刻スタンプ・サーバカウンタ採番をあり経路で使わない。
- **下流の重複対策はスキップ（insert-if-absent / 先勝ち）**。後勝ち upsert ではない（FR-006）。既存の下流は既にスキップ型なので、キーを cart_id に差し替えるのが主。
- **デュアルモード**（`CART_REQUEST_SNAPSHOT_MODE` env、DUAL/REQUIRED）。移行期間はキャッシュ・サーキットブレーカーを残置（撤去は本スコープ外）。

---

## Phase 1: Setup（共有設定）

**Purpose**: 設定・エラーコードの土台

- [ ] T001 `services/cart/app/config/settings_cart.py` に `CART_REQUEST_SNAPSHOT_MODE`（`DUAL` / `REQUIRED`、既定 `DUAL`）と、リクエスト展開後サイズ上限 `REQUEST_DECOMPRESS_MAX_BYTES`（既定値は `SNAPSHOT_SIZE_WARN_BYTES` と整合、例 1 MB）を追加（R-006/R-007）
- [ ] T002 [P] `services/cart/app/exceptions/cart_error_codes.py` に phase 2 用エラーコードを追加: なし経路拒否（REQUIRED 時）・展開サイズ超過・連番異常。phase 1 の `4015xx` 帯に続けて割当

---

## Phase 2: Foundational（全ストーリーの前提・ブロッキング）

**Purpose**: あり/なし経路のステートレス中核とモデル変更。ここが完了するまで US1〜US4 に着手できない。

- [ ] T003 [P] `services/commons/src/kugel_common/models/documents/base_tranlog.py` の `BaseTransaction` に `cart_id: Optional[str]` を追加（#152 の中核、R-004）
- [ ] T004 [P] `services/commons/src/kugel_common/middleware/http_compression.py` にリクエストボディ展開 ASGI ミドルウェアを追加: `Content-Encoding: gzip` / `br` を展開、展開後サイズ上限ガード（超過は途中打ち切りで 413 相当）、非圧縮は素通し（R-006/FR-009）。`brotli` 依存を commons の Pipfile に追加
- [ ] T005 `services/cart/app/models/documents/cart_document.py` の `CartDocument` に `seq: int`（既定 0）と `transaction_datetime`（取引時刻の持ち回り、型は plan で確定）を追加（data-model）
- [ ] T006 スナップショット搬送（H 案、R-001 見直し）: cart のボディ処理ミドルウェア `services/cart/app/middleware/snapshot_envelope.py`（新規）を実装。変更系ルートで、ボディが `signedSnapshot` キーを持つ JSON オブジェクトなら `signedSnapshot` を `request.state.cart_snapshot` に退避しボディを `payload` の中身へ差し替え、素のボディは素通し。エンドポイント署名・リクエストスキーマは無改修（配列ボディ対応のため per-schema フィールドは採らない）。`main.py` に登録（T010 と統合可）。contracts/request-snapshot.yaml を H 案に更新
- [ ] T007 `services/cart/app/services/snapshot_service.py` の検証を毎リクエスト用に一般化（`verify_envelope` を restore と共通で使えるよう整理。検証順: 形式→version→kid→署名→スコープ→状態）。restore と同一規則であることを担保（FR-010）。restore API 残置の回帰は既存 phase 1 restore テスト群（`test_cart_restore*.py`）の緑維持でカバー（専用タスクは設けない — ユーザー判断 2026-06-13）
- [ ] T008 `services/cart/app/services/cart_service.py` に「あり経路の再構成」を追加: 検証済みスナップショットからマスタ再ハイドレート + 状態設定で `current_cart` を構成し、**キャッシュを読まない・書かない**（phase 1 `restore_cart_async` の再構成を毎リクエスト・キャッシュ非依存に一般化、R-002/FR-004）
- [ ] T009 `services/cart/app/dependencies/get_cart_service.py` を分岐化: `request.state.cart_snapshot`（T006 のミドルウェアが退避）あり→あり経路（T008 で再構成）、なし→なし経路（従来どおりキャッシュ）。`CART_REQUEST_SNAPSHOT_MODE=REQUIRED` のときはなし経路を専用エラー（401508）で拒否（R-002/FR-008）
- [ ] T010 `services/cart/app/main.py` にリクエスト展開ミドルウェア（T004）を登録（log_requests との順序に注意 — 展開後にログ・ハンドラが本文を読む）
- [ ] T011 [P] `services/commons/tests/unit/` にリクエスト展開ミドルウェアの unit テスト（gzip/br 展開・サイズ上限超過の拒否・非圧縮素通し）

**Checkpoint**: あり/なし分岐とスナップショット再構成の中核が動く。US1〜US3 はここから着手可能。

---

## Phase 3: User Story 1 - どのバックエンドに繋いでも取引がそのまま続く（編集系）(Priority: P1) 🎯 MVP

**Goal**: 既存カートへの変更系操作（商品追加・数量・割引・小計等）を、スナップショット同梱で任意のバックエンドに送り、再入力なしで継続できる。各レスポンスに最新スナップショットが付く。

**Independent Test**: バックエンド A で作成→ A のスナップショットを B に同梱して商品追加→ 更新済みカートと新スナップショットが返ること。確定（bill）の跨ぎは US4 で扱う。

- [ ] T012 [US1] `services/cart/app/api/v1/cart.py` の編集系エンドポイント（lineItems / subtotal / discounts / line-item cancel / unitPrice / quantity / discounts / resume-item-entry）を T009 の DI 分岐に接続し、あり経路で操作適用後に最新スナップショットを返す
- [ ] T013 [US1] あり経路で操作適用後の cart_document に新しいスナップショットを生成・添付（phase 1 `_cart_data_with_snapshot` を流用）。あり経路ではキャッシュ書き込みに依存しないことを確認
- [ ] T014 [P] [US1] `services/cart/tests/integration/test_request_snapshot_roundtrip.py`（新規）: 各編集系エンドポイントであり経路の往復（スナップショット同梱→処理→新スナップショット返却）を検証
- [ ] T015 [P] [US1] `services/cart/tests/e2e/test_cross_backend_continue.py`（新規）: A で作成→ B（別 Redis/Mongo）でスナップショット同梱の編集継続が成功すること（quickstart シナリオ 1 の編集部分）

**Checkpoint**: 編集系の跨ぎ継続が単独で動作・テスト可能（MVP）。

---

## Phase 4: User Story 2 - サーバ側キャッシュの障害が取引に影響しない（デュアルモード）(Priority: P1)

**Goal**: あり経路はキャッシュ非依存。キャッシュ全損・タイムアウトでも編集が継続。なし経路は従来挙動を維持。

**Independent Test**: キャッシュ全消去後、スナップショット同梱の編集が成功（404 にならない）。なし経路は従来どおり。

- [ ] T016 [US2] あり経路がキャッシュを参照・依存しないことをコードで保証（T008 の不変条件をレビュー・固定）。キャッシュ読み書き失敗があり経路の成否に影響しないことを確認（FR-004）
- [ ] T017 [US2] あり経路での乖離検知（ベストエフォート）: 同一 cart_id のキャッシュ残存があり内容が乖離していれば監査記録、処理は提示スナップショットで続行。キャッシュ無し/読めない場合はスキップ（R-008/FR-005）
- [ ] T018 [P] [US2] `services/cart/tests/integration/test_dual_mode.py`（新規）: あり/なし × キャッシュ正常/障害 のマトリクス。あり経路はキャッシュ障害下でも成功、なし経路は従来挙動、`REQUIRED` ではなし経路が専用エラーで拒否されること
- [ ] T019 [P] [US2] `services/cart/tests/e2e/test_cache_wiped_continue.py`（新規）: 取引中にキャッシュ全消去→あり経路の編集継続が成功（quickstart シナリオ 2）

**Checkpoint**: キャッシュ非依存とデュアルモード分岐が検証済み。

---

## Phase 5: User Story 3 - 改ざん・偽造されたスナップショットでは操作できない (Priority: P1)

**Goal**: 全変更系エンドポイントで毎リクエスト検証。改ざん・スコープ違反・バージョン非対応は操作適用前に拒否し、監査に残す。

**Independent Test**: 正当なスナップショットを 1 バイト改ざんして各変更系 API に同梱→ 全エンドポイントで拒否・カート無影響・監査記録。

- [ ] T020 [US3] 監査の一般化＋改称: phase 1 `cart_restore_log_document.py` / `cart_restore_log_repository.py` を毎リクエスト検証へ拡張（`api_path` 追加、`result` 値拡張、異常系のみ記録）し、コレクションを `log_cart_restore` → **`log_cart_snapshot_event`** へ改称、document/repository も対応名へリネーム。既存 `log_cart_restore` レコードがあれば新コレクションへ移行（R-009/FR-007）
- [ ] T021 [US3] 検証失敗・スコープ違反・終端状態・バージョン非対応を T007 の検証パイプラインで拒否し、監査記録。あり経路の全変更系エンドポイントで検証が必ず通ること（検証欠落エンドポイントなし、NFR-003）
- [ ] T022 [P] [US3] `services/cart/tests/unit/test_per_request_verify.py`（新規）: 検証パイプラインの各拒否分岐（改ざん・欠署名・未知 kid・version 外・スコープ違反）
- [ ] T023 [P] [US3] `services/cart/tests/integration/test_tamper_rejection_all_endpoints.py`（新規）: 全変更系エンドポイントで改ざんスナップショット拒否・カート無影響・監査記録を確認（SC-003）。あわせて NFR-004 を担保: **拒否後、同じ操作を正当なスナップショットで再送すると成功する**（拒否は当該リクエストの失敗にとどまり進行中取引を失わせない）ことをアサート

**Checkpoint**: 攻撃面（全変更系 API）の検証が網羅され、改ざんが 100% 拒否される。

---

## Phase 6: User Story 4 - 確定の重複・古いスナップショットでも取引がちょうど 1 件になる (Priority: P2)

**Goal**: 確定をあり経路で決定論的に（carried 連番・取引時刻）、tranlog に cart_id を載せ、下流（report/journal/stock）を cart_id スキップに統一。lost-ACK 再送・別バックエンド確定でも取引ちょうど 1 件。端末交換も連番が衝突しない。

**Independent Test**: 同一カートの確定を 2 系統（別バックエンド含む）で実施→ report/journal/stock のいずれも 1 件・1 回に収束。端末交換後も連番が旧端末と衝突しない。

**注意**: T025（seq 再定義）と T028〜T030（下流 cart_id 化）は**同時にリリースする**（片方だけだと誤スキップ、research R-005）。

- [ ] T024 [US4] `services/cart/app/services/tran_service.py` の確定で `cart_id` を tranlog に引き継ぐ（CartDocument→BaseTransaction、T003 のフィールドへ）
- [ ] T025 [US4] `tran_service.py` の採番をあり経路で carried 化: `transaction_no`=carried `seq`、`receipt_no` も carried、`generate_date_time` を carried `transaction_datetime` から設定（サーバ時刻スタンプ `:166`・サーバカウンタ `:159,173` をあり経路で不使用）。なし経路は従来採番を維持（デュアル一貫性）（R-003/FR-012）
- [ ] T026 [US4] 取引時刻のクライアント打刻を実装: bill リクエストにクライアント打刻の確定時刻フィールドを追加し、あり経路の確定でそれを `generate_date_time` と confirmed スナップショットの `transaction_datetime` に設定。リトライで同値を再送 → 決定論的に同一の時刻・レシートになることを保証（FR-012、Clarifications 2026-06-13）
- [ ] T027 [US4] オフライン開設対応（案 B、Clarifications 2026-06-14）: **`business_counter` と `receipt_no` を端末所有・持ち回りに変更**し、open のたびに端末がローカルで前進（オフライン可）。terminal service の open 処理に **`max(service値, 端末提示値)` reconcile** を実装（耐久ホーム）。端末は両カウンタを close→open 跨ぎで永続保持。open イベント（opencloselog / business_date）のオフライン確定・後 reconcile。seq は business_counter エポックで端末側リセット（新エポックで 1 から、復元処理なし）。交換＋オフライン未reconcile は tranlog 高水位照会 or 安全ジャンプ（欠番許容・**再利用禁止**）。terminal service の open/close フローと JWT クレームの調整を含む（FR-012）
- [ ] T028 [P] [US4] report: `services/report/app/models/repositories/tranlog_repository.py` の存在チェックを cart_id 基準に差し替え、`services/report/app/database/database_setup.py` の unique index を `(tenant, store, cart_id)` へ（+ 参照用 `(tenant, store, terminal, business_counter, transaction_no)`）（R-005）
- [ ] T029 [P] [US4] journal: `services/journal/app/services/log_service.py` / `services/journal/app/database/database_setup.py` の tranlog 存在チェック・index を cart_id 基準へ
- [ ] T030 [P] [US4] stock: `services/stock/app/services/stock_service.py` の事前チェック（`:175-188`）とロールバック時検索（`:121-130`）を cart_id 基準へ、`services/stock/app/database/database_setup.py` の unique index を `(tenant, store, cart_id, item_code, update_type)` へ。`$inc` + ロールバック保護は温存（R-005）
- [ ] T031 [US4] 連番整合性の監査検知（下流）: report/journal で `(terminal, business_counter, seq)` の重複（異 cart_id）・欠番を cart_id 基準で検知・記録（R-010/FR-013）
- [ ] T032 [P] [US4] `services/cart/tests/unit/test_carried_numbering.py`（新規）: carried `(business_counter, seq)` 採番・取引時刻の決定論性、リトライで同一出力
- [ ] T033 [P] [US4] `services/stock/tests/integration/test_cart_id_skip.py`（新規）: 同一 cart_id 重複で在庫が 1 回のみ・別セッション同一 seq の別取引が誤スキップされないこと
- [ ] T034 [P] [US4] report/journal の integration: 同一 cart_id 重複の先勝ちスキップ、連番異常の検知
- [ ] T035 [US4] `services/cart/tests/e2e/test_double_finalize_and_replacement.py`（新規）: lost-ACK 再送（別バックエンド確定）で取引 1 件収束、端末交換で連番非衝突（quickstart シナリオ 4・5、SC-004/SC-005）

**Checkpoint**: 確定の決定論性・cart_id 収束・端末交換が成立し、二重計上ゼロ。

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: 計測・ドキュメント・整形

- [ ] T036 [P] 圧縮リクエストの e2e（quickstart シナリオ 6）: .NET 8 相当の `Content-Encoding: br`/`gzip` 同梱リクエストの正常処理、サイズ超過の 413、非圧縮の受領
- [ ] T037 計測（SC-005/SC-006）: `/perf-test` 標準手順で 40 商品カートのスナップショット同梱リクエストの圧縮後サイズ（≤15KB）・変更系 p95 増分（phase 1 比 +50ms 以内）を実測、結果を issue #156 に記録
- [ ] T038 [P] デュアルモード運用ドキュメント（`docs/ja/` 配下）: `CART_REQUEST_SNAPSHOT_MODE` の切替手順、なし経路メトリクスによる移行完了判定、移行後のキャッシュ撤去が後続作業である旨
- [ ] T039 [P] `cd services/cart && pipenv run ruff check --fix app/ && pipenv run ruff format app/`（commons / report / journal / stock も同様）+ quickstart の通し確認

---

## Dependencies & 完了順序

```
Setup(P1) → Foundational(P2) ─┬─→ US1(P3) ─┐
                              ├─→ US2(P4) ─┼─→ Polish(P7)
                              ├─→ US3(P5) ─┤
                              └─→ US4(P6) ─┘
```

- **Foundational(P2) は全ストーリーの前提**。T003〜T010 が完了するまで US1〜US4 に着手しない。
- **US1 / US2 / US3** は Foundational の上で概ね独立（編集経路の継続・キャッシュ非依存・検証網羅）。並行着手可能。
- **US4** は Foundational に加え、確定パス（tran_service）と下流 3 サービスを触る最重量ストーリー。US1 の「確定の跨ぎ」完全形は US4 の carried 採番に依存する（US1 の MVP は編集系まで）。
- **US4 内の同時適用制約**: T025（seq 再定義）と T028〜T030（下流 cart_id 化）は同一リリースで（research R-005）。

## 並行実行の例

- Foundational: T003（commons tranlog）/ T004（commons middleware）/ T011（middleware test）は別ファイルで並行可。
- US4 の下流: T028（report）/ T029（journal）/ T030（stock）は別サービスで並行可。
- 各ストーリーのテスト（T014/T015、T018/T019、T022/T023、T032〜T034）は [P] で並行可。

## 実装戦略（MVP → 増分）

1. **MVP = Foundational + US1（編集系跨ぎ継続）**。ここで「どのバックエンドでも編集を継続」が動く。
2. **US2 / US3** を追加（キャッシュ非依存の保証・全エンドポイント検証網羅）。
3. **US4** で確定の決定論化・下流 cart_id 収束・端末交換を仕上げ、二重計上ゼロを達成（#152 を本フィーチャーで駆動）。
4. **Polish** で計測（SC-005/SC-006）・運用ドキュメント・整形。
