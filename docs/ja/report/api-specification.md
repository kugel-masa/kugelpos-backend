# レポートサービス API仕様書

## 概要

売上レポートと日次サマリーを生成するサービスです。プラグインアーキテクチャを採用しています。

## サービス情報

- **ポート**: 8004
- **フレームワーク**: FastAPI
- **データベース**: MongoDB (Motor async driver)

## ベースURL

- ローカル環境: `http://localhost:8004`
- 本番環境: `https://report.{domain}`

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

### 店舗

### 4. 店舗レポート取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/reports`

店舗情報を取得します。店舗の詳細と設定を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | Terminal ID for api_key authentication |
| `report_scope` | string | Yes | - | Scope of the report: flash, daily |
| `report_type` | string | Yes | - | Type of the report: sales, category, ite |
| `business_date` | string | No | - | Business date for flash and daily (singl |
| `business_date_from` | string | No | - | Start date for date range (YYYYMMDD form |
| `business_date_to` | string | No | - | End date for date range (YYYYMMDD format |
| `open_counter` | integer | No | - | Open counter for flash and daily, None f |
| `business_counter` | integer | No | - | Business counter for the report |
| `limit` | integer | No | 100 | Limit of the number of records to return |
| `page` | integer | No | 1 | Page number to return |
| `is_terminal_service` | string | No | False | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |

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

### 5. 端末レポート取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports`

端末情報を取得します。端末の詳細と現在の状態を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | Terminal ID for api_key authentication |
| `report_scope` | string | Yes | - | Scope of the report: flash, daily |
| `report_type` | string | Yes | - | Type of the report: sales, category, ite |
| `business_date` | string | No | - | Business date for flash and daily (singl |
| `business_date_from` | string | No | - | Start date for date range (YYYYMMDD form |
| `business_date_to` | string | No | - | End date for date range (YYYYMMDD format |
| `open_counter` | integer | No | - | Open counter for flash and daily, None f |
| `business_counter` | integer | No | - | Business counter for the report |
| `limit` | integer | No | 100 | Limit of the number of records to return |
| `page` | integer | No | 1 | Page number to return |
| `is_terminal_service` | string | No | False | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |

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

### トランザクション

### 6. 取引データ受信

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

取引データを受信します。カートサービスからの取引データを処理します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

**レスポンス:**

**dataフィールド:** `TranResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |

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
    "terminalNo": 0,
    "transactionNo": 0
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

### 7. 現金ログ処理

**POST** `/api/v1/cashlog`

入出金ログを処理します。Dapr pub/sub経由で受信した入出金イベントを処理します。

**レスポンス:**

### 8. 開閉店ログ処理

**POST** `/api/v1/opencloselog`

開閉店ログを処理します。Dapr pub/sub経由で受信した端末状態変更イベントを処理します。

**レスポンス:**

### 9. 取引ログ処理

**POST** `/api/v1/tranlog`

取引ログを処理します。Dapr pub/sub経由で受信した取引ログイベントを処理します。

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
