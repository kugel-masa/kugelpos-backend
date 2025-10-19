# gRPC Channel Pooling Analysis - Phase 2

**分析日:** 2025-10-19
**対象:** Phase 2テスト実行ログ (20251019_055525)

---

## ログ分析結果

### gRPCチャネル作成回数

| テストパターン | リクエスト数 | gRPCチャネル作成回数 | 期待値 | 状態 |
|---------------|-------------|---------------------|--------|------|
| **1 User (3分)** | 58 | **86回** | 1-3回 | ❌ 期待値を大幅超過 |
| **3 Users (3分)** | 168 | **141回** | 3-15回 | ❌ 期待値を大幅超過 |
| **合計** | 226 | **227回** | 4-18回 | ❌ ほぼ1:1の比率 |

**結論:** gRPCチャネルプーリングは **機能していません**

### チャネル作成パターン

```
2025-10-19 05:55:39,821 [INFO] Created new gRPC channel for master-data service (tenant=T8831, store=5678)
2025-10-19 05:55:42,926 [INFO] Created new gRPC channel for master-data service (tenant=T8831, store=5678)
2025-10-19 05:55:45,981 [INFO] Created new gRPC channel for master-data service (tenant=T8831, store=5678)
2025-10-19 05:55:49,034 [INFO] Created new gRPC channel for master-data service (tenant=T8831, store=5678)
...（約3秒ごとに新しいチャネル作成）
```

**観察:**
- 約3秒ごとに新しいチャネルが作成されている
- 同じtenant/storeに対して繰り返しチャネル作成
- チャネル再利用の兆候なし

---

## 根本原因分析

### 問題の所在

**File:** `app/dependencies/get_cart_service.py:112-116`

```python
async def __get_cart_service_async(terminal_info: TerminalInfoDocument, cart_id: str = None) -> CartService:
    # ... 省略 ...

    # 🔴 問題: 各リクエストごとに新しいItemMasterGrpcRepositoryインスタンスを作成
    item_master_repo = create_item_master_repository(
        tenant_id=tenant_id,
        store_code=terminal_info.store_code,
        terminal_info=terminal_info,
    )

    return CartService(
        # ... item_master_repo を渡す ...
    )
```

**File:** `app/models/repositories/item_master_repository_factory.py:31-50`

```python
def create_item_master_repository(...) -> Union[ItemMasterWebRepository, ItemMasterGrpcRepository]:
    if cart_settings.USE_GRPC:
        # 🔴 問題: 毎回新しいインスタンス作成
        return ItemMasterGrpcRepository(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_info=terminal_info,
            item_master_documents=item_master_documents,
        )
```

### なぜチャネルプーリングが機能しなかったか

#### 設計上の誤り

**Phase 2の実装（インスタンスレベル）:**

```python
class ItemMasterGrpcRepository:
    def __init__(self, ...):
        # ✅ インスタンスレベルでチャネルを保持
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[item_service_pb2_grpc.ItemServiceStub] = None

    async def _get_stub(self):
        # ✅ 同じインスタンス内ではチャネル再利用
        if self._channel is None or self._stub is None:
            self._channel = await self.grpc_helper.get_channel()
            self._stub = item_service_pb2_grpc.ItemServiceStub(self._channel)
        return self._stub
```

**問題:**
- ✅ 同じインスタンス内ではチャネルが再利用される（ユニットテストでは正常動作）
- ❌ 各HTTPリクエストで新しいインスタンスが作成されるため、実運用では機能しない

#### リクエストフロー

```
HTTP Request 1
  ↓
FastAPI Dependency Injection: get_cart_service_async()
  ↓
__get_cart_service_async()
  ↓
create_item_master_repository()  ← 新しいインスタンス作成
  ↓
ItemMasterGrpcRepository instance #1 (新しいチャネル作成)
  ↓
Response


HTTP Request 2
  ↓
FastAPI Dependency Injection: get_cart_service_async()  ← 再度呼ばれる
  ↓
__get_cart_service_async()
  ↓
create_item_master_repository()  ← また新しいインスタンス作成
  ↓
ItemMasterGrpcRepository instance #2 (また新しいチャネル作成)  ← 前のインスタンスは破棄
  ↓
Response
```

**結論:** FastAPIの依存性注入により、各リクエストごとに新しいインスタンスが作成されるため、インスタンスレベルのチャネルプーリングでは不十分。

---

## 必要な修正

### Phase 1と同じアプローチを適用

**Phase 1の成功例（aiohttp Session Pooling）:**

**File:** `app/utils/dapr_statestore_session_helper.py`

```python
# ✅ モジュールレベルのセッション管理
_session: Optional[aiohttp.ClientSession] = None

async def get_dapr_statestore_session() -> aiohttp.ClientSession:
    """Get or create a shared aiohttp session."""
    global _session

    if _session is None or _session.closed:
        # 全リクエストで共有されるセッションを作成
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        logger.info("Created new aiohttp session for Dapr state store")

    return _session
```

**改善効果:**
- セッション作成回数: 366回 → **3回** (99.2%削減)
- セッション再利用率: **97.9%**

### Phase 2で必要な実装

同じパターンをgRPCチャネルにも適用：

**新規ファイル:** `app/utils/grpc_channel_helper.py` (作成予定)

```python
from typing import Optional, Dict, Tuple
import grpc
from kugel_common.grpc import item_service_pb2_grpc
from kugel_common.utils.grpc_client_helper import GrpcClientHelper
from app.config.settings_cart import cart_settings

# Module-level channel and stub cache (shared across all requests)
_channels: Dict[Tuple[str, str], grpc.aio.Channel] = {}
_stubs: Dict[Tuple[str, str], item_service_pb2_grpc.ItemServiceStub] = {}

async def get_master_data_grpc_stub(
    tenant_id: str,
    store_code: str
) -> item_service_pb2_grpc.ItemServiceStub:
    """
    Get or create a shared gRPC stub for master-data service.

    Stubs are cached per (tenant_id, store_code) combination.
    This eliminates 100-300ms channel creation overhead per request.
    """
    cache_key = (tenant_id, store_code)

    if cache_key not in _channels or cache_key not in _stubs:
        grpc_helper = GrpcClientHelper(
            target=cart_settings.MASTER_DATA_GRPC_URL,
            options=[
                ('grpc.max_send_message_length', 10 * 1024 * 1024),
                ('grpc.max_receive_message_length', 10 * 1024 * 1024),
            ]
        )

        _channels[cache_key] = await grpc_helper.get_channel()
        _stubs[cache_key] = item_service_pb2_grpc.ItemServiceStub(_channels[cache_key])

        logger.info(
            f"Created new gRPC channel for master-data service "
            f"(tenant={tenant_id}, store={store_code})"
        )

    return _stubs[cache_key]

async def close_master_data_grpc_channels() -> None:
    """Close all gRPC channels."""
    for cache_key, channel in _channels.items():
        try:
            await channel.close()
            logger.info(f"Closed gRPC channel for {cache_key}")
        except Exception as e:
            logger.warning(f"Error closing gRPC channel for {cache_key}: {e}")

    _channels.clear()
    _stubs.clear()
```

**変更ファイル:** `app/models/repositories/item_master_grpc_repository.py`

```python
# 既存のインスタンスレベルチャネル管理を削除し、ヘルパーを使用

from app.utils.grpc_channel_helper import get_master_data_grpc_stub

class ItemMasterGrpcRepository:
    def __init__(self, ...):
        self.tenant_id = tenant_id
        self.store_code = store_code
        # ... 省略 ...

        # ❌ 削除: インスタンスレベルチャネル
        # self._channel = None
        # self._stub = None

    async def get_item_by_code_async(self, item_code: str) -> ItemMasterDocument:
        # ... cache check ...

        try:
            # ✅ モジュールレベルの共有スタブを使用
            stub = await get_master_data_grpc_stub(self.tenant_id, self.store_code)

            request = item_service_pb2.ItemDetailRequest(...)
            response = await stub.GetItemDetail(request, timeout=cart_settings.GRPC_TIMEOUT)
            # ... rest of logic
```

**変更ファイル:** `app/main.py`

```python
async def close_event():
    """Shutdown event handler"""
    # ... existing code ...

    # Close gRPC channels
    logger.info("Closing gRPC channels")
    from app.utils.grpc_channel_helper import close_master_data_grpc_channels
    await close_master_data_grpc_channels()

    # ... existing code ...
```

---

## 期待される改善効果

### テスト結果予測（修正後）

**1 User Test (3分):**
- リクエスト数: 58
- 現在のチャネル作成回数: 86回
- **修正後の期待値: 1回** (99%削減)

**3 Users Test (3分):**
- リクエスト数: 168
- 現在のチャネル作成回数: 141回
- **修正後の期待値: 1回** (99%削減)
  - 注: 全ユーザーが同じtenant/storeのため、1つのチャネルを共有

### パフォーマンス改善予測

**1ユーザーテスト:**
- チャネル作成オーバーヘッド削減: 85回 × 100-300ms = **8.5-25.5秒削減**
- 99%ile予測: 340ms → **50-100ms** (さらに70-85%改善)

**3ユーザーテスト:**
- チャネル作成オーバーヘッド削減: 140回 × 100-300ms = **14-42秒削減**
- 99%ile予測: 2300ms → **400-600ms** (70-80%改善)

---

## ユニットテストが成功した理由

**tests/repositories/test_item_master_grpc_repository.py が全てパスした理由:**

```python
@pytest.mark.asyncio
async def test_get_stub_reuses_existing_channel(repository):
    """Test that _get_stub reuses existing channel (CORE FUNCTIONALITY)"""
    # ✅ 同じrepositoryインスタンスを2回呼び出し
    stub1 = await repository._get_stub()
    stub2 = await repository._get_stub()

    # ✅ インスタンス内では正しく再利用される
    assert stub1 is stub2  # PASSED
```

**ユニットテストと実運用の違い:**

| | ユニットテスト | 実運用 |
|---|--------------|--------|
| **リポジトリインスタンス** | 1個（同じインスタンスを再利用） | リクエストごとに新規作成 |
| **チャネル再利用** | ✅ 機能する（同じインスタンス内） | ❌ 機能しない（インスタンスが毎回新規） |
| **テスト結果** | ✅ PASSED（設計通り） | ❌ FAILED（アーキテクチャと不整合） |

**教訓:** ユニットテストだけでなく、実運用環境でのログ分析が重要

---

## 次のアクション

### 優先度1: 修正実装 ⭐⭐⭐

1. ✅ `app/utils/grpc_channel_helper.py` を作成
2. ✅ `item_master_grpc_repository.py` を修正
3. ✅ `main.py` のshutdown handlerを更新
4. ✅ ユニットテストを修正（モジュールレベルヘルパーのテスト）
5. ✅ 統合テスト実施

### 優先度2: 検証 ⭐⭐

1. ✅ 3分テストを再実行
2. ✅ ログでチャネル作成回数を確認（期待値: 1-3回）
3. ✅ パフォーマンス改善を測定

### 優先度3: 10分テスト ⭐

1. ✅ 修正後に10分テストを実施
2. ✅ Phase 0ベースラインとの比較
3. ✅ 最終レポート作成

---

## まとめ

### 発見事項

❌ **Phase 2実装は不完全:**
- インスタンスレベルのチャネルプーリングは、FastAPIの依存性注入と不整合
- 各リクエストで新しいインスタンスが作成されるため、チャネルが再利用されない
- ユニットテストは成功したが、実運用では機能しない

✅ **修正方針は明確:**
- Phase 1と同じモジュールレベルのアプローチを適用
- テナント/ストアごとにチャネルをキャッシュ
- 全リクエストで共有チャネルを使用

📊 **修正後の期待効果:**
- チャネル作成回数: 227回 → **1-3回** (98-99%削減)
- 99%ile latency: さらに70-85%改善の見込み

---

**分析完了日:** 2025-10-19
**ステータス:** 🔴 Phase 2修正が必要
**次のステップ:** モジュールレベルgRPCチャネルヘルパーの実装
