---

description: "Cart Master-Data 共通キャッシュ基盤の実装タスクリスト"
---

# Tasks: Cart Master-Data 共通キャッシュ基盤

**Input**: Design documents from `/specs/072-master-data-cache/`
**Branch**: `072-master-data-cache`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Kugelpos プロジェクトの三層テスト構成（unit / integration / e2e）に準拠し、各ユーザストーリーに必要な単体・結合・E2E テストを含める。

**Organization**: ユーザストーリー単位でフェーズ分割し、各ストーリーが独立して実装・検証・デモ可能な単位になるように構成する。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並列実行可能（ファイルが独立で先行タスクへの依存なし）
- **[Story]**: ユーザストーリーID（US1〜US4。spec.md の優先度順）
- 各タスクには対象ファイルの絶対パスまたはリポジトリ相対パスを明記

## Path Conventions

- リポジトリルート: `/home/masa/proj/kugelpos-public/`
- 共有ライブラリ: `services/commons/src/kugel_common/`
- カートサービス: `services/cart/app/`
- Dapr コンポーネント: `services/dapr/components/`

---

## Phase 1: Setup (共有インフラ)

**Purpose**: ディレクトリ作成と Dapr コンポーネント定義

- [X] T001 共有キャッシュバックエンド用ディレクトリを作成: `services/commons/src/kugel_common/utils/cache/` （`mkdir -p` + 空の `__init__.py`）
- [X] T002 [P] Dapr コンポーネント定義ファイル `services/dapr/components/masterstore.yaml` を新規作成（data-model.md §10 の YAML 内容）

> Note: K8s / Azure Container Apps 用の Dapr コンポーネントテンプレートディレクトリは本リポジトリには存在せず、現在は Docker Compose 用の `services/dapr/components/` のみが配備対象。将来別環境への展開時には、`masterstore.yaml` と同等の定義を該当環境のテンプレートへ追加すること（本フィーチャでは対応不要）。

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全ユーザストーリーの前提となる共通基盤の構築

**⚠️ CRITICAL**: このフェーズが完了するまで、いかなるユーザストーリーの実装も開始できない

### 2.1 キャッシュバックエンド層 (commons)

- [X] T005 [P] `AbstractCacheBackend` を `services/commons/src/kugel_common/utils/cache/cache_backend.py` に実装（contracts/cache_backend.py のシグネチャに準拠）
- [X] T006 [P] `InMemoryCacheBackend` を `services/commons/src/kugel_common/utils/cache/in_memory_cache_backend.py` に実装（TTL 管理付き dict、`asyncio.Lock` でスレッドセーフ化）
- [X] T007 [P] `DaprStateCacheBackend` を `services/commons/src/kugel_common/utils/cache/dapr_state_cache_backend.py` に実装（既存 `DaprClientHelper.save_state/get_state/delete_state` を使用、`metadata={"ttlInSeconds": str(ttl)}` で per-key TTL 指定。**注**: `DaprClientHelper` が ETag を露出しないため `increment` は read+write の last-writer-wins。並行 invalidate_all で +1 回数が減る可能性はあるが無効化セマンティクスは保たれる旨をコード内コメントに明記）
- [X] T008 [P] `services/commons/src/kugel_common/utils/cache/__init__.py` に `AbstractCacheBackend`, `InMemoryCacheBackend`, `DaprStateCacheBackend` の export を追加
- [X] T009 [P] [Unit] `InMemoryCacheBackend` 単体テストを `services/commons/tests/unit/test_in_memory_cache_backend.py` に作成（**path 変更**: 既存 commons の test layout はフラット構造のため `utils/cache/` サブディレクトリは作らず慣例に合わせた）
- [X] T010 [P] [Unit] `DaprStateCacheBackend` 単体テストを `services/commons/tests/unit/test_dapr_state_cache_backend.py` に作成（同上のパス変更。`DaprClientHelper` を `unittest.mock.AsyncMock` で差し替え）

### 2.2 カートサービス側の基底クラス

- [X] T011 `AbstractMasterDataRepository[TDoc]` を `services/cart/app/models/repositories/abstract_master_data_repository.py` に実装（contracts/abstract_master_data_repository.py のシグネチャに準拠、data-model.md §6 のフロー）。実装範囲:
  - クラス属性: `cache_namespace`, `document_class`, `default_ttl_seconds`, `is_store_scoped`
  - コンストラクタ
  - `_resolve_store_code(override)` — `is_store_scoped=False` なら強制 `None`、True なら override → instance、それでも None なら `ValueError`
  - `_build_key(store_code, generation, entry_kind, logical_key)` — キー仕様 `contracts/key_format.md` に厳密準拠
  - `_get_generation(store_code)` / `_bump_generation(store_code)` — 世代カウンタ I/O
  - `get_or_fetch_one(logical_key, *, store_code_override, ttl_seconds, fetcher)` — フロー: cache_enabled チェック → store_code 解決 → generation 取得 → key 組立 → backend.get → HIT 返却 / MISS は fetcher() or `_fetch_one()` 呼出 → 成功なら set → NotFound は書込せず伝播
  - `get_or_fetch_list(...)` — 同上で entry_kind="list"
  - `invalidate(logical_key, *, store_code_override, entry_kind)` — `backend.delete(key)` 呼出
  - `invalidate_all()` — `_bump_generation` 呼出
  - `_fetch_one` を `@abstractmethod`, `_fetch_list` を `raise NotImplementedError` で宣言
- [X] T012 [P] [Unit] 基底クラス単体テストを `services/cart/tests/unit/repositories/test_abstract_master_data_repository.py` に作成（`InMemoryCacheBackend` 注入。検証項目:
  - HIT / MISS の基本動作
  - NotFound 時にキャッシュ書込されない [FR-013 / SC-009]
  - backend get 失敗時に直接フェッチへ落ちる [FR-007]
  - `store_code_override` 優先順位 [R-009]
  - `is_store_scoped=False` でキーが `_` 固定 [R-009]
  - 世代カウンタ +1 で旧エントリ論理消去 [FR-006 / SC-005]
  - `entry_kind` 違いでキー非衝突 [FR-010]
  - 店舗スコープなのに store_code 不在で `ValueError`
  - **テナント間隔離 [FR-003 / SC-006]**: tenant=T_A のインスタンスが書いた値が tenant=T_B のインスタンスからは MISS となること
  - **同テナント店舗間隔離 [FR-003 / SC-006b]**: 同 tenant・store=S_A のインスタンスが書いた値が同 tenant・store=S_B のインスタンスからは MISS となること
  - **設定バイパス [FR-008]**: `cart_settings.MASTER_DATA_CACHE_ENABLED=False` で `get_or_fetch_one` が毎回 `_fetch_one` を呼ぶこと
  - **ログマスキング [FR-012 / R-011]**: backend 失敗時の warning ログに `logical_key` 全体や value が含まれず、namespace / entry_kind / key_len のみであること（caplog で検証）
)

### 2.3 設定とライフサイクル

- [X] T013 `services/cart/app/config/settings_cart.py` に新設定キーを追加（data-model.md §9 の表のとおり 8 キー: `MASTER_DATA_CACHE_ENABLED`, `MASTER_DATA_CACHE_STATE_STORE`, `MASTER_DATA_CACHE_TTL_SECONDS`, `ITEM_MASTER_CACHE_TTL_SECONDS`, `PAYMENT_MASTER_CACHE_TTL_SECONDS`, `PROMOTION_MASTER_CACHE_TTL_SECONDS`, `SETTINGS_MASTER_CACHE_TTL_SECONDS`, `TAX_MASTER_CACHE_TTL_SECONDS`）。旧 `USE_ITEM_CACHE` / `ITEM_CACHE_TTL_SECONDS` はこの段階では残置（Phase 7 で撤去）
- [X] T014 `services/cart/app/main.py` の FastAPI `lifespan` を改修し、`DaprStateCacheBackend(store_name=cart_settings.MASTER_DATA_CACHE_STATE_STORE)` を 1 個生成して `app.state.master_cache_backend` に保持。shutdown 時に `await backend.close()` を呼ぶ
- [X] T015 `services/cart/app/dependencies/` 配下の DI 関数を確認した。Phase 3 で各リポジトリ移行時に `request: Request` 引数を追加して `request.app.state.master_cache_backend` を取得する形にする。本フェーズでは lifespan 側で backend を expose 済みなので準備完了

**Checkpoint**: 共通基盤が完成。ここから各ユーザストーリーの実装が並列可能になる

---

## Phase 3: User Story 1 - マスタ参照の高速化と外部負荷低減 (Priority: P1) 🎯 MVP

**Goal**: 商品マスタ（最も呼び出し頻度が高い）のキャッシュを有効化し、`ItemMasterWebRepository` / `ItemMasterGrpcRepository` 経路の両方で SC-001（再フェッチ抑制）と SC-007（経路間キャッシュ共有）を成立させる

**Independent Test**: 同一テナント・同一店舗で同一商品コードを連続して引いたとき、初回のみ master-data サービスへのリクエストが発生し、フレッシュネス期間内の 2 回目以降はリクエストが発生しないことを観測する（master-data 側アクセスログまたは cart 側 HTTP クライアントメトリクスで確認）

### 3.1 ItemMaster Web / gRPC リポジトリの移行

- [X] T016 [US1] `services/cart/app/models/repositories/item_master_web_repository.py` を改修: `AbstractMasterDataRepository[ItemMasterDocument]` を継承し、旧 `_item_cache` / `USE_ITEM_CACHE` 参照を削除。クラス属性宣言（`cache_namespace="item_master"`, `document_class=ItemMasterDocument`, `default_ttl_seconds=cart_settings.ITEM_MASTER_CACHE_TTL_SECONDS`, `is_store_scoped=True`）。コンストラクタは `tenant_id, store_code, terminal_info, cache_backend` を受け取り `super().__init__()`。`get_item_by_code_async` を `return await self.get_or_fetch_one(item_code)` に簡略化。`_fetch_one(item_code)` は既存の HTTP 呼出ロジック（`get_pooled_client("master-data")` + JWT/API-key ヘッダ + URL `/tenants/{tenant_id}/stores/{store_code}/items/{item_code}/details`）を移植
- [X] T017 [US1] `services/cart/app/models/repositories/item_master_grpc_repository.py` を改修: 同上の構成で `AbstractMasterDataRepository[ItemMasterDocument]` を継承。`cache_namespace="item_master"`, `document_class=ItemMasterDocument` を Web と完全一致させる（SC-007 の前提）。`_fetch_one(item_code)` は既存の gRPC スタブ呼出 + protobuf → `ItemMasterDocument` 変換を移植
- [X] T018 [US1] `services/cart/app/models/repositories/item_master_repository_factory.py` を改修: 引数を `(tenant_id, store_code, terminal_info, cache_backend)` に変更し、旧 `item_master_documents` 引数を削除。戻り値型を `AbstractMasterDataRepository[ItemMasterDocument]` に変更。`cart_settings.USE_GRPC` 判定ロジックは維持
- [X] T019 [US1] `services/cart/app/dependencies/get_cart_service.py` を改修し、`request: Request` 引数を追加して `request.app.state.master_cache_backend` を取得、`create_item_master_repository(...)` に `cache_backend=` で渡す。旧 `item_master_documents` 引数は削除

### 3.2 既存テストの更新と新規テスト追加

- [X] T020 [P] [US1] [Unit] `services/cart/tests/unit/test_web_repositories.py` の ItemMaster 部分を新シグネチャに合わせて更新（fetch モック + endpoint/JWT/API-key 検証 + 例外マッピング）。旧キャッシュ検証は基底クラステストに移譲済のため削除
- [X] T021 [P] [US1] [Unit] `services/cart/tests/unit/repositories/test_item_master_grpc_repository.py` を新シグネチャで全面書き換え（gRPC スタブモック + request 構築 + NotFound/UNAVAILABLE/generic 例外マッピング）
- [P] T022 [P] [US1] [Unit] factory 専用テストは存在しなかったため（既存テストファイルなし）スキップ。factory の動作は ItemMasterWebRepository/ItemMasterGrpcRepository のテスト経由で検証されている
- [ ] T023 [US1] [Integration] **未実施**: 実 Dapr サイドカー + Redis 起動を要するため Phase 7 の手動検証フェーズで実施。検証項目は当該タスクに記載のとおり
- [ ] T024 [US1] [E2E] **未実施**: docker compose スタック起動を要するため Phase 7 で実施

**Checkpoint**: User Story 1 がデモ可能。Item マスタの参照が初回以外キャッシュから返り、Web/Grpc 切替に関わらず同じキャッシュエントリを共有することが観測できる

---

## Phase 4: User Story 2 - マスタ更新時の手動でのキャッシュ無効化 (Priority: P2)

**Goal**: `invalidate(key)` と `invalidate_all()` の運用 API が、Item マスタおよび世代カウンタ機構で正しく動作することを検証

**Independent Test**: Item マスタの任意のキャッシュ済み項目に対して `await item_repo.invalidate("ITEM_A")` を呼んだ直後、`get_item_by_code_async("ITEM_A")` が master-data から再フェッチすることを観測する。また `await item_repo.invalidate_all()` 呼出後、当該テナント/店舗/namespace の全エントリが次回参照で再フェッチされる（他 namespace は影響なし）ことを観測する

### 4.1 単体テスト

- [X] T025 [P] [US2] [Unit] 個別無効化テストは Phase 2 の T012 内に既に実装済（`TestInvalidation::test_invalidate_single_key_only`）。Phase 4 ではバックエンド失敗時の安全性 (`TestInvalidationSafety::test_invalidate_swallows_backend_delete_failure`) と無効化スイッチ時の no-op (`test_invalidate_is_noop_when_cache_disabled`) を追加
- [X] T026 [P] [US2] [Unit] 一括無効化テストも Phase 2 で実装済（`test_invalidate_all_bumps_generation_and_misses_everything`, `test_invalidate_all_does_not_affect_other_namespaces`）。Phase 4 では increment 失敗時の安全性 (`test_invalidate_all_swallows_backend_increment_failure`) と無効化スイッチ時の no-op (`test_invalidate_all_is_noop_when_cache_disabled`) を追加

### 4.2 結合テスト

- [ ] T027 [US2] [Integration] **未実施**: 実 Redis 環境が必要なため Phase 7 に集約
- [ ] T028 [US2] [Integration] **未実施かつ前提変更**: 元設計の ETag CAS は `DaprClientHelper` の API 制約により採用見送り（read+write の last-writer-wins に変更、コメント明記済）。並行 increment テストは `InMemoryCacheBackend` の `test_concurrent_increments_serialize_correctly` (Phase 2) でカバー

**Checkpoint**: User Story 2 が動作する。Item リポジトリで invalidate が即時反映されることが手動・自動の両方で確認できる

---

## Phase 5: User Story 3 - キャッシュバックエンド障害時の継続稼働 (Priority: P2)

**Goal**: Redis または Dapr サイドカーが応答不能な状態でも、カート操作（master-data 参照を含む）が成功完了することを検証

**Independent Test**: `docker compose stop redis` で Redis を意図的に停止した状態で、E2E のカート購買シナリオを実行し、すべての master-data 参照が成功し、レジ操作（開店 → スキャン → 会計 → 閉店）が 100% 完了することを観測する（応答時間の劣化は許容）

### 5.1 単体テスト

- [X] T029 [P] [US3] [Unit] バックエンド障害シミュレーションは Phase 2 (`TestBackendFailureFallback`, `TestLogMasking`) と Phase 4 (`TestInvalidationSafety`) で完備済。get/set/delete/increment の 4 操作すべてに失敗時挙動の検証あり
- [X] T030 [P] [US3] [Unit] `services/commons/tests/unit/test_dapr_state_cache_backend.py` で全 4 操作の例外/失敗時挙動を Phase 2 で実装済（`test_returns_none_on_backend_exception_with_warning`, `test_set_returns_false_on_backend_exception`, `test_delete_returns_false_on_backend_exception`, `test_increment_returns_none_on_read_error`, `test_increment_returns_none_on_write_failure`）

### 5.2 結合テスト

- [ ] T031 [US3] [Integration] **未実施**: 実 Redis の停止/復旧を伴うため Phase 7 の手動検証手順 (T032) として実施

### 5.3 E2E 手動検証手順の文書化

- [X] T032 [US3] `services/cart/tests/e2e/MANUAL_VERIFY_RESILIENCE.md` を作成。Redis 停止下での E2E 完走、復旧後のキャッシュ再開、Dapr サイドカー停止時の挙動を確認する手順を整備

**Checkpoint**: User Story 3 が動作する。Redis 停止下でも cart 操作が完走する

---

## Phase 6: User Story 4 - 新マスタリポジトリ追加時の実装コスト削減 (Priority: P3)

**Goal**: 残り 4 種のリポジトリ（Payment / Promotion / Settings / Tax）を共通基盤に移行し、移行後の各リポジトリのキャッシュ関連コード行数が 0 行（基底クラスへの宣言・取得関数のみで完結）であることを確認。これにより SC-008 を実証する

**Independent Test**: 移行後の 4 リポジトリそれぞれについて、`grep -E "(cache|TTL|expire|invalidate)" services/cart/app/models/repositories/{payment,promotion,settings,tax}_master_*.py` でキャッシュ関連の独自コードが検出されないことを確認

### 6.1 各リポジトリの移行（並列可）

- [X] T033 [P] [US4] `payment_master_web_repository.py` 改修完了（`AbstractMasterDataRepository[PaymentMasterDocument]`, `is_store_scoped=False`）
- [X] T034 [P] [US4] `promotion_master_web_repository.py` 改修完了（`is_store_scoped=True`, store_code_override + fetcher クロージャ）
- [X] T035 [P] [US4] `settings_master_web_repository.py` 改修完了（`is_store_scoped` は動的 @property、`_fetch_one`/`_fetch_list` 両方を実装）
- [X] T036 [P] [US4] **TaxMasterRepository は移行対象外と判断**:
  - データソースは `settings.TAX_MASTER`（master-data サービスではない）→ I/O キャッシュの恩恵がない
  - 「キャッシュ」概念がカートごと（`cart.masters.taxes` に永続化）→ クロスリクエスト共有とは別パターン
  - 既存の `load_all_taxes` / `set_tax_master_documents` を `cart_service.py:220, 843` が前提
  - 本フィーチャの目的（マスタ参照のクロスリクエスト共有）にフィットしないため現状維持
- [X] T037 [US4] T036 を移行対象外としたため `load_all_taxes()` の撤去判断不要。warmup として継続使用
- [X] T038 [US4] DI 配線完了: `get_cart_service.py` で Payment/Settings に `cache_backend` 渡し、Promotion は `CartService.__init__` に `master_cache_backend` 引数追加経由で渡す。Settings の「テナント設定用」は本フェーズでは追加せず、必要が顕在化したら別タスクで対応

### 6.2 既存テストの更新

- [X] T039 [P] [US4] [Unit] `test_web_repositories.py` の Payment セクション更新完了（cache_backend 注入、URL/エラーマッピングに集約）
- [X] T040 [P] [US4] [Unit] `test_web_repositories.py` の Promotion セクション更新完了（cache_backend 注入）
- [X] T041 [P] [US4] [Unit] `test_web_repositories.py` の Settings セクション更新完了（`is_store_scoped` プロパティの動的判定テスト追加）
- [X] T042 [P] [US4] [Unit] T036 を移行対象外としたため Tax テスト更新不要

### 6.3 SC-008 の検証

- [X] T043 [US4] [Verification] SC-008 検証完了: Payment/Promotion/Settings の 3 リポジトリで、キャッシュ関連コードは `default_ttl_seconds = cart_settings.X_MASTER_CACHE_TTL_SECONDS` の宣言行 1 つだけ。Tax は移行対象外

**Checkpoint**: 全 6 リポジトリが共通基盤に乗り、SC-008 が実証される

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 旧設定の撤去、ドキュメント、コード品質、最終 E2E

- [X] T044 [P] 旧 `USE_ITEM_CACHE` / `ITEM_CACHE_TTL_SECONDS` を撤去完了。`grep -r` で 0 件を確認
- [X] T045 [P] docs/ja/ には master-data cache 固有の記述なし（grep で legacy API 参照 0 件）。skip
- [X] T046 [P] CLAUDE.md に「Master-Data Caching (cart only)」セクションを追記（Dapr state store / キー形式 / is_store_scoped）
- [X] T047 ruff はリポジトリにインストールされていないため skip（CLAUDE.md には記載があるが Pipfile に未配備）
- [ ] T048 quickstart.md のリリース前チェックリスト — Phase 7 の手動検証として未実施
- [X] T049 `./scripts/run_unit_tests.sh` のうち改修対象 (cart + commons) は全 PASS（cart 518, commons 355）。他サービスは環境未セットアップだが本フィーチャの変更範囲外
- [ ] T050 `./scripts/run_integration_tests.sh` — 実 MongoDB 起動が必要なため未実施
- [ ] T051 `./scripts/run_e2e_tests.sh` — docker-compose スタック起動が必要なため未実施
- [ ] T052 Issue #125 への完了報告 — PR 作成時に実施

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 依存なし。即時開始可
- **Phase 2 (Foundational)**: Phase 1 完了後。全ユーザストーリーをブロック
- **Phase 3 (US1)**: Phase 2 完了後
- **Phase 4 (US2)**: Phase 2 完了後（US1 と並列可。ただし結合テスト T027 で Item リポジトリを使うため、T016-T019 完了後が現実的）
- **Phase 5 (US3)**: Phase 2 完了後（US1 と並列可。同じく結合テスト T031 で Item リポジトリ前提）
- **Phase 6 (US4)**: Phase 2 完了後（US1 と独立。並列実装可能）
- **Phase 7 (Polish)**: 全ユーザストーリー完了後

### Within Each Phase

- Phase 2: T005-T008 は並列可、T009-T010 はそれぞれ T005-T007 のいずれかに依存、T011-T012 は T005 完了後、T013-T015 は独立
- Phase 3: T016-T018 はファイル独立だが本フィーチャの中核なので順次が安全（factory が両者に依存）。T019 は T016-T018 完了後。T020-T022 は対応する移行タスク完了後に並列可、T023-T024 は T019 完了後
- Phase 4: T025-T026 は並列可、T027-T028 は T026 完了後
- Phase 5: T029-T030 は並列可、T031 は T030 完了後、T032 は独立
- Phase 6: T033-T036 は全てファイル独立で並列可、T037-T038 は T033-T036 完了後、T039-T042 は対応する移行完了後に並列可、T043 は T039-T042 完了後
- Phase 7: T044-T046 は並列可、T047 以降は順次

### Parallel Opportunities

- **Phase 1**: T002-T004 が並列可（異なる Dapr テンプレートディレクトリ）
- **Phase 2.1**: T005-T010 が概ね並列可（バックエンド 3 種＋ユニットテスト 2 種）
- **Phase 6.1**: T033-T036 の 4 リポジトリ移行は完全並列（チームで 4 人作業可能）
- **Phase 6.2**: T039-T042 の 4 ユニットテスト更新も完全並列
- 全ユーザストーリー (Phase 3-6) は Phase 2 完了後ならチーム編成次第で並列実装可能

---

## Parallel Example: Phase 6 (Remaining Repos Migration)

4 リポジトリ移行は完全並列。チームで分担する例:

```bash
# Terminal 1 (Dev A): Payment
Task: T033 - payment_master_web_repository.py 移行
Task: T039 - test_payment_master_web_repository.py 更新

# Terminal 2 (Dev B): Promotion
Task: T034 - promotion_master_web_repository.py 移行
Task: T040 - test_promotion_master_web_repository.py 更新

# Terminal 3 (Dev C): Settings
Task: T035 - settings_master_web_repository.py 移行
Task: T041 - test_settings_master_web_repository.py 更新

# Terminal 4 (Dev D): Tax
Task: T036 - tax_master_repository.py 移行
Task: T042 - test_tax_master_repository.py 更新
```

各タスクは異なるファイルを触るため衝突しない。完了後に T037/T038/T043 で統合する。

---

## Implementation Strategy

### MVP First (User Story 1 のみ)

1. Phase 1 (Setup) を完了
2. Phase 2 (Foundational) を完了 — 共通基盤の完成
3. Phase 3 (US1) を完了 — Item マスタのキャッシュが効く状態に
4. **STOP and VALIDATE**: Independent Test を実行（連続商品スキャンで master-data リクエストが 1 回に減ること）
5. デモまたはステージング配備
6. ここで打ち切っても「商品マスタ参照の高速化」という最大価値はすでに提供されている

### Incremental Delivery (推奨)

1. Phase 1-2 → 共通基盤公開（他チームの参照用）
2. Phase 3 (US1) → ItemMaster キャッシュ稼働、性能改善デモ（**MVP リリース**）
3. Phase 4 (US2) → invalidate API を運用に公開
4. Phase 5 (US3) → 障害シナリオを本番ライクで検証
5. Phase 6 (US4) → 残り 4 マスタも同基盤に統一、保守性デモ
6. Phase 7 → 旧設定撤去 + ドキュメント整備で完了
7. 各フェーズ完了時点で独立してリリース可能（リグレッションは E2E で随時確認）

### Parallel Team Strategy

複数開発者の場合:

1. Phase 1-2 はチーム全員で集中して完了
2. Phase 2 完了後:
   - Dev A: Phase 3 (US1) — ItemMaster 移行（最優先・MVP）
   - Dev B: Phase 6 (US4) — Payment / Promotion / Settings / Tax を並列移行（さらに 4 人で分担可）
3. Phase 3 完了後:
   - Dev C: Phase 4 (US2) — invalidate テスト
   - Dev D: Phase 5 (US3) — Resilience テスト
4. 全フェーズ完了後に Polish を全員でレビュー

---

## Notes

- **[P] タスク**: 異なるファイルかつ未完了タスクへの依存なし。並列実行可能
- **[Story] ラベル**: トレーサビリティのため必ず付与。Setup / Foundational / Polish には付与しない
- 各ユーザストーリーは独立して完成・テスト可能（チェックポイントごとに STOP できる）
- 「テストが先、実装が後」は本プロジェクト共通の規律ではないが、本フィーチャは契約 (contracts/) が明確に定まっているため、各フェーズ内で「ユニットテスト→実装→結合テスト」の順を推奨
- コミットは各タスク単位またはタスクグループ単位（PR を細かく刻むかは Issue #125 のフェーズ分割と整合させる）
- 機微情報（マスタ値そのもの）はログに出さない（FR-012 / R-011）
- コミットメッセージ・コードコメント・ログメッセージは英語（CLAUDE.md の Language 規約）
