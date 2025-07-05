# レポートサービス API仕様

## 概要

レポートサービスは、Kugelpos POSシステムの各種レポート生成機能を提供します。売上レポート、カテゴリー別レポート、商品別レポートなどを生成し、リアルタイム（flash）および日次（daily）の集計データを提供します。プラグインアーキテクチャにより、レポートタイプを拡張可能な設計となっています。

## ベースURL
- ローカル環境: `http://localhost:8004`
- 本番環境: `https://report.{domain}`

## 認証

レポートサービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダー: `Authorization: Bearer {token}`
- 用途: 管理者によるレポート閲覧・生成

### 2. APIキー認証
- ヘッダー: `X-API-Key: {api_key}`
- 用途: 端末からのレポート取得（ジャーナル連携あり）

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

## レポートタイプ

| タイプID | 名称 | 説明 |
|----------|------|------|
| sales | 売上レポート | 売上金額、取引数等の基本集計 |
| category | カテゴリーレポート | カテゴリー別売上集計（未実装） |
| item | 商品レポート | 商品別売上集計（未実装） |

## レポート範囲

| 範囲ID | 名称 | 説明 |
|--------|------|------|
| flash | フラッシュレポート | リアルタイム集計（現在のセッション） |
| daily | 日次レポート | 日単位の集計（要全端末閉店） |

## APIエンドポイント

### 1. 店舗レポート取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/reports`

店舗全体のレポートを取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード

**クエリパラメータ:**
- `report_scope` (string, 必須): レポート範囲（flash/daily）
- `report_type` (string, 必須): レポートタイプ（sales）
- `business_date` (string, 必須): ビジネス日付（YYYYMMDD）
- `open_counter` (integer): 開店カウンター（flashレポート時）
- `business_counter` (integer): ビジネスカウンター
- `limit` (integer, デフォルト: 100): ページサイズ
- `page` (integer, デフォルト: 1): ページ番号
- `sort` (string): ソート条件

**レスポンス例（売上レポート）:**
```json
{
  "success": true,
  "code": 200,
  "message": "Sales report fetched successfully",
  "data": {
    "tenantId": "tenant001",
    "storeCode": "STORE001",
    "storeName": "店舗001",
    "terminalNo": null,
    "businessDate": "20240101",
    "reportScope": "daily",
    "reportType": "sales",
    "salesGross": {
      "itemCount": 500,
      "transactionCount": 150,
      "totalAmount": 125000.00
    },
    "salesNet": {
      "itemCount": 495,
      "transactionCount": 148,
      "totalAmount": 120000.00
    },
    "discountForLineitems": {
      "itemCount": 20,
      "transactionCount": 15,
      "totalAmount": -2000.00
    },
    "discountForSubtotal": {
      "itemCount": 0,
      "transactionCount": 10,
      "totalAmount": -1000.00
    },
    "returns": {
      "itemCount": 5,
      "transactionCount": 2,
      "totalAmount": -2000.00
    },
    "taxes": [
      {
        "taxCode": "TAX_10",
        "taxType": "STANDARD",
        "taxName": "標準税率",
        "itemCount": 400,
        "targetAmount": 100000.00,
        "taxAmount": 10000.00
      },
      {
        "taxCode": "TAX_8",
        "taxType": "REDUCED",
        "taxName": "軽減税率",
        "itemCount": 100,
        "targetAmount": 25000.00,
        "taxAmount": 2000.00
      }
    ],
    "payments": [
      {
        "paymentCode": "CASH",
        "paymentName": "現金",
        "transactionCount": 100,
        "totalAmount": 80000.00
      },
      {
        "paymentCode": "CREDIT",
        "paymentName": "クレジット",
        "transactionCount": 50,
        "totalAmount": 45000.00
      }
    ],
    "cash": {
      "cashInCount": 5,
      "cashInAmount": 10000.00,
      "cashOutCount": 3,
      "cashOutAmount": -5000.00,
      "netCashMovement": 5000.00
    },
    "receiptText": "=== 日次売上レポート ===\n...",
    "journalText": "=== 日次売上レポート ===\n..."
  },
  "operation": "get_report_for_store"
}
```

### 2. 端末レポート取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports`

特定端末のレポートを取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード
- `terminal_no` (integer, 必須): 端末番号

**クエリパラメータ:**
店舗レポートと同じ

### 3. トランザクション受信（REST）
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

直接トランザクションデータを送信するRESTエンドポイント。

**リクエストボディ:**
kugel_commonのBaseTransaction構造に準拠したトランザクションデータ

### 4. テナント作成
**POST** `/api/v1/tenants`

新規テナント用のレポートサービスを初期化します。

**リクエストボディ:**
```json
{
  "tenantId": "tenant001"
}
```

**認証:** JWTトークンが必要

### 5. ヘルスチェック
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
    "mongodb": "connected"
  },
  "operation": "health_check"
}
```

## イベント処理エンドポイント（Dapr Pub/Sub）

### 6. 取引ログハンドラー
**POST** `/api/v1/tranlog`

**トピック:** `tranlog_report`

カートサービスからの取引ログを処理します。

### 7. 入出金ログハンドラー
**POST** `/api/v1/cashlog`

**トピック:** `cashlog_report`

ターミナルサービスからの入出金ログを処理します。

### 8. 開閉店ログハンドラー
**POST** `/api/v1/opencloselog`

**トピック:** `opencloselog_report`

ターミナルサービスからの開閉店ログを処理します。

## レポート構造詳細

### SalesReportTemplate
売上集計の基本構造：
```json
{
  "itemCount": 100,          // 商品数
  "transactionCount": 50,    // 取引数
  "totalAmount": 10000.00    // 金額合計
}
```

### TaxReportTemplate
税金集計構造：
```json
{
  "taxCode": "TAX_10",
  "taxType": "STANDARD",
  "taxName": "標準税率",
  "itemCount": 100,
  "targetAmount": 10000.00,   // 課税対象額
  "taxAmount": 1000.00        // 税額
}
```

### PaymentReportTemplate
支払方法別集計構造：
```json
{
  "paymentCode": "CASH",
  "paymentName": "現金",
  "transactionCount": 50,
  "totalAmount": 10000.00
}
```

### CashReportTemplate
現金入出金集計構造：
```json
{
  "cashInCount": 5,           // 入金回数
  "cashInAmount": 10000.00,   // 入金額
  "cashOutCount": 3,          // 出金回数
  "cashOutAmount": -5000.00,  // 出金額
  "netCashMovement": 5000.00  // 純移動額
}
```

## エラーコード

レポートサービスは40XXX範囲のエラーコードを使用します：

- `40001`: レポートデータが見つかりません
- `40002`: 端末が閉店していません（日次レポート時）
- `40003`: データ期間エラー
- `40004`: 無効なレポートタイプ
- `40005`: 無効なレポート範囲
- `40099`: 一般的なサービスエラー

## 特記事項

1. **日次レポートの前提条件**: 全端末が閉店していることが必要
2. **データ検証**: 日次レポート生成前に以下を検証
   - 全端末のクローズログ存在確認
   - 入出金ログ数の一致確認
   - 取引ログ数の一致確認
3. **冪等性**: イベントIDによる重複処理防止
4. **プラグイン拡張**: 新しいレポートタイプはプラグインで追加可能
5. **ジャーナル連携**: APIキー認証時はレポートをジャーナルに自動送信