# カートサービス API仕様書

## 概要

ショッピングカートとトランザクション処理を管理するサービスです。ステートマシンパターンによるカート状態管理を提供します。

## サービス情報

- **ポート**: 8003
- **フレームワーク**: FastAPI
- **データベース**: MongoDB (Motor async driver)

## ベースURL

- ローカル環境: `http://localhost:8003`
- 本番環境: `https://cart.{domain}`

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

### カート

### 4. カート作成

**POST** `/api/v1/carts`

新しいショッピングカートを作成します。現在の端末に対して、オプションのユーザー情報を含む新しいカートを初期化します。

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `transactionType` | integer | No | - |
| `userId` | string | No | - |
| `userName` | string | No | - |

**リクエスト例:**
```json
{
  "transactionType": 101,
  "userId": "string",
  "userName": "string"
}
```

**レスポンス:**

**dataフィールド:** `CartCreateResponse`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `cartId` | string | Yes | - |

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
    "cartId": "string"
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

### 5. カート取得

**GET** `/api/v1/carts/{cart_id}`

カートを取得します。指定されたカートの詳細情報を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 6. 会計完了

**POST** `/api/v1/carts/{cart_id}/bill`

会計を完了します。支払処理を完了し、取引レコードとレシートを生成します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 7. 取引取消

**POST** `/api/v1/carts/{cart_id}/cancel`

取引を取消します。カートを取消状態にし、以降の処理を防止します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 8. カート値引追加

**POST** `/api/v1/carts/{cart_id}/discounts`

Add discount to the entire cart.

Applies one or more discounts at the cart level, affecting the total price.

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**リクエストボディ:**

**リクエスト例:**
```json
[
  {
    "discountType": "string",
    "discountValue": 0.0,
    "discountDetail": "string"
  }
]
```

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 9. 商品追加

**POST** `/api/v1/carts/{cart_id}/lineItems`

カートに商品を追加します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**リクエストボディ:**

**リクエスト例:**
```json
[
  {
    "itemCode": "string",
    "quantity": 0,
    "unitPrice": 0.0
  }
]
```

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 10. 明細取消

**POST** `/api/v1/carts/{cart_id}/lineItems/{lineNo}/cancel`

明細を取消します。指定された明細を取消状態にします。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `lineNo` | integer | Yes | - |
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 11. 明細値引追加

**POST** `/api/v1/carts/{cart_id}/lineItems/{lineNo}/discounts`

カートに商品を追加します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `lineNo` | integer | Yes | - |
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**リクエストボディ:**

**リクエスト例:**
```json
[
  {
    "discountType": "string",
    "discountValue": 0.0,
    "discountDetail": "string"
  }
]
```

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 12. 数量変更

**PATCH** `/api/v1/carts/{cart_id}/lineItems/{lineNo}/quantity`

数量を更新します。指定された明細の数量を変更します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `lineNo` | integer | Yes | - |
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `quantity` | integer | Yes | - |

**リクエスト例:**
```json
{
  "quantity": 0
}
```

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 13. 単価変更

**PATCH** `/api/v1/carts/{cart_id}/lineItems/{lineNo}/unitPrice`

単価を更新します。指定された明細の単価を変更します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `lineNo` | integer | Yes | - |
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**リクエストボディ:**

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `unitPrice` | number | Yes | - |

**リクエスト例:**
```json
{
  "unitPrice": 0.0
}
```

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 14. 支払処理

**POST** `/api/v1/carts/{cart_id}/payments`

Add payments to a cart.

Processes one or more payment methods against the cart.

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**リクエストボディ:**

**リクエスト例:**
```json
[
  {
    "paymentCode": "string",
    "amount": 0,
    "detail": "string"
  }
]
```

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 15. 商品入力再開

**POST** `/api/v1/carts/{cart_id}/resume-item-entry`

商品入力を再開します。支払状態から商品入力状態に戻します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 16. 小計

**POST** `/api/v1/carts/{cart_id}/subtotal`

小計を計算します。カートの小計と税金情報を計算して更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**レスポンス:**

**dataフィールド:** `Cart`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### トランザクション

### 17. 取引検索

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

取引を取得します。指定された条件に一致する取引情報を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `business_date` | string | No | - | - |
| `open_counter` | integer | No | - | - |
| `transaction_type` | array | No | - | - |
| `receipt_no` | integer | No | - | - |
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `include_cancelled` | boolean | No | False | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | Yes | - | - |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `array[Tran]`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |

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
      "tenantId": "string",
      "storeCode": "string",
      "storeName": "string",
      "terminalNo": 0,
      "totalAmount": 0.0,
      "totalAmountWithTax": 0.0,
      "totalQuantity": 0,
      "totalDiscountAmount": 0.0,
      "depositAmount": 0.0,
      "changeAmount": 0.0
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

### 18. 取引番号で取得

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}`

取引を取得します。指定された条件に一致する取引情報を返します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |
| `transaction_no` | integer | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |
| `is_terminal_service` | string | No | False | - |

**レスポンス:**

**dataフィールド:** `Tran`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 19. 配信状態通知

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/delivery-status`

配信状態を通知します。取引の配信状態を更新します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |

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

### 20. 返品処理

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return`

返品を処理します。元の取引に対する返品取引を作成します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |
| `transaction_no` | integer | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

**リクエスト例:**
```json
[
  {
    "paymentCode": "string",
    "amount": 0,
    "detail": "string"
  }
]
```

**レスポンス:**

**dataフィールド:** `Tran`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### 21. 取消処理

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void`

取引を取消（無効化）します。取引を取消状態にし、取消レコードを作成します。

**パスパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |
| `transaction_no` | integer | Yes | - |

**クエリパラメータ:**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |
| `is_terminal_service` | string | No | False | - |

**リクエストボディ:**

**リクエスト例:**
```json
[
  {
    "paymentCode": "string",
    "amount": 0,
    "detail": "string"
  }
]
```

**レスポンス:**

**dataフィールド:** `Tran`

| フィールド | 型 | 必須 | 説明 |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |

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
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
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

### キャッシュ

### 22. 端末キャッシュクリア

**DELETE** `/api/v1/cache/terminal`

端末キャッシュをクリアします。キャッシュされたデータを削除します。

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

### 23. 端末キャッシュ状態取得

**GET** `/api/v1/cache/terminal/status`

端末キャッシュの状態を取得します。キャッシュされたデータと最終更新時刻を返します。

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
