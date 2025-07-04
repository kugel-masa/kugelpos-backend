# ターミナルサービスモデル仕様

## 概要

ターミナルサービスは、Kugelpos POSシステムにおけるPOS端末、店舗、および現金操作のためのデータモデルを管理します。このサービスは、端末のライフサイクル管理、スタッフ認証、ビジネスセッション制御を処理し、様々なログコレクションを通じて包括的な監査証跡を維持します。

## データベースドキュメントモデル

### 1. TenantInfoDocument（テナント情報）

テナントと埋め込み店舗情報を保存するためのメインドキュメント。

**コレクション名:** `info_tenant`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナントの一意識別子 |
| tenant_name | string | ✓ | テナントの表示名 |
| stores | array[StoreInfo] | ✓ | このテナントに属する店舗のリスト |
| tags | array[string] | - | 分類のための追加タグ |
| _id | ObjectId | ✓ | MongoDBドキュメントID（継承） |
| entry_datetime | datetime | ✓ | ドキュメント作成タイムスタンプ（継承） |
| last_update_datetime | datetime | - | 最終更新タイムスタンプ（継承） |
| shard_key | string | ✓ | シャーディングキー（継承） |

**インデックス:**
- ユニークインデックス: tenant_id
- インデックス: tags

### 2. StoreInfo（店舗情報 - 埋め込み）

TenantInfoDocument内の埋め込みドキュメントで、個々の店舗を表します。

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| store_code | string | ✓ | テナント内の一意の店舗コード |
| store_name | string | ✓ | 店舗の表示名 |
| status | string | - | 店舗ステータス（Active/Inactive） |
| business_date | string | - | 現在のビジネス日付（YYYYMMDD） |
| tags | array[string] | - | 分類のための追加タグ |
| created_at | datetime | ✓ | 店舗作成タイムスタンプ |
| updated_at | datetime | - | 最終更新タイムスタンプ |

### 3. TerminalInfoDocument（端末情報）

個々の端末情報を保存するためのドキュメント。このモデルはcommonsライブラリで定義され、サービス間で共有されます。

**コレクション名:** `info_terminal`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| terminal_id | string | ✓ | 一意ID: {tenant_id}-{store_code}-{terminal_no} |
| tenant_id | string | ✓ | この端末を所有するテナント |
| store_code | string | ✓ | 端末が設置されている店舗 |
| terminal_no | integer | ✓ | 店舗内の端末番号（1-999） |
| description | string | - | 端末の説明 |
| function_mode | string | ✓ | 現在の機能モード |
| status | string | ✓ | 端末ステータス（Idle/Opened/Closed） |
| business_date | string | - | 現在のビジネス日付（YYYYMMDD） |
| open_counter | integer | ✓ | 端末オープンセッションカウンター |
| business_counter | integer | ✓ | ビジネス操作カウンター |
| staff | StaffMasterDocument | - | 現在サインインしているスタッフ |
| initial_amount | float | - | 初期現金金額 |
| physical_amount | float | - | 実際の現金カウント |
| api_key | string | ✓ | 認証用APIキー |
| tags | array[string] | - | 追加タグ |
| _id | ObjectId | ✓ | MongoDBドキュメントID（継承） |
| entry_datetime | datetime | ✓ | 作成タイムスタンプ（継承） |
| last_update_datetime | datetime | - | 更新タイムスタンプ（継承） |
| shard_key | string | ✓ | シャーディングキー（継承） |

**インデックス:**
- ユニークインデックス: terminal_id
- 複合インデックス: (tenant_id, store_code, terminal_no)
- インデックス: api_key

### 4. CashInOutLog（現金取引ログ）

レジドロワーの取引を記録するためのドキュメント。

**コレクション名:** `log_cash_in_out`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| store_name | string | ✓ | 表示用店舗名 |
| terminal_no | integer | ✓ | 端末番号 |
| staff_id | string | ✓ | 取引を実行したスタッフ |
| staff_name | string | ✓ | 表示用スタッフ名 |
| business_date | string | ✓ | ビジネス日付（YYYYMMDD） |
| open_counter | integer | ✓ | 端末オープンカウンター |
| business_counter | integer | ✓ | ビジネスカウンター |
| generate_date_time | string | ✓ | 取引タイムスタンプ |
| amount | float | ✓ | 金額（正=入金、負=出金） |
| description | string | - | 取引の説明 |
| receipt_text | string | ✓ | フォーマット済みレシートテキスト |
| journal_text | string | ✓ | フォーマット済みジャーナルテキスト |
| _id | ObjectId | ✓ | MongoDBドキュメントID（継承） |
| entry_datetime | datetime | ✓ | 作成タイムスタンプ（継承） |
| last_update_datetime | datetime | - | 更新タイムスタンプ（継承） |
| shard_key | string | ✓ | シャーディングキー（継承） |

**インデックス:**
- 複合インデックス: (tenant_id, store_code, terminal_no, business_date)
- インデックス: generate_date_time

### 5. OpenCloseLog（端末セッションログ）

端末の開店/閉店操作を記録するためのドキュメント。

**コレクション名:** `log_open_close`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| store_name | string | ✓ | 表示用店舗名 |
| terminal_no | integer | ✓ | 端末番号 |
| staff_id | string | ✓ | 操作を実行したスタッフ |
| staff_name | string | ✓ | 表示用スタッフ名 |
| business_date | string | ✓ | ビジネス日付（YYYYMMDD） |
| open_counter | integer | ✓ | 端末オープンカウンター |
| business_counter | integer | ✓ | ビジネスカウンター |
| operation | string | ✓ | 操作タイプ: 'open' または 'close' |
| generate_date_time | string | ✓ | 操作タイムスタンプ |
| terminal_info | TerminalInfoDocument | ✓ | 端末状態のスナップショット |
| cart_transaction_count | integer | ✓ | セッション中の取引数 |
| cart_transaction_last_no | integer | - | 最後の取引番号 |
| cash_in_out_count | integer | ✓ | 現金操作の数 |
| cash_in_out_last_datetime | string | - | 最後の現金操作タイムスタンプ |
| receipt_text | string | ✓ | フォーマット済みレシートテキスト |
| journal_text | string | ✓ | フォーマット済みジャーナルテキスト |
| _id | ObjectId | ✓ | MongoDBドキュメントID（継承） |
| entry_datetime | datetime | ✓ | 作成タイムスタンプ（継承） |
| last_update_datetime | datetime | - | 更新タイムスタンプ（継承） |
| shard_key | string | ✓ | シャーディングキー（継承） |

**インデックス:**
- 複合インデックス: (tenant_id, store_code, terminal_no, business_date, operation)
- インデックス: generate_date_time

### 6. TerminallogDeliveryStatus（イベント配信追跡）

pub/subイベントの配信ステータスを追跡するためのドキュメント。

**コレクション名:** `status_terminal_delivery`

**フィールド定義:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| event_id | string | ✓ | イベントUUID |
| published_at | datetime | ✓ | イベント公開タイムスタンプ |
| status | string | ✓ | 配信ステータス |
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| terminal_no | integer | ✓ | 端末番号 |
| business_date | string | ✓ | ビジネス日付（YYYYMMDD） |
| open_counter | integer | ✓ | 端末オープンカウンター |
| payload | object | ✓ | イベントメッセージ本体 |
| services | array[ServiceStatus] | ✓ | サービス配信ステータス |
| last_updated_at | datetime | ✓ | 最終更新タイムスタンプ |
| _id | ObjectId | ✓ | MongoDBドキュメントID（継承） |
| entry_datetime | datetime | ✓ | 作成タイムスタンプ（継承） |
| last_update_datetime | datetime | - | 更新タイムスタンプ（継承） |
| shard_key | string | ✓ | シャーディングキー（継承） |

## APIリクエスト/レスポンススキーマ

すべてのスキーマは`BaseSchemmaModel`から継承し、JSONシリアライゼーション用にフィールド名をsnake_caseからcamelCaseに自動変換します。

### 端末管理スキーマ

#### TerminalCreateRequest
新規端末を作成するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| storeCode | string | ✓ | 端末を作成する店舗コード |
| terminalNo | integer | ✓ | 端末番号（1-999） |
| description | string | ✓ | 端末の説明 |

#### TerminalUpdateRequest
端末情報を更新するリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| description | string | ✓ | 新しい端末の説明 |

#### Terminal（レスポンス）
端末情報レスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| terminalId | string | 一意の端末識別子 |
| tenantId | string | テナント識別子 |
| storeCode | string | 店舗コード |
| terminalNo | integer | 端末番号 |
| description | string | 端末の説明 |
| functionMode | string | 現在の機能モード |
| status | string | 端末ステータス |
| businessDate | string | 現在のビジネス日付 |
| openCounter | integer | オープンセッションカウンター |
| businessCounter | integer | ビジネスカウンター |
| initialAmount | float | 初期現金金額 |
| physicalAmount | float | 実際の現金カウント |
| staff | object | サインインしているスタッフ情報 |
| apiKey | string | 端末APIキー |
| entryDatetime | string | 作成タイムスタンプ |
| lastUpdateDatetime | string | 更新タイムスタンプ |

### 端末操作スキーマ

#### TerminalSignInRequest
スタッフサインインのリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| staffId | string | ✓ | スタッフ識別子 |

#### TerminalOpenRequest
ビジネス用端末を開くリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| initialAmount | float | ✓ | 初期レジドロワー金額 |

#### TerminalOpenResponse
端末オープン後のレスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| terminalId | string | 端末識別子 |
| businessDate | string | 割り当てられたビジネス日付 |
| openCounter | integer | オープンセッションカウンター |
| businessCounter | integer | ビジネスカウンター |
| initialAmount | float | 初期現金金額 |
| terminalInfo | object | 完全な端末情報 |
| receiptText | string | フォーマット済みレシートテキスト |
| journalText | string | フォーマット済みジャーナルテキスト |

#### TerminalCloseRequest
端末を閉じるリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| physicalAmount | float | ✓ | カウントされた現金金額 |

#### TerminalCloseResponse
端末クローズ後のレスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| terminalId | string | 端末識別子 |
| businessDate | string | ビジネス日付 |
| openCounter | integer | オープンセッションカウンター |
| businessCounter | integer | ビジネスカウンター |
| physicalAmount | float | 最終現金金額 |
| terminalInfo | object | 完全な端末情報 |
| receiptText | string | フォーマット済みレシートテキスト |
| journalText | string | フォーマット済みジャーナルテキスト |

### 現金操作スキーマ

#### CashInOutRequest
レジドロワー操作のリクエスト。

| フィールド名（JSON） | 型 | 必須 | 説明 |
|-------------------|------|----------|-------------|
| amount | float | ✓ | 金額（正=入金、負=出金） |
| description | string | - | 操作の説明 |

#### CashInOutResponse
現金操作後のレスポンス。

| フィールド名（JSON） | 型 | 説明 |
|-------------------|------|-------------|
| terminalId | string | 端末識別子 |
| amount | float | 取引金額 |
| description | string | 操作の説明 |
| receiptText | string | フォーマット済みレシートテキスト |
| journalText | string | フォーマット済みジャーナルテキスト |

## 列挙型

### 端末ステータス
- `Idle` - ビジネス用に開かれていない端末
- `Opened` - 端末がアクティブで準備完了
- `Closed` - その日の端末が閉じられた

### 機能モード
- `MainMenu` - デフォルト表示モード
- `OpenTerminal` - 端末開店操作
- `Sales` - 販売取引処理
- `Returns` - 返品取引処理
- `Void` - 取引取消
- `Reports` - レポート生成
- `CloseTerminal` - 端末閉店操作
- `Journal` - 取引履歴表示
- `Maintenance` - システムメンテナンス
- `CashInOut` - レジドロワー操作

### 店舗ステータス
- `Active` - 店舗は稼働中
- `Inactive` - 店舗は非稼働

### 配信ステータス
- `published` - イベントがpub/subに公開された
- `delivered` - すべてのサービスがイベントを受信
- `partially_delivered` - 一部のサービスがイベントを受信
- `failed` - 配信失敗

## データフローと関係

### 1. 端末ライフサイクル
```
端末作成 → APIキー生成 → スタッフサインイン → 端末オープン
    ↓
日次操作（販売、現金入出金） → 端末クローズ → 新ビジネス日付
```

### 2. マルチテナント構造
```
テナント
  └── 店舗（埋め込み）
        └── 端末（別コレクション）
              └── 取引ログ
```

### 3. イベント公開フロー
```
端末操作 → ログ生成 → Daprに公開 → 配信ステータス追跡
```

## セキュリティ機能

1. **APIキー管理**: 
   - `secrets.token_urlsafe(32)`を使用して生成
   - 端末ドキュメントに安全に保存
   - 端末認証に使用

2. **マルチテナント分離**:
   - テナントごとに個別のデータベース
   - データベース名形式: `{DB_NAME_PREFIX}_{tenant_id}`
   - すべての操作でテナントID検証

3. **監査証跡**:
   - すべての操作をタイムスタンプ付きでログ記録
   - すべての取引でスタッフ識別
   - 不変のログエントリ

## パフォーマンスの考慮事項

1. **埋め込みドキュメント**: クエリを削減するため、店舗はテナントドキュメント内に埋め込まれています
2. **インデックス**: 一般的なクエリパターン（端末別、日付別、ステータス別）に最適化
3. **シャーディング**: shard_keyによる水平スケーリングのサポート
4. **イベント配信**: スケーラビリティのための非同期pub/sub