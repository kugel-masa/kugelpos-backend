# マスターデータサービス API仕様

## 概要

マスターデータサービスは、Kugelpos POSシステムの基幹となる参照データを管理するRESTful APIサービスです。スタッフ情報、商品マスター、支払方法、税金設定、システム設定などの静的データを一元管理し、他のサービスに提供します。

## ベースURL
- ローカル環境: `http://localhost:8002`
- 本番環境: `https://master-data.{domain}`

## 認証

マスターデータサービスは2つの認証方法をサポートしています：

### 1. JWTトークン（Bearerトークン）
- ヘッダー: `Authorization: Bearer {token}`
- 用途: 管理者によるマスターデータ管理

### 2. APIキー認証
- ヘッダー: `X-API-Key: {api_key}`
- 用途: 端末からのマスターデータ読み取り

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

## APIエンドポイント

### スタッフマスター管理

#### 1. スタッフ作成
**POST** `/api/v1/tenants/{tenant_id}/staff`

新規スタッフを登録します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子

**リクエストボディ:**
```json
{
  "staffId": "STF001",
  "name": "山田太郎",
  "pin": "1234",
  "roles": ["cashier", "manager"]
}
```

**レスポンス例:**
```json
{
  "success": true,
  "code": 201,
  "message": "Staff created successfully",
  "data": {
    "staffId": "STF001",
    "name": "山田太郎",
    "roles": ["cashier", "manager"]
  },
  "operation": "create_staff"
}
```

#### 2. スタッフ取得
**GET** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

特定のスタッフ情報を取得します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `staff_id` (string, 必須): スタッフID

#### 3. スタッフ一覧取得
**GET** `/api/v1/tenants/{tenant_id}/staff`

スタッフ一覧を取得します。

**クエリパラメータ:**
- `page` (integer, デフォルト: 1): ページ番号
- `limit` (integer, デフォルト: 100, 最大: 1000): ページサイズ
- `sort` (string): ソート条件

#### 4. スタッフ更新
**PUT** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

スタッフ情報を更新します。

#### 5. スタッフ削除
**DELETE** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

スタッフを削除します。

### 商品マスター管理

#### 6. 商品作成
**POST** `/api/v1/tenants/{tenant_id}/items`

新規商品を登録します。

**リクエストボディ:**
```json
{
  "itemCode": "ITEM001",
  "description": "コーヒー（ホット）",
  "shortDescription": "コーヒー",
  "detailDescription": "ブレンドコーヒー",
  "unitPrice": 300.00,
  "unitCost": 100.00,
  "categoryCode": "BEVERAGE",
  "taxCode": "TAX_10",
  "itemDetails": [
    {"name": "size", "value": "regular"},
    {"name": "temperature", "value": "hot"}
  ],
  "imageUrls": ["https://example.com/coffee.jpg"],
  "isDiscountRestricted": false
}
```

#### 7. 商品取得
**GET** `/api/v1/tenants/{tenant_id}/items/{item_code}`

特定の商品情報を取得します。

#### 8. 商品一覧取得
**GET** `/api/v1/tenants/{tenant_id}/items`

商品一覧を取得します。

**クエリパラメータ:**
- `page` (integer): ページ番号
- `limit` (integer): ページサイズ
- `sort` (string): ソート条件

#### 9. 商品更新
**PUT** `/api/v1/tenants/{tenant_id}/items/{item_code}`

商品情報を更新します。

#### 10. 商品削除
**DELETE** `/api/v1/tenants/{tenant_id}/items/{item_code}`

商品を削除します。

### 商品店舗別マスター管理

#### 11. 店舗別価格設定
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items`

店舗固有の商品価格を設定します。

**パスパラメータ:**
- `tenant_id` (string, 必須): テナント識別子
- `store_code` (string, 必須): 店舗コード

**リクエストボディ:**
```json
{
  "itemCode": "ITEM001",
  "storePrice": 280.00
}
```

### 商品ブックマスター管理

#### 12. 商品ブック取得
**GET** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}`

POS画面のUI階層（カテゴリー/タブ/ボタン）を取得します。

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Item book retrieved successfully",
  "data": {
    "itemBookId": "BOOK001",
    "title": "標準レイアウト",
    "categories": [
      {
        "categoryNumber": 1,
        "title": "ドリンク",
        "tabs": [
          {
            "tabNumber": 1,
            "title": "ホット",
            "buttons": [
              {
                "posX": 0,
                "posY": 0,
                "sizeX": 1,
                "sizeY": 1,
                "itemCode": "ITEM001",
                "title": "コーヒー",
                "color": "#8B4513"
              }
            ]
          }
        ]
      }
    ]
  },
  "operation": "get_item_book"
}
```

### 支払方法マスター管理

#### 13. 支払方法一覧取得
**GET** `/api/v1/tenants/{tenant_id}/payments`

利用可能な支払方法を取得します。

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Payment methods retrieved successfully",
  "data": [
    {
      "paymentCode": "CASH",
      "description": "現金",
      "limitAmount": null,
      "canRefund": true,
      "canDepositOver": true,
      "canChange": true
    },
    {
      "paymentCode": "CREDIT",
      "description": "クレジットカード",
      "limitAmount": 1000000,
      "canRefund": true,
      "canDepositOver": false,
      "canChange": false
    }
  ],
  "operation": "get_payment_methods"
}
```

### 設定マスター管理

#### 14. 設定値取得
**GET** `/api/v1/tenants/{tenant_id}/settings/{name}/value`

階層的な設定値を取得します（グローバル→店舗→端末の優先順位）。

**クエリパラメータ:**
- `store_code` (string): 店舗コード
- `terminal_no` (integer): 端末番号

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Setting value retrieved successfully",
  "data": {
    "name": "receipt_print_count",
    "value": "2",
    "scope": "store"
  },
  "operation": "get_setting_value"
}
```

### カテゴリーマスター管理

#### 15. カテゴリー一覧取得
**GET** `/api/v1/tenants/{tenant_id}/categories`

商品カテゴリーの階層を取得します。

### 税金マスター管理

#### 16. 税金設定一覧取得
**GET** `/api/v1/tenants/{tenant_id}/taxes`

税率設定を取得します。

**レスポンス例:**
```json
{
  "success": true,
  "code": 200,
  "message": "Tax settings retrieved successfully",  
  "data": [
    {
      "taxCode": "TAX_10",
      "taxType": "STANDARD",
      "taxName": "標準税率",
      "rate": 10.0,
      "roundDigit": 0,
      "roundMethod": "ROUND"
    },
    {
      "taxCode": "TAX_8",
      "taxType": "REDUCED",
      "taxName": "軽減税率",
      "rate": 8.0,
      "roundDigit": 0,
      "roundMethod": "ROUND"
    }
  ],
  "operation": "get_tax_settings"
}
```

### システム管理

#### 17. テナント初期化
**POST** `/api/v1/tenants`

新規テナントのマスターデータを初期化します。

**リクエストボディ:**
```json
{
  "tenantId": "tenant001"
}
```

**認証:** JWTトークンが必要

#### 18. ヘルスチェック
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

## ページネーション

一覧取得エンドポイントは共通のページネーション形式をサポート：

**レスポンスメタデータ:**
```json
{
  "metadata": {
    "total": 150,
    "page": 1,
    "limit": 50,
    "pages": 3
  }
}
```

## エラーコード

マスターデータサービスは405XX範囲のエラーコードを使用します：

### 基本エラー (4050X)
- `405001`: マスターデータ検証エラー
- `405002`: マスターデータが見つかりません
- `405003`: マスターデータが既に存在します
- `405004`: マスターデータを作成できません
- `405005`: マスターデータを更新できません
- `405006`: マスターデータを削除できません

### 商品マスター関連 (4051XX)
- `405101`: 商品が見つかりません
- `405102`: 商品コードが重複しています
- `405103`: 商品の価格が無効です
- `405104`: 商品の税率が無効です

### その他のマスター関連
- `405201`: 価格が見つかりません
- `405301`: 顧客が見つかりません
- `405401`: 店舗が見つかりません
- `405501`: 部門が見つかりません

## 特記事項

1. **マルチテナント対応**: 全ての操作はテナントスコープ内で実行
2. **階層的設定**: 設定値はグローバル→店舗→端末の優先順位で解決
3. **スタッフPIN**: 現在は平文で保存（将来的にはハッシュ化を予定）
4. **削除処理**: 現在は物理削除を実行（一部のマスターデータは論理削除フラグで管理）
5. **camelCase変換**: 内部snake_caseは自動的にcamelCaseに変換