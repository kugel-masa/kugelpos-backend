# Stock Service WebSocket仕様書

## 概要

Stock ServiceのWebSocket機能は、在庫レベルの変化をリアルタイムで通知するためのリアルタイム通信システムです。発注点や最小在庫数を下回った商品について、接続中のクライアントに即座にアラートを配信します。

## WebSocket エンドポイント

### 基本情報
- **エンドポイント**: `/api/v1/ws/{tenant_id}/{store_code}`
- **プロトコル**: WebSocket (ws://, wss://)
- **認証**: JWT トークンをクエリパラメータで送信

### 完全なURL例
```
ws://localhost:8006/api/v1/ws/tenant001/store001?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 認証システム

### JWT トークン認証
WebSocketプロトコルの制約により、認証はクエリパラメータを使用します：

```javascript
const token = 'your_jwt_token_here';
const wsUrl = `ws://localhost:8006/api/v1/ws/${tenantId}/${storeCode}?token=${token}`;
const websocket = new WebSocket(wsUrl);
```

### 認証エラー
認証に失敗した場合、WebSocket接続は以下のコードで閉じられます：
- **コード**: 1008 (Policy Violation)
- **理由**: "No token provided" または "Authentication failed"

## メッセージ形式

### 1. 接続確認メッセージ
WebSocket接続が確立されると送信されます：

```json
{
  "type": "connection",
  "status": "connected",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

### 2. 発注点アラート
在庫が発注点を下回った場合に送信されます：

```json
{
  "type": "stock_alert",
  "alert_type": "reorder_point",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "item_code": "ITEM001",
  "current_quantity": 40.0,
  "reorder_point": 50.0,
  "reorder_quantity": 100.0,
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

### 3. 最小在庫アラート
在庫が最小在庫数を下回った場合に送信されます：

```json
{
  "type": "stock_alert",
  "alert_type": "minimum_stock",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "item_code": "ITEM002",
  "current_quantity": 5.0,
  "minimum_quantity": 10.0,
  "reorder_quantity": 50.0,
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

## アラート制御システム

### アラートクールダウン
同一商品の重複アラートを防止するため、クールダウン機能を実装：

- **設定項目**: 環境変数 `ALERT_COOLDOWN_SECONDS`
- **デフォルト値**: 60秒
- **テスト環境**: 0秒に設定可能
- **対象**: 同一商品（tenant_id + store_code + item_code）の同一アラートタイプ

### アラート配信条件
アラートは以下の条件を満たした場合にのみ配信されます：

1. **在庫更新時**: 在庫数量が変更された時点で評価
2. **閾値判定**: 
   - 発注点アラート: `current_quantity <= reorder_point` かつ `reorder_point > 0`
   - 最小在庫アラート: `current_quantity < minimum_quantity` かつ `minimum_quantity > 0`
3. **クールダウン条件**: 最後のアラートから設定時間が経過

## 接続管理

### ConnectionManager
WebSocket接続は ConnectionManager クラスで管理されます：

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, tenant_id: str, store_code: str)
    async def disconnect(self, websocket: WebSocket, tenant_id: str, store_code: str)
    async def send_to_store(self, tenant_id: str, store_code: str, message: str)
```

### 接続ライフサイクル
1. **接続確立**: JWT認証後、接続プールに追加
2. **メッセージ配信**: 在庫更新時にアラート評価・配信
3. **接続終了**: 自動的に接続プールから削除

### 複数クライアント対応
- 同一テナント・店舗に対して複数のWebSocket接続が可能
- アラートは接続中のすべてのクライアントに同時配信
- 各接続は独立して管理され、1つの接続が切断されても他に影響なし

## 実装例

### JavaScript/TypeScript クライアント

#### 基本接続
```javascript
class StockAlertClient {
    constructor(tenantId, storeCode, token) {
        this.tenantId = tenantId;
        this.storeCode = storeCode;
        this.token = token;
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    connect() {
        const wsUrl = `ws://localhost:8006/api/v1/ws/${this.tenantId}/${this.storeCode}?token=${this.token}`;
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = (event) => {
            console.log('WebSocket接続が確立されました');
            this.reconnectAttempts = 0;
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.websocket.onclose = (event) => {
            if (event.code === 1008) {
                console.error('認証エラー:', event.reason);
                // 認証エラーの場合は再接続しない
                return;
            }
            
            console.log('WebSocket接続が閉じられました');
            this.attemptReconnect();
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocketエラー:', error);
        };
    }

    handleMessage(data) {
        switch (data.type) {
            case 'connection':
                console.log('接続確認:', data.status);
                break;
            case 'stock_alert':
                this.handleStockAlert(data);
                break;
            default:
                console.log('未知のメッセージタイプ:', data.type);
        }
    }

    handleStockAlert(alert) {
        const message = this.formatAlertMessage(alert);
        
        // ブラウザ通知
        if (Notification.permission === 'granted') {
            new Notification('在庫アラート', {
                body: message,
                icon: '/icons/alert.png'
            });
        }
        
        // UI更新
        this.updateUI(alert);
        
        // ログ出力
        console.log('在庫アラート受信:', alert);
    }

    formatAlertMessage(alert) {
        if (alert.alert_type === 'reorder_point') {
            return `${alert.item_code}: 発注点を下回りました (現在: ${alert.current_quantity})`;
        } else if (alert.alert_type === 'minimum_stock') {
            return `${alert.item_code}: 最小在庫を下回りました (現在: ${alert.current_quantity})`;
        }
        return `${alert.item_code}: 在庫アラート`;
    }

    updateUI(alert) {
        // DOM操作でアラート表示
        const alertElement = document.createElement('div');
        alertElement.className = 'alert alert-warning';
        alertElement.textContent = this.formatAlertMessage(alert);
        
        const container = document.getElementById('alerts-container');
        if (container) {
            container.prepend(alertElement);
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            
            console.log(`${delay}ms後に再接続を試行します (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            console.error('最大再接続試行回数に達しました');
        }
    }

    disconnect() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
    }
}

// 使用例
const client = new StockAlertClient('tenant001', 'store001', 'your_jwt_token');
client.connect();
```

#### React フック
```javascript
import { useEffect, useState, useRef } from 'react';

export function useStockAlerts(tenantId, storeCode, token) {
    const [alerts, setAlerts] = useState([]);
    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    const websocketRef = useRef(null);

    useEffect(() => {
        if (!tenantId || !storeCode || !token) return;

        const wsUrl = `ws://localhost:8006/api/v1/ws/${tenantId}/${storeCode}?token=${token}`;
        const websocket = new WebSocket(wsUrl);
        websocketRef.current = websocket;

        websocket.onopen = () => {
            setConnectionStatus('connected');
        };

        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'stock_alert') {
                setAlerts(prev => [data, ...prev.slice(0, 99)]); // 最新100件まで保持
            }
        };

        websocket.onclose = (event) => {
            setConnectionStatus('disconnected');
            
            if (event.code === 1008) {
                console.error('認証エラー:', event.reason);
            }
        };

        websocket.onerror = () => {
            setConnectionStatus('error');
        };

        return () => {
            websocket.close();
        };
    }, [tenantId, storeCode, token]);

    const clearAlerts = () => {
        setAlerts([]);
    };

    return {
        alerts,
        connectionStatus,
        clearAlerts
    };
}

// 使用例
function StockDashboard() {
    const { alerts, connectionStatus } = useStockAlerts('tenant001', 'store001', userToken);

    return (
        <div>
            <div className={`connection-status ${connectionStatus}`}>
                接続状態: {connectionStatus}
            </div>
            
            <div className="alerts-container">
                {alerts.map((alert, index) => (
                    <div key={index} className={`alert alert-${alert.alert_type}`}>
                        <strong>{alert.item_code}</strong>: {alert.alert_type === 'reorder_point' ? '発注点' : '最小在庫'}を下回りました
                        <br />
                        現在数量: {alert.current_quantity}
                        <br />
                        <small>{new Date(alert.timestamp).toLocaleString()}</small>
                    </div>
                ))}
            </div>
        </div>
    );
}
```

### Python クライアント
```python
import asyncio
import json
import websockets
from typing import Callable, Optional

class StockAlertClient:
    def __init__(self, tenant_id: str, store_code: str, token: str, 
                 base_url: str = "ws://localhost:8006"):
        self.tenant_id = tenant_id
        self.store_code = store_code
        self.token = token
        self.ws_url = f"{base_url}/api/v1/ws/{tenant_id}/{store_code}?token={token}"
        self.websocket = None
        self.alert_handlers = []

    def add_alert_handler(self, handler: Callable[[dict], None]):
        """アラートハンドラーを追加"""
        self.alert_handlers.append(handler)

    async def connect(self):
        """WebSocket接続を確立"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            print(f"WebSocket接続が確立されました: {self.tenant_id}/{self.store_code}")
            
            # メッセージ受信ループを開始
            await self._listen_for_messages()
            
        except websockets.exceptions.ConnectionClosedError as e:
            if e.code == 1008:
                print(f"認証エラー: {e.reason}")
            else:
                print(f"接続エラー: {e}")
        except Exception as e:
            print(f"予期しないエラー: {e}")

    async def _listen_for_messages(self):
        """メッセージ受信ループ"""
        async for message in self.websocket:
            try:
                data = json.loads(message)
                await self._handle_message(data)
            except json.JSONDecodeError:
                print(f"無効なJSONメッセージ: {message}")
            except Exception as e:
                print(f"メッセージ処理エラー: {e}")

    async def _handle_message(self, data: dict):
        """受信メッセージの処理"""
        if data.get("type") == "connection":
            print(f"接続確認: {data.get('status')}")
        elif data.get("type") == "stock_alert":
            for handler in self.alert_handlers:
                try:
                    handler(data)
                except Exception as e:
                    print(f"アラートハンドラーエラー: {e}")

    async def disconnect(self):
        """WebSocket接続を切断"""
        if self.websocket:
            await self.websocket.close()
            print("WebSocket接続を切断しました")

# 使用例
async def handle_stock_alert(alert_data):
    """在庫アラートの処理"""
    alert_type = "発注点" if alert_data["alert_type"] == "reorder_point" else "最小在庫"
    print(f"🚨 {alert_data['item_code']}: {alert_type}アラート")
    print(f"   現在数量: {alert_data['current_quantity']}")
    
    # データベースへの記録、メール送信など
    # await save_alert_to_database(alert_data)
    # await send_email_notification(alert_data)

async def main():
    client = StockAlertClient(
        tenant_id="tenant001",
        store_code="store001", 
        token="your_jwt_token"
    )
    
    client.add_alert_handler(handle_stock_alert)
    
    try:
        await client.connect()
    except KeyboardInterrupt:
        print("手動で停止されました")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## エラーハンドリング

### 接続エラー
| エラーコード | 理由 | 対処方法 |
|------------|------|----------|
| 1008 | 認証失敗 | JWTトークンを確認し、再取得 |
| 1006 | 異常切断 | 自動再接続を実装 |
| 1000 | 正常切断 | 必要に応じて再接続 |

### 再接続戦略
```javascript
class ReconnectManager {
    constructor(maxAttempts = 5, baseDelay = 1000) {
        this.maxAttempts = maxAttempts;
        this.baseDelay = baseDelay;
        this.attempts = 0;
    }

    async attempt(connectFunction) {
        while (this.attempts < this.maxAttempts) {
            try {
                await connectFunction();
                this.attempts = 0; // 成功時はリセット
                return;
            } catch (error) {
                this.attempts++;
                
                if (this.attempts >= this.maxAttempts) {
                    throw new Error('最大再接続試行回数に達しました');
                }
                
                const delay = Math.min(
                    this.baseDelay * Math.pow(2, this.attempts), 
                    30000
                );
                
                console.log(`${delay}ms後に再接続を試行します`);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }
}
```

## パフォーマンス特性

### システム制限
- **最大同時接続数**: システムリソースによる制限（実装上の制限なし）
- **メッセージレート**: アラート発生時のみ送信（低頻度）
- **メモリ使用量**: 接続数 × 約1KB（接続管理オーバーヘッド）
- **CPU使用量**: アラート評価時とメッセージ配信時のみ増加

### ネットワーク要件
- **帯域幅**: 1接続あたり約10-50 bytes/alert（JSON圧縮時）
- **レイテンシ**: 通常 < 100ms（在庫更新からアラート配信まで）
- **ハートビート**: WebSocketプロトコルのpingを使用

## セキュリティ考慮事項

### 認証・認可
- JWT トークンによる認証（有効期限チェック含む）
- テナント・店舗レベルでのアクセス制御
- 不正なアクセス試行の検出とログ記録

### データ保護
- センシティブな在庫データの暗号化伝送
- アラート内容の最小化（必要な情報のみ送信）
- ログへの個人情報記録の回避

### DoS攻撃対策
- 接続レート制限（将来実装予定）
- アラートクールダウンによるスパム防止
- リソース監視とアラート

## 監視・運用

### メトリクス
- アクティブWebSocket接続数
- アラート配信数（タイプ別、時間別）
- 接続エラー率
- 平均応答時間

### ログ
```json
{
  "timestamp": "2024-01-01T12:34:56.789Z",
  "level": "INFO",
  "event": "websocket_alert_sent",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "item_code": "ITEM001",
  "alert_type": "reorder_point",
  "connection_count": 3
}
```

### アラート
- WebSocket接続数の急激な増加
- アラート配信失敗率の上昇
- 異常な切断パターンの検出

この仕様書により、Stock ServiceのWebSocket機能を効果的に理解し、実装することができます。