# カートサービス モデル仕様

## 概要

カートサービスは、Kugelpos POSシステムのショッピングカート操作とトランザクション処理を管理します。カートライフサイクル管理用の洗練されたステートマシン、サーキットブレーカーパターンを持つデュアルストレージ戦略、決済とプロモーション用のプラグインアーキテクチャ、そしてイベント駆動通信を実装しています。このサービスは、包括的なトランザクション整合性と監査証跡を備えたマルチテナント分離を提供します。

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

### 1. CartDocument（アクティブショッピングカート）

ステートマシン管理を持つアクティブショッピングカートを格納するドキュメント。

**コレクション名:** `cache_cart`

**継承:** kugel_commonの`BaseTransaction`を継承

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| cart_id | string | - | 一意のUUIDカート識別子 |
| status | string | - | カート状態（Initial/Idle/EnteringItem/Paying/Completed/Cancelled） |
| subtotal_amount | float | - | 税金と割引前の合計 |
| balance_amount | float | - | すべての計算後の最終金額 |
| line_items | array[CartLineItem] | - | ショッピングカートアイテム |
| masters | ReferenceMasters | - | 埋め込み参照データキャッシュ |

**CartLineItemサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| item_details | dict | - | 追加アイテム情報 |
| image_urls | array[string] | - | 商品画像URL |
| is_discount_restricted | boolean | - | 割引適用可否フラグ |

**ReferenceMastersサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| items | array[ItemMasterDocument] | - | 商品カタログキャッシュ |
| taxes | array[TaxMasterDocument] | - | 税金ルールキャッシュ |
| settings | array[SettingsMasterDocument] | - | システム設定キャッシュ |

**インデックス:**
- ユニークインデックス: cart_id
- 複合インデックス: (tenant_id, store_code, terminal_no)
- インデックス: status

### 2. TranlogDocument（トランザクション履歴）

完了したトランザクション記録を格納するドキュメント。

**コレクション名:** `log_tran`

**継承:** kugel_commonの`BaseTransaction`を継承

**追加フィールド:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| invoice_issue_no | string | - | 請求書番号参照 |

**目的:** 監査とレポート用の完了したトランザクションの永続記録

**インデックス:**
- 複合インデックス: (tenant_id, store_code, terminal_no, business_date, transaction_no)
- インデックス: invoice_issue_no

### 3. TransactionStatusDocument（トランザクション状態追跡）

取消および返品操作を追跡するドキュメント。

**コレクション名:** `status_tran`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| store_code | string | - | 店舗コード |
| terminal_no | integer | - | ターミナル番号 |
| transaction_no | string | - | トランザクション番号 |
| is_voided | boolean | - | 取消状態フラグ |
| is_refunded | boolean | - | 返品状態フラグ |
| void_transaction_no | string | - | 取消トランザクション番号 |
| void_date_time | datetime | - | 取消操作タイムスタンプ |
| void_staff_id | string | - | トランザクションを取消したスタッフ |
| return_transaction_no | string | - | 返品トランザクション番号 |
| return_date_time | datetime | - | 返品操作タイムスタンプ |
| return_staff_id | string | - | 返品を処理したスタッフ |

**インデックス:**
- ユニークインデックス: (tenant_id, store_code, terminal_no, transaction_no)
- インデックス: is_voided
- インデックス: is_refunded

### 4. TerminalCounterDocument（ターミナルシーケンスジェネレータ）

ターミナル固有のシーケンスカウンタを管理するドキュメント。

**コレクション名:** `info_terminal_counter`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| terminal_id | string | - | ターミナル識別子 |
| count_dic | dict | - | カウンタ名と現在値の辞書 |

**カウンタタイプ:**
- transaction_no: トランザクションシーケンスカウンタ
- receipt_no: レシートシーケンスカウンタ
- business_counter: ビジネス操作カウンタ

**インデックス:**
- ユニークインデックス: terminal_id

### 5. TranlogDeliveryStatus（メッセージ配信追跡）

pub/subメッセージ配信状況を追跡するドキュメント。

**コレクション名:** `status_tran_delivery`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| event_id | string | - | メッセージ追跡用UUID |
| published_at | datetime | - | 発行タイムスタンプ |
| status | string | - | 全体配信状況 |
| payload | dict | - | 元のメッセージ内容 |
| services | array[ServiceStatus] | - | サービス別配信状況 |

**ServiceStatusサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| service_name | string | ✓ | 対象サービス名 |
| status | string | ✓ | 配信状況（pending/delivered/failed） |
| delivered_at | datetime | - | 配信タイムスタンプ |
| error_message | string | - | 失敗時のエラー詳細 |

**インデックス:**
- ユニークインデックス: event_id
- インデックス: status
- インデックス: published_at

### 6. BaseTransaction構造（CartとTranlogで継承）

CartDocumentとTranlogDocumentの両方で継承される基底構造。

**コアトランザクションフィールド:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| store_code | string | - | 店舗コード |
| terminal_no | integer | - | ターミナル番号 |
| transaction_no | string | - | 連続トランザクション番号 |
| business_date | string | - | ビジネス日付（YYYYMMDD） |
| user | UserInfoDocument | - | ユーザー情報 |
| staff | Staff | - | スタッフ情報ネストクラス |
| sales | SalesInfo | - | 売上サマリーネストクラス |
| line_items | array[LineItem] | - | トランザクション明細項目 |
| payments | array[Payment] | - | 決済記録 |
| taxes | array[Tax] | - | 税金計算 |
| subtotal_discounts | array[DiscountInfo] | - | カートレベル割引 |
| is_voided | boolean | - | 取消状態フラグ |
| is_refunded | boolean | - | 返品状態フラグ |
| receipt_text | string | - | フォーマットされたレシートテキスト |
| journal_text | string | - | フォーマットされたジャーナルテキスト |

## APIリクエスト/レスポンススキーマ

すべてのスキーマは、JSON直列化の際にsnake_caseからcamelCaseへの自動変換を提供する`BaseSchemaModel`を継承しています。

### カート管理スキーマ

#### CartCreateRequest
新しいショッピングカートを作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| transactionType | integer | ✓ | トランザクションタイプコード |
| userId | string | - | ユーザー識別子 |
| userName | string | - | ユーザー表示名 |

#### CartCreateResponse
新しいカート識別子を返すレスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| cartId | string | 一意のカート識別子 |

#### CartDeleteResponse
カート削除のレスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| message | string | 削除確認メッセージ |

### アイテム管理スキーマ

#### Item
カート操作用のアイテム情報。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| itemCode | string | ✓ | 商品アイテムコード |
| quantity | float | ✓ | アイテム数量 |
| unitPrice | float | - | 単価オーバーライド |

#### ItemQuantityUpdateRequest
アイテム数量を更新するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| quantity | float | ✓ | 新しい数量値 |

#### ItemUnitPriceUpdateRequest
アイテム単価を更新するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| unitPrice | float | ✓ | 新しい単価 |

### 決済処理スキーマ

#### PaymentRequest
決済を処理するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| paymentCode | string | ✓ | 決済方法コード |
| amount | integer | ✓ | 最小通貨単位での決済金額 |
| detail | string | - | 決済詳細または参照 |

### トランザクション表現スキーマ

#### Cart（レスポンス）
完全なカート情報レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| cartId | string | カート識別子 |
| cartStatus | string | 現在のカート状態 |
| subtotalAmount | float | 税金と割引前の金額 |
| balanceAmount | float | 計算後の最終金額 |
| lineItems | array[TranLineItem] | カートアイテム |
| payments | array[TranPayment] | 決済記録 |
| taxes | array[TranTax] | 税金計算 |

#### Tran（レスポンス）
完全なトランザクション記録レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| transactionNo | string | トランザクション番号 |
| businessDate | string | ビジネス日付（YYYYMMDD） |
| totalAmount | float | 最終トランザクション合計 |
| lineItems | array[TranLineItem] | トランザクションアイテム |
| payments | array[TranPayment] | 決済記録 |
| taxes | array[TranTax] | 税金計算 |

#### TranLineItem（レスポンス）
トランザクション明細詳細。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| lineNo | integer | 明細シーケンス番号 |
| itemCode | string | 商品コード |
| description | string | アイテム説明 |
| quantity | float | アイテム数量 |
| unitPrice | float | 単価 |
| amount | float | 明細合計金額 |
| discountAmount | float | 明細割引合計 |
| taxAmount | float | 明細税額 |

#### TranPayment（レスポンス）
トランザクション決済詳細。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| paymentNo | integer | 決済シーケンス番号 |
| paymentCode | string | 決済方法コード |
| amount | float | 決済金額 |
| detail | string | 決済詳細 |

#### TranTax（レスポンス）
トランザクション税金詳細。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| taxCode | string | 税金ルールコード |
| taxName | string | 税金表示名 |
| rate | float | 税率 |
| targetAmount | float | 課税対象金額 |
| taxAmount | float | 計算された税額 |

### 配信状況管理スキーマ

#### DeliveryStatusUpdateRequest
メッセージ配信状況を更新するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| eventId | string | ✓ | イベント識別子 |
| service | string | ✓ | サービス名 |
| status | string | ✓ | 配信状況 |
| message | string | - | 状況メッセージ |

#### DeliveryStatusUpdateResponse
配信状況更新のレスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| success | boolean | 更新成功フラグ |
| message | string | レスポンスメッセージ |

## ステートマシンパターン

### カート状態と遷移

**カート状態:**
1. **Initial** - カート作成、操作不可
2. **Idle** - 空のカート、アイテム受付可能
3. **EnteringItem** - アイテムあり、カート変更可能
4. **Paying** - 決済処理中、操作制限あり
5. **Completed** - トランザクション確定（終了状態）
6. **Cancelled** - カート破棄（終了状態）

**有効な遷移:**
- Initial → Idle
- Idle → EnteringItem（最初のアイテム追加）
- Idle → Cancelled
- EnteringItem → Paying（決済開始）
- EnteringItem → Cancelled
- Paying → EnteringItem（アイテム入力再開）
- Paying → Completed（トランザクション確定）

**ステートマネージャー:** `CartStateManager`が状態別の許可操作を制御

### 状態別操作

**Initial状態:**
- 操作不可
- 自動的にIdleに遷移

**Idle状態:**
- 最初のアイテム追加（→ EnteringItem）
- カートキャンセル（→ Cancelled）

**EnteringItem状態:**
- アイテム追加/変更/削除
- 割引適用
- 決済プロセス開始（→ Paying）
- カートキャンセル（→ Cancelled）

**Paying状態:**
- 決済処理
- アイテム入力再開（→ EnteringItem）
- トランザクション完了（→ Completed）

**Completed状態:**
- 操作不可
- トランザクション確定

**Cancelled状態:**
- 操作不可
- カート終了

## デュアルストレージ戦略

### プライマリストレージ: Dapr State Store（Redis）
- **目的:** 高性能アクティブカートストレージ
- **機能:** 復旧性のためのサーキットブレーカーパターン
- **TTL:** ターミナル情報キャッシュ5分

### フォールバックストレージ: MongoDB
- **目的:** ステートストア障害時の永続ストレージ
- **機能:** 完全なトランザクション履歴と監査証跡
- **整合性:** ステートストアとの結果的整合性

### サーキットブレーカー実装
- **障害閾値:** 3回連続障害
- **リセットタイムアウト:** 60秒
- **状態:** Closed → Open → Half-Open
- **適用対象:** Dapr状態操作、外部HTTP呼び出し

## プラグインアーキテクチャ

### 決済ストラテジープラグイン
- **現金決済:** おつり計算付き現金トランザクション処理
- **キャッシュレス決済:** クレジット/デビットカードとデジタル決済処理
- **その他決済:** カスタム決済方法実装

### 販促プラグイン
- **設定可能:** JSONベースのプロモーションルール設定
- **拡張可能:** カスタム割引ストラテジー用プラグインシステム
- **スタック可能:** 複数プロモーション組み合わせサポート

### レシートデータプラグイン
- **カスタマイズ可能:** 設定可能なレシートフォーマット
- **検証:** タイプセーフなレシート行設定
- **配置:** 左/中央/右テキスト配置サポート

## イベント駆動通信

### 発行イベント

#### トランザクションログイベント（`tranlog_report`）
トランザクション完了時に発行:
```json
{
  "eventId": "uuid",
  "tenantId": "tenant001",
  "storeCode": "store001", 
  "terminalNo": 1,
  "transactionNo": "0001",
  "businessDate": "20240101",
  "totalAmount": 1500.00,
  "lineItems": [...],
  "payments": [...]
}
```

#### トランザクション状況イベント（`tranlog_status`）
取消/返品操作時に発行:
```json
{
  "eventId": "uuid",
  "transactionNo": "0001",
  "statusType": "void",
  "operationDateTime": "2024-01-01T10:30:00Z"
}
```

#### 現金ログイベント（`cashlog_report`）
現金操作時に発行:
```json
{
  "eventId": "uuid", 
  "operationType": "cashin",
  "amount": 1000.00,
  "timestamp": "2024-01-01T10:30:00Z"
}
```

#### ターミナルログイベント（`opencloselog_report`）
ターミナル開店/閉店時に発行:
```json
{
  "eventId": "uuid",
  "operationType": "open",
  "terminalId": "T001",
  "timestamp": "2024-01-01T09:00:00Z"
}
```

## マルチテナンシー実装

1. **データベース分離**: 各テナントは個別のデータベースを使用: `db_cart_{tenant_id}`
2. **テナント検証**: すべての操作で認証からのtenant_idを検証
3. **データ分離**: アプリケーションレベルでテナント間アクセスを防止
4. **シャードキー**: `{tenant_id}_{store_code}_{business_date}`

## 検証ルール

### カート検証
- ターミナルは「Opened」状態である必要
- スタッフがサインインしている必要
- ビジネス日付がターミナルビジネス日付と一致する必要
- 状態遷移はステートマシンルールに従う必要

### アイテム検証
- アイテムコードがマスターデータに存在する必要
- 数量は正の値である必要
- 価格オーバーライドには認証が必要
- 税金計算は正確である必要

### 決済検証
- 合計決済がカート残高と等しい必要
- 決済方法がアクティブである必要
- 現金のおつりは自動計算
- キャッシュレス決済には参照番号が必要

### トランザクション検証
- 取消操作は同一ターミナルに制限
- 返品操作は同一店舗内で許可
- 返品数量は元の数量を超えてはならない

## パフォーマンス考慮事項

1. **インデックス戦略**: カート検索、トランザクションクエリ、イベント処理に最適化
2. **キャッシュ**: ターミナル情報とマスターデータをDapr state storeでキャッシュ
3. **デュアルストレージ**: 永続フォールバック付き高性能ステートストア
4. **サーキットブレーカー**: 外部サービス障害の復旧対応
5. **イベント処理**: スケーラビリティのための非同期pub/sub

## セキュリティ機能

1. **認証**: APIキー検証とスタッフセッション確認
2. **認可**: ターミナルスコープ操作と状態ベースアクセス制御
3. **監査証跡**: 完全なトランザクション履歴と操作追跡
4. **データ整合性**: ステートマシン強制とアトミック操作
5. **マルチテナント分離**: テナント間の完全なデータ分離