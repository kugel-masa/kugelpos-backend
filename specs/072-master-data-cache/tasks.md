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

- [ ] T016 [US1] `services/cart/app/models/repositories/item_master_web_repository.py` を改修: `AbstractMasterDataRepository[ItemMasterDocument]` を継承し、旧 `_item_cache` / `USE_ITEM_CACHE` 参照を削除。クラス属性宣言（`cache_namespace="item_master"`, `document_class=ItemMasterDocument`, `default_ttl_seconds=cart_settings.ITEM_MASTER_CACHE_TTL_SECONDS`, `is_store_scoped=True`）。コンストラクタは `tenant_id, store_code, terminal_info, cache_backend` を受け取り `super().__init__()`。`get_item_by_code_async` を `return await self.get_or_fetch_one(item_code)` に簡略化。`_fetch_one(item_code)` は既存の HTTP 呼出ロジック（`get_pooled_client("master-data")` + JWT/API-key ヘッダ + URL `/tenants/{tenant_id}/stores/{store_code}/items/{item_code}/details`）を移植
- [ ] T017 [US1] `services/cart/app/models/repositories/item_master_grpc_repository.py` を改修: 同上の構成で `AbstractMasterDataRepository[ItemMasterDocument]` を継承。`cache_namespace="item_master"`, `document_class=ItemMasterDocument` を Web と完全一致させる（SC-007 の前提）。`_fetch_one(item_code)` は既存の gRPC スタブ呼出 + protobuf → `ItemMasterDocument` 変換を移植
- [ ] T018 [US1] `services/cart/app/models/repositories/item_master_repository_factory.py` を改修: 引数を `(tenant_id, store_code, terminal_info, cache_backend)` に変更し、旧 `item_master_documents` 引数を削除。戻り値型を `AbstractMasterDataRepository[ItemMasterDocument]` に変更。`cart_settings.USE_GRPC` 判定ロジックは維持
- [ ] T019 [US1] `services/cart/app/dependencies/` 配下で `create_item_master_repository(...)` を呼ぶ DI 関数を改修し、`cache_backend=request.app.state.master_cache_backend` を渡す（旧 `item_master_documents` 引数の受け渡しも削除）

### 3.2 既存テストの更新と新規テスト追加

- [ ] T020 [P] [US1] [Unit] `services/cart/tests/unit/repositories/test_item_master_web_repository.py` を新シグネチャに合わせて更新（fetch のモック化: `monkeypatch.setattr(repo, "_fetch_one", ...)` で差し替え）。既存のキャッシュ検証ロジックは基底クラステストに移譲したため、ここでは「`_fetch_one` の URL 組立」「認証ヘッダ生成」「例外マッピング（NotFoundException/RepositoryException）」に絞る
- [ ] T021 [P] [US1] [Unit] `services/cart/tests/unit/repositories/test_item_master_grpc_repository.py` を新シグネチャに合わせて更新（gRPC スタブをモック化、`_fetch_one` の挙動と例外マッピングに絞る）
- [ ] T022 [P] [US1] [Unit] `services/cart/tests/unit/repositories/test_item_master_repository_factory.py` を更新（cache_backend 引数を渡す形に、`USE_GRPC` 分岐の検証）
- [ ] T023 [US1] [Integration] `services/cart/tests/integration/repositories/test_item_master_with_dapr.py` を新規作成: 実 Redis + Dapr サイドカー起動状態で以下を検証
  - キャッシュ MISS → fetch → 同キー再参照で HIT（SC-001）
  - TTL 経過後の再フェッチ
  - Web で書いた値を Grpc が読める（SC-007）
  - キー形式が `mdcache:{tenant}:{store}:item_master:gen0:one:{item_code}` 通り（`redis-cli KEYS` で確認）
  - **テナント間隔離 [SC-006]**: 2 テナントでそれぞれ同じ item_code を引いても相互にキャッシュが見えないこと（実 Redis 上で別キーとして格納されていることを `redis-cli KEYS` で確認）
  - **店舗間隔離 [SC-006b]**: 同テナント・異なる store_code でそれぞれ同じ item_code を引いた結果、Redis 上で別キーになっていること
  - **キャッシュ無効化バイパス [FR-008]**: `MASTER_DATA_CACHE_ENABLED=False` の場合、Redis にキーが書かれないこと
- [ ] T024 [US1] [E2E] 既存 E2E シナリオ `tests/e2e/test_purchase_*.py` に対するリグレッション確認（修正不要、`./scripts/run_e2e_tests.sh cart` が通ること）

**Checkpoint**: User Story 1 がデモ可能。Item マスタの参照が初回以外キャッシュから返り、Web/Grpc 切替に関わらず同じキャッシュエントリを共有することが観測できる

---

## Phase 4: User Story 2 - マスタ更新時の手動でのキャッシュ無効化 (Priority: P2)

**Goal**: `invalidate(key)` と `invalidate_all()` の運用 API が、Item マスタおよび世代カウンタ機構で正しく動作することを検証

**Independent Test**: Item マスタの任意のキャッシュ済み項目に対して `await item_repo.invalidate("ITEM_A")` を呼んだ直後、`get_item_by_code_async("ITEM_A")` が master-data から再フェッチすることを観測する。また `await item_repo.invalidate_all()` 呼出後、当該テナント/店舗/namespace の全エントリが次回参照で再フェッチされる（他 namespace は影響なし）ことを観測する

### 4.1 単体テスト

- [ ] T025 [P] [US2] [Unit] 個別無効化テストを `services/cart/tests/unit/repositories/test_abstract_master_data_repository.py` に追加（T012 と同ファイル）: `repo.invalidate("KEY_A")` 呼出後、`KEY_A` への次回参照で `_fetch_one` が再度呼ばれ、他キー（`KEY_B`）は HIT のままであることを検証
- [ ] T026 [P] [US2] [Unit] 一括無効化（世代カウンタ）テストを同ファイルに追加: `repo.invalidate_all()` 呼出で世代が +1 されること、全エントリが次回参照でミス→再フェッチに走ること、別 namespace（モックの他リポジトリ）は影響を受けないこと

### 4.2 結合テスト

- [ ] T027 [US2] [Integration] `services/cart/tests/integration/repositories/test_item_master_with_dapr.py` に invalidate / invalidate_all のシナリオを追加: 実 Redis 上で個別キーの delete と世代カウンタの +1 が観測できること（`redis-cli` で確認）
- [ ] T028 [US2] [Integration] 世代カウンタの ETag CAS リトライ挙動を `services/commons/tests/integration/utils/cache/test_dapr_state_cache_backend.py` に追加: 2 並行 `increment` が両方とも独立した値を取得すること（並行性検証）

**Checkpoint**: User Story 2 が動作する。Item リポジトリで invalidate が即時反映されることが手動・自動の両方で確認できる

---

## Phase 5: User Story 3 - キャッシュバックエンド障害時の継続稼働 (Priority: P2)

**Goal**: Redis または Dapr サイドカーが応答不能な状態でも、カート操作（master-data 参照を含む）が成功完了することを検証

**Independent Test**: `docker compose stop redis` で Redis を意図的に停止した状態で、E2E のカート購買シナリオを実行し、すべての master-data 参照が成功し、レジ操作（開店 → スキャン → 会計 → 閉店）が 100% 完了することを観測する（応答時間の劣化は許容）

### 5.1 単体テスト

- [ ] T029 [P] [US3] [Unit] `services/cart/tests/unit/repositories/test_abstract_master_data_repository.py` にバックエンド障害シミュレーションを追加: `cache_backend.get` が `None` を返す（バックエンド失敗時の契約）、`set` が `False` を返す状況で `get_or_fetch_one` がフェッチを実行し成功すること（例外を伝播しないこと）
- [ ] T030 [P] [US3] [Unit] `services/commons/tests/unit/utils/cache/test_dapr_state_cache_backend.py` に DaprClientHelper の例外（`DaprError`, `httpx.HTTPError` 相当）発生時の挙動検証を追加: `get` は `None`、`set` は `False`、`delete` は `False`、`increment` は `None` を返し、いずれも warning ログを出すこと

### 5.2 結合テスト

- [ ] T031 [US3] [Integration] `services/cart/tests/integration/repositories/test_item_master_resilience.py` を新規作成: docker-compose の Redis を programmatically 止めるフィクスチャを用意し、Item 参照が `_fetch_one` 経由で成功すること、復旧後にキャッシュが再び効くことを検証

### 5.3 E2E 手動検証手順の文書化

- [ ] T032 [US3] `services/cart/tests/e2e/MANUAL_VERIFY_RESILIENCE.md` を新規作成: quickstart.md §7.4 の手順を独立した検証手順書として整備（`docker compose stop redis` → E2E → `docker compose start redis` → 再 E2E のシーケンス）

**Checkpoint**: User Story 3 が動作する。Redis 停止下でも cart 操作が完走する

---

## Phase 6: User Story 4 - 新マスタリポジトリ追加時の実装コスト削減 (Priority: P3)

**Goal**: 残り 4 種のリポジトリ（Payment / Promotion / Settings / Tax）を共通基盤に移行し、移行後の各リポジトリのキャッシュ関連コード行数が 0 行（基底クラスへの宣言・取得関数のみで完結）であることを確認。これにより SC-008 を実証する

**Independent Test**: 移行後の 4 リポジトリそれぞれについて、`grep -E "(cache|TTL|expire|invalidate)" services/cart/app/models/repositories/{payment,promotion,settings,tax}_master_*.py` でキャッシュ関連の独自コードが検出されないことを確認

### 6.1 各リポジトリの移行（並列可）

- [ ] T033 [P] [US4] `services/cart/app/models/repositories/payment_master_web_repository.py` を改修: `AbstractMasterDataRepository[PaymentMasterDocument]` を継承、`cache_namespace="payment_master"`, `document_class=PaymentMasterDocument`, `default_ttl_seconds=cart_settings.PAYMENT_MASTER_CACHE_TTL_SECONDS`, `is_store_scoped=False`。コンストラクタは `tenant_id, terminal_info, cache_backend` を受け取り `store_code=None` で `super().__init__()`。`get_payment_by_code_async` を `get_or_fetch_one(payment_code)` 化。旧 `payment_master_documents` 引数は削除。`_fetch_one` に既存 HTTP 呼出を移植
- [ ] T034 [P] [US4] `services/cart/app/models/repositories/promotion_master_web_repository.py` を改修: `AbstractMasterDataRepository[PromotionMasterDocument]` を継承、`is_store_scoped=True`。`get_active_promotions_by_store_async(store_code=None)` 内で `effective = store_code or self.terminal_info.store_code` を組み立て、`get_or_fetch_list(logical_key="active", store_code_override=effective, fetcher=lambda: self._fetch_active(effective))` を呼ぶ。`_fetch_active(store_code)` に既存 HTTP 呼出を移植
- [ ] T035 [P] [US4] `services/cart/app/models/repositories/settings_master_web_repository.py` を改修: `AbstractMasterDataRepository[SettingsMasterDocument]` を継承、`is_store_scoped` は `@property` で `self.store_code is not None` を返す。`get_settings_value_by_name_async(name)` は `get_or_fetch_one(name)` 化（`NotFoundException` を捕捉して `None` 返却の既存仕様維持）。`get_all_settings_async()` は `get_or_fetch_list("__all__")` 化。旧 `settings_master_documents` 引数は削除。`_fetch_one` / `_fetch_list` に既存 HTTP 呼出を移植
- [ ] T036 [P] [US4] `services/cart/app/models/repositories/tax_master_repository.py` を改修: `AbstractMasterDataRepository[TaxMasterDocument]` を継承、`is_store_scoped=False`。コンストラクタは `db` も受け取る（MongoDB アクセス用）。`get_tax_by_code(tax_code)` を `get_or_fetch_one(tax_code)` 化。`_fetch_one` に既存 MongoDB クエリを移植。`load_all_taxes()` は warmup として残置（タスク T037 で削除判断）
- [ ] T037 [US4] `load_all_taxes()` の呼出元を grep で確認し、`get_tax_by_code` への移行で不要になっていれば撤去、必要なら warmup として残置。判断結果をコミットメッセージに記録
- [ ] T038 [US4] `services/cart/app/dependencies/` 配下の DI 関数を改修: Payment / Promotion / Settings / Tax の各リポジトリ生成時に `cache_backend=request.app.state.master_cache_backend` を渡し、旧 `*_master_documents` 引数を削除。Settings は「テナント設定用（store_code=None）」と「店舗設定用（store_code=terminal_info.store_code）」を別 DI で提供

### 6.2 既存テストの更新

- [ ] T039 [P] [US4] [Unit] `services/cart/tests/unit/repositories/test_payment_master_web_repository.py` を新シグネチャに合わせ更新
- [ ] T040 [P] [US4] [Unit] `services/cart/tests/unit/repositories/test_promotion_master_web_repository.py` を更新（メソッド引数 `store_code` がキャッシュキーに反映されることを `InMemoryCacheBackend` で検証）
- [ ] T041 [P] [US4] [Unit] `services/cart/tests/unit/repositories/test_settings_master_web_repository.py` を更新（`is_store_scoped` プロパティの動的判定、テナント設定 vs 店舗設定のキー分離を検証）
- [ ] T042 [P] [US4] [Unit] `services/cart/tests/unit/repositories/test_tax_master_repository.py` を更新（DB モック化、`_fetch_one` の挙動検証）

### 6.3 SC-008 の検証

- [ ] T043 [US4] [Verification] 移行後の各リポジトリファイルから「キャッシュ関連コードが 0 行」であることを以下のコマンドで確認: `for f in services/cart/app/models/repositories/{payment,promotion,settings,tax}_master_*.py; do echo "=== $f ==="; grep -nE "_cache|TTL|expire|invalidate" "$f" || echo "  OK: 0 hits"; done`。結果を本タスクのコミットメッセージに添付

**Checkpoint**: 全 6 リポジトリが共通基盤に乗り、SC-008 が実証される

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 旧設定の撤去、ドキュメント、コード品質、最終 E2E

- [ ] T044 [P] `services/cart/app/config/settings_cart.py` の旧 `USE_ITEM_CACHE` / `ITEM_CACHE_TTL_SECONDS` を撤去。`grep -r "USE_ITEM_CACHE\|ITEM_CACHE_TTL_SECONDS" services/cart` が 0 件であることを確認
- [ ] T045 [P] 既存ドキュメント `docs/ja/` 配下に master-data キャッシュに関する記述があれば最新仕様に合わせて更新（なければ skip。grep で確認）
- [ ] T046 [P] CLAUDE.md の "High-Level Architecture Patterns" セクションに「Master-data caching: AbstractMasterDataRepository + Dapr state store (masterstore, Redis db=3)」相当の 1〜2 行を追記
- [ ] T047 変更された全 Python ファイルに `pipenv run ruff check --fix` と `ruff format` を適用（cart / commons）
- [ ] T048 quickstart.md §8 のリリース前チェックリストに沿って手動検証を実施し、全項目を消化
- [ ] T049 `./scripts/run_unit_tests.sh` 全件 PASS を確認
- [ ] T050 `./scripts/run_integration_tests.sh` 全件 PASS を確認（実 Redis 起動状態）
- [ ] T051 `./scripts/run_e2e_tests.sh` 全件 PASS を確認（リグレッションなし）
- [ ] T052 Issue #125 のチェックボックス（あれば）を消化し、PR 説明に各 SC の検証結果を記載

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
