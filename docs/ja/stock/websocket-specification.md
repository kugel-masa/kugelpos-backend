# 在庫サービス WebSocket仕様

## 概要

在庫サービスのWebSocket機能は、在庫レベルの変化をリアルタイムで通知するシステムです。発注点や最小在庫数を下回った商品について、接続中のクライアントに即座にアラートを配信します。

## WebSocketエンドポイント

### 接続情報

**エンドポイント:** `WebSocket /ws/{tenant_id}/{store_code}`

**実装場所:** `/services/stock/app/api/v1/stock.py:996`

**認証:** JWT認証（クエリパラメータ経由）

**URL例:**
```
ws://localhost:8006/ws/tenant001/STORE001?token={jwt_token}
```

## 認証メカニズム

### JWT認証
**実装場所:** `/services/stock/app/api/v1/stock.py:1028`

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
  "tenant_id": "tenant001",
  "store_code": "STORE001",
  "message": "Connected to stock alert service"
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

**実装場所:** `/services/stock/app/websocket/connection_manager.py`

```python
class ConnectionManager:
    """WebSocket接続を管理するマネージャー"""

    def __init__(self):
        # Structure: {tenant_id: {store_code: set(websocket_connections)}}
        self._connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
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

**実装場所:** `/services/stock/app/services/alert_service.py`

**主要機能:**

1. **アラート判定ロジック**
   ```python
   async def check_and_send_alerts(self, stock: StockDocument) -> None:
       """Check stock levels and send alerts if necessary"""
   ```

2. **アラートタイプ**
   - `reorder_point`: 在庫数 ≤ 発注点（reorder_point > 0 の場合のみ）
   - `minimum_stock`: 在庫数 < 最小在庫（minimum_quantity > 0 の場合のみ）

3. **クールダウン機能**
   - デフォルト: 60秒
   - 環境変数: `ALERT_COOLDOWN_SECONDS`
   - キー形式: `{alert_type}_{tenant_id}_{store_code}_{item_code}`

### クールダウン実装

AlertService内でインメモリ辞書（`recent_alerts`）を使用して管理されます。

```python
class AlertService:
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.alert_cooldown = settings.ALERT_COOLDOWN_SECONDS
        self.recent_alerts: Dict[str, datetime] = {}  # Track recent alerts
        self._cleanup_task = None

    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if we should send an alert based on cooldown"""
```

**クリーンアップ:**
- 10分ごとにバックグラウンドタスク（`_cleanup_old_alerts`）で古いレコードを削除
- 実装: `/services/stock/app/services/alert_service.py:38`

## 統合ポイント

### 1. 在庫更新時のトリガー

**実装場所:** `/services/stock/app/services/stock_service.py:96`

```python
# Check for alerts if alert service is available
if self._alert_service:
    await self._alert_service.check_and_send_alerts(updated_stock)
```

### 2. WebSocket接続確立時

**実装場所:** `/services/stock/app/api/v1/stock.py:1079`

WebSocket接続確立時に現在のアラート状態を送信:
- 発注点以下の在庫アラート
- 最小在庫以下の在庫アラート

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