# ターミナルサービス API仕様書

## 概要

テナント管理、店舗管理、端末管理機能を提供するサービスです。端末のライフサイクル管理、現金入出金操作、スタッフ管理を行います。

## サービス情報

- **ポート**: 8001
- **フレームワーク**: FastAPI
- **データベース**: MongoDB (Motor async driver)

## ベースURL

- ローカル環境: `http://localhost:8001`
- 本番環境: `https://terminal.{domain}`

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

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |

**リクエスト例:**
```json
{
  "tenantId": "string",
  "tenantName": "string",
  "tags": [
    "string"
  ]
}
```

**レスポンス:**

**dataフィールド:** `Tenant`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |
| `stores` | array[BaseStore] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "tenantName": "string",
    "tags": [
      "string"
    ],
    "stores": [
      {
        "storeCode": "string",
        "storeName": "string",
        "status": "string",
        "businessDate": "string",
        "tags": [
          "string"
        ],
        "entryDatetime": "string",
        "lastUpdateDatetime": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 4. テナント取得

**GET** `/api/v1/tenants/{tenant_id}`

テナント情報を取得します。テナントの設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | - |

**レスポンス:**

**dataフィールド:** `Tenant`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |
| `stores` | array[BaseStore] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "tenantName": "string",
    "tags": [
      "string"
    ],
    "stores": [
      {
        "storeCode": "string",
        "storeName": "string",
        "status": "string",
        "businessDate": "string",
        "tags": [
          "string"
        ],
        "entryDatetime": "string",
        "lastUpdateDatetime": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 5. テナント更新

**PUT** `/api/v1/tenants/{tenant_id}`

Update Tenantを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |

**リクエスト例:**
```json
{
  "tenantName": "string",
  "tags": [
    "string"
  ]
}
```

**レスポンス:**

**dataフィールド:** `Tenant`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |
| `stores` | array[BaseStore] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "tenantName": "string",
    "tags": [
      "string"
    ],
    "stores": [
      {
        "storeCode": "string",
        "storeName": "string",
        "status": "string",
        "businessDate": "string",
        "tags": [
          "string"
        ],
        "entryDatetime": "string",
        "lastUpdateDatetime": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 6. テナント削除

**DELETE** `/api/v1/tenants/{tenant_id}`

Delete Tenantを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**レスポンス:**

**dataフィールド:** `TenantDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |

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
    "tenantId": "string"
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

### 店舗

### 7. 店舗一覧取得

**GET** `/api/v1/tenants/{tenant_id}/stores`

店舗情報を取得します。店舗の詳細と設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | - |

**レスポンス:**

**dataフィールド:** `array[Store]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
  "data": [
    {
      "storeCode": "string",
      "storeName": "string",
      "status": "string",
      "businessDate": "string",
      "tags": [
        "string"
      ],
      "entryDatetime": "string",
      "lastUpdateDatetime": "string"
    }
  ],
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

### 8. 店舗追加

**POST** `/api/v1/tenants/{tenant_id}/stores`

店舗を追加します。テナントに新しい店舗を追加します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |

**リクエスト例:**
```json
{
  "storeCode": "string",
  "storeName": "string",
  "status": "string",
  "businessDate": "string",
  "tags": [
    "string"
  ]
}
```

**レスポンス:**

**dataフィールド:** `Tenant`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |
| `stores` | array[BaseStore] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "tenantName": "string",
    "tags": [
      "string"
    ],
    "stores": [
      {
        "storeCode": "string",
        "storeName": "string",
        "status": "string",
        "businessDate": "string",
        "tags": [
          "string"
        ],
        "entryDatetime": "string",
        "lastUpdateDatetime": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 9. 店舗取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

店舗情報を取得します。店舗の詳細と設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | - |

**レスポンス:**

**dataフィールド:** `Store`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "storeCode": "string",
    "storeName": "string",
    "status": "string",
    "businessDate": "string",
    "tags": [
      "string"
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 10. 店舗更新

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Update Storeを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |

**リクエスト例:**
```json
{
  "storeName": "string",
  "status": "string",
  "businessDate": "string",
  "tags": [
    "string"
  ]
}
```

**レスポンス:**

**dataフィールド:** `Store`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "storeCode": "string",
    "storeName": "string",
    "status": "string",
    "businessDate": "string",
    "tags": [
      "string"
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 11. 店舗削除

**DELETE** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Delete Storeを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**レスポンス:**

**dataフィールド:** `StoreDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `storeCode` | string | Yes | - |

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
    "storeCode": "string"
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

### 端末

### 12. 端末一覧取得

**GET** `/api/v1/terminals`

端末情報を取得します。端末の詳細と現在の状態を返します。

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | Limit the number of results |
| `page` | integer | No | 1 | Page number |
| `store_code` | string | No | - | Filter by store code |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | - |

**レスポンス:**

**dataフィールド:** `array[Terminal]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
  "data": [
    {
      "terminalId": "string",
      "tenantId": "string",
      "storeCode": "string",
      "terminalNo": 0,
      "description": "string",
      "functionMode": "string",
      "status": "string",
      "businessDate": "string",
      "openCounter": 0,
      "businessCounter": 0
    }
  ],
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

### 13. 端末作成

**POST** `/api/v1/terminals`

新しい端末を作成します。店舗にPOS端末を登録します。

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |

**リクエスト例:**
```json
{
  "storeCode": "string",
  "terminalNo": 0,
  "description": "string"
}
```

**レスポンス:**

**dataフィールド:** `Terminal`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 14. 端末取得

**GET** `/api/v1/terminals/{terminal_id}`

端末情報を取得します。端末の詳細と現在の状態を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**レスポンス:**

**dataフィールド:** `Terminal`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 15. 端末削除

**DELETE** `/api/v1/terminals/{terminal_id}`

Delete Terminalを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**レスポンス:**

**dataフィールド:** `TerminalDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |

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
    "terminalId": "string"
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

### 16. 現金入金

**POST** `/api/v1/terminals/{terminal_id}/cash-in`

現金を入金します。端末のドロワーへの入金を記録し、レシートを生成します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `amount` | number | Yes | - |
| `description` | string | No | - |

**リクエスト例:**
```json
{
  "amount": 0.0,
  "description": "string"
}
```

**レスポンス:**

**dataフィールド:** `CashInOutResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `amount` | number | Yes | - |
| `description` | string | Yes | - |
| `receiptText` | string | Yes | - |
| `journalText` | string | Yes | - |

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
    "terminalId": "string",
    "amount": 0.0,
    "description": "string",
    "receiptText": "string",
    "journalText": "string"
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

### 17. 現金出金

**POST** `/api/v1/terminals/{terminal_id}/cash-out`

現金を出金します。端末のドロワーからの出金を記録し、レシートを生成します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `amount` | number | Yes | - |
| `description` | string | No | - |

**リクエスト例:**
```json
{
  "amount": 0.0,
  "description": "string"
}
```

**レスポンス:**

**dataフィールド:** `CashInOutResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `amount` | number | Yes | - |
| `description` | string | Yes | - |
| `receiptText` | string | Yes | - |
| `journalText` | string | Yes | - |

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
    "terminalId": "string",
    "amount": 0.0,
    "description": "string",
    "receiptText": "string",
    "journalText": "string"
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

### 18. 端末閉店

**POST** `/api/v1/terminals/{terminal_id}/close`

端末を閉店します。その日の取引を確定し、閉店レポートを生成します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `physicalAmount` | number | No | - |

**リクエスト例:**
```json
{
  "physicalAmount": 0.0
}
```

**レスポンス:**

**dataフィールド:** `TerminalCloseResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `businessDate` | string | Yes | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `terminalInfo` | BaseTerminal | Yes | Base Terminal Information Model

Represents termin |
| `receiptText` | string | Yes | - |
| `journalText` | string | Yes | - |
| `physicalAmount` | number | No | - |

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
    "terminalId": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0,
    "initialAmount": 0.0,
    "terminalInfo": {
      "terminalId": "string",
      "tenantId": "string",
      "storeCode": "string",
      "terminalNo": 0,
      "description": "string",
      "functionMode": "string",
      "status": "string",
      "businessDate": "string",
      "openCounter": 0,
      "businessCounter": 0
    },
    "receiptText": "string",
    "journalText": "string",
    "physicalAmount": 0.0
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

### 19. 配信状態更新

**POST** `/api/v1/terminals/{terminal_id}/delivery-status`

配信状態を更新します。取引の配信追跡情報を更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `event_id` | string | Yes | - |
| `service` | string | Yes | - |
| `status` | string | Yes | - |
| `message` | string | No | - |

**リクエスト例:**
```json
{
  "event_id": "string",
  "service": "string",
  "status": "string",
  "message": "string"
}
```

**レスポンス:**

**dataフィールド:** `DeliveryStatusUpdateResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `event_id` | string | Yes | - |
| `service` | string | Yes | - |
| `status` | string | Yes | - |
| `success` | boolean | Yes | - |

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
    "event_id": "string",
    "service": "string",
    "status": "string",
    "success": true
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

### 20. 端末説明更新

**PATCH** `/api/v1/terminals/{terminal_id}/description`

端末の説明を更新します。端末の表示名やメモを変更します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `description` | string | Yes | - |

**リクエスト例:**
```json
{
  "description": "string"
}
```

**レスポンス:**

**dataフィールド:** `Terminal`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 21. 端末機能モード更新

**PATCH** `/api/v1/terminals/{terminal_id}/function_mode`

端末の機能モードを更新します。操作モードを変更します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `functionMode` | string | Yes | - |

**リクエスト例:**
```json
{
  "functionMode": "string"
}
```

**レスポンス:**

**dataフィールド:** `Terminal`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 22. 端末開店

**POST** `/api/v1/terminals/{terminal_id}/open`

端末を開店します。新しい営業日のために端末を初期化します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `initialAmount` | number | No | - |

**リクエスト例:**
```json
{
  "initialAmount": 0.0
}
```

**レスポンス:**

**dataフィールド:** `TerminalOpenResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `businessDate` | string | Yes | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `terminalInfo` | BaseTerminal | Yes | Base Terminal Information Model

Represents termin |
| `receiptText` | string | Yes | - |
| `journalText` | string | Yes | - |

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
    "terminalId": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0,
    "initialAmount": 0.0,
    "terminalInfo": {
      "terminalId": "string",
      "tenantId": "string",
      "storeCode": "string",
      "terminalNo": 0,
      "description": "string",
      "functionMode": "string",
      "status": "string",
      "businessDate": "string",
      "openCounter": 0,
      "businessCounter": 0
    },
    "receiptText": "string",
    "journalText": "string"
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

### 23. スタッフサインイン

**POST** `/api/v1/terminals/{terminal_id}/sign-in`

スタッフをサインインします。端末へのスタッフサインインを記録します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `staffId` | string | Yes | - |

**リクエスト例:**
```json
{
  "staffId": "string"
}
```

**レスポンス:**

**dataフィールド:** `Terminal`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 24. スタッフサインアウト

**POST** `/api/v1/terminals/{terminal_id}/sign-out`

スタッフをサインアウトします。端末からのスタッフサインアウトを記録します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**レスポンス:**

**dataフィールド:** `Terminal`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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
