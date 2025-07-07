# 在庫サービス API仕様

## 概要

在庫サービスは、Kugelpos POSシステムの在庫管理機能を提供します。リアルタイム在庫追跡、在庫アラート、スナップショット管理、および取引連携による在庫更新を実装しています。WebSocketによるリアルタイムアラートと、Dapr pub/subによるカートサービス連携が特徴です。

## ベースURL
- ローカル環境: `http://localhost:8006`
- 本番環境: `https://stock.{domain}`

## 認証

在庫サービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダー: `Authorization: Bearer {token}`
- 用途: 管理者による在庫管理操作

### 2. APIキー認証
- ヘッダー: `X-API-Key: {api_key}`
- 用途: 端末からの在庫照会（一部のエンドポイント）

## フィールド形式

すべてのAPIリクエスト/レスポンスは**camelCase**形式を使用します。

## 共通レスポンス形式

```json
{
  "success": true,
  "code": 200,
  "message": "操作が正常に完了しました",
  "data": { ... },
  "operation": "function_name"
}
```

## 在庫更新タイプ

| タイプID | 名称 | 説明 |
|----------|------|------|
| SALE | 販売 | 販売による在庫減少 |
| RETURN | 返品 | 返品による在庫増加 |
| VOID | 取消 | 販売取消による在庫増加 |
| VOID_RETURN | 返品取消 | 返品取消による在庫減少 |
| PURCHASE | 仕入 | 仕入による在庫増加 |
| ADJUSTMENT | 調整 | 手動在庫調整 |
| INITIAL | 初期設定 | 初期在庫設定 |
| DAMAGE | 破損 | 破損による在庫減少 |
| TRANSFER_IN | 移動入庫 | 他店舗からの移動入庫 |
| TRANSFER_OUT | 移動出庫 | 他店舗への移動出庫 |

## APIエンドポイント

### 1. 在庫一覧取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock`

店舗の全在庫アイテムを取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード

**クエリパラメータ:**
- `page` (integer, デフォルト: 1): ページ番号
- `limit` (integer, デフォルト: 100): ページサイズ
- `terminal_id` (integer): 端末ID（APIキー認証時）

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stock items retrieved successfully",
  "data": {
    "items": [
      {
        "itemCode": "ITEM001",
        "itemName": "商品001",
        "storeCode": "STORE001",
        "currentQuantity": 100,
        "minimumQuantity": 20,
        "reorderPoint": 30,
        "reorderQuantity": 50,
        "lastUpdated": "2024-01-01T12:00:00Z",
        "updateType": "PURCHASE"
      }
    ],
    "total": 150,
    "page": 1,
    "limit": 100
  },
  "operation": "get_all_stock"
}
```

### 2. 個別在庫取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}`

特定商品の在庫情報を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード
- `item_code` (string, 必須): 商品コード

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stock item retrieved successfully",
  "data": {
    "itemCode": "ITEM001",
    "itemName": "商品001",
    "storeCode": "STORE001",
    "currentQuantity": 100,
    "minimumQuantity": 20,
    "reorderPoint": 30,
    "reorderQuantity": 50,
    "lastUpdated": "2024-01-01T12:00:00Z",
    "updateType": "PURCHASE"
  },
  "operation": "get_stock"
}
```

### 3. 在庫更新
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update`

在庫数量を更新します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード
- `item_code` (string, 必須): 商品コード

**リクエストボディ:**
```json
{
  "quantity": -1,
  "updateType": "SALE",
  "reason": "販売処理",
  "staffId": "STAFF001",
  "referenceNo": "TRAN001"
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stock updated successfully",
  "data": {
    "itemCode": "ITEM001",
    "previousQuantity": 100,
    "newQuantity": 99,
    "quantityChange": -1,
    "updateType": "SALE"
  },
  "operation": "update_stock"
}
```

### 4. 在庫履歴取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/history`

商品の在庫更新履歴を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード
- `item_code` (string, 必須): 商品コード

**クエリパラメータ:**
- `page` (integer, デフォルト: 1): ページ番号
- `limit` (integer, デフォルト: 100): ページサイズ

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stock history retrieved successfully",
  "data": {
    "history": [
      {
        "id": "507f1f77bcf86cd799439011",
        "timestamp": "2024-01-01T12:00:00Z",
        "previousQuantity": 100,
        "newQuantity": 99,
        "quantityChange": -1,
        "updateType": "SALE",
        "reason": "販売処理",
        "staffId": "STAFF001",
        "referenceNo": "TRAN001"
      }
    ],
    "total": 50,
    "page": 1,
    "limit": 100
  },
  "operation": "get_stock_history"
}
```

### 5. 最小在庫数設定
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/minimum`

最小在庫数を設定します。

**リクエストボディ:**
```json
{
  "minimumQuantity": 20
}
```

### 6. 発注点設定
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/reorder`

発注点と発注数量を設定します。

**リクエストボディ:**
```json
{
  "reorderPoint": 30,
  "reorderQuantity": 50
}
```

### 7. 低在庫アイテム取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/low`

最小在庫数を下回るアイテムを取得します。

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Low stock items retrieved successfully",
  "data": {
    "items": [
      {
        "itemCode": "ITEM001",
        "itemName": "商品001",
        "currentQuantity": 15,
        "minimumQuantity": 20,
        "shortageQuantity": 5
      }
    ],
    "total": 5
  },
  "operation": "get_low_stock"
}
```

### 8. 発注アラート取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/reorder-alerts`

発注点に達したアイテムを取得します。

### 9. WebSocket接続（リアルタイムアラート）
**WebSocket** `/ws/{tenant_id}/{store_code}`

在庫アラートをリアルタイムで受信します。

**接続手順:**
1. WebSocket接続を確立（JWTトークンはクエリパラメータで指定）
   - URL例: `/ws/{tenant_id}/{store_code}?token=JWT_TOKEN`
2. アラートメッセージを受信

**アラートメッセージ例:**
```json
{
  "type": "low_stock",
  "itemCode": "ITEM001",
  "itemName": "商品001",
  "currentQuantity": 15,
  "minimumQuantity": 20,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### 10. スナップショット作成
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

在庫スナップショットを手動作成します。

**リクエストボディ:**
```json
{
  "description": "月次棚卸",
  "takenBy": "STAFF001"
}
```

### 11. スナップショット一覧取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshots`

スナップショット一覧を取得します。

**クエリパラメータ:**
- `start_date` (string): 開始日（YYYY-MM-DD）
- `end_date` (string): 終了日（YYYY-MM-DD）
- `page` (integer, デフォルト: 1): ページ番号
- `limit` (integer, デフォルト: 100): ページサイズ

### 12. スナップショット詳細取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}`

特定のスナップショット詳細を取得します。

### 13. スナップショットスケジュール取得
**GET** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

自動スナップショットのスケジュール設定を取得します。

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Snapshot schedule retrieved successfully",
  "data": {
    "daily": {
      "enabled": true,
      "time": "02:00",
      "timezone": "Asia/Tokyo"
    },
    "weekly": {
      "enabled": false,
      "dayOfWeek": 0,
      "time": "02:00",
      "timezone": "Asia/Tokyo"
    },
    "monthly": {
      "enabled": true,
      "dayOfMonth": 1,
      "time": "02:00",
      "timezone": "Asia/Tokyo"
    },
    "retentionDays": 90
  },
  "operation": "get_snapshot_schedule"
}
```

### 14. スナップショットスケジュール更新
**PUT** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

自動スナップショットのスケジュールを更新します。

**リクエストボディ:**
```json
{
  "daily": {
    "enabled": true,
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "weekly": {
    "enabled": false,
    "dayOfWeek": 0,
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "monthly": {
    "enabled": true,
    "dayOfMonth": 1,
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "retentionDays": 90
}
```

### 15. スナップショットスケジュール削除
**DELETE** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

カスタムスケジュールを削除し、デフォルト設定に戻します。

### 16. テナント作成
**POST** `/api/v1/tenants`

新規テナント用の在庫サービスを初期化します。

**リクエストボディ:**
```json
{
  "tenantId": "tenant001"
}
```

**認証:** JWTトークンが必要

### 17. ヘルスチェック
**GET** `/health`

サービスの健全性を確認します。

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "サービスは正常です",
  "data": {
    "status": "healthy",
    "mongodb": "connected",
    "dapr": "connected",
    "scheduler": "running"
  },
  "operation": "health_check"
}
```

## イベント処理エンドポイント（Dapr Pub/Sub）

### 18. 取引ログハンドラー
**POST** `/api/v1/tranlog`

**トピック:** `topic-tranlog`

カートサービスからの取引ログを処理し、在庫を更新します。

### 19. Dapr Subscribe
**GET** `/dapr/subscribe`

Daprのサブスクリプション設定を返します。

## エラーコード

在庫サービスは41XXX範囲のエラーコードを使用します：

- `41401`: 在庫アイテムが見つかりません
- `41402`: 在庫が不足しています
- `41403`: 無効な更新タイプ
- `41404`: 無効な数量
- `41405`: スナップショットが見つかりません
- `41406`: スケジュール設定エラー
- `41499`: 一般的なサービスエラー

## 特記事項

1. **在庫の原子性**: 同時更新を防ぐための原子的操作を実装
2. **マイナス在庫**: バックオーダーに対応するためマイナス在庫を許可
3. **アラートクールダウン**: 同一アイテムのアラートは60秒間隔で制限
4. **冪等性**: イベントIDによる重複処理防止
5. **WebSocket認証**: 接続時にクエリパラメータでトークンを指定
6. **スナップショット保持**: デフォルトで90日間保持