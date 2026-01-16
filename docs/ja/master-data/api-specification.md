# マスターデータサービス API仕様書

## 概要

商品マスター、支払方法、税金設定、スタッフ情報などの参照データを管理するサービスです。

## サービス情報

- **ポート**: 8002
- **フレームワーク**: FastAPI
- **データベース**: MongoDB (Motor async driver)

## ベースURL

- ローカル環境: `http://localhost:8002`
- 本番環境: `https://master-data.{domain}`

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

### 4. カテゴリー一覧取得

**GET** `/api/v1/tenants/{tenant_id}/categories`

Get Categoriesの情報を取得します。

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
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `array[CategoryMasterResponse]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |
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
      "categoryCode": "string",
      "description": "string",
      "descriptionShort": "string",
      "taxCode": "string",
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

### 5. カテゴリー作成

**POST** `/api/v1/tenants/{tenant_id}/categories`

新しいカテゴリを作成します。商品を整理するためのカテゴリを追加します。

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
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |

**リクエスト例:**
```json
{
  "categoryCode": "string",
  "description": "string",
  "descriptionShort": "string",
  "taxCode": "string"
}
```

**レスポンス:**

**dataフィールド:** `CategoryMasterResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |
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
    "categoryCode": "string",
    "description": "string",
    "descriptionShort": "string",
    "taxCode": "string",
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

### 6. カテゴリー取得

**GET** `/api/v1/tenants/{tenant_id}/categories/{category_code}`

カテゴリを取得します。カテゴリの詳細を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `category_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `CategoryMasterResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |
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
    "categoryCode": "string",
    "description": "string",
    "descriptionShort": "string",
    "taxCode": "string",
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

### 7. カテゴリー更新

**PUT** `/api/v1/tenants/{tenant_id}/categories/{category_code}`

Update Categoryを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `category_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |

**リクエスト例:**
```json
{
  "description": "string",
  "descriptionShort": "string",
  "taxCode": "string"
}
```

**レスポンス:**

**dataフィールド:** `CategoryMasterResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |
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
    "categoryCode": "string",
    "description": "string",
    "descriptionShort": "string",
    "taxCode": "string",
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

### 8. カテゴリー削除

**DELETE** `/api/v1/tenants/{tenant_id}/categories/{category_code}`

Delete Categoryを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `category_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `CategoryMasterDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |

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
    "categoryCode": "string"
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

### 9. 商品ブック一覧取得

**GET** `/api/v1/tenants/{tenant_id}/item_books`

商品ブックを取得します。商品ブックの情報を返します。

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
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `array[ItemBookResponse]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
      "title": "string",
      "categories": [],
      "itemBookId": "string",
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

### 10. 商品ブック作成

**POST** `/api/v1/tenants/{tenant_id}/item_books`

新しい商品ブックを作成します。商品ブックはPOSでの素早いアクセスのために商品を整理します。

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
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Input] | No | - |

**リクエスト例:**
```json
{
  "title": "string",
  "categories": []
}
```

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 11. 商品ブック取得

**GET** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}`

商品ブックを取得します。商品ブックの情報を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `store_code` | string | No | - | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 12. 商品ブック更新

**PUT** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}`

Update Item Bookを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Input] | No | - |

**リクエスト例:**
```json
{
  "title": "string",
  "categories": []
}
```

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 13. 商品ブック削除

**DELETE** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}`

Delete Item Bookを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemBookDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemBookId` | string | Yes | - |

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
    "itemBookId": "string"
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

### 14. 商品ブックにカテゴリー追加

**POST** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories`

商品ブックにカテゴリを追加します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `categoryNumber` | integer | Yes | - |
| `title` | string | Yes | - |
| `color` | string | Yes | - |
| `tabs` | array[BaseItemBookTab-Input] | No | - |

**リクエスト例:**
```json
{
  "categoryNumber": 0,
  "title": "string",
  "color": "string",
  "tabs": []
}
```

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 15. 商品ブック内カテゴリー更新

**PUT** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}`

Update Category In Item Bookを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `categoryNumber` | integer | Yes | - |
| `title` | string | Yes | - |
| `color` | string | Yes | - |
| `tabs` | array[BaseItemBookTab-Input] | No | - |

**リクエスト例:**
```json
{
  "categoryNumber": 0,
  "title": "string",
  "color": "string",
  "tabs": []
}
```

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 16. 商品ブックからカテゴリー削除

**DELETE** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}`

Delete Category From Item Bookを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemBookCategoryDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemBookId` | string | Yes | - |
| `categoryNumber` | integer | Yes | - |

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
    "itemBookId": "string",
    "categoryNumber": 0
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

### 17. 商品ブック内カテゴリーにタブ追加

**POST** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs`

商品ブックにカテゴリを追加します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tabNumber` | integer | Yes | - |
| `title` | string | Yes | - |
| `color` | string | Yes | - |
| `buttons` | array[BaseItemBookButton] | No | - |

**リクエスト例:**
```json
{
  "tabNumber": 0,
  "title": "string",
  "color": "string",
  "buttons": []
}
```

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 18. 商品ブック内カテゴリーのタブ更新

**PUT** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}`

Update Tab In Category In Item Bookを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tabNumber` | integer | Yes | - |
| `title` | string | Yes | - |
| `color` | string | Yes | - |
| `buttons` | array[BaseItemBookButton] | No | - |

**リクエスト例:**
```json
{
  "tabNumber": 0,
  "title": "string",
  "color": "string",
  "buttons": []
}
```

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 19. 商品ブック内カテゴリーからタブ削除

**DELETE** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}`

Delete Tab From Category In Item Bookを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemBookTabDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemBookId` | string | Yes | - |
| `categoryNumber` | integer | Yes | - |
| `tabNumber` | integer | Yes | - |

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
    "itemBookId": "string",
    "categoryNumber": 0,
    "tabNumber": 0
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

### 20. 商品ブック内タブにボタン追加

**POST** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons`

商品ブックにカテゴリを追加します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `posX` | integer | Yes | - |
| `posY` | integer | Yes | - |
| `size` | ButtonSize | Yes | - |
| `imageUrl` | string | Yes | - |
| `colorText` | string | Yes | - |
| `itemCode` | string | Yes | - |
| `unitPrice` | number | No | - |
| `description` | string | No | - |

**リクエスト例:**
```json
{
  "posX": 0,
  "posY": 0,
  "size": "Single",
  "imageUrl": "string",
  "colorText": "string",
  "itemCode": "string",
  "unitPrice": 0.0,
  "description": "string"
}
```

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 21. 商品ブック内タブのボタン更新

**PUT** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons/pos_x/{pos_x}/pos_y/{pos_y}`

Update Button In Tab In Category In Item Bookを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `pos_x` | integer | Yes | - |
| `pos_y` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `posX` | integer | Yes | - |
| `posY` | integer | Yes | - |
| `size` | ButtonSize | Yes | - |
| `imageUrl` | string | Yes | - |
| `colorText` | string | Yes | - |
| `itemCode` | string | Yes | - |
| `unitPrice` | number | No | - |
| `description` | string | No | - |

**リクエスト例:**
```json
{
  "posX": 0,
  "posY": 0,
  "size": "Single",
  "imageUrl": "string",
  "colorText": "string",
  "itemCode": "string",
  "unitPrice": 0.0,
  "description": "string"
}
```

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 22. 商品ブック内タブからボタン削除

**DELETE** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons/pos_x/{pos_x}/pos_y/{pos_y}`

Delete Button From Tab In Category In Item Bookを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `pos_x` | integer | Yes | - |
| `pos_y` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemBookButtonDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemBookId` | string | Yes | - |
| `categoryNumber` | integer | Yes | - |
| `tabNumber` | integer | Yes | - |
| `posX` | integer | Yes | - |
| `posY` | integer | Yes | - |

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
    "itemBookId": "string",
    "categoryNumber": 0,
    "tabNumber": 0,
    "posX": 0,
    "posY": 0
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

### 23. 商品ブック詳細取得

**GET** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/detail`

商品ブックを取得します。商品ブックの情報を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `store_code` | string | Yes | - | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemBookResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
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

### 24. 商品マスター一覧取得

**GET** `/api/v1/tenants/{tenant_id}/items`

Retrieve all item master records for a tenant.

This endpoint returns a paginated list of all active items for the specified tenant.
The results can be sorted and paginated as needed.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

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
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `array[ItemResponse]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
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
      "itemCode": "string",
      "description": "string",
      "unitPrice": 0.0,
      "unitCost": 0.0,
      "itemDetails": [
        "string"
      ],
      "imageUrls": [
        "string"
      ],
      "categoryCode": "string",
      "taxCode": "string",
      "isDiscountRestricted": true,
      "isDeleted": true
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

### 25. 商品マスター作成

**POST** `/api/v1/tenants/{tenant_id}/items`

新しい商品マスターレコードを作成します。商品をカタログに追加します。

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
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | No | - |

**リクエスト例:**
```json
{
  "itemCode": "string",
  "description": "string",
  "unitPrice": 0.0,
  "unitCost": 0.0,
  "itemDetails": [
    "string"
  ],
  "imageUrls": [
    "string"
  ],
  "categoryCode": "string",
  "taxCode": "string",
  "isDiscountRestricted": false
}
```

**レスポンス:**

**dataフィールド:** `ItemResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
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
    "itemCode": "string",
    "description": "string",
    "unitPrice": 0.0,
    "unitCost": 0.0,
    "itemDetails": [
      "string"
    ],
    "imageUrls": [
      "string"
    ],
    "categoryCode": "string",
    "taxCode": "string",
    "isDiscountRestricted": true,
    "isDeleted": true
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

### 26. 商品マスター取得

**GET** `/api/v1/tenants/{tenant_id}/items/{item_code}`

商品を取得します。商品の詳細情報を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `is_logical_deleted` | boolean | No | False | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
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
    "itemCode": "string",
    "description": "string",
    "unitPrice": 0.0,
    "unitCost": 0.0,
    "itemDetails": [
      "string"
    ],
    "imageUrls": [
      "string"
    ],
    "categoryCode": "string",
    "taxCode": "string",
    "isDiscountRestricted": true,
    "isDeleted": true
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

### 27. 商品マスター更新

**PUT** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Update Item Master Asyncを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | No | - |

**リクエスト例:**
```json
{
  "description": "string",
  "unitPrice": 0.0,
  "unitCost": 0.0,
  "itemDetails": [
    "string"
  ],
  "imageUrls": [
    "string"
  ],
  "categoryCode": "string",
  "taxCode": "string",
  "isDiscountRestricted": false
}
```

**レスポンス:**

**dataフィールド:** `ItemResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
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
    "itemCode": "string",
    "description": "string",
    "unitPrice": 0.0,
    "unitCost": 0.0,
    "itemDetails": [
      "string"
    ],
    "imageUrls": [
      "string"
    ],
    "categoryCode": "string",
    "taxCode": "string",
    "isDiscountRestricted": true,
    "isDeleted": true
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

### 28. 商品マスター削除

**DELETE** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Delete Item Master Asyncを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `is_logical` | boolean | No | False | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `isLogical` | boolean | Yes | - |

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
    "itemCode": "string",
    "isLogical": true
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

### 29. 支払方法一覧取得

**GET** `/api/v1/tenants/{tenant_id}/payments`

支払方法を取得します。支払方法の設定を返します。

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
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `array[PaymentResponse]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |
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
      "paymentCode": "string",
      "description": "string",
      "limitAmount": 0.0,
      "canRefund": true,
      "canDepositOver": true,
      "canChange": true,
      "isActive": true,
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

### 30. 支払方法作成

**POST** `/api/v1/tenants/{tenant_id}/payments`

新しい支払方法を作成します。支払オプションをシステムに追加します。

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
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |

**リクエスト例:**
```json
{
  "paymentCode": "string",
  "description": "string",
  "limitAmount": 0.0,
  "canRefund": true,
  "canDepositOver": true,
  "canChange": true,
  "isActive": true
}
```

**レスポンス:**

**dataフィールド:** `PaymentResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |
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
    "paymentCode": "string",
    "description": "string",
    "limitAmount": 0.0,
    "canRefund": true,
    "canDepositOver": true,
    "canChange": true,
    "isActive": true,
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

### 31. 支払方法取得

**GET** `/api/v1/tenants/{tenant_id}/payments/{payment_code}`

支払方法を取得します。支払方法の設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `payment_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `PaymentResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |
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
    "paymentCode": "string",
    "description": "string",
    "limitAmount": 0.0,
    "canRefund": true,
    "canDepositOver": true,
    "canChange": true,
    "isActive": true,
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

### 32. 支払方法更新

**PUT** `/api/v1/tenants/{tenant_id}/payments/{payment_code}`

Update Paymentを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `payment_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |

**リクエスト例:**
```json
{
  "description": "string",
  "limitAmount": 0.0,
  "canRefund": true,
  "canDepositOver": true,
  "canChange": true,
  "isActive": true
}
```

**レスポンス:**

**dataフィールド:** `PaymentResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |
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
    "paymentCode": "string",
    "description": "string",
    "limitAmount": 0.0,
    "canRefund": true,
    "canDepositOver": true,
    "canChange": true,
    "isActive": true,
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

### 33. 支払方法削除

**DELETE** `/api/v1/tenants/{tenant_id}/payments/{payment_code}`

Delete Paymentを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `payment_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `PaymentDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |

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
    "paymentCode": "string"
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

### 34. 設定マスター一覧取得

**GET** `/api/v1/tenants/{tenant_id}/settings`

設定を取得します。設定の値と構成を返します。

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
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `array[SettingsMasterResponse]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |
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
      "name": "string",
      "defaultValue": "string",
      "values": [
        {
          "storeCode": "string",
          "terminalNo": 0,
          "value": "string"
        }
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

### 35. 設定マスター作成

**POST** `/api/v1/tenants/{tenant_id}/settings`

新しい設定エントリを作成します。設定項目をシステムに追加します。

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
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |

**リクエスト例:**
```json
{
  "name": "string",
  "defaultValue": "string",
  "values": [
    {
      "storeCode": "string",
      "terminalNo": 0,
      "value": "string"
    }
  ]
}
```

**レスポンス:**

**dataフィールド:** `SettingsMasterResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |
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
    "name": "string",
    "defaultValue": "string",
    "values": [
      {
        "storeCode": "string",
        "terminalNo": 0,
        "value": "string"
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

### 36. 設定マスター取得

**GET** `/api/v1/tenants/{tenant_id}/settings/{name}`

設定を取得します。設定の値と構成を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `SettingsMasterResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |
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
    "name": "string",
    "defaultValue": "string",
    "values": [
      {
        "storeCode": "string",
        "terminalNo": 0,
        "value": "string"
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

### 37. 設定マスター更新

**PUT** `/api/v1/tenants/{tenant_id}/settings/{name}`

Update Settings Master Asyncを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |

**リクエスト例:**
```json
{
  "defaultValue": "string",
  "values": [
    {
      "storeCode": "string",
      "terminalNo": 0,
      "value": "string"
    }
  ]
}
```

**レスポンス:**

**dataフィールド:** `SettingsMasterResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |
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
    "name": "string",
    "defaultValue": "string",
    "values": [
      {
        "storeCode": "string",
        "terminalNo": 0,
        "value": "string"
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

### 38. 設定マスター削除

**DELETE** `/api/v1/tenants/{tenant_id}/settings/{name}`

Delete Settings Master Asyncを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `SettingsMasterDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |

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
    "name": "string"
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

### 39. 設定値取得

**GET** `/api/v1/tenants/{tenant_id}/settings/{name}/value`

設定を取得します。設定の値と構成を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `store_code` | string | Yes | - | - |
| `terminal_no` | integer | Yes | - | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `SettingsMasterValueResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `value` | string | Yes | - |

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
    "value": "string"
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

### 40. 税率一覧取得

**GET** `/api/v1/tenants/{tenant_id}/taxes`

税率を取得します。税率の設定を返します。

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
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `array[TaxMasterResponse]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `taxCode` | string | Yes | - |
| `taxType` | string | Yes | - |
| `taxName` | string | Yes | - |
| `rate` | number | Yes | - |
| `roundDigit` | integer | Yes | - |
| `roundMethod` | string | No | - |
| `entryDatetime` | string | No | - |
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
      "taxCode": "string",
      "taxType": "string",
      "taxName": "string",
      "rate": 0.0,
      "roundDigit": 0,
      "roundMethod": "string",
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

### 41. 税率取得

**GET** `/api/v1/tenants/{tenant_id}/taxes/{tax_code}`

税率を取得します。税率の設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tax_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `TaxMasterResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `taxCode` | string | Yes | - |
| `taxType` | string | Yes | - |
| `taxName` | string | Yes | - |
| `rate` | number | Yes | - |
| `roundDigit` | integer | Yes | - |
| `roundMethod` | string | No | - |
| `entryDatetime` | string | No | - |
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
    "taxCode": "string",
    "taxType": "string",
    "taxName": "string",
    "rate": 0.0,
    "roundDigit": 0,
    "roundMethod": "string",
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

### 店舗

### 42. 店舗別商品マスター一覧取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items`

店舗情報を取得します。店舗の詳細と設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `array[ItemStoreResponse]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |
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
      "itemCode": "string",
      "storePrice": 0.0,
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

### 43. 商品マスター作成

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items`

新しい商品マスターレコードを作成します。商品をカタログに追加します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |

**リクエスト例:**
```json
{
  "itemCode": "string",
  "storePrice": 0.0
}
```

**レスポンス:**

**dataフィールド:** `ItemStoreResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |
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
    "itemCode": "string",
    "storePrice": 0.0,
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

### 44. 店舗別商品マスター取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}`

店舗情報を取得します。店舗の詳細と設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemStoreResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |
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
    "itemCode": "string",
    "storePrice": 0.0,
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

### 45. 店舗別商品マスター更新

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}`

Update Item Store Master Asyncを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `storePrice` | number | Yes | - |

**リクエスト例:**
```json
{
  "storePrice": 0.0
}
```

**レスポンス:**

**dataフィールド:** `ItemStoreResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |
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
    "itemCode": "string",
    "storePrice": 0.0,
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

### 46. 店舗別商品マスター削除

**DELETE** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}`

Delete Item Store Master Asyncを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemStoreDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |

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
    "itemCode": "string"
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

### 47. 店舗別商品マスター詳細取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}/details`

店舗情報を取得します。店舗の詳細と設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `ItemStoreDetailResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `storePrice` | number | No | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
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
    "itemCode": "string",
    "description": "string",
    "unitPrice": 0.0,
    "unitCost": 0.0,
    "storePrice": 0.0,
    "itemDetails": [
      "string"
    ],
    "imageUrls": [
      "string"
    ],
    "categoryCode": "string",
    "taxCode": "string",
    "isDiscountRestricted": true
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

### スタッフ

### 48. スタッフマスター一覧取得

**GET** `/api/v1/tenants/{tenant_id}/staff`

スタッフ情報を取得します。スタッフメンバーの詳細を返します。

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
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `array[StaffResponse]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | No | - |
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
      "id": "string",
      "name": "string",
      "pin": "string",
      "roles": [],
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

### 49. スタッフマスター作成

**POST** `/api/v1/tenants/{tenant_id}/staff`

新しいスタッフレコードを作成します。スタッフメンバーをシステムに追加します。

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
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | Yes | - |

**リクエスト例:**
```json
{
  "id": "string",
  "name": "string",
  "pin": "string",
  "roles": [
    "string"
  ]
}
```

**レスポンス:**

**dataフィールド:** `StaffResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | No | - |
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
    "id": "string",
    "name": "string",
    "pin": "string",
    "roles": [],
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

### 50. スタッフマスター取得

**GET** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

スタッフ情報を取得します。スタッフメンバーの詳細を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `staff_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `StaffResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | No | - |
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
    "id": "string",
    "name": "string",
    "pin": "string",
    "roles": [],
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

### 51. スタッフマスター更新

**PUT** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Update Staff Master Asyncを更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `staff_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | Yes | - |

**リクエスト例:**
```json
{
  "name": "string",
  "pin": "string",
  "roles": [
    "string"
  ]
}
```

**レスポンス:**

**dataフィールド:** `StaffResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | No | - |
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
    "id": "string",
    "name": "string",
    "pin": "string",
    "roles": [],
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

### 52. スタッフマスター削除

**DELETE** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Delete Staff Master Asyncを削除します。対象をシステムから削除します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `staff_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `StaffDeleteResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `staffId` | string | Yes | - |

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
    "staffId": "string"
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
