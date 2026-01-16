# ジャーナルサービス モデル仕様

## 概要

ジャーナルサービスは、Kugelpos POSシステムの電子ジャーナルおよびトランザクションログ管理システムです。全てのPOS操作（取引、現金操作、端末開閉）の永続的で検索可能な記録を管理し、監査・コンプライアンス要件に対応します。イベント駆動アーキテクチャ、冪等性保証、マルチテナント分離を実装しています。

## データベースドキュメントモデル

すべてのドキュメントモデルは`BaseDocumentModel`を継承しています。

### 1. JournalDocument（統合ジャーナルストレージ）

全てのPOS操作の統合ジャーナルエントリーを保存するメインドキュメント。

**コレクション名:** `journal`

**継承:** `AbstractDocument`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| terminal_no | integer | ✓ | 端末番号 |
| transaction_no | integer | - | トランザクション番号（売上取引用） |
| transaction_type | integer | ✓ | トランザクションタイプコード |
| business_date | string | ✓ | ビジネス日付（YYYYMMDD形式） |
| open_counter | integer | ✓ | 端末セッションカウンター |
| business_counter | integer | ✓ | ビジネス操作カウンター |
| receipt_no | integer | - | レシート番号 |
| amount | float | - | 金額（正/負、デフォルト: 0.0） |
| quantity | integer | - | 数量合計（デフォルト: 0） |
| staff_id | string | - | スタッフ識別子 |
| user_id | string | - | ユーザー識別子 |
| generate_date_time | string | ✓ | 生成日時（ISO 8601形式） |
| journal_text | string | ✓ | 人間が読める形式のジャーナルテキスト |
| receipt_text | string | ✓ | フォーマット済みレシートテキスト |
| receipts | array[ReceiptDocument] | - | 複数レシートドキュメント（顧客控え、店舗控え等） |

**インデックス:**
- ユニーク複合: (tenant_id, store_code, terminal_no, transaction_type, generate_date_time)
- 複合: (tenant_id, store_code, business_date)
- 複合: (tenant_id, store_code, terminal_no, business_date)
- transaction_type
- receipt_no
- journal_text (text)
- generate_date_time

### 2. CashInOutLog（現金操作記録）

現金入出金操作の詳細ログを保存するドキュメント。

**コレクション名:** `log_cash_in_out`

**継承:** `AbstractDocument`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| store_code | string | - | 店舗コード |
| store_name | string | - | 店舗名 |
| terminal_no | integer | - | 端末番号 |
| staff_id | string | - | スタッフ識別子 |
| staff_name | string | - | スタッフ名 |
| business_date | string | - | ビジネス日付（YYYYMMDD） |
| open_counter | integer | - | セッションカウンター |
| business_counter | integer | - | ビジネスカウンター |
| generate_date_time | string | - | 操作日時（ISO 8601形式） |
| amount | float | - | 金額（入金:正、出金:負） |
| description | string | - | 操作理由/説明 |
| receipt_text | string | - | レシートテキスト |
| journal_text | string | - | ジャーナルテキスト |

**注:** 全フィールドはOptionalで定義されていますが、実際の運用では主要フィールドは必須として扱われます。

**インデックス:**
- 複合: (tenant_id, store_code, terminal_no, business_date)
- amount

### 3. OpenCloseLog（端末開閉記録）

端末の開店・閉店操作ログを保存するドキュメント。

**コレクション名:** `log_open_close`

**継承:** `AbstractDocument`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | - | テナント識別子 |
| store_code | string | - | 店舗コード |
| store_name | string | - | 店舗名 |
| terminal_no | integer | - | 端末番号 |
| staff_id | string | - | スタッフ識別子 |
| staff_name | string | - | スタッフ名 |
| business_date | string | - | ビジネス日付（YYYYMMDD） |
| open_counter | integer | - | セッションカウンター |
| business_counter | integer | - | ビジネスカウンター |
| operation | string | - | 操作タイプ（'open'/'close'） |
| generate_date_time | string | - | 操作日時（ISO 8601形式） |
| terminal_info | TerminalInfoDocument | - | 端末情報スナップショット |
| cart_transaction_count | integer | - | 取引数（close時） |
| cart_transaction_last_no | integer | - | 最終取引番号（close時） |
| cash_in_out_count | integer | - | 現金操作数（close時） |
| cash_in_out_last_datetime | string | - | 最終現金操作日時（close時、ISO 8601形式） |
| receipt_text | string | - | レシートテキスト |
| journal_text | string | - | ジャーナルテキスト |

**注:** 全フィールドはOptionalで定義されていますが、実際の運用では主要フィールドは必須として扱われます。

**インデックス:**
- 複合: (tenant_id, store_code, terminal_no, business_date, open_counter)
- operation

### 4. TranlogDocument（取引ログ）

カートサービスからの完全な取引データを保存するドキュメント。

**コレクション名:** `log_tran`

**継承:** kugel_commonの`BaseTransaction`構造を参照

**主要フィールド:**
- 取引明細、決済、税金情報を含む完全な取引データ
- トランザクションタイプコード
- ビジネス日付とカウンター情報
- 金額と数量の合計

## トランザクションタイプ定義

| コード | 説明 | ソース |
|------|------|--------|
| 101 | 通常売上 | カートサービス |
| -101 | 通常売上取消 | カートサービス |
| 102 | 返品売上 | カートサービス |
| 201 | 売上取消 | カートサービス |
| 202 | 返品取消 | カートサービス |
| 301 | レジ開け | ターミナルサービス |
| 302 | レジ締め | ターミナルサービス |
| 401 | 現金入金 | ターミナルサービス |
| 402 | 現金出金 | ターミナルサービス |
| 501 | 売上レポート | レポートサービス |
| 502 | その他レポート | レポートサービス |

## APIリクエスト/レスポンススキーマ

すべてのスキーマは`BaseSchemaModel`を継承し、snake_caseからcamelCaseへの自動変換を提供します。

### リクエストスキーマ

#### CreateJournalRequest
手動ジャーナルエントリー作成用。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| transactionNo | string | - | トランザクション番号 |
| transactionType | integer | ✓ | トランザクションタイプコード |
| businessDate | string | ✓ | ビジネス日付（YYYY-MM-DD） |
| openCounter | integer | - | セッションカウンター |
| businessCounter | integer | - | ビジネスカウンター |
| receiptNo | string | - | レシート番号 |
| amount | float | - | 金額 |
| quantity | float | - | 数量 |
| staffId | string | - | スタッフID |
| userId | string | - | ユーザーID |
| journalText | string | ✓ | ジャーナルテキスト |
| receiptText | string | - | レシートテキスト |

#### SearchJournalRequest（クエリパラメータ）
ジャーナル検索用パラメータ。

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| terminals | string | - | 端末番号（カンマ区切り） |
| transaction_types | string | - | トランザクションタイプ（カンマ区切り） |
| business_date_from | string | - | 開始ビジネス日付（YYYY-MM-DD） |
| business_date_to | string | - | 終了ビジネス日付（YYYY-MM-DD） |
| generate_date_time_from | string | - | 開始生成日時（YYYYMMDDTHHMMSS） |
| generate_date_time_to | string | - | 終了生成日時（YYYYMMDDTHHMMSS） |
| receipt_no_from | string | - | 開始レシート番号 |
| receipt_no_to | string | - | 終了レシート番号 |
| keywords | string | - | キーワード検索（カンマ区切り） |
| page | integer | - | ページ番号（デフォルト: 1） |
| limit | integer | - | ページサイズ（デフォルト: 100、最大: 1000） |
| sort | string | - | ソート条件（例: "generateDateTime:-1"） |

### レスポンススキーマ

#### JournalResponse
個別ジャーナルエントリーレスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| journalId | string | ジャーナルID |
| tenantId | string | テナントID |
| storeCode | string | 店舗コード |
| terminalNo | integer | 端末番号 |
| transactionNo | string | トランザクション番号 |
| transactionType | integer | トランザクションタイプコード |
| transactionTypeName | string | トランザクションタイプ名 |
| businessDate | string | ビジネス日付 |
| openCounter | integer | セッションカウンター |
| businessCounter | integer | ビジネスカウンター |
| receiptNo | string | レシート番号 |
| amount | float | 金額 |
| quantity | float | 数量 |
| staffId | string | スタッフID |
| userId | string | ユーザーID |
| generateDateTime | string | 生成日時 |
| journalText | string | ジャーナルテキスト |
| receiptText | string | レシートテキスト |

## イベント駆動アーキテクチャ

### Dapr Pub/Subトピック

#### tranlog_report
- **ソース:** カートサービス
- **エンドポイント:** `/api/v1/tranlog`
- **内容:** 完全な取引データ
- **処理:** 取引ログとジャーナルエントリーを作成

#### cashlog_report
- **ソース:** ターミナルサービス
- **エンドポイント:** `/api/v1/cashlog`
- **内容:** 現金入出金操作データ
- **処理:** 現金ログとジャーナルエントリーを作成

#### opencloselog_report
- **ソース:** ターミナルサービス
- **エンドポイント:** `/api/v1/opencloselog`
- **内容:** 端末開閉操作データ
- **処理:** 開閉ログとジャーナルエントリーを作成

### 冪等性処理

1. **イベントID管理:** Dapr State Storeで処理済みイベントIDを記録
2. **重複防止:** 同一イベントIDの再処理を防止
3. **原子性保証:** MongoDBトランザクションで複数コレクションへの書き込みを保証
4. **Circuit Breaker:** 外部サービス障害時の自動復旧

## マルチテナント実装

### データベース分離
- **データベース名:** `db_journal_{tenant_id}`
- **テナント検証:** 全ての操作でテナントIDを検証
- **データアクセス:** テナント間のデータアクセスは不可

### 認証・認可
- **JWT認証:** 管理者による検索・照会用
- **APIキー認証:** 端末からのジャーナル作成用
- **サービス間認証:** イベント処理用の専用トークン

## データ保持とアーカイブ

### 不変性保証
- ジャーナルエントリーは作成後変更不可
- 更新・削除操作はサポートしない
- 監査証跡の完全性を保証

### アーカイブ戦略
- ビジネス日付ベースのパーティショニング
- テナント毎の保持ポリシー設定可能
- 規制要件に応じた長期保存

## 検索機能

### 検索条件
- 端末番号範囲
- トランザクションタイプ
- ビジネス日付範囲
- 生成日時範囲
- レシート番号範囲
- キーワード検索（journal_text内）

### パフォーマンス最適化
- 複合インデックスによるクエリ最適化
- テキストインデックスによる全文検索
- ページネーションによる大量データ対応
- ソート条件の柔軟な指定

## エラーハンドリング

### エラーコード体系
ジャーナルサービスは50XXX範囲のエラーコードを使用：
- 50001-50099: 一般的なジャーナル操作エラー
- 50101-50199: 検証エラー
- 50201-50299: 外部サービス通信エラー

### 障害通知
- 重大エラー時のSlack通知
- Circuit Breakerによる障害の自動隔離
- 詳細なエラーコンテキストの記録