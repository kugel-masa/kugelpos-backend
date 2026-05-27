# Phase 1 — データモデル / クラス構造

**Feature**: Cart Master-Data 共通キャッシュ基盤
**Branch**: `072-master-data-cache`

本ドキュメントは [spec.md](./spec.md) の Key Entities と [research.md](./research.md) の決定事項に基づき、実装上のクラス・データ構造・キー仕様を確定する。

---

## 1. キャッシュエントリのキー形式

```
mdcache:{tenant_id}:{store_code or '_'}:{namespace}:gen{N}:{entry_kind}:{logical_key}
```

| セグメント | 例 | 役割 |
|---|---|---|
| `mdcache` | 固定 | master-data 用キャッシュの prefix。他キャッシュ系統との衝突防止 |
| `{tenant_id}` | `T001` | テナント隔離（FR-003 / SC-006） |
| `{store_code or '_'}` | `S001` / `_` | 店舗隔離。テナントスコープのマスタは `_` 固定（FR-003 / SC-006b） |
| `{namespace}` | `item_master` | マスタ種別（cache_namespace） |
| `gen{N}` | `gen0`, `gen1`... | 名前空間世代カウンタ（`invalidate_all` で +1） |
| `{entry_kind}` | `one` / `list` | 単一エントリ参照 / リストエントリ参照の区別（FR-010） |
| `{logical_key}` | `ITEM001` / `active` | 論理キー（商品コードや「active」など） |

### 世代カウンタキー（別系統）

```
mdcache:{tenant_id}:{store_code or '_'}:{namespace}:generation
```

- 値: 整数（文字列で保存可）。未保存なら 0 として扱う
- TTL: なし
- 更新: ETag で atomic +1（リトライあり）

---

## 2. クラス階層

```
┌─────────────────────────────────┐
│   AbstractCacheBackend (ABC)    │  ← commons/utils/cache/cache_backend.py
└──────────────┬──────────────────┘
               │
   ┌───────────┴────────────┐
   │                        │
   ▼                        ▼
InMemoryCacheBackend   DaprStateCacheBackend
(commons)              (commons)

──────────────────────────────────────────

┌──────────────────────────────────────────────────┐
│   AbstractMasterDataRepository[TDoc] (ABC)        │  ← cart/app/models/repositories/abstract_master_data_repository.py
│   - tenant_id                                     │
│   - store_code (optional)                         │
│   - terminal_info                                 │
│   - cache_backend                                 │
│   - cache_namespace (class attr)                  │
│   - document_class (class attr)                   │
│   - default_ttl_seconds (class attr)              │
│                                                   │
│   + get_or_fetch_one(...)                         │
│   + get_or_fetch_list(...)                        │
│   + invalidate(...)                               │
│   + invalidate_all()                              │
│   # _build_key(...)                               │
│   # _resolve_store_code(override)                 │
│   # _get_generation(...)                          │
│   # _bump_generation(...)                         │
│   # _fetch_one (abstract)                         │
│   # _fetch_list (raises NotImplementedError)      │
└──────────────────────────────────────────────────┘
               │
   ┌───────────┴─────────────────────────────────────────┐
   │                                                      │
   ▼                                                      ▼
ItemMasterWebRepository    ItemMasterGrpcRepository    PaymentMasterWebRepository
PromotionMasterWebRepository    SettingsMasterWebRepository    TaxMasterRepository
```

---

## 3. AbstractCacheBackend インターフェース

```python
class AbstractCacheBackend(ABC):
    """Generic key/value cache abstraction with TTL semantics."""

    @abstractmethod
    async def get(self, key: str) -> Optional[dict]:
        """Returns the cached value as dict, or None on miss / backend error."""

    @abstractmethod
    async def set(self, key: str, value: dict, ttl_seconds: int) -> bool:
        """Returns True on success. Returns False (no exception) on backend error."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Returns True if removed (or already absent). False on backend error."""

    @abstractmethod
    async def increment(self, key: str) -> Optional[int]:
        """Atomically increments an integer counter at the key. Returns new value, or None on backend error."""
```

**設計指針**:
- value は dict（呼び出し側で `model_dump(mode="json")` 済み）
- すべてのメソッドは **例外を呼び出し元に伝播しない**。バックエンド障害時は False / None を返し、上位（基底リポジトリ）がフォールバックする
- `increment` は世代カウンタ用。Dapr ETag セマンティクスで実装

---

## 4. InMemoryCacheBackend

テスト用 / フォールバック用。スレッドセーフ・TTL 付き dict。

| 属性 | 型 | 役割 |
|---|---|---|
| `_store` | `dict[str, tuple[dict, float]]` | (value, expires_at_epoch) |
| `_lock` | `asyncio.Lock` | 並行アクセス保護 |

挙動:
- `get`: expires_at <= now なら entry を削除し None。それ以外は value を返す
- `set`: expires_at = now + ttl_seconds で保存
- `delete`: あれば削除
- `increment`: 整数として保存されている値を +1 して返す（未存在なら 1）

---

## 5. DaprStateCacheBackend

```python
class DaprStateCacheBackend(AbstractCacheBackend):
    def __init__(self, store_name: str):
        self.store_name = store_name  # e.g. "masterstore"
        # uses get_pooled_dapr_client() singleton internally

    async def get(self, key: str) -> Optional[dict]:
        # DaprClientHelper.get_state(self.store_name, key) → dict or None
        # On error: warning log, return None

    async def set(self, key: str, value: dict, ttl_seconds: int) -> bool:
        # DaprClientHelper.save_state(self.store_name, key, value, metadata={"ttlInSeconds": str(ttl_seconds)})

    async def delete(self, key: str) -> bool:
        # DaprClientHelper.delete_state(self.store_name, key)

    async def increment(self, key: str) -> Optional[int]:
        # Loop with ETag:
        #   1. Read current value (default 0 if absent)
        #   2. CAS save with new value (current+1) and old ETag
        #   3. On ETag mismatch → retry up to 3 times
        #   4. Return final value
```

**注意点**:
- Dapr の Redis state store では ETag が自動付与される
- `save_state` で `etag` パラメータを指定するとサーバ側の現在値の ETag と一致するときだけ成功する
- 3 回リトライ後も成功しない場合は None を返し、呼び出し元（基底リポジトリの `invalidate_all`）は warning ログを出すのみ

---

## 6. AbstractMasterDataRepository

### コンストラクタ

```python
def __init__(
    self,
    tenant_id: str,
    terminal_info: TerminalInfoDocument,
    cache_backend: AbstractCacheBackend,
    store_code: Optional[str] = None,
):
    self.tenant_id = tenant_id
    self.terminal_info = terminal_info
    self.cache_backend = cache_backend
    self.store_code = store_code  # may be None for tenant-scoped masters
```

### クラス属性（サブクラス必須）

```python
cache_namespace: ClassVar[str]                # 例: "item_master"
document_class: ClassVar[type[BaseDocumentModel]]
default_ttl_seconds: ClassVar[int] = 300
is_store_scoped: ClassVar[bool] = True        # 店舗依存マスタかどうか。R-009 参照
                                              # False ならキーの store 位置は強制 "_"
                                              # Settings のように動的判定が必要なクラスは
                                              # ClassVar ではなく @property でオーバライド
```

### 公開メソッド

```python
async def get_or_fetch_one(
    self,
    logical_key: str,
    *,
    store_code_override: Optional[str] = None,
    ttl_seconds: Optional[int] = None,
    fetcher: Optional[Callable[[], Awaitable[TDoc]]] = None,
) -> TDoc: ...

async def get_or_fetch_list(
    self,
    logical_key: str,
    *,
    store_code_override: Optional[str] = None,
    ttl_seconds: Optional[int] = None,
    fetcher: Optional[Callable[[], Awaitable[list[TDoc]]]] = None,
) -> list[TDoc]: ...

async def invalidate(
    self,
    logical_key: str,
    *,
    store_code_override: Optional[str] = None,
    entry_kind: str = "one",
) -> None: ...

async def invalidate_all(self) -> None:
    # Bumps the generation counter for this namespace/tenant/store scope
    ...
```

### サブクラス側で実装する抽象メソッド

```python
@abstractmethod
async def _fetch_one(self, logical_key: str) -> TDoc: ...

async def _fetch_list(self, logical_key: str) -> list[TDoc]:
    raise NotImplementedError
```

`_fetch_one` / `_fetch_list` は `store_code` 引数を取らない。`store_code` はリポジトリインスタンスの `self.store_code` または override 経由でメソッド側に流れるが、fetch 関数は「論理キーで取りに行く」純粋関数として書ける。

ただし `get_or_fetch_*` の `fetcher` パラメータを指定すると、外部から fetch クロージャを差し込めるようになっている。これは Promotion のようにメソッド引数 `store_code` を fetch にも渡す必要があるケース用:

```python
return await self.get_or_fetch_list(
    logical_key="active",
    store_code_override=effective_store_code,
    fetcher=lambda: self._fetch_active_promotions(effective_store_code),
)
```

### 主要処理フロー（get_or_fetch_one）

```
1. cache_enabled が False → fetcher() を直接呼び返す
2. effective_store_code = _resolve_store_code(store_code_override)
3. generation = _get_generation(effective_store_code)
4. key = _build_key(effective_store_code, generation, "one", logical_key)
5. cached = await cache_backend.get(key)
6a. cached が dict → document_class.model_validate(cached) を返す
6b. cached が None → fetcher() を呼ぶ
       - 成功 → cache_backend.set(key, doc.model_dump(mode="json"), ttl) → doc を返す
       - NotFoundException → 例外を伝播（キャッシュ書込なし）
       - その他例外 → 例外を伝播（キャッシュ書込なし）
```

`get_or_fetch_list` は entry_kind を "list" にし、戻り値型と直列化形式が `list[dict]` ↔ `list[TDoc]` になる以外は同じフロー。

### `_resolve_store_code` の優先順位

R-009 の決定に従い、`terminal_info.store_code` への暗黙フォールバックは行わない。テナントスコープのマスタが端末の所属店舗コードに引きずられてキーが分裂することを防ぐ。

```python
def _resolve_store_code(self, override: Optional[str]) -> Optional[str]:
    if not self.is_store_scoped:
        # Tenant-scoped master: store position in the key is forced to "_".
        return None
    if override is not None:
        return override
    if self.store_code is not None:
        return self.store_code
    # Store-scoped repository with no store_code resolvable: programming error.
    raise ValueError(
        f"{type(self).__name__} is store-scoped but no store_code was provided "
        "(neither via constructor nor via store_code_override)."
    )
```

業務ロジックとして「メソッド引数省略時に端末の所属店舗で補完」したい場合（例: Promotion）は、サブクラスのメソッド側で明示的に組み立てて `store_code_override` に渡す。基底クラスは terminal_info を**認証ヘッダ生成にしか**参照しない。

---

## 7. サブクラスごとの宣言と fetch ロジック

### 7.1 ItemMasterWebRepository

`store_code` はコンストラクタで一度受け取り、以降はインスタンス状態 (`self.store_code`) として保持する。キャッシュキー組み立て側（基底クラスの `_resolve_store_code()`）と HTTP リクエスト URL の組み立て側（`_fetch_one` 内）の双方が `self.store_code` を読む。Item ではメソッド呼び出し時に店舗を切り替える要件がないため、`store_code_override` や `fetcher` クロージャ（Promotion で使う形）は不要。

```python
class ItemMasterWebRepository(AbstractMasterDataRepository[ItemMasterDocument]):
    cache_namespace = "item_master"
    document_class = ItemMasterDocument
    default_ttl_seconds = cart_settings.ITEM_MASTER_CACHE_TTL_SECONDS
    is_store_scoped = True

    def __init__(
        self,
        tenant_id: str,
        store_code: str,                       # ← required, persisted via super().__init__
        terminal_info: TerminalInfoDocument,
        cache_backend: AbstractCacheBackend,
    ):
        super().__init__(
            tenant_id=tenant_id,
            terminal_info=terminal_info,
            cache_backend=cache_backend,
            store_code=store_code,             # ← stored as self.store_code by the base class
        )

    async def get_item_by_code_async(self, item_code: str) -> ItemMasterDocument:
        # Cache lookup: self.store_code is read by the base class via _resolve_store_code()
        # because is_store_scoped=True. No method-level override is needed.
        return await self.get_or_fetch_one(item_code)

    async def _fetch_one(self, item_code: str) -> ItemMasterDocument:
        # HTTP fetch: self.store_code is also embedded in the master-data endpoint URL.
        endpoint = (
            f"/tenants/{self.tenant_id}"
            f"/stores/{self.store_code}"
            f"/items/{item_code}/details"
        )
        headers = self._build_master_data_headers()  # JWT or X-API-KEY (existing pattern)
        async with get_pooled_client("master-data") as client:
            response_data = await client.get(endpoint, headers=headers)
        return ItemMasterDocument.model_validate(response_data)
```

**store_code の流れ**:

1. DI コンテナが端末の所属店舗から `store_code` を取得し、コンストラクタに渡す
2. `super().__init__()` で `self.store_code` に保存
3. `get_item_by_code_async(item_code)` 呼び出し時、基底クラスが `self.store_code` をキー組み立てに使う
4. キャッシュ MISS の場合、`_fetch_one(item_code)` が `self.store_code` を URL に埋め込んで HTTP リクエストを送る

つまりメソッドシグネチャに `store_code` が現れないのは、「同一リポジトリインスタンスが扱う店舗は常に 1 つで、それは構築時に固定される」という設計を反映している。複数店舗を 1 インスタンスで扱いたい場合は、別インスタンスを生成するか、Promotion 同様の `store_code_override` パターンを採用する。

### 7.2 ItemMasterGrpcRepository

```python
class ItemMasterGrpcRepository(AbstractMasterDataRepository[ItemMasterDocument]):
    cache_namespace = "item_master"            # ← Web と同一 namespace
    document_class = ItemMasterDocument        # ← Web と同一 document_class
    default_ttl_seconds = cart_settings.ITEM_MASTER_CACHE_TTL_SECONDS
    is_store_scoped = True

    async def get_item_by_code_async(self, item_code: str) -> ItemMasterDocument:
        return await self.get_or_fetch_one(item_code)

    async def _fetch_one(self, item_code: str) -> ItemMasterDocument:
        # 既存の gRPC 呼び出し → protobuf 変換 → ItemMasterDocument
        ...
```

→ 同じ (tenant, store, "item_master", entry_kind, item_code) のキーを共有（SC-007 を満たす）

### 7.3 PaymentMasterWebRepository

```python
class PaymentMasterWebRepository(AbstractMasterDataRepository[PaymentMasterDocument]):
    cache_namespace = "payment_master"
    document_class = PaymentMasterDocument
    default_ttl_seconds = cart_settings.PAYMENT_MASTER_CACHE_TTL_SECONDS
    is_store_scoped = False                    # ← テナント単位

    def __init__(self, tenant_id, terminal_info, cache_backend):
        # store_code は持たない。is_store_scoped=False なのでキー中 store 位置は強制 "_"
        super().__init__(tenant_id, terminal_info, cache_backend, store_code=None)

    async def get_payment_by_code_async(self, payment_code: str) -> PaymentMasterDocument:
        return await self.get_or_fetch_one(payment_code)

    async def _fetch_one(self, payment_code: str) -> PaymentMasterDocument:
        ...
```

### 7.4 PromotionMasterWebRepository

```python
class PromotionMasterWebRepository(AbstractMasterDataRepository[PromotionMasterDocument]):
    cache_namespace = "promotion_master"
    document_class = PromotionMasterDocument
    default_ttl_seconds = cart_settings.PROMOTION_MASTER_CACHE_TTL_SECONDS
    is_store_scoped = True

    async def get_active_promotions_by_store_async(
        self, store_code: str | None = None
    ) -> list[PromotionMasterDocument]:
        # 業務ロジックとして「メソッド引数省略時は端末の所属店舗で補完」する。
        # 基底クラスは terminal_info への暗黙フォールバックを行わないので、
        # ここで明示的に組み立てて store_code_override に渡す（R-009）。
        effective = store_code or self.terminal_info.store_code
        return await self.get_or_fetch_list(
            logical_key="active",
            store_code_override=effective,
            fetcher=lambda: self._fetch_active(effective),
        )

    async def _fetch_active(self, store_code: str) -> list[PromotionMasterDocument]:
        ...
```

### 7.5 SettingsMasterWebRepository

```python
class SettingsMasterWebRepository(AbstractMasterDataRepository[SettingsMasterDocument]):
    cache_namespace = "settings_master"
    document_class = SettingsMasterDocument
    default_ttl_seconds = cart_settings.SETTINGS_MASTER_CACHE_TTL_SECONDS

    # ClassVar ではなく動的プロパティ。インスタンスの store_code の有無で
    # テナント設定 / 店舗設定を切り替える（R-002）。
    @property
    def is_store_scoped(self) -> bool:                  # type: ignore[override]
        return self.store_code is not None

    async def get_settings_value_by_name_async(self, name: str) -> SettingsMasterDocument | None:
        try:
            return await self.get_or_fetch_one(name)
        except NotFoundException:
            return None  # 既存仕様: 404 は None を返す

    async def get_all_settings_async(self) -> list[SettingsMasterDocument]:
        return await self.get_or_fetch_list("__all__")

    async def _fetch_one(self, name: str) -> SettingsMasterDocument:
        ...
    async def _fetch_list(self, _key: str) -> list[SettingsMasterDocument]:
        ...
```

DI は 2 種類のインスタンスを提供する想定（テナント設定用: `store_code=None` → `is_store_scoped=False` 相当 / 店舗設定用: `store_code=terminal_info.store_code` → `is_store_scoped=True` 相当）。

### 7.6 TaxMasterRepository

```python
class TaxMasterRepository(AbstractMasterDataRepository[TaxMasterDocument]):
    cache_namespace = "tax_master"
    document_class = TaxMasterDocument
    default_ttl_seconds = cart_settings.TAX_MASTER_CACHE_TTL_SECONDS
    is_store_scoped = False                    # ← テナント単位

    def __init__(self, db, tenant_id, terminal_info, cache_backend):
        super().__init__(tenant_id, terminal_info, cache_backend, store_code=None)
        self.db = db  # MongoDB AsyncIOMotorDatabase

    async def get_tax_by_code(self, tax_code: str) -> TaxMasterDocument:
        return await self.get_or_fetch_one(tax_code)

    async def _fetch_one(self, tax_code: str) -> TaxMasterDocument:
        # 既存の MongoDB 直読クエリ
        ...

    # load_all_taxes() は warmup として残してもよいが、本フィーチャでは必須ではない
```

---

## 8. ItemMasterRepositoryFactory

```python
def create_item_master_repository(
    tenant_id: str,
    store_code: str,
    terminal_info: TerminalInfoDocument,
    cache_backend: AbstractCacheBackend,
) -> AbstractMasterDataRepository[ItemMasterDocument]:
    cls = ItemMasterGrpcRepository if cart_settings.USE_GRPC else ItemMasterWebRepository
    return cls(
        tenant_id=tenant_id,
        terminal_info=terminal_info,
        cache_backend=cache_backend,
        store_code=store_code,
    )
```

### 多経路マスタの一般原則（将来の追加時にも適用）

将来あるマスタ種別に複数の取得経路（HTTP / gRPC / その他）が追加される場合、以下の規律を必ず守る。これは Item に限らず Payment / Promotion / Settings / 新規マスタすべてに適用する一般原則である。

| 要件 | 必須 / 任意 | 理由 |
|---|---|---|
| 同一マスタ種別の全経路実装で `cache_namespace` を**完全一致**させる | **必須** | キーの namespace セグメントが揃い、SC-007（経路間キャッシュ共有率 100%）が成立する |
| 同一マスタ種別の全経路実装で `document_class` を**完全一致**させる | **必須** | `model_dump(mode="json")` ↔ `model_validate` のラウンドトリップが経路をまたいで成立する |
| 同一マスタ種別の全経路実装で `is_store_scoped` を**一致**させる | **必須** | キーの store セグメントの解決ロジックが揃い、片方が `_`、他方が実 store_code になる事故を防ぐ |
| 同一マスタ種別の全経路実装で `default_ttl_seconds` を**一致**させる | **強く推奨** | 不一致でも動作はするが、書込側の TTL で実効的な鮮度が決まるため運用予測がブレる |
| 経路選択のためのファクトリ関数を提供する | **任意** | 呼び出し側コードに `if USE_GRPC:` の分岐が散らかるのを防ぐための DRY 化。経路が 1 つのうちは不要 |

これらの規律が守られていれば、ファクトリの有無にかかわらず、書込側経路（例: HTTP）でキャッシュに入った値を読出側経路（例: gRPC）が正しく取り出せる。

逆にこれらの規律が破られた場合のリスク:

- `cache_namespace` 不一致 → 片方が書いたエントリをもう片方が見つけられず、キャッシュ二重化。両方で MISS → fetch 起動が止まらない
- `document_class` 不一致 → `model_validate` で型エラー、もしくはフィールド欠落のサイレント不整合
- `is_store_scoped` 不一致 → 片方は店舗単位、片方はテナント単位でキーが分かれ、上書きで誤データが見える可能性

---

## 9. 設定（`services/cart/app/config/settings_cart.py`）

新規追加:

| 設定キー | 型 | 既定値 | 用途 |
|---|---|---|---|
| `MASTER_DATA_CACHE_ENABLED` | bool | True | キャッシュ機構の全体スイッチ（FR-008） |
| `MASTER_DATA_CACHE_STATE_STORE` | str | `"masterstore"` | Dapr ステートストア名 |
| `MASTER_DATA_CACHE_TTL_SECONDS` | int | 300 | namespace 個別設定がない場合のフォールバック TTL |
| `ITEM_MASTER_CACHE_TTL_SECONDS` | int | 300 | 商品マスタの TTL |
| `PAYMENT_MASTER_CACHE_TTL_SECONDS` | int | 600 | 支払マスタの TTL |
| `PROMOTION_MASTER_CACHE_TTL_SECONDS` | int | 60 | 販促マスタの TTL |
| `SETTINGS_MASTER_CACHE_TTL_SECONDS` | int | 600 | 設定マスタの TTL |
| `TAX_MASTER_CACHE_TTL_SECONDS` | int | 3600 | 税マスタの TTL |

撤去:

| 旧設定キー | 撤去理由 |
|---|---|
| `USE_ITEM_CACHE` | `MASTER_DATA_CACHE_ENABLED` に統合 |
| `ITEM_CACHE_TTL_SECONDS` | `ITEM_MASTER_CACHE_TTL_SECONDS` に改名 |

---

## 10. Dapr コンポーネント（`services/dapr/components/masterstore.yaml`）

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: masterstore
spec:
  type: state.redis
  version: v1
  metadata:
    - name: redisHost
      value: redis:6379
    - name: redisPassword
      value: ""
    - name: actorStateStore
      value: "false"
    - name: ttlInSeconds
      value: "300"          # フォールバック TTL（per-save metadata で上書き）
    - name: databaseIndex
      value: "3"            # cart=2 / 既存 statestore=1 / 0 はデフォルト
```

K8s 用テンプレート（`services/dapr/k8s-components/` または相当ディレクトリ）と Azure Container Apps 用テンプレートにも同等の設定を追加する。

---

## 11. 例外マッピング

各サブクラスの `_fetch_one` / `_fetch_list` が投げる例外と、基底クラスでの扱い:

| 例外 | 基底の扱い |
|---|---|
| `NotFoundException` | キャッシュ書込なし、そのまま伝播 |
| `RepositoryException` | キャッシュ書込なし、そのまま伝播 |
| `httpx.HTTPError` 等 | サブクラスで `RepositoryException` に包んで投げる → 基底はそのまま伝播 |

キャッシュバックエンド側の例外:

| バックエンド呼び出し | 失敗時の挙動 |
|---|---|
| `cache_backend.get(...)` | warning ログ、`None` 扱い（fetch にフォールバック） |
| `cache_backend.set(...)` | warning ログ、無視（fetch 結果は呼び出し元へ返す） |
| `cache_backend.delete(...)` | warning ログ、無視 |
| `cache_backend.increment(...)` | warning ログ、`invalidate_all` 失敗を呼び出し元には例外で返さず警告のみ |

---

## 12. 検証可能性マトリクス（要件 ↔ データモデル）

| 要件 | データモデル要素 |
|---|---|
| FR-001（再フェッチ抑制） | `get_or_fetch_*` の HIT パス |
| FR-002（ワーカー横断共有） | DaprStateCacheBackend + Redis |
| FR-003（テナント・店舗隔離） | キー形式の `{tenant_id}`/`{store_code or '_'}` セグメント + サブクラスの `is_store_scoped` 宣言（R-009）でテナント単位マスタの店舗分裂を防止 |
| FR-004（namespace 別 TTL） | `default_ttl_seconds` クラス属性 + 設定 |
| FR-005（個別無効化） | `invalidate(logical_key)` |
| FR-006（namespace 一括無効化） | `invalidate_all()` + 世代カウンタ |
| FR-007（障害時継続） | バックエンド例外を伝播せず `None`/`False` を返す契約 |
| FR-008（全体スイッチ） | `MASTER_DATA_CACHE_ENABLED` |
| FR-009（新規追加コスト最小） | 基底クラス + クラス属性 3 つ + 抽象メソッドのみ |
| FR-010（単一/リスト区別） | キー中の `entry_kind` セグメント |
| FR-011（経路共有） | Item Web/Grpc が同じ namespace + document_class |
| FR-012（ログ機微情報） | R-011 のマスキング規約 |
| FR-013（NotFound 非キャッシュ） | フロー 6b で NotFound 時は書込スキップ |
