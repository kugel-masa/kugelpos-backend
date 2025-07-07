# ジャーナルサービス API仕様

## 概要

ジャーナルサービスは、Kugelpos POSシステムの電子ジャーナル管理機能を提供します。全ての取引記録、現金操作、端末開閉情報を永続的に保存し、監査・コンプライアンス要件に対応します。

## ベースURL
- ローカル環境: `http://localhost:8005`  
- 本番環境: `https://journal.{domain}`

## 認証

ジャーナルサービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダー: `Authorization: Bearer {token}`
- 用途: 管理者によるジャーナル検索・照会

### 2. APIキー認証
- ヘッダー: `X-API-Key: {api_key}`
- 用途: 端末からのジャーナル作成

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

## トランザクションタイプコード

| コード | 説明 |
|------|------|
| 101 | 通常売上 |
| -101 | 通常売上取消 |
| 102 | 返品売上 |
| 201 | 売上取消 |
| 202 | 返品取消 |
| 301 | レジ開け |
| 302 | レジ締め |
| 401 | 現金入金 |
| 402 | 現金出金 |
| 501 | 売上レポート |
| 502 | その他レポート |

## APIエンドポイント

### 1. ジャーナル作成
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/journals`

新規ジャーナルエントリーを作成します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード  
- `terminal_no` (integer, 必須): 端末番号

**リクエストボディ:**
```json
{
  "transactionNo": "0001",
  "transactionType": 101,
  "businessDate": "2024-01-01",
  "businessCounter": 100,
  "openCounter": 1,
  "receiptNo": "R0001",
  "amount": 99.00,
  "quantity": 2.0,
  "staffId": "STF001",
  "userId": "user001",
  "journalText": "=== 売上取引 ===\n...",
  "receiptText": "=== レシート ===\n..."
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Transaction received successfully. tenant_id: tenant001, store_code: store001, terminal_no: 1",
  "data": {
    "tenantId": "tenant001",
    "storeCode": "store001",
    "terminalNo": 1,
    "transactionNo": "0001",
    "transactionType": 101,
    "businessDate": "2024-01-01",
    "receiptNo": "R0001",
    "amount": 99.00,
    "generateDateTime": "2024-01-01T10:30:00Z"
  },
  "operation": "create_journal"
}
```

### 2. ジャーナル検索
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/journals`

複数条件でジャーナルエントリーを検索します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード

**クエリパラメータ:**
- `terminals` (string): 端末番号（カンマ区切り）
- `transaction_types` (string): トランザクションタイプ（カンマ区切り）
- `business_date_from` (string): 開始ビジネス日付（YYYY-MM-DD）
- `business_date_to` (string): 終了ビジネス日付（YYYY-MM-DD）
- `generate_date_time_from` (string): 開始生成日時（YYYYMMDDTHHMMSS）
- `generate_date_time_to` (string): 終了生成日時（YYYYMMDDTHHMMSS）
- `receipt_no_from` (string): 開始レシート番号
- `receipt_no_to` (string): 終了レシート番号
- `keywords` (string): キーワード検索（カンマ区切り）
- `page` (integer, デフォルト: 1): ページ番号
- `limit` (integer, デフォルト: 100, 最大: 1000): ページサイズ
- `sort` (string): ソート順（例: "generateDateTime:-1"）

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Journals found successfully. tenant_id: tenant001, store_code: store001",
  "data": [
    {
      "tenantId": "tenant001",
      "storeCode": "store001",
      "terminalNo": 1,
      "transactionNo": "0001",
      "transactionType": 101,
      "businessDate": "2024-01-01",
      "businessCounter": 100,
      "openCounter": 1,
      "receiptNo": "R0001",
      "amount": 99.00,
      "quantity": 2.0,
      "staffId": "STF001",
      "userId": "user001",
      "generateDateTime": "2024-01-01T10:30:00Z",
      "journalText": "=== 売上取引 ===\n...",
      "receiptText": "=== レシート ===\n..."
    }
  ],
  "metadata": {
    "total": 150,
    "page": 1,
    "limit": 50,
    "pages": 3
  },
  "operation": "search_journals"
}
```

### 3. トランザクション受信（REST）
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

直接トランザクションデータを送信するRESTエンドポイント。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード
- `terminal_no` (integer, 必須): 端末番号

**リクエストボディ:**
ジャーナル作成エンドポイントと同じ構造

### 4. テナント作成
**POST** `/api/v1/tenants`

新規テナント用のジャーナルサービスを初期化します。

**リクエストボディ:**
```json
{
  "tenantId": "tenant001"
}
```

**認証:** JWTトークンが必要

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "テナント作成が完了しました: tenant001",
  "data": {
    "tenantId": "tenant001"
  },
  "operation": "create_tenant"
}
```

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
    "mongodb": "connected",
    "dapr_sidecar": "connected",
    "dapr_state_store": "connected",
    "pubsub_topics": "subscribed"
  },
  "operation": "health_check"
}
```

## イベント処理エンドポイント（Dapr Pub/Sub）

### 6. トランザクションログハンドラー
**POST** `/api/v1/tranlog`

**トピック:** `tranlog_report`

カートサービスからのトランザクションログを処理します。

### 7. 現金ログハンドラー
**POST** `/api/v1/cashlog`

**トピック:** `cashlog_report`  

ターミナルサービスからの現金入出金ログを処理します。

### 8. 開閉ログハンドラー
**POST** `/api/v1/opencloselog`

**トピック:** `opencloselog_report`

ターミナルサービスからの端末開閉ログを処理します。

## ソートオプション

利用可能なソートフィールド:
- `terminalNo`: 端末番号
- `businessDate`: ビジネス日付
- `transactionNo`: トランザクション番号
- `receiptNo`: レシート番号
- `generateDateTime`: 生成日時
- `amount`: 金額

デフォルトソート順:
- `terminalNo:1, businessDate:1, receiptNo:1`（端末番号、ビジネス日付、レシート番号の昇順）

方向:
- `1`: 昇順
- `-1`: 降順

## エラーコード

ジャーナルサービスは410XX-411XX範囲のエラーコードを使用します：

### ジャーナル基本操作関連 (4100X)
- `410001`: ジャーナルが見つかりません
- `410002`: ジャーナルのバリデーションエラー
- `410003`: ジャーナル作成エラー
- `410004`: ジャーナル検索エラー
- `410005`: ジャーナルフォーマットエラー
- `410006`: ジャーナル日付エラー
- `410007`: ジャーナルデータエラー

### ジャーナル検証関連 (4101X)
- `410101`: 端末が見つかりません
- `410102`: 店舗が見つかりません
- `410103`: 必要なログが欠落しています
- `410104`: ログシーケンスエラー
- `410105`: トランザクション検証エラー

### その他のジャーナル関連 (411XX)
- `411001`: レシート生成エラー
- `411002`: ジャーナルテキスト生成エラー
- `411003`: エクスポートエラー
- `411004`: インポートエラー
- `411005`: トランザクションレシートエラー
- `411006`: 外部サービスエラー

## 特記事項

1. **冪等性**: イベントIDによる重複処理防止
2. **データ保持**: 永続保存（自動削除なし）
3. **全文検索**: journal_text内のキーワード検索対応
4. **非同期処理**: 全ての操作は非同期実行
5. **Circuit Breaker**: 外部サービス障害時の自動復旧