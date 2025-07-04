# Stock Service API仕様書

## 概要

Stock Serviceは、Kugelpos POSシステムにおける在庫追跡と在庫レベルを管理します。在庫照会、更新、履歴追跡、スナップショット管理、発注管理、およびリアルタイムWebSocketアラートのためのエンドポイントを提供します。

## ベースURL
- ローカル環境: `http://localhost:8006`
- 本番環境: `https://stock.{domain}`

## 認証

Stock Serviceは2つの認証方式をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダーに含める: `Authorization: Bearer {token}`
- トークンの取得先: Account Service の `/api/v1/accounts/token`
- 管理操作に必要

### 2. APIキー認証
- ヘッダーに含める: `X-API-Key: {api_key}`
- クエリパラメータを含める: `terminal_id={tenant_id}_{store_code}_{terminal_no}`
- POS端末操作で使用

## フィールド形式

すべてのAPIリクエストとレスポンスは**camelCase**のフィールド命名規則を使用します。サービスは`BaseSchemaModel`とトランスフォーマーを使用して、内部のsnake_caseと外部のcamelCase形式を自動的に変換します。

## 共通レスポンス形式

すべてのエンドポイントは以下の形式でレスポンスを返します：

```json
{
  "success": true,
  "code": 200,
  "message": "操作が成功しました",
  "data": { ... },
  "operation": "function_name"
}
```

## 列挙型

### UpdateType（更新タイプ）
在庫変更を追跡するための在庫更新タイプ：
- `sale` - 商品販売
- `return` - 顧客による返品
- `void` - 販売取消
- `void_return` - 返品取消
- `purchase` - 在庫仕入/受領
- `adjustment` - 手動調整
- `initial` - 初期在庫設定
- `damage` - 破損在庫
- `transfer_in` - 在庫移動入庫
- `transfer_out` - 在庫移動出庫

## APIエンドポイント

### 1. 店舗の在庫リスト取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock`

店舗のすべての在庫商品をページネーション付きで取得します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID
  - `skip` (integer, デフォルト: 0): スキップする項目数
  - `limit` (integer, デフォルト: 100, 最大: 1000): 返す最大項目数

**リクエスト例:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock?skip=0&limit=50" \
  -H "Authorization: Bearer {token}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "在庫リストの取得に成功しました",
  "data": {
    "items": [
      {
        "id": "507f1f77bcf86cd799439011",
        "tenantId": "tenant001",
        "storeCode": "store001",
        "itemCode": "ITEM001",
        "currentQuantity": 150.0,
        "minimumQuantity": 20.0,
        "reorderPoint": 50.0,
        "reorderQuantity": 100.0,
        "lastUpdated": "2024-01-01T10:30:00Z",
        "lastTransactionId": "TRX001"
      }
    ],
    "total": 100,
    "skip": 0,
    "limit": 50
  },
  "operation": "get_store_stocks"
}
```

### 2. 低在庫商品の取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/low`

最小数量を下回る在庫の商品を取得します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID

**リクエスト例:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/low" \
  -H "Authorization: Bearer {token}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "低在庫商品の取得に成功しました",
  "data": {
    "items": [
      {
        "id": "507f1f77bcf86cd799439012",
        "tenantId": "tenant001",
        "storeCode": "store001",
        "itemCode": "ITEM002",
        "currentQuantity": 5.0,
        "minimumQuantity": 20.0,
        "reorderPoint": 30.0,
        "reorderQuantity": 50.0,
        "lastUpdated": "2024-01-01T10:30:00Z",
        "lastTransactionId": "TRX002"
      }
    ],
    "total": 3,
    "skip": 0,
    "limit": 3
  },
  "operation": "get_low_stocks"
}
```

### 3. 商品の在庫取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}`

特定商品の現在の在庫情報を取得します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
  - `item_code` (string, 必須): 商品コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID

**リクエスト例:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001" \
  -H "Authorization: Bearer {token}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "在庫の取得に成功しました",
  "data": {
    "id": "507f1f77bcf86cd799439011",
    "tenantId": "tenant001",
    "storeCode": "store001",
    "itemCode": "ITEM001",
    "currentQuantity": 150.0,
    "minimumQuantity": 20.0,
    "reorderPoint": 50.0,
    "reorderQuantity": 100.0,
    "lastUpdated": "2024-01-01T10:30:00Z",
    "lastTransactionId": "TRX001"
  },
  "operation": "get_stock"
}
```

### 4. 在庫数量の更新
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update`

商品の在庫数量を更新し、更新を記録します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
  - `item_code` (string, 必須): 商品コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID

**リクエストボディ:**
```json
{
  "quantityChange": -2.0,
  "updateType": "sale",
  "referenceId": "TRX001",
  "operatorId": "user001",
  "note": "販売トランザクション"
}
```

**フィールド説明:**
- `quantityChange` (number, 必須): 数量変更値（正の値で増加、負の値で減少）
- `updateType` (string, 必須): 更新タイプ（列挙型参照）
- `referenceId` (string, オプション): 参照ID（トランザクションIDなど）
- `operatorId` (string, オプション): 操作者ID
- `note` (string, オプション): 備考

**リクエスト例:**
```bash
curl -X PUT "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001/update" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "quantityChange": -2.0,
    "updateType": "sale",
    "referenceId": "TRX001",
    "note": "販売トランザクション"
  }'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "在庫の更新に成功しました",
  "data": {
    "id": "507f1f77bcf86cd799439013",
    "tenantId": "tenant001",
    "storeCode": "store001",
    "itemCode": "ITEM001",
    "updateType": "sale",
    "quantityChange": -2.0,
    "beforeQuantity": 150.0,
    "afterQuantity": 148.0,
    "referenceId": "TRX001",
    "timestamp": "2024-01-01T10:35:00Z",
    "operatorId": "user001",
    "note": "販売トランザクション"
  },
  "operation": "update_stock"
}
```

### 5. 在庫更新履歴の取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/history`

商品の在庫更新履歴を取得します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
  - `item_code` (string, 必須): 商品コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID
  - `skip` (integer, デフォルト: 0): スキップする項目数
  - `limit` (integer, デフォルト: 100, 最大: 1000): 返す最大項目数

**リクエスト例:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001/history?skip=0&limit=20" \
  -H "Authorization: Bearer {token}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "在庫履歴の取得に成功しました",
  "data": {
    "items": [
      {
        "id": "507f1f77bcf86cd799439013",
        "tenantId": "tenant001",
        "storeCode": "store001",
        "itemCode": "ITEM001",
        "updateType": "sale",
        "quantityChange": -2.0,
        "beforeQuantity": 150.0,
        "afterQuantity": 148.0,
        "referenceId": "TRX001",
        "timestamp": "2024-01-01T10:35:00Z",
        "operatorId": "user001",
        "note": "販売トランザクション"
      }
    ],
    "total": 50,
    "skip": 0,
    "limit": 20
  },
  "operation": "get_stock_history"
}
```

### 6. 発注アラート商品の取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/reorder-alerts`

発注点を下回った商品の一覧を取得します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID

**リクエスト例:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/reorder-alerts" \
  -H "Authorization: Bearer {token}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "発注アラート商品の取得に成功しました",
  "data": {
    "data": [
      {
        "tenantId": "tenant001",
        "storeCode": "store001",
        "itemCode": "ITEM003",
        "currentQuantity": 15.0,
        "minimumQuantity": 10.0,
        "reorderPoint": 20.0,
        "reorderQuantity": 50.0,
        "lastUpdated": "2024-01-01T10:30:00Z"
      }
    ],
    "metadata": {
      "total": 1,
      "page": 1,
      "limit": 1,
      "sort": null,
      "filter": null
    }
  },
  "operation": "get_reorder_alerts"
}
```

### 7. 最小在庫数量の設定
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/minimum`

アラート用の最小在庫数量を設定します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
  - `item_code` (string, 必須): 商品コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID

**リクエストボディ:**
```json
{
  "minimumQuantity": 25.0
}
```

**リクエスト例:**
```bash
curl -X PUT "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001/minimum" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"minimumQuantity": 25.0}'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "最小数量の設定に成功しました",
  "data": null,
  "operation": "set_minimum_quantity"
}
```

### 8. 発注パラメータの設定
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/reorder`

商品の発注点と発注数量を設定します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
  - `item_code` (string, 必須): 商品コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID

**リクエストボディ:**
```json
{
  "reorderPoint": 50.0,
  "reorderQuantity": 100.0
}
```

**フィールド説明:**
- `reorderPoint` (number, 必須): 発注点（この数量を下回ると発注アラートが発生）
- `reorderQuantity` (number, 必須): 発注数量（発注時の推奨数量）

**リクエスト例:**
```bash
curl -X PUT "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001/reorder" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "reorderPoint": 50.0,
    "reorderQuantity": 100.0
  }'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "発注パラメータの設定に成功しました",
  "data": null,
  "operation": "set_reorder_parameters"
}
```

### 9. 在庫スナップショットの作成
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

現在の在庫レベルのスナップショットを作成します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID

**リクエストボディ:**
```json
{
  "createdBy": "user001"
}
```

**リクエスト例:**
```bash
curl -X POST "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/snapshot" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"createdBy": "user001"}'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "スナップショットの作成に成功しました",
  "data": {
    "id": "507f1f77bcf86cd799439014",
    "tenantId": "tenant001",
    "storeCode": "store001",
    "totalItems": 150,
    "totalQuantity": 5250.0,
    "stocks": [
      {
        "itemCode": "ITEM001",
        "quantity": 148.0,
        "minimumQuantity": 25.0,
        "reorderPoint": 50.0,
        "reorderQuantity": 100.0
      },
      {
        "itemCode": "ITEM002",
        "quantity": 5.0,
        "minimumQuantity": 20.0,
        "reorderPoint": 30.0,
        "reorderQuantity": 50.0
      }
    ],
    "createdBy": "user001",
    "createdAt": "2024-01-01T11:00:00Z",
    "updatedAt": null
  },
  "operation": "create_snapshot"
}
```

### 10. 在庫スナップショットの一覧取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

店舗の在庫スナップショットの一覧を取得します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID
  - `skip` (integer, デフォルト: 0): スキップする項目数
  - `limit` (integer, デフォルト: 20, 最大: 100): 返す最大項目数

**リクエスト例:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/snapshot?skip=0&limit=10" \
  -H "Authorization: Bearer {token}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "スナップショットの取得に成功しました",
  "data": {
    "items": [
      {
        "id": "507f1f77bcf86cd799439014",
        "tenantId": "tenant001",
        "storeCode": "store001",
        "totalItems": 150,
        "totalQuantity": 5250.0,
        "stocks": [...],
        "createdBy": "user001",
        "createdAt": "2024-01-01T11:00:00Z",
        "updatedAt": null
      }
    ],
    "total": 5,
    "skip": 0,
    "limit": 10
  },
  "operation": "get_snapshots"
}
```

### 11. IDによる在庫スナップショットの取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}`

特定のIDで在庫スナップショットを取得します。

**パラメータ:**
- パス:
  - `tenant_id` (string, 必須): テナント識別子
  - `store_code` (string, 必須): 店舗コード
  - `snapshot_id` (string, 必須): スナップショットID
- クエリ:
  - `terminal_id` (string, オプション): APIキー認証用の端末ID

**リクエスト例:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/snapshot/507f1f77bcf86cd799439014" \
  -H "Authorization: Bearer {token}"
```

### 12. テナントの作成
**POST** `/api/v1/tenants`

新しいテナント用に在庫サービスを初期化します（JWT認証が必要）。

**リクエストボディ:**
```json
{
  "tenantId": "tenant001"
}
```

**リクエスト例:**
```bash
curl -X POST "http://localhost:8006/api/v1/tenants" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"tenantId": "tenant001"}'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "テナントの作成が完了しました: tenant001",
  "data": {
    "tenantId": "tenant001"
  },
  "operation": "create_tenant"
}
```

## 内部エンドポイント

### トランザクションログハンドラー（PubSub）
**POST** `/api/v1/tranlog`

Dapr pub/sub経由でカートサービスからのトランザクションログを処理する内部エンドポイント。このエンドポイントは：
- 販売トランザクションを処理して在庫数量を更新
- イベントIDを使用した冪等性を実装
- カートサービスに確認応答を送信

このエンドポイントは外部クライアントから直接呼び出されることを想定していません。

## エラーレスポンス

APIは標準的なHTTPステータスコードと構造化されたエラーレスポンスを使用します：

```json
{
  "success": false,
  "code": 404,
  "message": "店舗store001の商品ITEM999の在庫が見つかりません",
  "data": null,
  "operation": "get_stock"
}
```

### 一般的なステータスコード
- `200` - 成功
- `201` - 作成成功
- `400` - 不正なリクエスト
- `401` - 認証エラー
- `403` - アクセス拒否
- `404` - リソースが見つかりません
- `500` - 内部サーバーエラー

### エラーコード体系

Stock Serviceは60XXX番台のエラーコードを使用します：

- `60001` - 在庫が見つかりません
- `60002` - 在庫更新エラー
- `60003` - スナップショット作成エラー
- `60004` - 無効な数量
- `60005` - 無効な更新タイプ
- `60099` - その他のエラー

## 注意事項

1. **ページネーション**: リストエンドポイントは`skip`と`limit`パラメータでページネーションをサポート
2. **CamelCase規則**: すべてのJSONフィールドはcamelCaseを使用（例：`itemCode`、`item_code`ではない）
3. **タイムスタンプ**: すべてのタイムスタンプはISO 8601形式（UTC）
4. **数量変更**: 正の値は在庫を増加、負の値は在庫を減少
5. **冪等性**: トランザクション処理はイベントIDを使用して重複更新を防止
6. **マルチテナント**: 各テナントは分離された在庫データを持つ
7. **同時実行制御**: MongoDBのアトミック操作により、同時更新時のデータ整合性を保証

## レート制限

現在、Stock Serviceには明示的なレート制限は実装されていませんが、将来的に以下の制限が追加される可能性があります：

- 1分あたり1000リクエスト/IPアドレス
- 1時間あたり10000リクエスト/APIキー

## WebSocket リアルタイム通知

**WebSocket エンドポイント:** `ws://localhost:8006/api/v1/ws/{tenant_id}/{store_code}?token={jwt_token}`

リアルタイムの在庫アラート通知を提供します。

### 認証
- JWT トークンをクエリパラメータで渡す必要があります
- WebSocket プロトコルの制約により、ヘッダー認証は使用できません

### 接続例
```javascript
const token = 'your_jwt_token_here';
const ws = new WebSocket(`ws://localhost:8006/api/v1/ws/tenant001/store001?token=${token}`);

ws.onopen = function(event) {
    console.log('WebSocket 接続が確立されました');
};

ws.onmessage = function(event) {
    const alert = JSON.parse(event.data);
    console.log('アラート受信:', alert);
};
```

### アラートタイプ

#### 1. 発注点アラート
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

#### 2. 最小在庫アラート
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

#### 3. 接続確認メッセージ
接続が確立されると送信されます：

```json
{
  "type": "connection",
  "status": "connected",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

### アラート制御

#### アラートクールダウン
- 同一商品のアラートスパムを防止するため、クールダウン機能を実装
- 環境変数 `ALERT_COOLDOWN_SECONDS` で設定可能（デフォルト: 60秒）
- テスト環境では 0 秒に設定可能

#### 複数クライアント対応
- 同一テナント・店舗の複数のWebSocket接続に対してアラートを配信
- 接続管理により、切断されたクライアントは自動的に削除

### エラーハンドリング

#### 認証エラー
```javascript
ws.onclose = function(event) {
    if (event.code === 1008) {
        console.error('認証エラー:', event.reason);
        // 'No token provided' または 'Authentication failed'
    }
};
```

#### 接続エラー
```javascript
ws.onerror = function(error) {
    console.error('WebSocket エラー:', error);
};
```

### 使用例

#### React での実装例
```javascript
import { useEffect, useState } from 'react';

function StockAlerts({ tenantId, storeCode, token }) {
    const [alerts, setAlerts] = useState([]);
    const [ws, setWs] = useState(null);

    useEffect(() => {
        const websocket = new WebSocket(
            `ws://localhost:8006/api/v1/ws/${tenantId}/${storeCode}?token=${token}`
        );

        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'stock_alert') {
                setAlerts(prev => [data, ...prev]);
                // アラート通知の表示処理
                showNotification(data);
            }
        };

        websocket.onclose = (event) => {
            if (event.code === 1008) {
                console.error('認証エラー:', event.reason);
            }
        };

        setWs(websocket);

        return () => {
            websocket.close();
        };
    }, [tenantId, storeCode, token]);

    const showNotification = (alert) => {
        const message = alert.alert_type === 'reorder_point' 
            ? `${alert.item_code}: 発注点を下回りました (現在: ${alert.current_quantity})` 
            : `${alert.item_code}: 最小在庫を下回りました (現在: ${alert.current_quantity})`;
        
        // ブラウザ通知またはトースト通知を表示
        new Notification('在庫アラート', { body: message });
    };

    return (
        <div>
            <h3>リアルタイム在庫アラート</h3>
            {alerts.map((alert, index) => (
                <div key={index} className="alert">
                    {alert.item_code}: {alert.alert_type} - 現在数量: {alert.current_quantity}
                </div>
            ))}
        </div>
    );
}
```

### パフォーマンス特性

- **接続数制限**: 実装上の制限なし（システムリソースによる制限）
- **メッセージ配信**: 非同期でリアルタイム配信
- **メモリ使用量**: 接続数に比例
- **CPU 使用量**: アラート発生時のみ増加