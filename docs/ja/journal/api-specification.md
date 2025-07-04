# ジャーナルサービスAPI仕様

## 概要

ジャーナルサービスは、Kugelpos POSシステムの電子ジャーナル保存とトランザクションログアーカイブAPIを提供します。販売取引、現金移動、端末操作、生成レポートを含むすべてのPOS操作の永続的で検索可能な記録を管理し、法規制準拠と監査要件に対応します。

## ベースURL
- ローカル環境: `http://localhost:8005`
- 本番環境: `https://journal.{domain}`

## 認証

ジャーナルサービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダーに含める: `Authorization: Bearer {token}`
- トークン取得元: アカウントサービスの `/api/v1/accounts/token`
- 管理的なジャーナルアクセスに必要

### 2. APIキー認証
- ヘッダーに含める: `X-API-Key: {api_key}`
- クエリパラメータを含める: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- 端末からのジャーナルエントリー作成に使用

## フィールド形式

すべてのAPIリクエストとレスポンスは**camelCase**フィールド命名規則を使用します。サービスは`BaseSchemaModel`とトランスフォーマーを使用して、内部のsnake_caseと外部のcamelCase形式を自動的に変換します。

## 共通レスポンス形式

すべてのエンドポイントは以下の形式でレスポンスを返します：

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

ジャーナルエントリーはトランザクションタイプで分類されます：

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

### ジャーナル管理

#### 1. ジャーナルエントリー作成
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/journals`

アーカイブ用の新規ジャーナルエントリーを作成します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード
- `terminal_no` (integer, 必須): 端末番号

**クエリパラメータ:**
- `terminal_id` (string, オプション): APIキー認証時の端末ID

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

**フィールド説明:**
- `transactionNo` (string, オプション): トランザクション番号
- `transactionType` (integer, 必須): トランザクションタイプコード
- `businessDate` (string, 必須): ビジネス日付（YYYY-MM-DD）
- `businessCounter` (integer, オプション): ビジネス操作カウンター
- `openCounter` (integer, オプション): 端末セッションカウンター
- `receiptNo` (string, オプション): レシート番号
- `amount` (number, オプション): トランザクション金額
- `quantity` (number, オプション): 商品数量
- `staffId` (string, オプション): スタッフ識別子
- `userId` (string, オプション): ユーザー識別子
- `journalText` (string, 必須): フォーマット済みジャーナル表示テキスト
- `receiptText` (string, オプション): フォーマット済みレシートテキスト

**リクエスト例:**
```bash
curl -X POST "http://localhost:8005/api/v1/tenants/tenant001/stores/store001/terminals/1/journals" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "transactionNo": "0001",
    "transactionType": 101,
    "businessDate": "2024-01-01",
    "receiptNo": "R0001",
    "amount": 99.00,
    "journalText": "=== 売上取引 ===\n...",
    "receiptText": "=== レシート ===\n..."
  }'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "ジャーナルエントリーが正常に作成されました",
  "data": {
    "journalId": "507f1f77bcf86cd799439011",
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

#### 2. ジャーナル検索/取得
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/journals`

柔軟なフィルタリングでジャーナルエントリーを検索・取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード

**クエリパラメータ:**
- `terminal_id` (string, オプション): APIキー認証時の端末ID
- `terminals` (string, オプション): 端末番号でフィルタ（カンマ区切り）
- `transaction_types` (string, オプション): トランザクションタイプでフィルタ（カンマ区切り）
- `business_date_from` (string, オプション): 開始ビジネス日付（YYYY-MM-DD）
- `business_date_to` (string, オプション): 終了ビジネス日付（YYYY-MM-DD）
- `generate_date_from` (string, オプション): 開始生成日付（YYYY-MM-DD）
- `generate_date_to` (string, オプション): 終了生成日付（YYYY-MM-DD）
- `receipt_no_from` (string, オプション): 開始レシート番号
- `receipt_no_to` (string, オプション): 終了レシート番号
- `keywords` (string, オプション): ジャーナルテキスト内の検索キーワード（カンマ区切り）
- `page` (integer, デフォルト: 1): ページ番号
- `limit` (integer, デフォルト: 20, 最大: 100): ページサイズ
- `sort` (string, オプション): ソートフィールドと順序（例: "generateDateTime:-1"）

**リクエスト例:**
```bash
curl -X GET "http://localhost:8005/api/v1/tenants/tenant001/stores/store001/journals?terminals=1,2&transaction_types=101,102&business_date_from=2024-01-01&business_date_to=2024-01-31&limit=50" \
  -H "Authorization: Bearer {token}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "ジャーナルが正常に取得されました",
  "data": {
    "items": [
      {
        "journalId": "507f1f77bcf86cd799439011",
        "tenantId": "tenant001",
        "storeCode": "store001",
        "terminalNo": 1,
        "transactionNo": "0001",
        "transactionType": 101,
        "transactionTypeName": "通常売上",
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
    }
  },
  "operation": "search_journals"
}
```

### イベント処理エンドポイント（Dapr Pub/Sub）

#### 3. トランザクションログハンドラー
**POST** `/api/v1/tranlog`

Dapr pub/sub経由でカートサービスからトランザクションログを処理します。

**トピック:** `topic-tranlog`

**イベント構造:**
```json
{
  "eventId": "evt_123456",
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
  "receiptText": "=== レシート ===\n...",
  "journalText": "=== 売上取引 ===\n...",
  "timestamp": "2024-01-01T10:30:00Z"
}
```

**レスポンス:**
サービスは受信を確認し、ソースサービスに通知します：
```json
{
  "success": true,
  "eventId": "evt_123456",
  "message": "トランザクションログが正常に処理されました"
}
```

#### 4. 現金ログハンドラー
**POST** `/api/v1/cashlog`

Dapr pub/sub経由でターミナルサービスから現金操作ログを処理します。

**トピック:** `topic-cashlog`

**イベント構造:**
```json
{
  "eventId": "evt_789012",
  "tenantId": "tenant001",
  "storeCode": "store001",
  "terminalNo": 1,
  "operationType": "cash_in",
  "amount": 100.00,
  "businessDate": "2024-01-01",
  "businessCounter": 100,
  "openCounter": 1,
  "receiptNo": "CI001",
  "reason": "釣銭補充",
  "staffId": "STF001",
  "receiptText": "=== 現金入金 ===\n...",
  "journalText": "現金入金操作\n...",
  "timestamp": "2024-01-01T09:00:00Z"
}
```

#### 5. 開け締めログハンドラー
**POST** `/api/v1/opencloselog`

Dapr pub/sub経由でターミナルサービスから端末開け締めログを処理します。

**トピック:** `topic-opencloselog`

**イベント構造:**
```json
{
  "eventId": "evt_345678",
  "tenantId": "tenant001",
  "storeCode": "store001",
  "terminalNo": 1,
  "operationType": "open",
  "businessDate": "2024-01-01",
  "businessCounter": 100,
  "openCounter": 1,
  "initialAmount": 500.00,
  "staffId": "STF001",
  "receiptText": "=== レジ開け ===\n...",
  "journalText": "レジ開け\n...",
  "timestamp": "2024-01-01T08:00:00Z"
}
```

### 直接トランザクションAPI

#### 6. トランザクション受信
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

直接トランザクション送信のための代替RESTエンドポイント。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード
- `terminal_no` (integer, 必須): 端末番号

**クエリパラメータ:**
- `terminal_id` (string, オプション): APIキー認証時の端末ID

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
  "receiptText": "=== レシート ===\n...",
  "journalText": "=== 売上取引 ===\n..."
}
```

### システムエンドポイント

#### 7. テナント作成
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
    "tenantId": "tenant001",
    "collectionsCreated": [
      "journal",
      "log_tran",
      "log_cash_in_out",
      "log_open_close"
    ]
  },
  "operation": "create_tenant"
}
```

#### 8. ヘルスチェック
**GET** `/health`

サービスヘルスと依存関係をチェックします。

**リクエスト例:**
```bash
curl -X GET "http://localhost:8005/health"
```

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

## ジャーナル検索機能

### 端末番号による検索
```
GET /api/v1/tenants/tenant001/stores/store001/journals?terminals=1,2,3
```

### トランザクションタイプによる検索
```
GET /api/v1/tenants/tenant001/stores/store001/journals?transaction_types=101,102,201
```

### 日付範囲による検索
```
GET /api/v1/tenants/tenant001/stores/store001/journals?business_date_from=2024-01-01&business_date_to=2024-01-31
```

### レシート番号範囲による検索
```
GET /api/v1/tenants/tenant001/stores/store001/journals?receipt_no_from=R0001&receipt_no_to=R0100
```

### 全文検索
```
GET /api/v1/tenants/tenant001/stores/store001/journals?keywords=ITEM001
```

### 複合検索
```
GET /api/v1/tenants/tenant001/stores/store001/journals?terminals=1&transaction_types=101&business_date_from=2024-01-01&keywords=cash&sort=generateDateTime:-1&limit=50
```

## ソートオプション

ソートパラメータ形式: `field:direction`（field:1 昇順、field:-1 降順）

利用可能なソートフィールド:
- `generateDateTime` - ジャーナル作成タイムスタンプ
- `businessDate` - ビジネス日付
- `transactionNo` - トランザクション番号
- `receiptNo` - レシート番号
- `amount` - トランザクション金額

方向:
- `1` - 昇順
- `-1` - 降順（generateDateTimeのデフォルト）

## エラーレスポンス

APIは標準的なHTTPステータスコードと構造化されたエラーレスポンスを使用します：

```json
{
  "success": false,
  "code": 404,
  "message": "指定された条件に一致するジャーナルエントリーが見つかりません",
  "data": null,
  "operation": "search_journals"
}
```

### 共通ステータスコード
- `200` - 成功
- `201` - 正常に作成されました
- `400` - 不正なリクエスト
- `401` - 認証エラー
- `403` - アクセス拒否
- `404` - データが見つかりません
- `500` - 内部サーバーエラー

### エラーコードシステム

ジャーナルサービスは50XXX範囲のエラーコードを使用します：

- `50001` - ジャーナルエントリー作成エラー
- `50002` - ジャーナル検索エラー
- `50003` - トランザクションログ処理エラー
- `50004` - 現金ログ処理エラー
- `50005` - 端末ログ処理エラー
- `50006` - データ検証エラー
- `50007` - 外部サービス通信エラー
- `50008` - 重複イベント処理
- `50099` - 一般的なジャーナルサービスエラー

## イベント処理機能

### 冪等性処理
- 重複処理を防ぐためのイベントIDの使用
- 処理済みイベントIDをDapr state storeに保存
- 重複イベントに対して同じレスポンスを返す

### サービス通知
イベント処理後、ジャーナルサービスはソースサービスに通知します：

```python
# カートサービストランザクション用
POST /api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/delivery-status

# ターミナルサービス操作用
POST /api/v1/terminals/{terminal_id}/delivery-status
```

### サーキットブレーカー
- カスケード障害に対する保護
- 指数バックオフによる自動リトライ
- 外部サービス利用不可時の優雅な劣化

## データ保持

ジャーナルエントリーは監査とコンプライアンスのための永続的な記録です：
- 自動削除なし
- 手動アーカイブプロセスが必要
- ローカル規制への準拠

## パフォーマンス考慮事項

1. **ページネーション**: 大きな結果セットにはskip/limitを使用
2. **インデックス**: 検索フィールドに最適化されたインデックス
3. **全文検索**: journal_textのMongoDBテキストインデックス
4. **非同期処理**: すべての操作は非同期
5. **コネクションプーリング**: 効率的なデータベース接続

## 統合例

### 端末からのジャーナル作成
```javascript
// トランザクション完了後
const journalEntry = {
  transactionNo: "0001",
  transactionType: 101,
  businessDate: "2024-01-01",
  receiptNo: "R0001",
  amount: 99.00,
  journalText: formatJournalText(transaction),
  receiptText: formatReceiptText(transaction)
};

const response = await fetch(
  `/api/v1/tenants/${tenantId}/stores/${storeCode}/terminals/${terminalNo}/journals`,
  {
    method: 'POST',
    headers: {
      'X-API-Key': apiKey,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(journalEntry)
  }
);
```

### ジャーナル検索
```javascript
// 今日の売上トランザクションを検索
const params = new URLSearchParams({
  transaction_types: '101',
  business_date_from: '2024-01-01',
  business_date_to: '2024-01-01',
  sort: 'generateDateTime:-1',
  limit: '100'
});

const response = await fetch(
  `/api/v1/tenants/${tenantId}/stores/${storeCode}/journals?${params}`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
```

## 注意事項

1. **ジャーナルテキスト形式**: 監査目的のために人間が読めるようにする必要があります
2. **レシートテキスト形式**: レシートプリンター出力用にフォーマット
3. **トランザクションタイプ**: 一貫性のために標準コードを使用
4. **CamelCase規約**: すべてのJSONフィールドはcamelCaseを使用
5. **タイムスタンプ**: すべてのタイムスタンプはISO 8601形式（UTC）
6. **冪等性**: イベント処理は冪等です
7. **コンプライアンス**: 規制監査要件のために設計

ジャーナルサービスは、Kugelpos POSシステムの監査とコンプライアンスの基盤を提供し、すべてのトランザクションの永続性、検索可能性、規制準拠を保証します。