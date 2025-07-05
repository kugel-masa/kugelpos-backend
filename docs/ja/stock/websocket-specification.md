# 在庫サービス WebSocket仕様

## 概要

在庫サービスのWebSocket機能は、在庫レベルの変化をリアルタイムで通知するシステムです。発注点や最小在庫数を下回った商品について、接続中のクライアントに即座にアラートを配信します。

## WebSocketエンドポイント

### 接続情報

**エンドポイント:** `WebSocket /api/v1/ws/{tenant_id}/{store_code}`

**実装場所:** `/services/stock/app/routers/websocket_router.py:21`

**認証:** JWT認証（クエリパラメータ経由）

**URL例:**
```
ws://localhost:8006/api/v1/ws/tenant001/STORE001?token={jwt_token}
```

## 認証メカニズム

### JWT認証
**実装場所:** `/services/stock/app/routers/websocket_router.py:29`

WebSocketプロトコルの制約により、認証トークンはクエリパラメータとして送信します：

```python
async def verify_jwt_from_query(token: str) -> Optional[User]:
    """クエリパラメータからJWTトークンを検証"""
```

**認証エラー:**
- コード: 1008 (Policy Violation)
- 理由: "No token provided", "Authentication failed", "Tenant ID mismatch"

## メッセージ形式

### 1. 接続確認メッセージ

接続確立時に送信されます：

```json
{
  "type": "connection",
  "status": "connected",
  "message": "WebSocket connected successfully"
}
```

### 2. 在庫アラート

#### 発注点アラート
```json
{
  "type": "stock_alert",
  "alert_type": "reorder_point",
  "tenant_id": "tenant001",
  "store_code": "STORE001",
  "item_code": "ITEM001",
  "current_quantity": 15.0,
  "reorder_point": 20.0,
  "reorder_quantity": 50.0,
  "timestamp": "2025-01-05T12:00:00Z"
}
```

#### 最小在庫アラート
```json
{
  "type": "stock_alert",
  "alert_type": "minimum_stock",
  "tenant_id": "tenant001",
  "store_code": "STORE001",
  "item_code": "ITEM002",
  "current_quantity": 8.0,
  "minimum_quantity": 10.0,
  "reorder_quantity": 30.0,
  "timestamp": "2025-01-05T12:00:00Z"
}
```

### 3. Ping/Pongメッセージ

接続維持のためのハートビート：
- クライアント送信: `"ping"`
- サーバー応答: `"pong"`

## 接続管理

### ConnectionManager

**実装場所:** `/services/stock/app/services/websocket/connection_manager.py`

```python
class ConnectionManager:
    """WebSocket接続を管理するマネージャー"""
    
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        self._lock = asyncio.Lock()
```

**主要メソッド:**
- `connect()`: 新規接続を登録
- `disconnect()`: 接続を削除
- `send_to_store()`: 特定店舗の全接続に送信
- `broadcast_to_tenant()`: テナントの全店舗に送信
- `get_connection_count()`: 接続数を取得

**階層構造:**
```
{tenant_id: {store_code: set(websockets)}}
```

## アラートサービス

### AlertService

**実装場所:** `/services/stock/app/services/websocket/alert_service.py`

**主要機能:**

1. **アラート判定ロジック**
   ```python
   async def check_and_send_alerts(
       self,
       tenant_id: str,
       store_code: str,
       item: StockItemDocument
   )
   ```

2. **アラートタイプ**
   - `reorder_point`: 在庫数 ≤ 発注点
   - `minimum_stock`: 在庫数 < 最小在庫

3. **クールダウン機能**
   - デフォルト: 60秒
   - 環境変数: `ALERT_COOLDOWN_SECONDS`
   - キー形式: `{alert_type}_{tenant_id}_{store_code}_{item_code}`

### クールダウン実装

**実装場所:** `/services/stock/app/repositories/alert_cooldown_repository.py`

```python
class AlertCooldownRepository:
    """アラートクールダウンを管理するリポジトリ"""
    
    async def is_in_cooldown(
        self,
        alert_type: str,
        tenant_id: str,
        store_code: str,
        item_code: str
    ) -> bool
```

**クリーンアップ:**
- 10分ごとにバックグラウンドタスクで古いレコードを削除
- 実装: `/services/stock/app/services/websocket/alert_service.py:60`

## 統合ポイント

### 1. 在庫更新時のトリガー

**実装場所:** `/services/stock/app/services/stock_service.py:239`

```python
# 在庫更新後にアラートチェック
await self.alert_service.check_and_send_alerts(
    tenant_id=tenant_id,
    store_code=store_code,
    item=updated_item
)
```

### 2. トランザクション処理時

**実装場所:** `/services/stock/app/services/transaction_handler.py:100`

トランザクションログ処理後、在庫変更がある場合にアラートチェック

## パフォーマンス特性

1. **接続管理**
   - 階層的データ構造による効率的な接続管理
   - 非同期ロックによる同時実行制御

2. **メッセージ配信**
   - ストア単位での一括送信
   - 非同期処理による並列配信

3. **クールダウン**
   - インメモリキャッシュによる高速判定
   - 定期的なクリーンアップで肥大化防止

## セキュリティ

1. **認証**
   - JWT検証必須
   - テナントIDの一致確認

2. **データ分離**
   - テナント・店舗レベルでの厳密な分離
   - 他テナントのデータへのアクセス不可

3. **接続制限**
   - 認証失敗時の即座な切断
   - 不正なメッセージの無視

## エラー処理

### WebSocket接続エラー

| コード | 説明 | 対処 |
|--------|------|------|
| 1008 | ポリシー違反（認証失敗） | トークン再取得 |
| 1006 | 異常切断 | 再接続実装推奨 |
| 1000 | 正常終了 | 必要に応じて再接続 |

### メッセージ送信エラー

送信失敗時は個別接続をクローズし、接続プールから削除

## 制限事項

1. **スケーラビリティ**
   - 単一サーバーインスタンス内での接続管理
   - 水平スケーリングには外部メッセージブローカーが必要

2. **メッセージ保証**
   - At-most-once配信（再送なし）
   - 接続断時のメッセージ欠落の可能性

3. **リソース制限**
   - 接続数はシステムリソースに依存
   - 大量接続時のメモリ使用量に注意