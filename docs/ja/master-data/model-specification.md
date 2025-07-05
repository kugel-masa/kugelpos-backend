# マスターデータサービス モデル仕様

## 概要

マスターデータサービスは、Kugelpos POSシステムの基幹となる参照データを管理します。スタッフ情報、商品マスター、支払方法、税金設定、システム設定、商品ブック（POS UI）などの静的データを一元管理し、他のサービスに提供します。マルチテナントアーキテクチャに対応し、階層的な設定管理を実装しています。

## データベースドキュメントモデル

すべてのドキュメントモデルは`BaseDocumentModel`を継承しています。

### 1. StaffMasterDocument（スタッフマスター）

スタッフ情報と認証データを管理するドキュメント。

**コレクション名:** `master_staff`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| staff_id | string | ✓ | スタッフID |
| name | string | ✓ | スタッフ名 |
| pin | string | ✓ | 認証PIN（bcryptハッシュ化） |
| roles | array[string] | - | 役割リスト（デフォルト: []） |

**インデックス:**
- ユニーク: (tenant_id, staff_id)

### 2. ItemCommonMasterDocument（商品共通マスター）

全店舗で共通の商品基本情報を管理するドキュメント。

**コレクション名:** `master_item_common`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| item_code | string | ✓ | 商品コード |
| description | string | ✓ | 商品説明 |
| description_short | string | - | 短縮説明 |
| description_long | string | - | 詳細説明 |
| category_code | string | - | カテゴリーコード |
| unit_price | float | - | 標準販売価格（デフォルト: 0.0） |
| unit_cost | float | - | 原価（デフォルト: 0.0） |
| tax_code | string | - | 税コード |
| item_details | array[ItemDetail] | - | 追加情報リスト |
| image_urls | array[string] | - | 商品画像URL |
| is_discount_restricted | boolean | - | 割引制限フラグ（デフォルト: false） |

**ItemDetailサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| name | string | ✓ | 属性名 |
| value | string | ✓ | 属性値 |

**インデックス:**
- ユニーク: (tenant_id, item_code)
- category_code
- tax_code

### 3. ItemStoreMasterDocument（商品店舗別マスター）

店舗固有の商品情報（価格等）を管理するドキュメント。

**コレクション名:** `master_item_store`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| item_code | string | ✓ | 商品コード |
| store_price | float | - | 店舗別価格 |

**インデックス:**
- ユニーク: (tenant_id, store_code, item_code)

### 4. ItemBookMasterDocument（商品ブックマスター）

POS画面のUI階層（カテゴリー/タブ/ボタン）を管理するドキュメント。

**コレクション名:** `master_item_book`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| item_book_id | string | ✓ | 商品ブックID |
| title | string | ✓ | タイトル |
| categories | array[ItemBookCategory] | - | カテゴリーリスト |

**ItemBookCategoryサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| category_number | integer | ✓ | カテゴリー番号 |
| title | string | ✓ | カテゴリータイトル |
| color | string | - | 背景色 |
| tabs | array[ItemBookTab] | - | タブリスト |

**ItemBookTabサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tab_number | integer | ✓ | タブ番号 |
| title | string | ✓ | タブタイトル |
| color | string | - | 背景色 |
| buttons | array[ItemBookButton] | - | ボタンリスト |

**ItemBookButtonサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| pos_x | integer | ✓ | X座標位置 |
| pos_y | integer | ✓ | Y座標位置 |
| size_x | integer | - | 横サイズ（デフォルト: 1） |
| size_y | integer | - | 縦サイズ（デフォルト: 1） |
| item_code | string | - | 商品コード |
| title | string | - | ボタンタイトル |
| color | string | - | ボタン色 |
| image_url | string | - | ボタン画像URL |

**インデックス:**
- ユニーク: (tenant_id, item_book_id)

### 5. PaymentMasterDocument（支払方法マスター）

利用可能な支払方法と制約を管理するドキュメント。

**コレクション名:** `master_payment`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| payment_code | string | ✓ | 支払方法コード |
| description | string | ✓ | 説明 |
| limit_amount | float | - | 上限金額 |
| can_refund | boolean | - | 返金可能フラグ（デフォルト: true） |
| can_deposit_over | boolean | - | 預り金超過可能フラグ（デフォルト: false） |
| can_change | boolean | - | お釣り可能フラグ（デフォルト: false） |

**インデックス:**
- ユニーク: (tenant_id, payment_code)

### 6. SettingsMasterDocument（設定マスター）

階層的なシステム設定を管理するドキュメント。

**コレクション名:** `master_settings`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| name | string | ✓ | 設定名 |
| default_value | string | ✓ | デフォルト値 |
| values | array[SettingsValue] | - | スコープ別設定値 |

**SettingsValueサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| store_code | string | - | 店舗コード（店舗スコープ） |
| terminal_no | integer | - | 端末番号（端末スコープ） |
| value | string | ✓ | 設定値 |

**設定解決優先順位:**
1. 端末レベル（最優先）
2. 店舗レベル
3. グローバル（デフォルト値）

**インデックス:**
- ユニーク: (tenant_id, name)

### 7. CategoryMasterDocument（カテゴリーマスター）

商品カテゴリーを管理するドキュメント。

**コレクション名:** `master_category`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| category_code | string | ✓ | カテゴリーコード |
| description | string | ✓ | カテゴリー説明 |
| description_short | string | - | 短縮説明 |
| tax_code | string | - | デフォルト税コード |

**インデックス:**
- ユニーク: (tenant_id, category_code)
- tax_code

### 8. TaxMasterDocument（税金マスター）

税率と計算ルールを管理するドキュメント。

**コレクション名:** `master_tax`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tax_code | string | ✓ | 税コード |
| tax_type | string | ✓ | 税タイプ |
| tax_name | string | ✓ | 税名称 |
| rate | float | ✓ | 税率（%） |
| round_digit | integer | - | 丸め桁数（デフォルト: 0） |
| round_method | string | - | 丸め方法 |

**インデックス:**
- tax_code (unique)

## APIリクエスト/レスポンススキーマ

すべてのスキーマは`BaseSchemaModel`を継承し、snake_caseからcamelCaseへの自動変換を提供します。

### スタッフ管理スキーマ

#### StaffCreateRequest
新規スタッフ作成リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| staffId | string | ✓ | スタッフID |
| name | string | ✓ | スタッフ名 |
| pin | string | ✓ | 認証PIN |
| roles | array[string] | - | 役割リスト |

#### StaffResponse
スタッフ情報レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| staffId | string | スタッフID |
| name | string | スタッフ名 |
| pin | string | マスク表示（"***"） |
| roles | array[string] | 役割リスト |

### 商品管理スキーマ

#### ItemCommonCreateRequest
商品作成リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| itemCode | string | ✓ | 商品コード |
| description | string | ✓ | 商品説明 |
| shortDescription | string | - | 短縮説明 |
| detailDescription | string | - | 詳細説明 |
| categoryCode | string | - | カテゴリーコード |
| unitPrice | float | - | 販売価格 |
| unitCost | float | - | 原価 |
| taxCode | string | - | 税コード |
| itemDetails | array[object] | - | 追加情報 |
| imageUrls | array[string] | - | 画像URL |
| isDiscountRestricted | boolean | - | 割引制限 |

#### ItemStoreCreateRequest
店舗別価格設定リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| storeCode | string | ✓ | 店舗コード |
| itemCode | string | ✓ | 商品コード |
| storePrice | float | ✓ | 店舗別価格 |

### 支払方法スキーマ

#### PaymentResponse
支払方法レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| paymentCode | string | 支払方法コード |
| description | string | 説明 |
| limitAmount | float | 上限金額 |
| canRefund | boolean | 返金可能フラグ |
| canDepositOver | boolean | 預り金超過可能フラグ |
| canChange | boolean | お釣り可能フラグ |

### 設定管理スキーマ

#### SettingValueResponse
設定値取得レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| name | string | 設定名 |
| value | string | 解決された設定値 |
| scope | string | 適用スコープ（global/store/terminal） |

## データ関係

### 商品データ階層
```
ItemCommonMasterDocument（基本情報）
    ↓
ItemStoreMasterDocument（店舗別上書き）
    ↓
最終的な商品情報（マージ結果）
```

### 商品ブック階層
```
ItemBookMasterDocument
  └── categories[]
        └── tabs[]
              └── buttons[] → ItemCommonMasterDocument（item_code参照）
```

### 設定解決階層
```
SettingsMasterDocument
  ├── default_value（グローバル）
  └── values[]
        ├── store_code指定（店舗レベル）
        └── store_code + terminal_no指定（端末レベル）
```

## マルチテナント実装

1. **データベース分離:** `db_master_{tenant_id}`形式でテナント別DB
2. **認証連携:** JWTトークンまたはAPIキーによる認証
3. **データアクセス:** 全ての操作でテナントIDを検証

## パフォーマンス最適化

1. **インデックス戦略:** 頻繁に検索されるフィールドにインデックス設定
2. **階層的データ:** 商品ブックの入れ子構造で結合操作を削減
3. **設定キャッシュ:** 設定値の解決結果をキャッシュ可能

## セキュリティ

1. **PIN管理:** スタッフPINはbcryptでハッシュ化
2. **API認証:** JWT/APIキーによる認証必須
3. **監査ログ:** created_at/updated_atによる変更追跡