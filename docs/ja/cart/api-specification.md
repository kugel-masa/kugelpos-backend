# カートサービスAPI仕様

## 概要

カートサービスは、Kugelpos POSシステムのショッピングカートとトランザクション処理APIを提供します。ステートマシンパターンによるトランザクション管理、動的な商品操作、プラグイン可能な決済処理、リアルタイムの価格計算を処理し、POSシステムの中核となる販売機能を実現します。

## ベースURL
- ローカル環境: `http://localhost:8003`
- 本番環境: `https://cart.{domain}`

## 認証

カートサービスはAPIキー認証を使用します：

- ヘッダーに含める: `X-API-Key: {api_key}`
- クエリパラメータを含める: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- すべてのエンドポイントで必須

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

## カート状態

カートは以下の状態を持ちます：

| 状態 | 説明 | 許可される操作 |
|------|------|----------------|
| initial | 初期状態 | カート初期化 |
| idle | アイドル（商品なし） | 商品追加 |
| entering_item | 商品入力中 | 商品操作、チェックアウト |
| paying | 支払い処理中 | 決済追加、完了、キャンセル |
| completed | 取引完了 | 読み取りのみ |
| cancelled | キャンセル済み | 読み取りのみ |

## APIエンドポイント

### カート管理

#### 1. カート作成
**POST** `/api/v1/carts`

新規ショッピングカートを作成します。

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "staffId": "STF001",
  "userName": "山田太郎",
  "customerId": "CUST001"
}
```

**フィールド説明:**
- `staffId` (string, オプション): スタッフID
- `userName` (string, オプション): ユーザー名
- `customerId` (string, オプション): 顧客ID

**リクエスト例:**
```bash
curl -X POST "http://localhost:8003/api/v1/carts?terminal_id=tenant001-STORE001-1" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "staffId": "STF001",
    "userName": "山田太郎"
  }'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "カートの作成に成功しました",
  "data": {
    "cartId": "cart_20240101_001",
    "terminalId": "tenant001-STORE001-1",
    "state": "idle",
    "businessDate": "2024-01-01",
    "businessCounter": 100,
    "openCounter": 1,
    "transactionNo": "0001",
    "items": [],
    "subtotal": 0.00,
    "taxAmount": 0.00,
    "totalAmount": 0.00,
    "createdAt": "2024-01-01T10:00:00Z"
  },
  "operation": "create_cart"
}
```

#### 2. カート情報取得
**GET** `/api/v1/carts/{cart_id}`

カートの詳細情報を取得します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエスト例:**
```bash
curl -X GET "http://localhost:8003/api/v1/carts/cart_20240101_001?terminal_id=tenant001-STORE001-1" \
  -H "X-API-Key: {api_key}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "カート情報を取得しました",
  "data": {
    "cartId": "cart_20240101_001",
    "terminalId": "tenant001-STORE001-1",
    "state": "entering_item",
    "businessDate": "2024-01-01",
    "transactionNo": "0001",
    "items": [
      {
        "itemId": "item_001",
        "productId": "prod_001",
        "barcode": "4901234567890",
        "name": "コーヒー（ホット）",
        "price": 300.00,
        "quantity": 2,
        "subtotal": 600.00,
        "taxType": "standard",
        "taxRate": 10.0,
        "taxAmount": 60.00,
        "discount": 0.00,
        "total": 660.00
      }
    ],
    "subtotal": 600.00,
    "discountAmount": 0.00,
    "taxAmount": 60.00,
    "totalAmount": 660.00,
    "itemCount": 1,
    "totalQuantity": 2,
    "payments": [],
    "createdAt": "2024-01-01T10:00:00Z",
    "updatedAt": "2024-01-01T10:05:00Z"
  },
  "operation": "get_cart"
}
```

### 商品操作

#### 3. 商品追加
**POST** `/api/v1/carts/{cart_id}/items`

カートに商品を追加します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "barcode": "4901234567890",
  "quantity": 2,
  "price": 300.00
}
```

**フィールド説明:**
- `barcode` (string, 必須): 商品バーコード
- `quantity` (number, デフォルト: 1): 数量
- `price` (number, オプション): 手動価格（価格変更権限が必要）

**リクエスト例:**
```bash
curl -X POST "http://localhost:8003/api/v1/carts/cart_20240101_001/items?terminal_id=tenant001-STORE001-1" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "barcode": "4901234567890",
    "quantity": 2
  }'
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "商品をカートに追加しました",
  "data": {
    "itemId": "item_001",
    "productId": "prod_001",
    "barcode": "4901234567890",
    "name": "コーヒー（ホット）",
    "price": 300.00,
    "quantity": 2,
    "subtotal": 600.00,
    "taxAmount": 60.00,
    "total": 660.00,
    "cartTotals": {
      "subtotal": 600.00,
      "taxAmount": 60.00,
      "totalAmount": 660.00
    }
  },
  "operation": "add_item"
}
```

#### 4. 商品更新
**PUT** `/api/v1/carts/{cart_id}/items/{item_id}`

カート内の商品情報を更新します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID
- `item_id` (string, 必須): アイテムID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "quantity": 3,
  "discountDetail": {
    "amount": 50,
    "reason": "商品割引"
  }
}
```

**フィールド説明:**
- `quantity` (number, オプション): 新しい数量
- `discountDetail` (object, オプション): 商品レベル割引
  - `amount` (integer, 必須): 割引金額
  - `reason` (string, 必須): 割引理由
- `price` (number, オプション): 新しい価格（権限必要）

#### 5. 商品削除
**DELETE** `/api/v1/carts/{cart_id}/items/{item_id}`

カートから商品を削除します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID
- `item_id` (string, 必須): アイテムID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

### チェックアウトと決済

#### 6. チェックアウト開始
**POST** `/api/v1/carts/{cart_id}/checkout`

チェックアウトプロセスを開始し、カートを支払い状態に遷移します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "customerId": "CUST001",
  "promotions": ["PROMO001", "PROMO002"]
}
```

**フィールド説明:**
- `customerId` (string, オプション): 顧客ID（ポイント利用など）
- `promotions` (array[string], オプション): 適用するプロモーションコード

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "チェックアウトを開始しました",
  "data": {
    "cartId": "cart_20240101_001",
    "state": "paying",
    "subtotal": 1000.00,
    "appliedPromotions": [
      {
        "promotionId": "PROMO001",
        "name": "10%割引",
        "discountAmount": 100.00
      }
    ],
    "discountAmount": 100.00,
    "taxAmount": 90.00,
    "totalAmount": 990.00,
    "paymentDue": 990.00
  },
  "operation": "start_checkout"
}
```

#### 7. 決済追加
**POST** `/api/v1/carts/{cart_id}/payments`

カートに決済を追加します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "paymentCode": "CASH",
  "amount": 1000,
  "detail": {
    "tenderedAmount": 1000,
    "reference": "現金支払い"
  }
}
```

**フィールド説明:**
- `paymentCode` (string, 必須): 決済方法コード
- `amount` (integer, 必須): 決済金額（整数）
- `detail` (object, オプション): 決済詳細情報
  - `tenderedAmount` (integer, 現金時必須): 受取金額
  - `reference` (string, オプション): 決済参照情報

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "決済を追加しました",
  "data": {
    "paymentId": "pay_001",
    "paymentCode": "CASH",
    "paymentMethodName": "現金",
    "amount": 990,
    "tenderedAmount": 1000,
    "changeAmount": 10,
    "status": "approved",
    "remainingAmount": 0,
    "canComplete": true
  },
  "operation": "add_payment"
}
```

#### 8. 取引完了
**POST** `/api/v1/carts/{cart_id}/complete`

取引を完了し、レシートを生成します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "printReceipt": true,
  "emailReceipt": "customer@example.com"
}
```

**フィールド説明:**
- `printReceipt` (boolean, デフォルト: true): レシート印刷フラグ
- `emailReceipt` (string, オプション): 電子レシート送信先

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "取引が完了しました",
  "data": {
    "cartId": "cart_20240101_001",
    "state": "completed",
    "transactionNo": "0001",
    "receiptNo": "R000001",
    "totalAmount": 990.00,
    "changeAmount": 10.00,
    "completedAt": "2024-01-01T10:15:00Z",
    "receipt": {
      "text": "=== レシート ===\n...",
      "printed": true,
      "emailed": true
    },
    "journal": {
      "text": "=== ジャーナル ===\n...",
      "sent": true
    }
  },
  "operation": "complete_transaction"
}
```

### カート操作

#### 9. カートキャンセル
**POST** `/api/v1/carts/{cart_id}/cancel`

カートをキャンセルします。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "reason": "顧客都合によるキャンセル",
  "supervisorId": "SUP001"
}
```

**フィールド説明:**
- `reason` (string, 必須): キャンセル理由
- `supervisorId` (string, 支払い後は必須): 承認者ID

#### 10. カート保留
**POST** `/api/v1/carts/{cart_id}/suspend`

カートを保留状態にします。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "note": "顧客が追加商品を取りに行っています"
}
```

#### 11. カート再開
**POST** `/api/v1/carts/{cart_id}/resume`

保留中のカートを再開します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

### 状態管理

#### 12. カート状態取得
**GET** `/api/v1/carts/{cart_id}/state`

カートの現在の状態を取得します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "カート状態を取得しました",
  "data": {
    "currentState": "entering_item",
    "allowedTransitions": ["checkout", "cancel", "suspend"],
    "stateHistory": [
      {
        "state": "initial",
        "timestamp": "2024-01-01T10:00:00Z"
      },
      {
        "state": "idle",
        "timestamp": "2024-01-01T10:00:01Z"
      },
      {
        "state": "entering_item",
        "timestamp": "2024-01-01T10:05:00Z"
      }
    ]
  },
  "operation": "get_cart_state"
}
```

### その他の操作

#### 13. 価格再計算
**POST** `/api/v1/carts/{cart_id}/recalculate`

カートの価格を再計算します（プロモーション変更時など）。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

#### 14. レシート再印刷
**POST** `/api/v1/carts/{cart_id}/reprint-receipt`

完了した取引のレシートを再印刷します。

**パスパラメータ:**
- `cart_id` (string, 必須): カートID

**クエリパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**リクエストボディ:**
```json
{
  "reason": "顧客要求",
  "copyNumber": 1
}
```

### システムエンドポイント

#### 15. ヘルスチェック
**GET** `/health`

サービスヘルスと依存関係ステータスをチェックします。

**リクエスト例:**
```bash
curl -X GET "http://localhost:8003/health"
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
    "stateStore": "connected",
    "pubsub": "connected",
    "timestamp": "2024-01-01T10:00:00Z"
  },
  "operation": "health_check"
}
```

## イベント通知（Dapr Pub/Sub）

### トランザクションログイベント
**トピック:** `tranlog_report`

取引完了時に発行されるイベント：
```json
{
  "eventId": "evt_123456",
  "tenantId": "tenant001",
  "storeCode": "STORE001",
  "terminalNo": 1,
  "transactionNo": "0001",
  "transactionType": 101,
  "businessDate": "2024-01-01",
  "businessCounter": 100,
  "openCounter": 1,
  "receiptNo": "R000001",
  "amount": 990.00,
  "quantity": 2,
  "staffId": "STF001",
  "receiptText": "=== レシート ===\n...",
  "journalText": "=== ジャーナル ===\n...",
  "timestamp": "2024-01-01T10:15:00Z"
}
```

### ステータス更新イベント
**トピック:** `tranlog_status`

カート状態変更時に発行されるイベント：
```json
{
  "eventId": "evt_789012",
  "cartId": "cart_20240101_001",
  "terminalId": "tenant001-STORE001-1",
  "previousState": "idle",
  "newState": "entering_item",
  "timestamp": "2024-01-01T10:05:00Z"
}
```

## エラーレスポンス

APIは標準的なHTTPステータスコードと構造化されたエラーレスポンスを使用します：

```json
{
  "success": false,
  "code": 404,
  "message": "指定されたカートが見つかりません",
  "data": null,
  "operation": "get_cart"
}
```

### 共通ステータスコード
- `200` - 成功
- `201` - 正常に作成されました
- `400` - 不正なリクエスト（検証エラー）
- `401` - 認証失敗
- `403` - アクセス拒否
- `404` - リソースが見つかりません
- `409` - 競合（無効な状態遷移など）
- `500` - 内部サーバーエラー

### エラーコードシステム

カートサービスは40XXX範囲のエラーコードを使用します：

- `40001` - カートが見つかりません
- `40002` - 無効な状態遷移
- `40003` - 商品が見つかりません
- `40004` - 在庫不足
- `40005` - 決済処理エラー
- `40006` - 決済金額不足
- `40007` - プロモーション適用エラー
- `40008` - 税金計算エラー
- `40009` - タイムアウトエラー
- `40099` - 一般的なサービスエラー

## 決済方法コード

標準的な決済方法コード：

| コード | 説明 | 釣銭 |
|--------|------|------|
| CASH | 現金 | 可 |
| CREDIT_VISA | VISAカード | 不可 |
| CREDIT_MASTER | Masterカード | 不可 |
| CREDIT_JCB | JCBカード | 不可 |
| EMONEY_SUICA | Suica | 不可 |
| EMONEY_PASMO | PASMO | 不可 |
| QR_PAYPAY | PayPay | 不可 |
| QR_LINEPAY | LINE Pay | 不可 |

## データ形式

### 金額
- すべての金額は小数点以下2桁までの数値
- 税込み/税抜きは設定により決定
- 負の値は返品や割引に使用

### 数量
- 小数点対応（0.001単位まで）
- 重量販売商品に対応

### 日付時刻
- ISO 8601形式（UTC）
- `YYYY-MM-DDTHH:mm:ssZ`

## パフォーマンス

### タイムアウト
- カート操作: 30秒
- 決済処理: 60秒
- 外部サービス連携: 30秒

### 制限事項
- カートあたり最大商品数: 1000
- 同時カート数: 端末あたり10
- カート有効期限: 24時間

## セキュリティ

### 認証
- すべてのエンドポイントでAPIキー必須
- 端末IDの一致確認

### データ保護
- 決済情報の暗号化
- PCI DSS準拠
- センシティブデータのマスキング

### 監査
- すべての操作のログ記録
- 状態遷移の追跡
- エラーの詳細記録

## 注意事項

1. **ステートマシン**: カート状態に応じた操作制限
2. **冪等性**: 重要な操作は冪等性を保証
3. **トランザクション**: データ整合性の保証
4. **CamelCase規約**: すべてのJSONフィールドはcamelCase形式を使用
5. **非同期処理**: イベント発行は非同期
6. **プラグイン**: 決済方法とプロモーションは動的ロード
7. **マルチテナント**: テナント間の完全な分離

カートサービスは、Kugelpos POSシステムの販売処理の中核を提供し、柔軟なトランザクション管理と拡張可能なビジネスロジックを実現します。