# マスターデータサービス モデル仕様

## 概要

マスターデータサービスは、Kugelpos POSシステムのすべての静的参照データと設定データを管理します。商品カタログ、スタッフ情報、決済方法、税務ルール、カテゴリ、システム設定、および他のすべてのサービスで使用されるアイテムブックレイアウトの一元管理を提供します。このサービスはマルチテナントアーキテクチャに従い、包括的なデータ検証と監査証跡を備えています。

## データベースドキュメントモデル

すべてのドキュメントモデルは、監査、キャッシュ、シャーディング用の共通フィールドを提供する`AbstractDocument`を継承しています。

### AbstractDocument（基底クラス）

すべてのドキュメントに共通機能を提供する基底クラス。

**基底フィールド:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| shard_key | string | - | 水平スケーリング用のデータベースシャーディングキー |
| created_at | datetime | - | ドキュメント作成タイムスタンプ |
| updated_at | datetime | - | 最終更新タイムスタンプ |
| cached_on | datetime | - | キャッシュ無効化用のキャッシュタイムスタンプ |
| etag | string | - | 楽観的並行性制御用のエンティティタグ |

### 1. StaffMasterDocument（スタッフ情報）

スタッフメンバー情報と認証データを格納するドキュメント。

**コレクション名:** `master_staff`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| id | string | - | スタッフ一意識別子 |
| name | string | - | スタッフ表示名 |
| pin | string | - | 認証PIN（ハッシュ化） |
| status | string | - | スタッフステータス（active/inactive） |
| roles | array[string] | - | 割り当てられた役割のリスト |

**インデックス:**
- ユニークインデックス: (tenant_id, id)
- インデックス: status

### 2. CategoryMasterDocument（商品カテゴリ）

商品を階層カテゴリに整理するためのドキュメント。

**コレクション名:** `master_category`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| category_code | string | - | カテゴリ一意コード |
| description | string | - | カテゴリ説明 |
| description_short | string | - | UI用短縮説明 |
| tax_code | string | - | 関連税コード参照 |

**インデックス:**
- ユニークインデックス: (tenant_id, category_code)
- インデックス: tax_code

### 3. ItemCommonMasterDocument（共通アイテムデータ）

全店舗で共有されるベースアイテム情報を格納するドキュメント。

**コレクション名:** `master_item_common`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| item_code | string | - | アイテム一意コード |
| category_code | string | - | カテゴリ参照 |
| description | string | - | アイテム説明 |
| description_short | string | - | 短縮説明 |
| description_long | string | - | 詳細説明 |
| unit_price | float | - | 標準単価（デフォルト: 0.0） |
| unit_cost | float | - | 原価（デフォルト: 0.0） |
| item_details | array[string] | - | 追加アイテム詳細 |
| image_urls | array[string] | - | アイテム画像URL |
| tax_code | string | - | 税コード参照 |
| is_discount_restricted | boolean | - | 割引制限フラグ（デフォルト: false） |
| is_deleted | boolean | - | 論理削除フラグ（デフォルト: false） |

**インデックス:**
- ユニークインデックス: (tenant_id, item_code)
- インデックス: category_code
- インデックス: tax_code
- インデックス: is_deleted

### 4. ItemStoreMasterDocument（店舗固有アイテムデータ）

店舗固有のアイテムオーバーライドと価格設定のドキュメント。

**コレクション名:** `master_item_store`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| store_code | string | - | 店舗コード |
| item_code | string | - | アイテムコード参照 |
| store_price | float | - | 店舗固有価格オーバーライド |

**インデックス:**
- ユニークインデックス: (tenant_id, store_code, item_code)

### 5. ItemStoreDetailDocument（結合アイテムビュー）

共通アイテムデータと店舗固有オーバーライドを結合した仮想ドキュメント。

**目的:** 特定店舗のアイテムデータの統一ビューを提供

**継承:** ItemCommonMasterDocument

**追加フィールド:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| store_code | string | - | 店舗コード |
| store_price | float | - | 店舗固有価格（unit_priceをオーバーライド） |

### 6. PaymentMasterDocument（決済方法）

決済方法の機能と制限を設定するドキュメント。

**コレクション名:** `master_payment`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| payment_code | string | - | 決済方法コード |
| description | string | - | 決済方法説明 |
| limit_amount | float | - | 最大取引金額（デフォルト: 0.0） |
| can_refund | boolean | - | 返金サポート（デフォルト: true） |
| can_deposit_over | boolean | - | 過払い許可（デフォルト: false） |
| can_change | boolean | - | おつり提供可能（デフォルト: false） |
| is_active | boolean | - | アクティブステータス（デフォルト: true） |

**インデックス:**
- ユニークインデックス: (tenant_id, payment_code)
- インデックス: is_active

### 7. TaxMasterDocument（税設定）

税計算ルールと税率のドキュメント。

**コレクション名:** `master_tax`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tax_code | string | - | 税コード識別子 |
| tax_type | string | - | 税種類（sales_tax、vat等） |
| tax_name | string | - | 税表示名 |
| rate | float | - | 小数での税率（デフォルト: 0.0） |
| round_digit | integer | - | 丸め精度（デフォルト: 0） |
| round_method | string | - | 丸め方法 |

**インデックス:**
- ユニークインデックス: tax_code

### 8. SettingsMasterDocument（システム設定）

階層システム設定のドキュメント。

**コレクション名:** `master_settings`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| name | string | - | 設定名 |
| default_value | string | - | デフォルト値 |
| values | array[SettingsValue] | - | スコープ固有値 |

**SettingsValueサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| store_code | string | - | 店舗スコープ（テナントレベルの場合null） |
| terminal_no | integer | - | ターミナルスコープ（店舗レベルの場合null） |
| value | string | ✓ | 設定値 |

**設定解決順序:**
1. ターミナル固有（最も具体的）
2. 店舗固有
3. テナントレベルデフォルト

**インデックス:**
- ユニークインデックス: (tenant_id, name)

### 9. ItemBookMasterDocument（アイテムブックレイアウト）

階層構造を持つPOSターミナルUIレイアウトを設定するドキュメント。

**コレクション名:** `master_item_book`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| item_book_id | string | - | ブック一意識別子 |
| title | string | - | ブックタイトル |
| categories | array[ItemBookCategory] | - | カテゴリリスト |

**ItemBookCategoryサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| category_number | integer | - | カテゴリ番号 |
| title | string | - | カテゴリタイトル |
| color | string | - | カテゴリ色 |
| tabs | array[ItemBookTab] | - | タブリスト |

**ItemBookTabサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tab_number | integer | - | タブ番号 |
| title | string | - | タブタイトル |
| color | string | - | タブ色 |
| buttons | array[ItemBookButton] | - | ボタンリスト |

**ItemBookButtonサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| pos_x | integer | - | グリッド上のX位置 |
| pos_y | integer | - | グリッド上のY位置 |
| size | ButtonSize | - | ボタンサイズ列挙型 |
| image_url | string | - | ボタン画像URL |
| color_text | string | - | テキスト色 |
| item_code | string | - | 関連アイテムコード |

**ButtonSize列挙型:**
- `Single` - 標準1x1ボタン
- `DoubleWidth` - 2x1ボタン
- `DoubleHeight` - 1x2ボタン
- `Quad` - 2x2ボタン

**インデックス:**
- ユニークインデックス: (tenant_id, item_book_id)

### 10. TerminalInfoDocument（ターミナル参照）

ターミナル操作で参照されるドキュメント（commonsで定義）。

**コレクション名:** `info_terminal`

**使用される主要フィールド:**

| フィールド名 | 型 | 説明 |
|------------|------|-------------|
| terminal_id | string | ターミナル一意識別子 |
| tenant_id | string | テナント識別子 |
| store_code | string | 店舗コード |
| terminal_no | integer | ターミナル番号 |
| status | string | ターミナルステータス |
| staff | StaffMasterDocument | 現在サインインしているスタッフ |

## APIリクエスト/レスポンススキーマ

すべてのスキーマは、JSON直列化の際にsnake_caseからcamelCaseへの自動変換を提供する`BaseSchemaModel`を継承しています。

### スタッフ管理スキーマ

#### StaffCreateRequest
新しいスタッフメンバーを作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| id | string | ✓ | スタッフ一意識別子 |
| name | string | ✓ | スタッフ表示名 |
| pin | string | ✓ | 認証PIN |
| status | string | - | スタッフステータス（デフォルト: active） |
| roles | array[string] | - | 割り当てられた役割 |

#### StaffUpdateRequest
スタッフ情報を更新するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| name | string | - | 更新されたスタッフ名 |
| pin | string | - | 更新されたPIN |
| status | string | - | 更新されたステータス |
| roles | array[string] | - | 更新された役割 |

#### Staff（レスポンス）
スタッフ情報レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| id | string | スタッフ識別子 |
| name | string | スタッフ名 |
| pin | string | マスクされたPIN（"***"） |
| status | string | スタッフステータス |
| roles | array[string] | 割り当てられた役割 |
| createdAt | string | 作成タイムスタンプ |
| updatedAt | string | 更新タイムスタンプ |

### アイテム管理スキーマ

#### ItemCommonCreateRequest
新しいアイテムを作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| itemCode | string | ✓ | アイテム一意コード |
| categoryCode | string | - | カテゴリ参照 |
| description | string | ✓ | アイテム説明 |
| descriptionShort | string | - | 短縮説明 |
| descriptionLong | string | - | 詳細説明 |
| unitPrice | float | - | 標準価格 |
| unitCost | float | - | 原価 |
| itemDetails | array[string] | - | 追加詳細 |
| imageUrls | array[string] | - | 画像URL |
| taxCode | string | - | 税コード |
| isDiscountRestricted | boolean | - | 割引制限 |

#### ItemCommon（レスポンス）
アイテム情報レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| itemCode | string | アイテムコード |
| categoryCode | string | カテゴリ参照 |
| description | string | アイテム説明 |
| descriptionShort | string | 短縮説明 |
| descriptionLong | string | 詳細説明 |
| unitPrice | float | 標準価格 |
| unitCost | float | 原価 |
| itemDetails | array[string] | 追加詳細 |
| imageUrls | array[string] | 画像URL |
| taxCode | string | 税コード |
| isDiscountRestricted | boolean | 割引制限 |
| isDeleted | boolean | 削除ステータス |
| createdAt | string | 作成タイムスタンプ |
| updatedAt | string | 更新タイムスタンプ |

### 決済方法スキーマ

#### PaymentCreateRequest
決済方法を作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| paymentCode | string | ✓ | 決済方法コード |
| description | string | ✓ | 方法説明 |
| limitAmount | float | - | 最大金額 |
| canRefund | boolean | - | 返金機能 |
| canDepositOver | boolean | - | 過払い機能 |
| canChange | boolean | - | おつり機能 |
| isActive | boolean | - | アクティブステータス |

#### Payment（レスポンス）
決済方法レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| paymentCode | string | 決済方法コード |
| description | string | 方法説明 |
| limitAmount | float | 最大金額 |
| canRefund | boolean | 返金機能 |
| canDepositOver | boolean | 過払い機能 |
| canChange | boolean | おつり機能 |
| isActive | boolean | アクティブステータス |
| createdAt | string | 作成タイムスタンプ |
| updatedAt | string | 更新タイムスタンプ |

### 設定管理スキーマ

#### SettingsCreateRequest
設定を作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| name | string | ✓ | 設定名 |
| defaultValue | string | ✓ | デフォルト値 |
| values | array[SettingsValueCreate] | - | スコープ固有値 |

#### SettingsValueCreate
スコープ固有設定値。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| storeCode | string | - | 店舗スコープ |
| terminalNo | integer | - | ターミナルスコープ |
| value | string | ✓ | 設定値 |

### カテゴリ管理スキーマ

#### CategoryCreateRequest
カテゴリを作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| categoryCode | string | ✓ | カテゴリ一意コード |
| description | string | ✓ | カテゴリ説明 |
| descriptionShort | string | - | 短縮説明 |
| taxCode | string | - | 税コード参照 |

### 税管理スキーマ

#### Tax（レスポンス）
税設定レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| taxCode | string | 税コード |
| taxType | string | 税種類 |
| taxName | string | 税名 |
| rate | float | 税率 |
| roundDigit | integer | 丸め精度 |
| roundMethod | string | 丸め方法 |

### アイテムブック管理スキーマ

#### ItemBookCreateRequest
アイテムブックレイアウトを作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| itemBookId | string | ✓ | ブック識別子 |
| title | string | ✓ | ブックタイトル |
| categories | array[CategoryCreate] | - | カテゴリ |

#### ItemBookCategoryCreate
アイテムブック内のカテゴリ。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| categoryNumber | integer | ✓ | カテゴリ番号 |
| title | string | ✓ | カテゴリタイトル |
| color | string | - | カテゴリ色 |
| tabs | array[TabCreate] | - | タブ |

#### ItemBookTabCreate
カテゴリ内のタブ。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| tabNumber | integer | ✓ | タブ番号 |
| title | string | ✓ | タブタイトル |
| color | string | - | タブ色 |
| buttons | array[ButtonCreate] | - | ボタン |

#### ItemBookButtonCreate
タブ内のボタン。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| posX | integer | ✓ | X位置 |
| posY | integer | ✓ | Y位置 |
| size | string | ✓ | ボタンサイズ |
| imageUrl | string | - | 画像URL |
| colorText | string | - | テキスト色 |
| itemCode | string | - | アイテム参照 |

## データ関係

### 1. アイテム階層
```
ItemCommonMasterDocument（ベースデータ）
  ↓
ItemStoreMasterDocument（店舗オーバーライド）
  ↓
ItemStoreDetailDocument（結合ビュー）
```

### 2. カテゴリ-アイテム関係
```
CategoryMasterDocument
  ↓ (category_code経由)
ItemCommonMasterDocument
```

### 3. 税関係
```
TaxMasterDocument
  ↓ (tax_code経由)
CategoryMasterDocument, ItemCommonMasterDocument
```

### 4. アイテムブック階層
```
ItemBookMasterDocument
  └── ItemBookCategory[]
        └── ItemBookTab[]
              └── ItemBookButton[]
                    ↓ (item_code経由)
                  ItemCommonMasterDocument
```

### 5. 設定階層
```
テナントレベル（default_value）
  └── 店舗レベル（store_code + value）
        └── ターミナルレベル（store_code + terminal_no + value）
```

## マルチテナンシー実装

1. **データベース分離**: 各テナントは個別のデータベースを使用: `{DB_NAME_PREFIX}_{tenant_id}`
2. **テナント検証**: すべての操作でtenant_idを検証
3. **データ分離**: アプリケーションレベルでテナント間アクセスを防止
4. **一意制約**: ほとんどの一意インデックスにtenant_idを含む

## 検証ルール

### フィールド検証
- **コード**: 英数字、通常3-20文字
- **価格**: 非負の浮動小数点値
- **ステータス**: 列挙型検証（active/inactive）
- **参照**: リンクされたドキュメントの外部キー検証

### ビジネスルール
- アイテムは既存のカテゴリと税コードのみ参照可能
- 店舗固有価格は共通価格をオーバーライド
- 設定解決は階層に従う（ターミナル > 店舗 > テナント）
- 論理削除は参照整合性を保持

## パフォーマンス考慮事項

1. **インデックス戦略**: 一般的なクエリパターンに最適化
2. **複合ビュー**: ItemStoreDetailDocumentがジョイン操作を削減
3. **キャッシュ**: ETagベースの楽観的並行性制御
4. **シャーディング**: シャードキーが水平スケーリングをサポート
5. **参照整合性**: パフォーマンスのためアプリケーションレベルで実行

## セキュリティ機能

1. **PINハッシュ化**: スタッフPINを安全なハッシュ化で保存
2. **監査証跡**: すべての変更をタイムスタンプで追跡
3. **論理削除**: 履歴を維持する論理削除
4. **検証**: すべてのフィールドで包括的な入力検証
5. **マルチテナント分離**: テナント間の完全なデータ分離