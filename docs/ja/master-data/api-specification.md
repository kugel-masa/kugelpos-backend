# マスターデータサービスAPI仕様

## 概要

マスターデータサービスは、Kugelpos POSシステムの中央集権的なマスターデータ管理APIを提供します。商品カタログ、決済方法、税金ルール、プロモーション、スタッフ情報の管理と配信を処理し、システム全体で使用される基本データの一貫性を保証します。

## ベースURL
- ローカル環境: `http://localhost:8002`
- 本番環境: `https://master-data.{domain}`

## 認証

マスターデータサービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダーに含める: `Authorization: Bearer {token}`
- トークン取得元: アカウントサービスの `/api/v1/accounts/token`
- 管理操作に必要

### 2. APIキー認証
- ヘッダーに含める: `X-API-Key: {api_key}`
- クエリパラメータを含める: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- POS端末からの読み取り専用アクセスに使用

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

### 商品管理

#### 1. 商品一覧取得
**GET** `/api/v1/tenants/{tenant_id}/products`

商品の一覧を取得します。ページネーションとフィルタリングをサポートします。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**クエリパラメータ:**
- `category` (string, オプション): カテゴリーでフィルタ
- `barcode` (string, オプション): バーコードで検索
- `name` (string, オプション): 商品名で検索
- `is_active` (boolean, オプション): アクティブ状態でフィルタ
- `skip` (integer, デフォルト: 0): ページネーションオフセット
- `limit` (integer, デフォルト: 20, 最大: 100): ページサイズ
- `sort` (string, オプション): ソートフィールドと順序（例: "name:asc"）

**リクエスト例:**
```bash
curl -X GET "http://localhost:8002/api/v1/tenants/tenant001/products?category=beverages&is_active=true&limit=50" \
  -H "Authorization: Bearer {token}"
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "商品一覧を取得しました",
  "data": {
    "items": [
      {
        "productId": "prod_001",
        "name": "コーヒー（ホット）",
        "description": "ブレンドコーヒー",
        "category": "beverages",
        "subcategory": "hot_drinks",
        "barcode": "4901234567890",
        "sku": "BEV-001",
        "price": 300.00,
        "taxType": "standard",
        "isActive": true,
        "attributes": {
          "size": "regular",
          "temperature": "hot"
        },
        "imageUrl": "https://example.com/coffee.jpg",
        "createdAt": "2024-01-01T10:00:00Z",
        "updatedAt": "2024-01-05T15:30:00Z"
      }
    ],
    "total": 150,
    "skip": 0,
    "limit": 50
  },
  "operation": "get_products"
}
```

#### 2. 商品登録
**POST** `/api/v1/tenants/{tenant_id}/products`

新規商品を登録します。

**認証:** JWTトークンが必要

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**リクエストボディ:**
```json
{
  "name": "アイスコーヒー",
  "description": "アイスブレンドコーヒー",
  "category": "beverages",
  "subcategory": "cold_drinks",
  "barcode": "4901234567897",
  "sku": "BEV-002",
  "price": 350.00,
  "cost": 120.00,
  "taxType": "standard",
  "isActive": true,
  "attributes": {
    "size": "regular",
    "temperature": "cold"
  },
  "imageUrl": "https://example.com/iced-coffee.jpg"
}
```

**フィールド説明:**
- `name` (string, 必須): 商品名
- `description` (string, オプション): 商品説明
- `category` (string, 必須): カテゴリー
- `subcategory` (string, オプション): サブカテゴリー
- `barcode` (string, 必須): バーコード（一意）
- `sku` (string, 必須): 在庫管理単位（一意）
- `price` (number, 必須): 販売価格
- `cost` (number, オプション): 原価
- `taxType` (string, 必須): 税区分（"standard", "reduced", "exempt"）
- `isActive` (boolean, デフォルト: true): アクティブ状態
- `attributes` (object, オプション): カスタム属性
- `imageUrl` (string, オプション): 商品画像URL

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "商品の登録に成功しました",
  "data": {
    "productId": "prod_002",
    "name": "アイスコーヒー",
    "barcode": "4901234567897",
    "sku": "BEV-002",
    "createdAt": "2024-01-10T10:00:00Z"
  },
  "operation": "create_product"
}
```

#### 3. 商品更新
**PUT** `/api/v1/tenants/{tenant_id}/products/{product_id}`

既存商品の情報を更新します。

**認証:** JWTトークンが必要

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `product_id` (string, 必須): 商品ID

**リクエストボディ:**
部分更新をサポートします。更新したいフィールドのみを含めます。

```json
{
  "price": 380.00,
  "description": "プレミアムアイスコーヒー",
  "attributes": {
    "size": "large",
    "temperature": "cold"
  }
}
```

#### 4. 商品検索
**GET** `/api/v1/tenants/{tenant_id}/products/search`

高度な検索条件で商品を検索します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**クエリパラメータ:**
- `q` (string, 必須): 検索キーワード
- `fields` (string, オプション): 検索対象フィールド（カンマ区切り）
- `price_min` (number, オプション): 最小価格
- `price_max` (number, オプション): 最大価格
- `categories` (string, オプション): カテゴリーフィルタ（カンマ区切り）

#### 5. 一括商品操作
**POST** `/api/v1/tenants/{tenant_id}/products/bulk`

複数商品の一括登録、更新、削除を実行します。

**認証:** JWTトークンが必要

**リクエストボディ:**
```json
{
  "operation": "upsert",
  "products": [
    {
      "barcode": "4901234567890",
      "name": "商品1",
      "price": 100.00
    },
    {
      "barcode": "4901234567891",
      "name": "商品2",
      "price": 200.00
    }
  ]
}
```

**操作タイプ:**
- `upsert`: 存在しない場合は作成、存在する場合は更新
- `update`: 既存商品の更新のみ
- `delete`: 商品の削除

### 決済方法管理

#### 6. 決済方法一覧取得
**GET** `/api/v1/tenants/{tenant_id}/payments`

利用可能な決済方法の一覧を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**クエリパラメータ:**
- `is_active` (boolean, オプション): アクティブ状態でフィルタ
- `type` (string, オプション): 決済タイプでフィルタ（"cash", "credit", "debit", "emoney", "qr"）

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "決済方法一覧を取得しました",
  "data": {
    "items": [
      {
        "paymentMethodId": "pm_001",
        "code": "CASH",
        "name": "現金",
        "type": "cash",
        "isActive": true,
        "allowChange": true,
        "minimumAmount": 1,
        "maximumAmount": 1000000,
        "fee": 0,
        "feeType": "fixed",
        "displayOrder": 1,
        "icon": "cash-icon.png"
      },
      {
        "paymentMethodId": "pm_002",
        "code": "CREDIT_VISA",
        "name": "クレジットカード（VISA）",
        "type": "credit",
        "isActive": true,
        "allowChange": false,
        "minimumAmount": 1000,
        "feeRate": 3.25,
        "feeType": "percentage",
        "displayOrder": 2,
        "icon": "visa-icon.png",
        "settings": {
          "processorId": "stripe",
          "merchantId": "MERCHANT001"
        }
      }
    ],
    "total": 10
  },
  "operation": "get_payment_methods"
}
```

#### 7. 決済方法登録
**POST** `/api/v1/tenants/{tenant_id}/payments`

新規決済方法を登録します。

**認証:** JWTトークンが必要

**リクエストボディ:**
```json
{
  "code": "EMONEY_SUICA",
  "name": "交通系電子マネー（Suica）",
  "type": "emoney",
  "isActive": true,
  "allowChange": false,
  "minimumAmount": 1,
  "maximumAmount": 20000,
  "feeRate": 2.5,
  "feeType": "percentage",
  "displayOrder": 5,
  "icon": "suica-icon.png",
  "settings": {
    "terminalId": "TERM001",
    "merchantCode": "MERCH001"
  }
}
```

### 税金ルール管理

#### 8. 税金ルール一覧取得
**GET** `/api/v1/tenants/{tenant_id}/tax-rules`

税金ルールの一覧を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "税金ルール一覧を取得しました",
  "data": {
    "items": [
      {
        "taxRuleId": "tax_001",
        "code": "STANDARD",
        "name": "標準税率",
        "rate": 10.0,
        "type": "standard",
        "calculationMethod": "exclusive",
        "isDefault": true,
        "effectiveFrom": "2019-10-01",
        "effectiveTo": null,
        "categories": ["general", "electronics", "clothing"]
      },
      {
        "taxRuleId": "tax_002",
        "code": "REDUCED",
        "name": "軽減税率",
        "rate": 8.0,
        "type": "reduced",
        "calculationMethod": "exclusive",
        "isDefault": false,
        "effectiveFrom": "2019-10-01",
        "effectiveTo": null,
        "categories": ["food", "beverages"]
      }
    ],
    "total": 3
  },
  "operation": "get_tax_rules"
}
```

#### 9. 税金計算
**POST** `/api/v1/tenants/{tenant_id}/tax-rules/calculate`

商品リストに対する税金を計算します。

**リクエストボディ:**
```json
{
  "items": [
    {
      "productId": "prod_001",
      "price": 300.00,
      "quantity": 2,
      "taxType": "standard"
    },
    {
      "productId": "prod_002",
      "price": 500.00,
      "quantity": 1,
      "taxType": "reduced"
    }
  ],
  "calculationMethod": "exclusive"
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "税金計算が完了しました",
  "data": {
    "items": [
      {
        "productId": "prod_001",
        "subtotal": 600.00,
        "taxAmount": 60.00,
        "total": 660.00,
        "taxRate": 10.0
      },
      {
        "productId": "prod_002",
        "subtotal": 500.00,
        "taxAmount": 40.00,
        "total": 540.00,
        "taxRate": 8.0
      }
    ],
    "totalSubtotal": 1100.00,
    "totalTax": 100.00,
    "totalAmount": 1200.00
  },
  "operation": "calculate_tax"
}
```

### プロモーション管理

#### 10. アクティブプロモーション取得
**GET** `/api/v1/tenants/{tenant_id}/promotions/active`

現在有効なプロモーションを取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**クエリパラメータ:**
- `store_code` (string, オプション): 店舗コードでフィルタ
- `datetime` (string, オプション): 特定日時での有効プロモーション（ISO 8601形式）

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "アクティブプロモーションを取得しました",
  "data": {
    "items": [
      {
        "promotionId": "promo_001",
        "code": "SUMMER2024",
        "name": "サマーセール2024",
        "description": "夏の特別割引",
        "type": "percentage_discount",
        "value": 20.0,
        "startDate": "2024-07-01T00:00:00Z",
        "endDate": "2024-08-31T23:59:59Z",
        "conditions": {
          "minimumAmount": 3000,
          "categories": ["clothing", "accessories"],
          "maxUsagePerCustomer": 1
        },
        "priority": 10,
        "isStackable": false
      }
    ],
    "total": 5
  },
  "operation": "get_active_promotions"
}
```

#### 11. プロモーション登録
**POST** `/api/v1/tenants/{tenant_id}/promotions`

新規プロモーションを登録します。

**認証:** JWTトークンが必要

**リクエストボディ:**
```json
{
  "code": "BOGO2024",
  "name": "Buy One Get One Free",
  "description": "対象商品を1つ購入で1つ無料",
  "type": "bogo",
  "startDate": "2024-06-01T00:00:00Z",
  "endDate": "2024-06-30T23:59:59Z",
  "conditions": {
    "products": ["prod_001", "prod_002"],
    "quantity": 2
  },
  "stores": ["STORE001", "STORE002"],
  "priority": 5,
  "isStackable": true
}
```

### スタッフ管理

#### 12. スタッフ一覧取得
**GET** `/api/v1/tenants/{tenant_id}/staff`

スタッフの一覧を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**クエリパラメータ:**
- `store_code` (string, オプション): 店舗コードでフィルタ
- `is_active` (boolean, オプション): アクティブ状態でフィルタ
- `role` (string, オプション): 役職でフィルタ

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "スタッフ一覧を取得しました",
  "data": {
    "items": [
      {
        "staffId": "STF001",
        "staffCode": "001",
        "name": "山田太郎",
        "role": "manager",
        "stores": ["STORE001"],
        "permissions": ["sales", "refund", "report", "cash_management"],
        "isActive": true,
        "email": "yamada@example.com",
        "phone": "090-1234-5678",
        "createdAt": "2024-01-01T10:00:00Z"
      }
    ],
    "total": 25
  },
  "operation": "get_staff"
}
```

#### 13. スタッフ登録
**POST** `/api/v1/tenants/{tenant_id}/staff`

新規スタッフを登録します。

**認証:** JWTトークンが必要

**リクエストボディ:**
```json
{
  "staffCode": "002",
  "name": "佐藤花子",
  "role": "cashier",
  "stores": ["STORE001", "STORE002"],
  "permissions": ["sales", "refund"],
  "email": "sato@example.com",
  "phone": "090-9876-5432",
  "pin": "1234"
}
```

### データ同期

#### 14. 端末用マスターデータ取得
**GET** `/api/v1/terminals/{terminal_id}/master-data`

端末用の完全なマスターデータセットを取得します。

**パスパラメータ:**
- `terminal_id` (string, 必須): 端末ID

**クエリパラメータ:**
- `version` (string, オプション): 現在のデータバージョン（差分更新用）
- `data_types` (string, オプション): 取得するデータタイプ（カンマ区切り）

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "マスターデータを取得しました",
  "data": {
    "version": "2024010110000001",
    "products": [...],
    "paymentMethods": [...],
    "taxRules": [...],
    "promotions": [...],
    "staff": [...],
    "categories": [...],
    "settings": {...}
  },
  "operation": "get_master_data"
}
```

### システムエンドポイント

#### 15. ヘルスチェック
**GET** `/health`

サービスヘルスと依存関係ステータスをチェックします。

**リクエスト例:**
```bash
curl -X GET "http://localhost:8002/health"
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
    "cache": "connected",
    "timestamp": "2024-01-01T10:00:00Z"
  },
  "operation": "health_check"
}
```

## エラーレスポンス

APIは標準的なHTTPステータスコードと構造化されたエラーレスポンスを使用します：

```json
{
  "success": false,
  "code": 404,
  "message": "指定された商品が見つかりません",
  "data": null,
  "operation": "get_product"
}
```

### 共通ステータスコード
- `200` - 成功
- `201` - 正常に作成されました
- `400` - 不正なリクエスト（検証エラー）
- `401` - 認証失敗
- `403` - アクセス拒否
- `404` - リソースが見つかりません
- `409` - 競合（重複データなど）
- `500` - 内部サーバーエラー

### エラーコードシステム

マスターデータサービスは30XXX範囲のエラーコードを使用します：

- `30001` - 商品が見つかりません
- `30002` - 無効な商品データ
- `30003` - 重複するバーコード/SKU
- `30004` - 決済方法エラー
- `30005` - 税金計算エラー
- `30006` - プロモーション適用エラー
- `30007` - スタッフ認証エラー
- `30008` - データ同期エラー
- `30009` - 一括操作エラー
- `30099` - 一般的なサービスエラー

## データ形式

### 日付と時刻
- すべての日付時刻はISO 8601形式（UTC）
- 日付のみ: `YYYY-MM-DD`
- 日付時刻: `YYYY-MM-DDTHH:mm:ssZ`

### 金額
- すべての金額は小数点以下2桁までの数値
- 通貨記号は含まない
- 負の値は返品やディスカウントに使用

### ページネーション
- `skip`: オフセット（0から開始）
- `limit`: 取得件数（最大100）
- レスポンスには`total`が含まれる

## キャッシング

マスターデータサービスはDapr state storeを使用してデータをキャッシュします：

- 商品データ: 5分間キャッシュ
- 決済方法: 30分間キャッシュ
- 税金ルール: 60分間キャッシュ
- プロモーション: リアルタイム（キャッシュなし）

キャッシュはデータ更新時に自動的に無効化されます。

## レート制限

現在、マスターデータサービスは明示的なレート制限を実装していませんが、以下の制限が追加される可能性があります：

- 読み取り操作: 1分あたり600リクエスト
- 書き込み操作: 1分あたり60リクエスト
- 一括操作: 1分あたり10リクエスト

## 注意事項

1. **マルチテナント**: すべての操作はテナントスコープ内で実行
2. **データ整合性**: 一括操作はトランザクション内で実行
3. **バージョニング**: マスターデータのバージョン管理をサポート
4. **CamelCase規約**: すべてのJSONフィールドはcamelCase形式を使用
5. **非同期処理**: 大量データ操作は非同期で処理
6. **監査ログ**: すべての変更操作は監査ログに記録
7. **ソフトデリート**: データは物理削除されず、非アクティブ化

マスターデータサービスは、Kugelpos POSシステムの基盤データ管理を提供し、データの一貫性、効率的な配信、柔軟な拡張性を保証します。