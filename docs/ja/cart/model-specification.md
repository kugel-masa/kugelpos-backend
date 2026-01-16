# カートサービス モデル仕様

## 概要

カートサービスは、Kugelpos POSシステムのショッピングカート管理とトランザクション処理を担当します。ステートマシンパターンによるカートライフサイクル管理、デュアルストレージ戦略（Dapr State Store + MongoDB）、プラグインアーキテクチャ（決済・プロモーション）、イベント駆動通信を実装しています。

## データベースドキュメントモデル

### 1. CartDocument（アクティブショッピングカート）

ステートマシン管理されたアクティブショッピングカートを格納するドキュメント。

**コレクション名:** `cache_cart`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| cart_id | string | ✓ | 一意のUUIDカート識別子 |
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| terminal_no | integer | ✓ | ターミナル番号 |
| receipt_no | integer | - | レシート番号 |
| transaction_no | integer | - | トランザクション番号 |
| transaction_type | integer | - | トランザクションタイプ |
| user | UserInfoDocument | - | ユーザー情報 |
| staff | StaffDocument | - | スタッフ情報 |
| sales | SalesDocument | - | 売上サマリー情報 |
| status | string | - | カート状態（Initial/Idle/EnteringItem/Paying/Completed/Cancelled） |
| generate_date_time | datetime | - | カート生成日時 |
| business_date | string | - | ビジネス日付（YYYYMMDD） |
| subtotal_amount | float | - | 税金と割引前の合計 |
| total_amount | float | - | 税込み合計金額 |
| total_quantity | integer | - | 合計数量 |
| total_discount_amount | float | - | 合計割引金額 |
| deposit_amount | float | - | 預かり金額 |
| change_amount | float | - | おつり金額 |
| balance_amount | float | - | 残高金額 |
| line_items | array[LineItemDocument] | - | カート内商品明細 |
| payments | array[PaymentDocument] | - | 決済情報 |
| taxes | array[TaxDocument] | - | 税金計算情報 |
| subtotal_discounts | array[DiscountInfoDocument] | - | 小計レベル割引 |
| is_voided | boolean | - | 取消フラグ |
| is_refunded | boolean | - | 返品フラグ |
| masters | ReferenceMasters | - | マスターデータキャッシュ |
| receipt_text | string | - | レシートテキスト |
| journal_text | string | - | ジャーナルテキスト |

**LineItemDocumentサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| line_no | integer | ✓ | 明細行番号 |
| item_code | string | ✓ | 商品コード |
| item_name | string | - | 商品名 |
| unit_price | float | ✓ | 単価 |
| unit_price_original | float | - | 元の単価 |
| is_unit_price_changed | boolean | - | 単価変更フラグ |
| quantity | float | ✓ | 数量 |
| amount | float | - | 金額 |
| discount_amount | float | - | 割引金額 |
| tax_amount | float | - | 税額 |
| discounts | array[DiscountInfoDocument] | - | 明細レベル割引 |
| item_details | dict | - | 追加商品情報 |
| image_urls | array[string] | - | 商品画像URL |
| is_discount_restricted | boolean | - | 割引制限フラグ |
| is_cancelled | boolean | - | キャンセルフラグ |

**PaymentDocumentサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| payment_no | integer | ✓ | 決済番号 |
| payment_code | string | ✓ | 決済方法コード |
| payment_name | string | - | 決済方法名 |
| payment_amount | float | ✓ | 決済金額 |
| payment_detail | string | - | 決済詳細 |

**TaxDocumentサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tax_no | integer | ✓ | 税番号 |
| tax_code | string | - | 税コード |
| tax_type | string | ✓ | 税タイプ |
| tax_name | string | - | 税名称 |
| tax_amount | float | ✓ | 税額 |
| target_amount | float | - | 課税対象金額 |
| target_quantity | integer | - | 課税対象数量 |

**インデックス:**
- cart_id (unique)
- 複合インデックス: (tenant_id, store_code, terminal_no)
- cart_status

### 2. TranlogDocument（トランザクション履歴）

完了したトランザクション記録を格納するドキュメント。

**コレクション名:** `log_tran`

**継承:** `BaseDocumentModel`

**フィールド定義:**

CartDocumentと同じフィールド構造に加えて：

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| invoice_issue_no | string | - | 請求書発行番号 |

**インデックス:**
- 複合インデックス: (tenant_id, store_code, terminal_no, business_date, transaction_no)
- invoice_issue_no

### 3. TransactionStatusDocument（トランザクション状態追跡）

取消および返品操作を追跡するドキュメント。

**コレクション名:** `status_tran`

**継承:** `AbstractDocument`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| terminal_no | integer | ✓ | ターミナル番号 |
| transaction_no | integer | ✓ | トランザクション番号 |
| is_voided | boolean | - | 取消状態フラグ（デフォルト: false） |
| is_refunded | boolean | - | 返品状態フラグ（デフォルト: false） |
| void_transaction_no | integer | - | 取消トランザクション番号 |
| void_date_time | string | - | 取消日時（ISO 8601文字列） |
| void_staff_id | string | - | 取消実行スタッフID |
| return_transaction_no | integer | - | 返品トランザクション番号 |
| return_date_time | string | - | 返品日時（ISO 8601文字列） |
| return_staff_id | string | - | 返品実行スタッフID |

**インデックス:**
- ユニークインデックス: (tenant_id, store_code, terminal_no, transaction_no)
- is_voided
- is_refunded

### 4. TerminalCounterDocument（ターミナルシーケンスカウンタ）

ターミナル固有のシーケンスカウンタを管理するドキュメント。

**コレクション名:** `info_terminal_counter`

**継承:** `BaseDocumentModel`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| terminal_id | string | ✓ | ターミナル識別子 |
| count_dic | dict | ✓ | カウンタ辞書 |

**カウンタタイプ:**
- transaction_no: トランザクション番号カウンタ
- receipt_no: レシート番号カウンタ

**インデックス:**
- terminal_id (unique)

### 5. TranlogDeliveryStatus（メッセージ配信追跡）

pub/subメッセージ配信状況を追跡するドキュメント。

**コレクション名:** `status_tran_delivery`

**継承:** `AbstractDocument`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| event_id | string | ✓ | イベント識別子（UUID） |
| published_at | datetime | ✓ | 発行日時 |
| status | string | ✓ | 全体配信状況（published/delivered/partially_delivered/failed） |
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| terminal_no | integer | ✓ | ターミナル番号 |
| transaction_no | integer | ✓ | トランザクション番号 |
| business_date | string | ✓ | 営業日（YYYYMMDD） |
| open_counter | integer | ✓ | 開設回数 |
| payload | dict | ✓ | メッセージペイロード |
| services | array[ServiceStatus] | - | サービス別配信状況 |
| last_updated_at | datetime | ✓ | 最終更新日時 |

**ServiceStatusサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| service_name | string | ✓ | サービス名 |
| status | string | - | 配信状況（pending/received/failed、デフォルト: pending） |
| received_at | datetime | - | 受信日時 |
| message | string | - | エラーメッセージなど |

**インデックス:**
- event_id (unique)
- status
- published_at

## APIリクエスト/レスポンススキーマ

すべてのスキーマは`BaseSchemaModel`（一部実装では`BaseSchemmaModel`）を継承し、snake_caseからcamelCaseへの自動変換を提供します。

### カート管理スキーマ

#### CartCreateRequest
新しいショッピングカートを作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| transactionType | integer | - | トランザクションタイプ（デフォルト: 1 = 通常販売） |
| userId | string | - | ユーザー識別子 |
| userName | string | - | ユーザー名 |

#### CartCreateResponse
カート作成レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| cartId | string | 生成されたカートID |

#### CartDeleteResponse
カート削除レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| message | string | 削除結果メッセージ |

### アイテム管理スキーマ

#### Item
カートに追加するアイテム情報。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| itemCode | string | ✓ | 商品コード |
| quantity | integer | ✓ | 数量 |
| unitPrice | float | - | 単価（オーバーライド用） |

#### ItemQuantityUpdateRequest
アイテム数量更新リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| quantity | integer | ✓ | 新しい数量 |

#### ItemUnitPriceUpdateRequest
アイテム単価更新リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| unitPrice | float | ✓ | 新しい単価 |

### 決済処理スキーマ

#### PaymentRequest
決済処理リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| paymentCode | string | ✓ | 決済方法コード |
| amount | integer | ✓ | 決済金額（最小通貨単位） |
| detail | string | - | 決済詳細情報 |

### トランザクション表現スキーマ

#### Cart（レスポンス）
カート全体情報レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| cartId | string | カートID |
| cartStatus | string | カート状態 |
| subtotalAmount | float | 小計金額 |
| totalAmount | float | 合計金額 |
| balanceAmount | float | 残高金額 |
| lineItems | array[TranLineItem] | 明細項目 |
| payments | array[TranPayment] | 決済情報 |
| taxes | array[TranTax] | 税金情報 |

#### Tran（レスポンス）
トランザクション情報レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| transactionNo | integer | トランザクション番号 |
| businessDate | string | ビジネス日付 |
| totalAmount | float | 合計金額 |
| lineItems | array[TranLineItem] | 明細項目 |
| payments | array[TranPayment] | 決済情報 |
| taxes | array[TranTax] | 税金情報 |

### 配信状況管理スキーマ

#### DeliveryStatusUpdateRequest
配信状況更新リクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| eventId | string | ✓ | イベントID |
| service | string | ✓ | サービス名 |
| status | string | ✓ | 配信状況 |
| message | string | - | メッセージ |

#### DeliveryStatusUpdateResponse
配信状況更新レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| eventId | string | イベントID |
| service | string | サービス名 |
| status | string | 配信状況 |
| success | boolean | 更新成功フラグ |

## ステートマシンパターン

### カート状態と遷移

**カート状態:**
1. **Initial** - 初期状態
2. **Idle** - アイドル状態（空のカート）
3. **EnteringItem** - アイテム入力中
4. **Paying** - 決済処理中
5. **Completed** - 完了（終了状態）
6. **Cancelled** - キャンセル（終了状態）

**有効な遷移:**
- Initial → Idle
- Idle → EnteringItem（アイテム追加時）
- Idle → Cancelled
- EnteringItem → Paying（決済開始時）
- EnteringItem → Cancelled
- Paying → EnteringItem（アイテム入力再開時）
- Paying → Completed（決済完了時）

## デュアルストレージ戦略

### プライマリストレージ: Dapr State Store
- **用途:** アクティブカートの高速アクセス
- **実装:** Redis経由でのキー値ストア
- **TTL:** ターミナル情報キャッシュ5分（設定可能）

### セカンダリストレージ: MongoDB
- **用途:** 永続化とフォールバック
- **実装:** 完全なドキュメントストレージ
- **同期:** State Storeとの結果的整合性

## プラグインアーキテクチャ

### 決済プラグイン（/services/strategies/payments/）
- 現金決済: おつり計算を含む処理
- キャッシュレス決済: カード・電子マネー処理
- カスタム決済: 拡張可能な決済方法

### プロモーションプラグイン
- JSONベースの設定
- 複数プロモーションの組み合わせ可能
- カスタム割引ロジックの実装可能

## イベント駆動通信

### 発行トピック

#### tranlog_report
トランザクション完了時に発行されるイベント。レポートサービスやジャーナルサービスが購読。

#### cashlog_report
現金入出金操作時に発行されるイベント。

#### opencloselog_report
ターミナル開店・閉店時に発行されるイベント。

## マルチテナント実装

1. **データベース分離:** `db_cart_{tenant_id}`形式でテナント別DB
2. **認証連携:** JWTトークンからtenant_id取得
3. **アクセス制御:** すべての操作でテナント検証実施

## 設定パラメータ

### CartSettings（settings_cart.py）

| パラメータ名 | 型 | デフォルト値 | 説明 |
|------------|------|------------|-------------|
| UNDELIVERED_CHECK_INTERVAL_IN_MINUTES | integer | 5 | 未配信チェック間隔（分） |
| UNDELIVERED_CHECK_PERIOD_IN_HOURS | integer | 24 | 未配信チェック期間（時間） |
| UNDELIVERED_CHECK_FAILED_PERIOD_IN_MINUTES | integer | 15 | 失敗判定期間（分） |
| TERMINAL_CACHE_TTL_SECONDS | integer | 300 | ターミナルキャッシュTTL（秒） |
| USE_TERMINAL_CACHE | boolean | true | ターミナルキャッシュ使用フラグ |
| DEBUG | string | "false" | デバッグモード |
| DEBUG_PORT | integer | 5678 | デバッグポート |