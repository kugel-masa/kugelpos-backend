# Phase 0 — 調査・決定事項

**Feature**: Cart Master-Data 共通キャッシュ基盤
**Branch**: `072-master-data-cache`
**Spec**: [spec.md](./spec.md) ・ [plan.md](./plan.md)

本ドキュメントは Phase 1 設計に進む前に解決しておくべき技術的未確定事項を一覧化し、各項目について採用案・根拠・代替案を記録する。

---

## R-001: Promotion リポジトリのメソッド引数 store_code をキャッシュキーに反映する方法

**問題**:
`PromotionMasterWebRepository.get_active_promotions_by_store_async(store_code: str = None)` は店舗コードを**メソッド引数**で受け取る。基底クラスの想定 API である `await self.get_or_fetch_list(logical_key)` は `tenant_id` / `store_code` をリポジトリインスタンスから取る前提のため、メソッド引数の店舗コードが反映されないとキャッシュキーが誤同一化される（バグの原因）。

**Decision**: **メソッド引数の `store_code` を最終的に `effective_store_code` としてキー生成に明示的に渡す**。基底クラスは `get_or_fetch_one(logical_key, *, store_code_override: Optional[str] = None)` / `get_or_fetch_list(logical_key, *, store_code_override: Optional[str] = None)` を提供し、override が指定された場合はインスタンス保持の store_code を上書きしてキーを構築する。

具体的には Promotion 実装は:

```python
async def get_active_promotions_by_store_async(self, store_code: str | None = None):
    effective = store_code or self.terminal_info.store_code
    return await self.get_or_fetch_list(
        logical_key="active",
        store_code_override=effective,
        fetcher=lambda: self._fetch_active_promotions(effective),
    )
```

**Rationale**:
- 引数 store_code が論理キーの一部として常に正しく反映される（隔離要件 SC-006b を満たす）
- 既存呼び出し側（`get_active_promotions_by_store_async(store_code=X)`）の API 互換を保てる
- 他リポジトリ（Item/Payment/Tax 等）はインスタンスの store_code がそのまま使われるので `store_code_override` を渡す必要がなく、純粋オプション

**Alternatives considered**:
- (b) `logical_key` に埋め込む（`logical_key=f"store:{store_code}"`）: 文字列規約が散逸し、リスト系キーと衝突しないかをユーザコードが管理する必要が出る → 採用却下
- (c) Promotion のシグネチャを変えてコンストラクタに store_code を持たせる: 既存呼び出し側の改修範囲が広く、Promotion は本質的に「ある店舗の現在有効な販促」を引くというユースケースでクラスに固定する意味が薄い → 採用却下

---

## R-002: Settings リポジトリの「テナント設定」と「店舗設定」のキー分離

**問題**:
`SettingsMasterWebRepository.__init__` は `store_code: str = None` をオプションで受け取る。同一テナントで「店舗 X の設定」と「テナント全体の設定」が別物として共存する。両者を同じ namespace で扱うとキーが衝突する。

**Decision**: **`SettingsMasterWebRepository` インスタンスが店舗依存モードか否かを `is_store_scoped` プロパティで明示的に決定**し、それに応じてキーの `store_code` 位置が実 store_code または `_`（テナント単位）になる。

```python
class SettingsMasterWebRepository(AbstractMasterDataRepository[SettingsMasterDocument]):
    cache_namespace = "settings_master"
    @property
    def is_store_scoped(self) -> bool:
        return self.store_code is not None
```

基底クラスは `is_store_scoped` を読み、True なら `store_code` をキーに含め、False なら `_` を使う。テナント設定取得用と店舗設定取得用はインスタンスを分けて生成する（DI で 2 種類を提供）。

**Rationale**:
- キー衝突を機械的に防げる
- マスタ種別の概念上の二重性（テナント設定 vs 店舗設定）がクラスレベルではなくインスタンスレベルで表現される

**Alternatives considered**:
- 同一インスタンスで両方を扱い、`logical_key` に prefix を付ける: 同 namespace で運用上混在し、`invalidate_all()` の意味が曖昧になる → 却下

---

## R-003: 単一キャッシュエントリ参照とリストキャッシュエントリ参照のキー区別

**問題**:
同一マスタ種別で「単一項目（例: 商品コード）」と「リスト（例: 店舗の有効販促一覧）」の両方をキャッシュする場合、キー衝突を防ぐ必要がある。FR-010 で別エントリとして扱うことが要求される。

**Decision**: **キーに `entry_kind` セグメントを挿入**。最終キー形式:

```
mdcache:{tenant_id}:{store_code or '_'}:{namespace}:gen{N}:{entry_kind}:{logical_key}
```

`entry_kind ∈ {"one", "list"}`。

- `get_or_fetch_one(...)` は内部で `entry_kind="one"` を使う
- `get_or_fetch_list(...)` は内部で `entry_kind="list"` を使う

**Rationale**:
- 衝突が機械的に不可能になる
- キーを見て即座に分類できる（デバッグ・運用観測性）

**Alternatives considered**:
- `logical_key` 側に呼び出し側が prefix を付ける: 規約に頼る方式は事故が起きやすい → 却下

---

## R-004: 名前空間世代カウンタの保存場所とライフサイクル

**問題**:
`invalidate_all(namespace)` を一括無効化のために実装する場合、Dapr Redis 経由では `KEYS pattern` のような bulk delete API が無い。そこで namespace ごとに「世代カウンタ (generation counter)」を別キーで持ち、`invalidate_all()` で +1 することで古い世代のキーを論理的に到達不能にする。
このカウンタをどこに保存し、どのタイミングで読むかを決定する必要がある。

**Decision**:

- 世代カウンタ自身も同じ Dapr ステートストア `masterstore` に保存する
- カウンタキー: `mdcache:{tenant_id}:{store_code or '_'}:{namespace}:generation`（TTL なし）
- 各リポジトリ操作の冒頭で「現在の世代」を 1 回読み、その操作の最後までその値をローカルキャッシュ（リクエストスコープ）で使う
- 「現在の世代」が未保存（None）なら 0 として扱う（初回は世代 0）
- `invalidate_all()` は世代カウンタを atomic にインクリメントする（Dapr の ETag セマンティクスを利用 — 失敗時はリトライ）

**Rationale**:
- Dapr の Redis 状態ストアは個別 DEL は提供するが `KEYS pattern` を公開していないため、論理的な世代付けで bulk invalidation を表現する標準的パターン
- カウンタ自体に TTL を付けない（消えると古い世代のキーが復活するため）

**Alternatives considered**:
- カウンタをローカルファイル / プロセスメモリに置く: ワーカー間で世代が一致せず無効化が伝播しない → 却下
- 全エントリの `keys()` を SCAN で列挙して DEL: Dapr ではサポートされない / コンポーネント直叩きが必要になり依存が増える → 却下

---

## R-005: TTL の設定方法（Dapr state store の per-save metadata）

**問題**:
Dapr の state store コンポーネントには component-level `ttlInSeconds` を設定できる（既存の `cartstore.yaml` がそうしている）が、マスタ種別ごとに TTL を変えたい（販促 60s、税 3600s 等）。per-save で上書きする手段を確認する必要がある。

**Decision**: **`DaprClientHelper.save_state(store_name, key, value, metadata={"ttlInSeconds": str(ttl)})` で per-key TTL を指定する**。

確認済み事項:
- 既存 `DaprClientHelper.save_state` は `metadata: Optional[Dict[str, str]]` 引数を持ち、内部で state_data に metadata を結合する (`services/commons/src/kugel_common/utils/dapr_client_helper.py:264-265`)
- Dapr の Redis state store は `ttlInSeconds` metadata をサポートしており、per-key TTL として Redis 側 EXPIRE に変換される
- コンポーネント側 `ttlInSeconds: 300` はフォールバック（metadata 指定がない場合の既定）として残す

**Rationale**: 既存 API を再利用するだけで実現でき、新依存なし。

**Alternatives considered**:
- すべて同一 TTL を component に固定: namespace ごとの差別化要求 (Assumptions の販促 60 / 税 3600) に応えられない → 却下

---

## R-006: キャッシュバックエンドのライフサイクル / DI

**問題**:
`DaprStateCacheBackend` は内部で `DaprClientHelper`（HTTP 接続プール持ち）を抱える。これを「リクエスト毎に生成」すると httpx 接続プールが毎回作り直されてオーバヘッドが出る。一方「アプリ起動時にシングルトン」だと初期化順序と shutdown 制御が必要。

**Decision**:

- アプリ起動時 (`main.py` の FastAPI `lifespan`) に `DaprStateCacheBackend` インスタンスを 1 つ生成し、`app.state.master_cache_backend` に保持
- 各リクエストの DI 関数（`get_cart_service_async()` 周辺）が `app.state.master_cache_backend` を読み、master-data リポジトリのコンストラクタに渡す
- 内部の `DaprClientHelper` は既存の `get_pooled_dapr_client()` シングルトン (`commons/utils/dapr_client_helper.py`) を再利用する。サーキットブレーカ状態もここで一元化される
- shutdown 時に `backend.close()` を呼ぶ（lifespan の exit handler で）

**Rationale**:
- 接続プール再利用でオーバヘッド最小
- サーキットブレーカ状態がワーカー単位で共有される

**Alternatives considered**:
- リクエスト毎生成: 上記オーバヘッド → 却下
- 完全グローバル変数: テスト時に差し替えが効きにくい → `app.state` 経由なら test の `dependency_overrides` で容易に差し替え可能なので採用

---

## R-007: ItemMaster Web vs Grpc の document 型互換性

**問題**:
仕様 SC-007 で「2 経路で同じキャッシュエントリを共有」が要求される。Web (`ItemMasterWebRepository`) と Grpc (`ItemMasterGrpcRepository`) がそれぞれ返す `ItemMasterDocument` は完全に同じ型・同じシリアライズ形式でなければ、片方が書いた値をもう片方が `model_validate` で読み戻せない。

**Decision**:

- 両者は `kugel_common.models.documents.item_master_document.ItemMasterDocument`（既存）を共通の document_class とする
- 基底クラスはシリアライズに `doc.model_dump(mode="json")`、デシリアライズに `cls.document_class.model_validate(data)` を使う
- gRPC レスポンス（protobuf）→ `ItemMasterDocument` 変換は既存 `_fetch_one` の中で完結する（キャッシュには Pydantic doc を渡す）

**Rationale**: Pydantic v2 の `model_dump(mode="json")` は datetime や Decimal を含む JSON シリアライズ可能な dict を返すため、Dapr (JSON) と完全互換。

**Alternatives considered**:
- protobuf 形式で直接キャッシュ: 経路依存が残り、Web 側が読めなくなる → 却下

---

## R-008: 無効化 API の公開範囲

**問題**:
`invalidate(key)` / `invalidate_all()` をどこから呼べるようにするか（リポジトリインスタンスメソッド / モジュール関数 / HTTP API / CLI ?）。

**Decision**: **本フィーチャでは「リポジトリインスタンスメソッド」のみ公開**。

- `repo.invalidate(logical_key)` / `repo.invalidate_all()` を Python レベルで提供
- HTTP API / CLI / 運用画面からの呼び出しは **本フィーチャでは追加しない**（Out of Scope）
- 将来、master-data 側の pub/sub change event を購読する subscriber が cart 側に実装される場合、その subscriber が `repo.invalidate_all()` を呼ぶことを想定

**Rationale**:
- 仕様 Out of Scope: 「マスタ管理サービス側からの変更通知イベントの発行、およびそれを受けたカート側の自動無効化フロー」は別フィーチャ
- 早期に外部 API を公開すると認可・スコープの議論が混入する。まずは内部 API として安定させてから検討する

**Alternatives considered**:
- 管理者向け HTTP `POST /admin/cache/invalidate` を同時提供: 認証スコープ・テナント分離の検討が必要で工数増 → 却下（別 Issue で扱う）

---

## R-009: テナント ID と店舗コードの取得元（店舗スコープか否かの明示宣言）

**問題**:
キー生成時に必要な `tenant_id` / `store_code` をリポジトリのどの属性から取るかを統一する必要がある。素朴に「store_code が未設定なら `terminal_info.store_code` を使う」と決めてしまうと、**テナントスコープのマスタ**（Payment, Tax 等）でも端末の所属店舗コードがキーに紛れ込み、同一テナントなのに店舗ごとに異なるキャッシュキーになってエントリが分裂する（SC-007 / SC-006b の趣旨に反する）。

**Decision**:

- リポジトリの基底クラスは `tenant_id: str` を直接受け取る
- **「店舗スコープか否か」をサブクラスがクラス属性 `is_store_scoped: ClassVar[bool]` で明示宣言する**（既定: 安全側に `True`）
- `store_code` は以下の優先順位で決定:
  1. **`is_store_scoped = False` の場合**: 常に `None` を返す（キーの該当位置は強制的に `_`）。`store_code_override` も無視
  2. `is_store_scoped = True` の場合:
     1. `store_code_override`（メソッド引数で渡された場合）
     2. インスタンスの `self.store_code`（コンストラクタで明示的に受け取った値）
     3. それでも `None` の場合は **エラー扱い**（`ValueError` を投げる、または warning ログ + `None` でテナントスコープに退避）
- **`terminal_info.store_code` への暗黙フォールバックは基底クラスでは行わない**。terminal_info は認証ヘッダ生成にのみ使う。Promotion のように「メソッド引数で店舗コードが省略されたら端末の所属店舗を使う」ような業務ロジックは、**サブクラス側のメソッド内で明示的に組み立てる**（例: `effective = store_code or self.terminal_info.store_code` を `get_or_fetch_list(..., store_code_override=effective)` の呼び出し直前で行う）
- サブクラスごとの宣言:
  - `ItemMasterWebRepository` / `ItemMasterGrpcRepository`: `is_store_scoped = True`
  - `PaymentMasterWebRepository`: `is_store_scoped = False`
  - `PromotionMasterWebRepository`: `is_store_scoped = True`
  - `SettingsMasterWebRepository`: クラス属性ではなく **インスタンスプロパティ** `@property is_store_scoped` で `self.store_code is not None` を返す（R-002 と整合）
  - `TaxMasterRepository`: `is_store_scoped = False`

**Rationale**:
- テナントスコープのマスタが意図せず店舗単位に分裂する事故を機械的に防げる
- スコープがクラス（または明示プロパティ）レベルで宣言されているため、新規リポジトリ追加時の判断点が明確
- terminal_info への暗黙フォールバックを基底から除去することで、「terminal_info の店舗が偶然セットされていたために誤動作」というクラスの不具合を排除
- Promotion のような「メソッド引数省略時に端末店舗で補完」する業務挙動は、サブクラスメソッド内で明示することで、業務意図が局所化される

**Alternatives considered**:
- 「store_code がコンストラクタで None なら自動でテナントスコープ」: 一見シンプルだが、店舗スコープマスタで store_code 渡し忘れが「サイレントなテナントスコープ化」になり、検出困難なバグを生む → 却下
- `is_store_scoped` を実装側プロパティではなく namespace 名から導出（命名規則ベース）: 暗黙的すぎる → 却下

---

## R-010: 「該当なし」応答の扱いとフォールバック挙動

**問題**:
仕様 FR-013 で「該当なしはキャッシュしない」と確定。実装上は「マスタへ問い合わせて NotFoundException が上がったら、キャッシュには何も書かずに例外を呼び出し元に伝播」が正解。一方で「キャッシュバックエンド障害時のフォールバック」(FR-007) と区別する必要がある。

**Decision**:

| 状況 | 基底クラスの挙動 |
|---|---|
| キャッシュ HIT | キャッシュ値を返す（`document_class.model_validate(data)`） |
| キャッシュ MISS → fetch 成功 | キャッシュに保存し、値を返す |
| キャッシュ MISS → fetch で NotFound | キャッシュに**保存しない**、NotFoundException を伝播 |
| キャッシュ MISS → fetch で別エラー | キャッシュに**保存しない**、例外を伝播 |
| キャッシュ get でバックエンド障害 | warning ログ、直接 fetch にフォールバック（結果はキャッシュにも書きに行くが、save も失敗してよい） |
| キャッシュ set でバックエンド障害 | warning ログ、無視（fetch 結果は呼び出し元に返す） |

**Rationale**: 仕様の FR-007 / FR-013 を機械的に実装に落とした表。

---

## R-011: ログ出力の機微情報マスキング

**問題**:
FR-012 で「マスタ値そのもの」を平文ログに残してはならない。バックエンド到達失敗時のフォールバックログにキャッシュ値や論理キー全体を載せるか否かを決める必要がある。

**Decision**:

- ログには `tenant_id` / `namespace` / `entry_kind` / 「キー長（バイト数）」のみを含める。`logical_key` 全体や value は出さない
  - 例: `logger.warning("master cache miss with backend error: tenant=%s namespace=%s entry_kind=%s key_len=%d", ...)`
- 価格・税率など機微なフィールドを含む doc 本体は出さない
- 例外の文字列化時は、`document` を含めず `key` の hash 値だけにする

**Rationale**: 顧客識別子や価格情報が運用ログに漏れるリスクを最小化。

---

## 解決済み未確定事項のサマリ

| ID | テーマ | 採用案 |
|---|---|---|
| R-001 | Promotion メソッド引数 store_code | `store_code_override` キーワード引数で明示伝搬 |
| R-002 | Settings のテナント設定 / 店舗設定共存 | `is_store_scoped` プロパティで動的判定 |
| R-003 | 単一 / リストエントリのキー区別 | キーに `entry_kind ∈ {one, list}` セグメント挿入 |
| R-004 | 名前空間世代カウンタ | `masterstore` 内に `:generation` キーで保存、ETag で atomic +1 |
| R-005 | TTL 設定方法 | `save_state` の `metadata={"ttlInSeconds": str(ttl)}` per-key 指定 |
| R-006 | バックエンドのライフサイクル | `lifespan` でシングルトン生成、`app.state` 経由 DI |
| R-007 | Item Web/Grpc 共有 | 同一 `ItemMasterDocument` を document_class とし `model_dump(mode="json")` で往復 |
| R-008 | 無効化 API 公開範囲 | Python メソッドのみ。HTTP/CLI は Out of Scope |
| R-009 | tenant_id / store_code の取得元 | `is_store_scoped` をサブクラスで明示。False なら強制 `_`、True なら override → instance の順。terminal_info への暗黙フォールバックなし |
| R-010 | NotFound と障害の区別 | NotFound はキャッシュ書込なし＋伝播、障害は warning＋直接 fetch |
| R-011 | ログマスキング | key 全体・value を出さない。namespace/entry_kind/key_len のみ |

**結論**: 未解決の NEEDS CLARIFICATION なし。Phase 1 設計へ進行可。
