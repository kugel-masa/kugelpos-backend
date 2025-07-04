# フロントエンド開発者向けガイド

このガイドはKugelpos POSバックエンドAPIを利用してフロントエンドアプリケーションを開発するための手順と参考情報をまとめています。

## 目次
1. [システム概要](#システム概要)
2. [環境セットアップ](#環境セットアップ)
3. [認証と認可](#認証と認可)
4. [APIエンドポイント](#apiエンドポイント)
5. [データモデル](#データモデル)
6. [エラーハンドリング](#エラーハンドリング)
7. [開発フロー例](#開発フロー例)
8. [よくある問題とその解決方法](#よくある問題とその解決方法)

## システム概要

Kugelpos POSシステムは、マイクロサービスアーキテクチャに基づいて構築されています。主要なサービスと役割は以下の通りです：

- **Account Service (8000)**: ユーザー認証、トークン管理
- **Terminal Service (8001)**: 端末、店舗、テナント管理
- **Master-data Service (8002)**: 商品、支払い方法、スタッフなどのマスターデータ管理
- **Cart Service (8003)**: 買い物カート、取引処理
- **Report Service (8004)**: 売上レポート生成と取得
- **Journal Service (8005)**: 電子ジャーナル（取引履歴）管理
- **Stock Service (8006)**: 在庫管理とリアルタイムWebSocketアラート

各サービスは独立して動作し、REST APIを通じて通信します。サービス間の通信にはDaprを使用し、pub/subイベントとステート管理を行っています。

## 環境セットアップ

### 必要条件
- Node.js 18以上
- npm または yarn
- モダンなWebブラウザ（Chrome、Firefox、Edgeなど）

### APIサーバーへの接続設定

フロントエンド開発時は、以下のベースURLを使用してAPIにアクセスします：

**ローカル開発環境：**
```
http://localhost:8000/ - Account Service
http://localhost:8001/ - Terminal Service
http://localhost:8002/ - Master-data Service
http://localhost:8003/ - Cart Service
http://localhost:8004/ - Report Service
http://localhost:8005/ - Journal Service
http://localhost:8006/ - Stock Service
ws://localhost:8006/ - Stock Service (WebSocket)
```

**本番/テスト環境：**
```
https://{環境URL}/api/v1/...
```

### CORSに関する注意

バックエンドサービスはCORS（Cross-Origin Resource Sharing）を有効にしており、デフォルトですべてのオリジンからのリクエストを許可しています。本番環境では適切なオリジン制限が設定される場合があります。

## 認証と認可

### 認証フロー

1. **ログイン処理**:
```javascript
// ログイン例（fetch APIを使用）
const response = await fetch('http://localhost:8000/api/v1/accounts/token', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin',
    password: 'your_password'
  })
});

const data = await response.json();
const token = data.access_token;
// トークンをローカルストレージまたはセキュアクッキーに保存
localStorage.setItem('token', token);
```

2. **認証済みリクエスト**:
```javascript
// 認証が必要なAPIへのリクエスト例
const response = await fetch('http://localhost:8001/api/v1/terminals', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'Content-Type': 'application/json'
  }
});
```

3. **端末認証（API Key）**:
```javascript
// 端末認証が必要なAPIへのリクエスト例
const response = await fetch('http://localhost:8003/api/v1/carts?terminal_id=TENANT-STORE-TERMINAL', {
  method: 'POST',
  headers: {
    'X-API-KEY': 'your_api_key',
    'Content-Type': 'application/json'
  }
});
```

4. **WebSocket認証（Stockサービス）**:
```javascript
// JWTトークン認証を使用したWebSocket接続
const token = localStorage.getItem('token');
const ws = new WebSocket(`ws://localhost:8006/ws/TENANT_ID/STORE_CODE?token=${token}`);

ws.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  console.log('在庫アラートを受信:', alert);
};

ws.onerror = (error) => {
  console.error('WebSocketエラー:', error);
};
```

## APIエンドポイント

各サービスの主要なエンドポイントを以下に示します。完全なAPI仕様は各サービスの`/docs`エンドポイント（Swagger UI）で確認できます。

### Account Service

- `POST /api/v1/accounts/token` - ログイン認証、トークン取得
- `POST /api/v1/accounts/register` - スーパーユーザー登録＆新規テナント作成
- `POST /api/v1/accounts/register/user` - スーパーユーザーによる一般ユーザー登録

### Terminal Service

- `POST /api/v1/tenants` - テナント登録
- `POST /api/v1/tenants/{tenant_id}/stores` - 店舗登録
- `POST /api/v1/terminals` - 端末登録
- `POST /api/v1/terminals/{terminal_id}/sign-in` - 端末サインイン
- `POST /api/v1/terminals/{terminal_id}/open` - 端末オープン
- `POST /api/v1/terminals/{terminal_id}/close` - 端末締め

### Master-data Service

- `POST /api/v1/tenants/{tenant_id}/staffs` - スタッフ登録
- `GET /api/v1/tenants/{tenant_id}/staffs` - スタッフ一覧取得
- `POST /api/v1/tenants/{tenant_id}/items` - 商品登録
- `GET /api/v1/tenants/{tenant_id}/items` - 商品一覧取得

### Cart Service

- `POST /api/v1/carts?terminal_id={terminal_id}` - カート作成
- `POST /api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}` - 商品追加
- `POST /api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}` - 小計計算
- `POST /api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}` - 支払い追加
- `POST /api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}` - 会計処理完了

### Report Service

- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/reports/daily?business_date={date}` - 日次レポート取得

### Journal Service

- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/journals` - ジャーナル検索

### Stock Service

- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stocks` - 在庫一覧取得
- `POST /api/v1/tenants/{tenant_id}/stores/{store_code}/stocks/{item_code}` - 在庫作成/更新
- `PUT /api/v1/tenants/{tenant_id}/stores/{store_code}/stocks/{item_code}` - 在庫数量調整
- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stocks/{item_code}/snapshots` - 在庫スナップショット取得
- `WS /ws/{tenant_id}/{store_code}` - リアルタイム在庫アラート用WebSocketエンドポイント

## データモデル

主要なデータモデルとその構造は以下の通りです：

### 共通レスポンス形式

すべてのAPIレスポンスは以下の統一された形式で返されます：

```json
{
  "success": true|false,
  "code": 200|201|400|401|403|404|500,
  "message": "処理の説明メッセージ",
  "userError": {
    "code": "エラーコード",
    "message": "ユーザー向けエラーメッセージ"
  },
  "data": {
    // 実際のデータ（エンドポイントによって異なる）
  },
  "metadata": {
    // ページネーション情報など
  },
  "operation": "実行された操作の名前"
}
```

### 主要なモデル例

**テナント情報**:
```json
{
  "tenantId": "J5578",
  "tenantName": "サンプル企業",
  "tags": ["小売", "衣料"],
  "stores": [
    {
      "storeCode": "0001",
      "storeName": "銀座店",
      "status": "Active",
      "businessDate": "20250506",
      "tags": ["都心", "旗艦店"],
      "entryDatetime": "2025-05-01 10:00:00",
      "lastUpdateDatetime": "2025-05-06 15:30:00"
    }
  ],
  "entryDatetime": "2025-05-01 10:00:00",
  "lastUpdateDatetime": "2025-05-06 15:30:00"
}
```

**端末情報**:
```json
{
  "terminalId": "J5578-0001-01",
  "tenantId": "J5578",
  "storeCode": "0001",
  "terminalNo": 1,
  "description": "レジ1",
  "functionMode": "MainMenu",
  "status": "Idle",
  "businessDate": "20250506",
  "openCounter": 2,
  "businessCounter": 15,
  "initialAmount": 50000.0,
  "physicalAmount": 123000.0,
  "staff": {
    "staffId": "S001",
    "staffName": "山田太郎",
    "staffPin": "****"
  },
  "apiKey": "****",
  "entryDatetime": "2025-05-01 09:00:00",
  "lastUpdateDatetime": "2025-05-06 18:30:00"
}
```

**カート情報**:
```json
{
  "cartId": "550e8400-e29b-41d4-a716-446655440000",
  "tenantId": "J5578",
  "storeCode": "0001",
  "terminalNo": 1,
  "status": "InProgress",
  "lineItems": [
    {
      "lineNo": 1,
      "itemCode": "ITEM001",
      "description": "Tシャツ 白 L",
      "unitPrice": 2000.0,
      "quantity": 2,
      "amount": 4000.0,
      "taxCode": "01",
      "discounts": []
    }
  ],
  "subtotal": {
    "totalAmount": 4000.0,
    "totalAmountWithTax": 4400.0,
    "taxAmount": 400.0,
    "totalQuantity": 2
  },
  "payments": [],
  "taxes": [
    {
      "taxNo": 1,
      "taxCode": "01",
      "taxName": "消費税10%",
      "taxAmount": 400.0,
      "targetAmount": 4000.0,
      "targetQuantity": 2
    }
  ]
}
```

## エラーハンドリング

### エラーレスポンス形式

エラーが発生した場合も共通レスポンス形式でエラー情報が返されます。`success: false`となり、エラー詳細が含まれます。

```json
{
  "success": false,
  "code": 400,
  "message": "Invalid input data: tenant_id -> field required",
  "userError": {
    "code": "400001",
    "message": "入力データが不正です"
  },
  "data": null,
  "metadata": null,
  "operation": "validation_exception_handler"
}
```

### 主なエラーコード

- `400xxx`: 入力データエラー
- `401xxx`: 認証エラー
- `403xxx`: 権限エラー
- `404xxx`: リソース未発見
- `405xxx`: メソッド未対応
- `406xxx`: 処理受付不可
- `500xxx`: サーバー内部エラー

### フロントエンドでのエラーハンドリング例

```javascript
async function fetchData(url) {
  try {
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    });
    
    const result = await response.json();
    
    if (!result.success) {
      // エラーメッセージを表示
      showError(result.userError?.message || result.message);
      return null;
    }
    
    return result.data;
  } catch (error) {
    console.error('API通信エラー:', error);
    showError('サーバーとの通信に失敗しました。');
    return null;
  }
}
```

## 開発フロー例

以下は典型的なPOSアプリケーションの開発フローです：

1. **初期セットアップと認証**
   - ユーザーログイン画面の実装
   - トークン取得とストレージ

2. **マスターデータ設定**
   - テナント、店舗、端末の登録（管理者向け）
   - 商品、スタッフ、支払い方法の登録（管理者向け）

3. **店舗端末機能**
   - 端末サインイン、オープン処理
   - カート作成と商品登録
   - 支払い処理と取引完了
   - ジャーナル検索と返品処理
   - 締め処理とレポート出力

### 基本的なフローの実装例

**ステップ1: 端末サインインとオープン**
```javascript
// 1. 端末サインイン
async function signInTerminal(terminalId, staffId, staffPin) {
  const response = await fetch(`http://localhost:8001/api/v1/terminals/${terminalId}/sign-in`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ staff_id: staffId, pin: staffPin })
  });
  return await response.json();
}

// 2. 端末オープン
async function openTerminal(terminalId, initialAmount) {
  const response = await fetch(`http://localhost:8001/api/v1/terminals/${terminalId}/open`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ initial_amount: initialAmount })
  });
  return await response.json();
}
```

**ステップ2: 取引処理**
```javascript
// 1. カート作成
async function createCart(terminalId) {
  const response = await fetch(`http://localhost:8003/api/v1/carts?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    }
  });
  const result = await response.json();
  return result.data.cartId;
}

// 2. 商品追加
async function addItemToCart(cartId, terminalId, itemCode, quantity) {
  const response = await fetch(`http://localhost:8003/api/v1/carts/${cartId}/lineItems?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      item_code: itemCode,
      quantity: quantity
    })
  });
  return await response.json();
}

// 3. 小計計算
async function calculateSubtotal(cartId, terminalId) {
  const response = await fetch(`http://localhost:8003/api/v1/carts/${cartId}/subtotal?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    }
  });
  return await response.json();
}

// 4. 支払い追加
async function addPayment(cartId, terminalId, paymentCode, amount) {
  const response = await fetch(`http://localhost:8003/api/v1/carts/${cartId}/payments?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      payment_code: paymentCode,
      amount: amount
    })
  });
  return await response.json();
}

// 5. 会計処理完了
async function finalizeBill(cartId, terminalId) {
  const response = await fetch(`http://localhost:8003/api/v1/carts/${cartId}/bill?terminal_id=${terminalId}`, {
    method: 'POST',
    headers: {
      'X-API-KEY': localStorage.getItem('apiKey'),
      'Content-Type': 'application/json'
    }
  });
  return await response.json();
}
```

## リアルタイム機能（WebSocket）

Stockサービスは、WebSocket接続を通じてリアルタイムの在庫アラートを提供します。これにより、フロントエンドアプリケーションは在庫レベルと発注点に関する即時通知を受け取ることができます。

### WebSocket接続のセットアップ

```javascript
class StockAlertManager {
  constructor(tenantId, storeCode) {
    this.tenantId = tenantId;
    this.storeCode = storeCode;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // 1秒から開始
  }

  connect() {
    const token = localStorage.getItem('token');
    const wsUrl = `ws://localhost:8006/ws/${this.tenantId}/${this.storeCode}?token=${token}`;
    
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('在庫アラートに接続しました');
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
    };
    
    this.ws.onmessage = (event) => {
      const alert = JSON.parse(event.data);
      this.handleStockAlert(alert);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocketエラー:', error);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket接続が閉じられました');
      this.attemptReconnect();
    };
  }
  
  handleStockAlert(alert) {
    // アラートタイプ: 'low_stock', 'reorder_point', 'out_of_stock'
    switch(alert.type) {
      case 'low_stock':
        console.warn(`在庫不足アラート: ${alert.itemCode} - 残り${alert.currentQuantity}個`);
        break;
      case 'reorder_point':
        console.warn(`発注点到達: ${alert.itemCode} - 残り${alert.currentQuantity}個`);
        break;
      case 'out_of_stock':
        console.error(`在庫切れ: ${alert.itemCode}`);
        break;
    }
    
    // UIをアラート情報で更新
    this.displayAlert(alert);
  }
  
  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`再接続中... 試行 ${this.reconnectAttempts}`);
      
      setTimeout(() => {
        this.connect();
      }, this.reconnectDelay);
      
      // 指数バックオフ
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    } else {
      console.error('最大再接続試行回数に達しました');
    }
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// 使用例
const stockAlerts = new StockAlertManager('J5578', '0001');
stockAlerts.connect();
```

### 在庫アラートメッセージフォーマット

```json
{
  "type": "low_stock",  // 'low_stock', 'reorder_point', 'out_of_stock'
  "itemCode": "ITEM001",
  "itemName": "Tシャツ 白 L",
  "currentQuantity": 5,
  "minimumQuantity": 10,
  "reorderPoint": 20,
  "timestamp": "2025-01-26T10:30:00Z",
  "message": "在庫レベルが最小数量を下回りました"
}
```

### WebSocket処理のベストプラクティス

1. **認証**: 接続URLに必ずJWTトークンを含める
2. **再接続ロジック**: 再接続試行には指数バックオフを実装
3. **エラーハンドリング**: 接続障害を適切に処理し、オフライン状態を表示
4. **メッセージ検証**: 受信メッセージを処理前に検証
5. **リソースクリーンアップ**: コンポーネントのアンマウントやページ遷移時に接続を閉じる

## よくある問題とその解決方法

### 1. 認証エラー
**問題**: `401 Unauthorized`エラーが発生する
**解決策**: 
- トークンの有効期限が切れていないか確認
- 正しいAPIキーを使用しているか確認
- 再ログインを試みる

### 2. CORSエラー
**問題**: ブラウザコンソールにCORSエラーが表示される
**解決策**:
- バックエンドでCORS設定が正しいか確認
- 開発時はブラウザのCORS制限を一時的に無効にするプラグインの使用を検討

### 3. データ整合性エラー
**問題**: 取引処理中に`406 Not Acceptable`エラーが発生する
**解決策**:
- エラーメッセージを確認し、データの整合性問題（支払い金額不足など）を修正
- デバッグログを確認して問題を特定

### 4. パフォーマンス最適化
**問題**: 大量のデータ取得時にレスポンスが遅い
**解決策**:
- ページネーションパラメータ（limit, page）を適切に設定
- 必要なデータのみを取得するようにクエリを最適化

### 5. 接続エラー
**問題**: APIサーバーに接続できない
**解決策**:
- バックエンドサービスが実行中か確認
- ネットワーク設定やファイアウォールを確認
- 正しいURLとポートを使用しているか確認

### 6. WebSocket接続の問題
**問題**: WebSocketが接続できない、または頻繁に切断される
**解決策**:
- JWTトークンが有効で期限切れでないか確認
- ネットワークの安定性とファイアウォール設定を確認
- 指数バックオフによる適切な再接続ロジックを実装
- WebSocket接続状態を監視し、ユーザーに接続状態を表示

## ヘルスチェックエンドポイント

すべてのサービスは、サービスの可用性を監視するためのヘルスチェックエンドポイントを提供しています：

```javascript
// サービスのヘルスチェック
async function checkServiceHealth(serviceUrl) {
  try {
    const response = await fetch(`${serviceUrl}/health`);
    const health = await response.json();
    return health.status === 'healthy';
  } catch (error) {
    return false;
  }
}

// すべてのサービスを監視
async function monitorServices() {
  const services = [
    { name: 'Account', url: 'http://localhost:8000' },
    { name: 'Terminal', url: 'http://localhost:8001' },
    { name: 'Master-data', url: 'http://localhost:8002' },
    { name: 'Cart', url: 'http://localhost:8003' },
    { name: 'Report', url: 'http://localhost:8004' },
    { name: 'Journal', url: 'http://localhost:8005' },
    { name: 'Stock', url: 'http://localhost:8006' }
  ];
  
  for (const service of services) {
    const isHealthy = await checkServiceHealth(service.url);
    console.log(`${service.name}: ${isHealthy ? '正常' : '異常'}`);
  }
}
```

## サポートとリソース

- **APIドキュメント**: 各サービスの`/docs`エンドポイントでSwagger UIを利用可能
- **ヘルス監視**: 各サービスの`/health`エンドポイントでヘルスチェックを利用可能
- **サンプルコード**: `examples`ディレクトリにサンプル実装あり
- **問題報告**: バグや問題は課題管理システムにチケットを作成