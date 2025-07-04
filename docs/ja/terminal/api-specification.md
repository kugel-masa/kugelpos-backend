# ターミナルサービスAPI仕様

## 概要

ターミナルサービスは、Kugelpos POSシステムにおける端末管理、店舗運営、現金管理APIを提供します。端末の初期化、ビジネス日付管理、レジ開け・締め操作、現金入出金、APIキー管理を処理し、POS端末の完全なライフサイクル管理を実現します。

## ベースURL
- ローカル環境: `http://localhost:8001`
- 本番環境: `https://terminal.{domain}`

## 認証

ターミナルサービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダーに含める: `Authorization: Bearer {token}`
- トークン取得元: アカウントサービスの `/api/v1/accounts/token`
- 管理操作に必要

### 2. APIキー認証
- ヘッダーに含める: `X-API-Key: {api_key}`
- クエリパラメータを含める: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- POS端末操作に使用

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

## APIエンドポイント

### 端末管理

#### 1. 端末作成
**POST** `/api/v1/terminals`

新規POS端末を店舗に関連付けて作成します。

**認証:** JWTトークンが必要

**リクエストボディ:**
```json
{
  "storeCode": "store001",
  "terminalNo": 1,
  "description": "フロントカウンター端末"
}
```

**フィールド説明:**
- `storeCode` (string, 必須): 端末を作成する店舗コード
- `terminalNo` (integer, 必須): 店舗内で一意の端末番号（1-999）
- `description` (string, 必須): 端末の説明

**注意:** テナントIDはリクエストボディではなく、JWT認証トークンから抽出されます。

**リクエスト例:**
```bash
curl -X POST "http://localhost:8001/api/v1/terminals" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "storeCode": "store001",
    "terminalNo": 1,
    "description": "フロントカウンター端末"
  }'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "端末の登録に成功しました",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "tenantId": "tenant001",
    "storeCode": "STORE001",
    "terminalNo": 1,
    "businessDate": "2024-01-01",
    "openCounter": 0,
    "businessCounter": 0,
    "status": "closed",
    "cashBalance": 0.0,
    "apiKey": "sk_live_1234567890abcdef",
    "createdAt": "2024-01-01T10:00:00Z"
  },
  "operation": "register_terminal"
}
```

#### 2. 端末情報取得
**GET** `/api/v1/terminals/{terminal_id}`

端末の詳細情報を取得します。

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID（形式: {tenant_id}-{store_code}-{terminal_no}）

**クエリパラメータ:**
- `terminal_id` (string, APIキー認証時は必須): 端末IDの確認用

**リクエスト例:**
```bash
curl -X GET "http://localhost:8001/api/v1/terminals/tenant001-STORE001-1" \
  -H "X-API-Key: {api_key}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "端末情報を取得しました",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "tenantId": "tenant001",
    "storeCode": "STORE001",
    "terminalNo": 1,
    "businessDate": "2024-01-01",
    "openCounter": 1,
    "businessCounter": 100,
    "status": "open",
    "cashBalance": 1500.00,
    "lastOpenedAt": "2024-01-01T08:00:00Z",
    "lastOpenedBy": "STF001",
    "updatedAt": "2024-01-01T15:30:00Z"
  },
  "operation": "get_terminal"
}
```

#### 3. 端末情報更新
**PUT** `/api/v1/terminals/{terminal_id}`

端末の設定情報を更新します。

**認証:** JWTトークンが必要

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "status": "maintenance",
  "settings": {
    "receiptHeader": "Welcome to Store 001",
    "taxRate": 10
  }
}
```

### ビジネス日付管理

#### 4. ビジネス日付取得
**GET** `/api/v1/terminals/{terminal_id}/business-date`

端末の現在のビジネス日付を取得します。

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "ビジネス日付を取得しました",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "businessDate": "2024-01-01",
    "actualDate": "2024-01-02",
    "lastUpdated": "2024-01-01T00:00:00Z"
  },
  "operation": "get_business_date"
}
```

#### 5. ビジネス日付更新
**PUT** `/api/v1/terminals/{terminal_id}/business-date`

端末のビジネス日付を手動で更新します。

**認証:** JWTトークンが必要

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "businessDate": "2024-01-02",
  "reason": "日次処理遅延のため"
}
```

### レジ開け・締め操作

#### 6. レジ開け
**POST** `/api/v1/terminals/{terminal_id}/open`

端末をレジ開け状態にし、日次業務を開始します。

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**クエリパラメータ:**
- `terminal_id` (string, APIキー認証時は必須): 端末IDの確認用

**リクエストボディ:**
```json
{
  "initialAmount": 10000.00,
  "staffId": "STF001",
  "openingNote": "通常営業開始"
}
```

**フィールド説明:**
- `initialAmount` (number, 必須): 開始時現金額
- `staffId` (string, 必須): スタッフID
- `openingNote` (string, オプション): 開店メモ

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "レジ開けに成功しました",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "businessDate": "2024-01-01",
    "openCounter": 1,
    "businessCounter": 100,
    "status": "open",
    "cashBalance": 10000.00,
    "openedAt": "2024-01-01T08:00:00Z",
    "openedBy": "STF001",
    "receiptNo": "OP000001",
    "receiptText": "=== レジ開け ===\n..."
  },
  "operation": "open_terminal"
}
```

#### 7. レジ締め
**POST** `/api/v1/terminals/{terminal_id}/close`

端末をレジ締め状態にし、日次業務を終了します。

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**クエリパラメータ:**
- `terminal_id` (string, APIキー認証時は必須): 端末IDの確認用

**リクエストボディ:**
```json
{
  "physicalAmount": 25800.00,
  "staffId": "STF001",
  "closingNote": "通常営業終了"
}
```

**フィールド説明:**
- `physicalAmount` (number, 必須): 実現金カウント額
- `staffId` (string, 必須): スタッフID
- `closingNote` (string, オプション): 閉店メモ

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "レジ締めに成功しました",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "businessDate": "2024-01-01",
    "status": "closed",
    "theoreticalAmount": 25850.00,
    "physicalAmount": 25800.00,
    "difference": -50.00,
    "transactionCount": 152,
    "salesTotal": 15850.00,
    "closedAt": "2024-01-01T22:00:00Z",
    "closedBy": "STF001",
    "receiptNo": "CL000001",
    "receiptText": "=== レジ締め ===\n...",
    "reportGenerated": true
  },
  "operation": "close_terminal"
}
```

### 現金管理

#### 8. 現金入金
**POST** `/api/v1/terminals/{terminal_id}/cash-in`

レジに現金を追加します。

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**クエリパラメータ:**
- `terminal_id` (string, APIキー認証時は必須): 端末IDの確認用

**リクエストボディ:**
```json
{
  "amount": 5000.00,
  "reason": "釣銭補充",
  "staffId": "STF001",
  "note": "1000円札×5枚"
}
```

**フィールド説明:**
- `amount` (number, 必須): 入金額
- `reason` (string, 必須): 入金理由
- `staffId` (string, 必須): スタッフID
- `note` (string, オプション): 追加メモ

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "現金入金に成功しました",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "operationType": "cash_in",
    "amount": 5000.00,
    "previousBalance": 15000.00,
    "newBalance": 20000.00,
    "receiptNo": "CI000001",
    "timestamp": "2024-01-01T14:00:00Z",
    "receiptText": "=== 現金入金 ===\n..."
  },
  "operation": "cash_in"
}
```

#### 9. 現金出金
**POST** `/api/v1/terminals/{terminal_id}/cash-out`

レジから現金を取り出します。

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**クエリパラメータ:**
- `terminal_id` (string, APIキー認証時は必須): 端末IDの確認用

**リクエストボディ:**
```json
{
  "amount": 10000.00,
  "reason": "金庫預け入れ",
  "staffId": "STF001",
  "note": "中間預け入れ"
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "現金出金に成功しました",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "operationType": "cash_out",
    "amount": 10000.00,
    "previousBalance": 20000.00,
    "newBalance": 10000.00,
    "receiptNo": "CO000001",
    "timestamp": "2024-01-01T16:00:00Z",
    "receiptText": "=== 現金出金 ===\n..."
  },
  "operation": "cash_out"
}
```

#### 10. 現金残高取得
**GET** `/api/v1/terminals/{terminal_id}/cash-balance`

現在の現金残高を取得します。

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "現金残高を取得しました",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "currentBalance": 10000.00,
    "initialAmount": 10000.00,
    "totalCashIn": 5000.00,
    "totalCashOut": 10000.00,
    "totalSales": 15850.00,
    "totalReturns": 850.00,
    "lastUpdated": "2024-01-01T16:00:00Z"
  },
  "operation": "get_cash_balance"
}
```

### APIキー管理

#### 11. APIキー生成
**POST** `/api/v1/terminals/{terminal_id}/api-keys`

端末用の新規APIキーを生成します。

**認証:** JWTトークンが必要

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "description": "メインPOS端末用",
  "expiresAt": "2025-01-01T00:00:00Z"
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "APIキーの生成に成功しました",
  "data": {
    "keyId": "key_1234567890",
    "apiKey": "sk_live_abcdefghijklmnop",
    "terminalId": "tenant001-STORE001-1",
    "description": "メインPOS端末用",
    "createdAt": "2024-01-01T10:00:00Z",
    "expiresAt": "2025-01-01T00:00:00Z"
  },
  "operation": "create_api_key"
}
```

#### 12. APIキー一覧取得
**GET** `/api/v1/terminals/{terminal_id}/api-keys`

端末の有効なAPIキー一覧を取得します。

**認証:** JWTトークンが必要

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "APIキー一覧を取得しました",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "keys": [
      {
        "keyId": "key_1234567890",
        "description": "メインPOS端末用",
        "createdAt": "2024-01-01T10:00:00Z",
        "expiresAt": "2025-01-01T00:00:00Z",
        "lastUsed": "2024-01-01T15:30:00Z",
        "isActive": true
      }
    ]
  },
  "operation": "list_api_keys"
}
```

#### 13. APIキー無効化
**DELETE** `/api/v1/terminals/{terminal_id}/api-keys/{key_id}`

APIキーを無効化します。

**認証:** JWTトークンが必要

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID
- `key_id` (string, 必須): キーID

### システムエンドポイント

#### 14. ヘルスチェック
**GET** `/health`

サービスヘルスと依存関係ステータスをチェックします。

**リクエスト例:**
```bash
curl -X GET "http://localhost:8001/health"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "サービスは正常です",
  "data": {
    "status": "healthy",
    "database": "connected",
    "timestamp": "2024-01-01T10:00:00Z"
  },
  "operation": "health_check"
}
```

## イベント通知（Dapr Pub/Sub）

### 現金操作イベント
**トピック:** `cashlog_report`

現金入出金時に発行されるイベント：
```json
{
  "eventId": "evt_123456",
  "tenantId": "tenant001",
  "storeCode": "STORE001",
  "terminalNo": 1,
  "operationType": "cash_in",
  "amount": 5000.00,
  "businessDate": "2024-01-01",
  "businessCounter": 100,
  "openCounter": 1,
  "receiptNo": "CI000001",
  "reason": "釣銭補充",
  "staffId": "STF001",
  "receiptText": "=== 現金入金 ===\n...",
  "journalText": "現金入金操作\n...",
  "timestamp": "2024-01-01T14:00:00Z"
}
```

### 開け・締めイベント
**トピック:** `opencloselog_report`

レジ開け・締め時に発行されるイベント：
```json
{
  "eventId": "evt_789012",
  "tenantId": "tenant001",
  "storeCode": "STORE001",
  "terminalNo": 1,
  "operationType": "open",
  "businessDate": "2024-01-01",
  "businessCounter": 100,
  "openCounter": 1,
  "initialAmount": 10000.00,
  "staffId": "STF001",
  "receiptText": "=== レジ開け ===\n...",
  "journalText": "レジ開け\n...",
  "timestamp": "2024-01-01T08:00:00Z"
}
```

## エラーレスポンス

APIは標準的なHTTPステータスコードと構造化されたエラーレスポンスを使用します：

```json
{
  "success": false,
  "code": 404,
  "message": "指定された端末が見つかりません",
  "data": null,
  "operation": "get_terminal"
}
```

### 共通ステータスコード
- `200` - 成功
- `201` - 正常に作成されました
- `400` - 不正なリクエスト（検証エラー）
- `401` - 認証失敗
- `403` - アクセス拒否
- `404` - リソースが見つかりません
- `409` - 競合（端末が既に開いているなど）
- `500` - 内部サーバーエラー

### エラーコードシステム

ターミナルサービスは20XXX範囲のエラーコードを使用します：

- `20001` - 端末登録エラー
- `20002` - 端末が見つかりません
- `20003` - 無効なAPIキー
- `20004` - 端末が既に開いています
- `20005` - 端末が既に閉じています
- `20006` - 不十分な現金残高
- `20007` - 無効なビジネス日付
- `20008` - 端末状態エラー
- `20009` - 現金操作エラー
- `20099` - 一般的なサービスエラー

## セキュリティの考慮事項

### APIキーセキュリティ
- SHA-256ハッシュ化で保存
- 定期的なキーローテーション推奨
- 有効期限の設定
- 最小権限の原則

### アクセス制御
- 管理操作にはJWT認証が必要
- 端末操作にはAPIキー認証
- テナント分離の厳格な実施
- 操作ログの完全な記録

### データ保護
- センシティブデータの暗号化
- セキュアな通信（HTTPS）
- 監査証跡の保持
- PCI DSSコンプライアンス

## レート制限

現在、ターミナルサービスは明示的なレート制限を実装していませんが、以下の制限が追加される可能性があります：

- 端末ごとに1分あたり60リクエスト
- APIキーごとに1時間あたり1000リクエスト
- バーストトラフィック保護

## 注意事項

1. **端末ID形式**: `{tenant_id}-{store_code}-{terminal_no}`形式を使用
2. **ビジネス日付**: カレンダー日付とは独立して管理
3. **現金管理**: すべての現金操作は監査証跡を生成
4. **CamelCase規約**: すべてのJSONフィールドはcamelCase形式を使用
5. **非同期処理**: イベント発行は非同期で処理
6. **冪等性**: 重要な操作は冪等性を保証
7. **マルチテナント**: 完全なテナント分離を実施

ターミナルサービスは、Kugelpos POSシステムにおける端末運用の基盤を提供し、信頼性の高い店舗運営と正確な現金管理を保証します。