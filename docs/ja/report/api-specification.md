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

`business_date` か、`business_date_from` と `business_date_to` の両端で範囲を指定します。範囲と `business_date` の両方を指定したときは、範囲を使います。範囲の片方だけの指定は、`business_date` と一緒でも 400（`412006`）で拒否されます。

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

`business_date` か、`business_date_from` と `business_date_to` の両端で範囲を指定します。範囲と `business_date` の両方を指定したときは、範囲を使います。範囲の片方だけの指定は、`business_date` と一緒でも 400（`412006`）で拒否されます。

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

本文の `tenantId`、`storeCode`、`terminalNo` は、パスのテナント・店舗・端末と同じでなければなりません。本文にない項目はパスの値になり、違う値を書いた本文は 400 で拒否します（issue #134）。

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

### レポートの名前（#326）

| レポートの項目 | 出どころ |
|---|---|
| 分類名（分類別・商品別レポート） | master-data。全ページを読み、論理削除した分類も含める。見つからないコードはコードのまま |
| 商品名（商品別レポート） | 取引ログ。期間内でいちばん新しい明細の `description`、つまり売ったときの名前。master-data には問い合わせない。名前がなければコード |
| 支払方法名（支払レポート） | master-data の今の名前。なければ、期間内でいちばん新しい支払明細の `builtin_description`。それもなければ `01` / `11` / `12` に `Cash` / `Cashless` / `Others`、それ以外は `Payment {code}` |

そのため、売ったあとに名前を変えたり削除したりしたマスタも、過去のレポートで名前が出る。ただし、あとから名前を変えた分類は、今の名前で出る。

### 支払・プロモーションのレポートの応答（#329）

売上・分類別・商品別のレポートと同じく、支払とプロモーションのレポートも camelCase で応答し、保存している文書の内部の項目（`shard_key`・`etag`・`created_at`・`updated_at`）は返さない。#329 より前は、保存している文書をそのまま snake_case で返していた。

```json
{
  "tenantId": "T001", "storeCode": "5678", "terminalNo": null,
  "businessDate": "20261123", "reportScope": "flash", "reportType": "payment",
  "paymentSummary": [
    {"paymentCode": "11", "paymentName": "Cashless", "count": 2, "amount": 3300.0, "ratio": 100.0,
     "variants": [{"variantCode": "VISA", "variantName": "VISA", "amount": 3300.0, "count": 2}]}
  ],
  "total": {"count": 2, "amount": 3300.0},
  "receiptText": "...", "journalText": "...", "generateDateTime": "2026-11-23T18:00:00+09:00"
}
```

プロモーションのレポートは、`promotions[]`（`promotionCode`・`promotionType`・`grossAmount`・`discountAmount`・`netAmount`・`quantity`・`transactionCount`）と、`totalGrossAmount`・`totalDiscountAmount`・`totalNetAmount`・`totalQuantity`・`totalTransactionCount` を返す。

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
