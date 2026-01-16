# 在庫サービス API仕様書

## 概要

在庫管理と在庫追跡を行うサービスです。スナップショット機能と発注点管理を提供します。

## サービス情報

- **ポート**: 8006
- **フレームワーク**: FastAPI
- **データベース**: MongoDB (Motor async driver)

## ベースURL

- ローカル環境: `http://localhost:8006`
- 本番環境: `https://stock.{domain}`

## 認証

以下の認証方法をサポートしています：

### APIキー認証
- ヘッダー: `X-API-Key: {api_key}`
- 用途: 端末からのAPI呼び出し

### JWTトークン認証
- ヘッダー: `Authorization: Bearer {token}`
- 用途: 管理者によるシステム操作

## 共通レスポンス形式

```json
{
  "success": true,
  "code": 200,
  "message": "操作が正常に完了しました",
  "data": {
    "...": "..."
  },
  "operation": "operation_name"
}
```

## APIエンドポイント

### システム

### 1. ルートエンドポイント

**GET** `/`

ルートエンドポイントです。ウェルカムメッセージとAPI情報を返します。

**レスポンス:**

### 2. ヘルスチェック

**GET** `/health`

ヘルスチェックエンドポイントです。サービスの稼働状態を監視します。

**レスポンス:**

**レスポンス例:**
```json
{
  "status": "healthy",
  "timestamp": "string",
  "service": "string",
  "version": "string",
  "checks": {}
}
```

### テナント

### 3. テナント作成

**POST** `/api/v1/tenants`

新しいテナントを作成します。必要なデータベースコレクションとインデックスをセットアップします。

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |

**リクエスト例:**
```json
{
  "tenantId": "string"
}
```

**レスポンス:**

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 4. スナップショットスケジュール設定取得

**GET** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

在庫情報を取得します。在庫レベルと関連データを返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `SnapshotScheduleResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `enabled` | boolean | No | - |
| `schedule_interval` | string | Yes | Schedule interval: daily, weekly, monthly |
| `schedule_hour` | integer | Yes | Execution hour (0-23) |
| `schedule_minute` | integer | No | Execution minute (0-59) |
| `schedule_day_of_week` | integer | No | Day of week for weekly schedule (0=Monday, 6=Sunda |
| `schedule_day_of_month` | integer | No | Day of month for monthly schedule (1-31) |
| `retention_days` | integer | No | Snapshot retention days |
| `target_stores` | array[string] | No | Target stores: ['all'] or specific store codes |
| `tenant_id` | string | Yes | - |
| `last_executed_at` | string | No | - |
| `next_execution_at` | string | No | - |
| `created_at` | string | No | - |
| `updated_at` | string | No | - |
| `created_by` | string | No | - |
| `updated_by` | string | No | - |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "enabled": true,
    "schedule_interval": "string",
    "schedule_hour": 0,
    "schedule_minute": 0,
    "schedule_day_of_week": 0,
    "schedule_day_of_month": 0,
    "retention_days": 30,
    "target_stores": [
      "all"
    ],
    "tenant_id": "string",
    "last_executed_at": "2025-01-01T00:00:00Z"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 5. スナップショットスケジュール設定更新

**PUT** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

スナップショットスケジュールを更新します。自動スナップショットの作成タイミングを設定します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `enabled` | boolean | No | - |
| `schedule_interval` | string | Yes | Schedule interval: daily, weekly, monthly |
| `schedule_hour` | integer | Yes | Execution hour (0-23) |
| `schedule_minute` | integer | No | Execution minute (0-59) |
| `schedule_day_of_week` | integer | No | Day of week for weekly schedule (0=Monday, 6=Sunda |
| `schedule_day_of_month` | integer | No | Day of month for monthly schedule (1-31) |
| `retention_days` | integer | No | Snapshot retention days |
| `target_stores` | array[string] | No | Target stores: ['all'] or specific store codes |

**リクエスト例:**
```json
{
  "enabled": true,
  "schedule_interval": "string",
  "schedule_hour": 0,
  "schedule_minute": 0,
  "schedule_day_of_week": 0,
  "schedule_day_of_month": 0,
  "retention_days": 30,
  "target_stores": [
    "all"
  ]
}
```

**レスポンス:**

**dataフィールド:** `SnapshotScheduleResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `enabled` | boolean | No | - |
| `schedule_interval` | string | Yes | Schedule interval: daily, weekly, monthly |
| `schedule_hour` | integer | Yes | Execution hour (0-23) |
| `schedule_minute` | integer | No | Execution minute (0-59) |
| `schedule_day_of_week` | integer | No | Day of week for weekly schedule (0=Monday, 6=Sunda |
| `schedule_day_of_month` | integer | No | Day of month for monthly schedule (1-31) |
| `retention_days` | integer | No | Snapshot retention days |
| `target_stores` | array[string] | No | Target stores: ['all'] or specific store codes |
| `tenant_id` | string | Yes | - |
| `last_executed_at` | string | No | - |
| `next_execution_at` | string | No | - |
| `created_at` | string | No | - |
| `updated_at` | string | No | - |
| `created_by` | string | No | - |
| `updated_by` | string | No | - |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "enabled": true,
    "schedule_interval": "string",
    "schedule_hour": 0,
    "schedule_minute": 0,
    "schedule_day_of_week": 0,
    "schedule_day_of_month": 0,
    "retention_days": 30,
    "target_stores": [
      "all"
    ],
    "tenant_id": "string",
    "last_executed_at": "2025-01-01T00:00:00Z"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 6. スナップショットスケジュール設定削除

**DELETE** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

スナップショットスケジュールを削除します。自動スナップショット作成を無効化します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 在庫

### 7. 店舗在庫一覧取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock`

店舗情報を取得します。店舗の詳細と設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `page` | integer | No | 1 | Page number |
| `limit` | integer | No | 100 | Maximum number of items to return |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `PaginatedResult_StockResponse_`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `data` | array[StockResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "itemCode": "string",
        "currentQuantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0,
        "lastUpdated": "2025-01-01T00:00:00Z",
        "lastTransactionId": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 8. 在庫僅少商品取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/low`

商品を取得します。商品の詳細情報を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `PaginatedResult_StockResponse_`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `data` | array[StockResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "itemCode": "string",
        "currentQuantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0,
        "lastUpdated": "2025-01-01T00:00:00Z",
        "lastTransactionId": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 9. 発注点アラート取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/reorder-alerts`

商品を取得します。商品の詳細情報を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `PaginatedResult_StockResponse_`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `data` | array[StockResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "itemCode": "string",
        "currentQuantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0,
        "lastUpdated": "2025-01-01T00:00:00Z",
        "lastTransactionId": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 10. 在庫スナップショット作成

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

在庫スナップショットを作成します。監査用の特定時点の在庫記録を提供します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `createdBy` | string | No | User or system that created the snapshot |

**リクエスト例:**
```json
{
  "createdBy": "system"
}
```

**レスポンス:**

**dataフィールド:** `StockSnapshotResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | Tenant ID |
| `storeCode` | string | Yes | Store code |
| `totalItems` | integer | Yes | Total number of items |
| `totalQuantity` | number | Yes | Total stock quantity |
| `stocks` | array[StockSnapshotItemResponse] | Yes | Stock details by item |
| `createdBy` | string | Yes | User or system that created the snapshot |
| `createdAt` | string | Yes | Creation timestamp |
| `updatedAt` | string | No | Last update timestamp |
| `generateDateTime` | string | No | Snapshot generation datetime in ISO format |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "totalItems": 0,
    "totalQuantity": 0.0,
    "stocks": [
      {
        "itemCode": "string",
        "quantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0
      }
    ],
    "createdBy": "string",
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-01T00:00:00Z",
    "generateDateTime": "string"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 11. 在庫スナップショット取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}`

在庫情報を取得します。在庫レベルと関連データを返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `snapshot_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `StockSnapshotResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | Tenant ID |
| `storeCode` | string | Yes | Store code |
| `totalItems` | integer | Yes | Total number of items |
| `totalQuantity` | number | Yes | Total stock quantity |
| `stocks` | array[StockSnapshotItemResponse] | Yes | Stock details by item |
| `createdBy` | string | Yes | User or system that created the snapshot |
| `createdAt` | string | Yes | Creation timestamp |
| `updatedAt` | string | No | Last update timestamp |
| `generateDateTime` | string | No | Snapshot generation datetime in ISO format |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "totalItems": 0,
    "totalQuantity": 0.0,
    "stocks": [
      {
        "itemCode": "string",
        "quantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0
      }
    ],
    "createdBy": "string",
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-01T00:00:00Z",
    "generateDateTime": "string"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 12. Get stock snapshots by date range

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshots`

Get list of stock snapshots filtered by generate_date_time range

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `start_date` | string | No | - | Start date in ISO format |
| `end_date` | string | No | - | End date in ISO format |
| `page` | integer | No | 1 | Page number |
| `limit` | integer | No | 100 | Maximum number of items to return |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `PaginatedResult_StockSnapshotResponse_`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `data` | array[StockSnapshotResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "totalItems": 0,
        "totalQuantity": 0.0,
        "stocks": [
          {
            "itemCode": "...",
            "quantity": "...",
            "minimumQuantity": "...",
            "reorderPoint": "...",
            "reorderQuantity": "..."
          }
        ],
        "createdBy": "string",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "generateDateTime": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 13. 商品在庫取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}`

商品を取得します。商品の詳細情報を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `StockResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | Tenant ID |
| `storeCode` | string | Yes | Store code |
| `itemCode` | string | Yes | Item code |
| `currentQuantity` | number | Yes | Current stock quantity |
| `minimumQuantity` | number | Yes | Minimum stock quantity for alerts |
| `reorderPoint` | number | Yes | Reorder point - quantity that triggers reorder |
| `reorderQuantity` | number | Yes | Quantity to order when reorder point is reached |
| `lastUpdated` | string | Yes | Last update timestamp |
| `lastTransactionId` | string | No | Last transaction reference |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "itemCode": "string",
    "currentQuantity": 0.0,
    "minimumQuantity": 0.0,
    "reorderPoint": 0.0,
    "reorderQuantity": 0.0,
    "lastUpdated": "2025-01-01T00:00:00Z",
    "lastTransactionId": "string"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 14. Get stock update history

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/history`

Get stock update history for an item

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `page` | integer | No | 1 | Page number |
| `limit` | integer | No | 100 | Maximum number of items to return |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `PaginatedResult_StockUpdateResponse_`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `data` | array[StockUpdateResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "itemCode": "string",
        "updateType": "sale",
        "quantityChange": 0.0,
        "beforeQuantity": 0.0,
        "afterQuantity": 0.0,
        "referenceId": "string",
        "timestamp": "2025-01-01T00:00:00Z",
        "operatorId": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 15. 最小在庫数設定

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/minimum`

最小在庫数を設定します。在庫僅少アラートの閾値を設定します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `minimumQuantity` | number | Yes | Minimum stock quantity for alerts |

**リクエスト例:**
```json
{
  "minimumQuantity": 0.0
}
```

**レスポンス:**

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 16. 発注点パラメータ設定

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/reorder`

発注点パラメータを設定します。発注点と発注数量を設定します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `reorderPoint` | number | Yes | Reorder point - quantity that triggers reorder |
| `reorderQuantity` | number | Yes | Quantity to order when reorder point is reached |

**リクエスト例:**
```json
{
  "reorderPoint": 0.0,
  "reorderQuantity": 0.0
}
```

**レスポンス:**

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 17. 在庫数更新

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update`

数量を更新します。指定された明細の数量を変更します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `quantityChange` | number | Yes | Quantity change (positive for increase, negative f |
| `updateType` | UpdateType | Yes | - |
| `referenceId` | string | No | Reference ID (transaction, adjustment, etc.) |
| `operatorId` | string | No | User who performed the update |
| `note` | string | No | Additional notes |

**リクエスト例:**
```json
{
  "quantityChange": 0.0,
  "updateType": "sale",
  "referenceId": "string",
  "operatorId": "string",
  "note": "string"
}
```

**レスポンス:**

**dataフィールド:** `StockUpdateResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | Tenant ID |
| `storeCode` | string | Yes | Store code |
| `itemCode` | string | Yes | Item code |
| `updateType` | UpdateType | Yes | - |
| `quantityChange` | number | Yes | Quantity change |
| `beforeQuantity` | number | Yes | Stock quantity before update |
| `afterQuantity` | number | Yes | Stock quantity after update |
| `referenceId` | string | No | Reference ID |
| `timestamp` | string | Yes | Update timestamp |
| `operatorId` | string | No | User who performed the update |
| `note` | string | No | Additional notes |

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "itemCode": "string",
    "updateType": "sale",
    "quantityChange": 0.0,
    "beforeQuantity": 0.0,
    "afterQuantity": 0.0,
    "referenceId": "string",
    "timestamp": "2025-01-01T00:00:00Z",
    "operatorId": "string"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### イベント処理

### 18. カートサービスから取引ログ受信

**POST** `/api/v1/tranlog`

Handle transaction log from cart serviceを処理します。

**レスポンス:**

## エラーコード

エラーレスポンスは以下の形式で返されます：

```json
{
  "success": false,
  "code": 400,
  "message": "エラーメッセージ",
  "errorCode": "ERROR_CODE",
  "operation": "operation_name"
}
```
