# レポートサービス モデル仕様

## 概要

レポートサービスのデータモデル仕様書です。MongoDBのコレクション構造、スキーマ定義、およびデータフローについて説明します。

## データベース設計

### データベース名
- `{tenant_id}_report` (例: `tenant001_report`)

### コレクション一覧

| コレクション名 | 用途 | 主なデータ |
|---------------|------|------------|
| report_transactions | 取引ログ保存 | カートからの取引データ |
| report_cashinout | 入出金ログ保存 | ターミナルからの入出金データ |
| report_open_close | 開閉店ログ保存 | ターミナルからの開閉店データ |
| report_daily_info | 日次情報保存 | 日次集計用のメタデータ |
| report_aggregate_data | 集計データ保存 | 生成されたレポートデータ |

## 詳細スキーマ定義

### 1. report_transactions コレクション

取引ログを保存するコレクション。kugel_commonの`BaseTransaction`構造を使用。

**注:** レポートサービスは専用のTransactionドキュメントモデルを持たず、共通ライブラリの`BaseTransaction`を直接使用します。構造の詳細はkugel_commonのドキュメントを参照してください。

**主要フィールド:**
- トランザクション識別子（tenant_id, store_code, terminal_no, transaction_no）
- ビジネス日付とカウンター情報
- 明細項目（line_items）、決済（payments）、税金（taxes）
- 金額と数量の合計
- レシート/ジャーナルテキスト

### 2. report_cashinout コレクション

入出金ログを保存するコレクション。

**継承:** `AbstractDocument`

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "staff_id": "string",
  "staff_name": "string",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "business_counter": "integer",
  "generate_date_time": "string (ISO 8601)",
  "amount": "float (正: 入金, 負: 出金)",
  "description": "string (入出金の理由・説明)",
  "receipt_text": "string",
  "journal_text": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**フィールド説明:**
- `amount`: 入金の場合は正の値、出金の場合は負の値
- `description`: 入出金の理由や説明

### 3. report_open_close コレクション

開閉店ログを保存するコレクション。

**継承:** `AbstractDocument`

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "staff_id": "string",
  "staff_name": "string",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "business_counter": "integer",
  "operation": "string (open/close)",
  "generate_date_time": "string (ISO 8601)",
  "terminal_info": "TerminalInfoDocument (端末情報スナップショット)",
  "cart_transaction_count": "integer (close時の取引数)",
  "cart_transaction_last_no": "integer (close時の最終取引番号)",
  "cash_in_out_count": "integer (close時の現金操作数)",
  "cash_in_out_last_datetime": "string (close時の最終現金操作日時)",
  "receipt_text": "string",
  "journal_text": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 4. report_daily_info コレクション

日次情報と検証ステータスを保存するコレクション。端末・営業日・開店回数ごとにデータ検証状態を管理。

**継承:** `AbstractDocument`

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "terminal_no": "integer",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "verified": "boolean (検証完了フラグ)",
  "verified_update_time": "string (最終検証日時)",
  "verified_message": "string (検証結果メッセージ)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**フィールド説明:**
- `verified`: データ検証が完了しているかどうか
- `verified_message`: 検証結果の詳細（成功/失敗理由）

### 5. レポート集計データ

レポートタイプごとに専用のドキュメントクラスを使用して集計データを保存します。

**実装構造:**
- `SalesReportDocument` - 売上レポート（コレクション: `report_sales`）
- `PaymentReportDocument` - 決済レポート（コレクション: `report_payment`）
- `CategoryReportDocument` - カテゴリレポート（コレクション: `report_category`）
- `ItemReportDocument` - 商品別レポート（コレクション: `report_item`）

**共通フィールド:**

| フィールド名 | 型 | 説明 |
|------------|------|-------------|
| tenant_id | string | テナント識別子 |
| store_code | string | 店舗コード |
| terminal_no | integer | 端末番号（nullは店舗合計） |
| business_date | string | 営業日（YYYYMMDD） |
| open_counter | integer | 開店カウンター（flashのみ） |
| report_scope | string | レポートスコープ（flash/daily） |

**SalesReportDocument追加フィールド:**
- `sales_gross`: 総売上（金額・数量・件数）
- `sales_net`: 純売上（金額・数量・件数）
- `discount_for_lineitems`: 明細割引
- `discount_for_subtotal`: 小計割引
- `returns`: 返品
- `voids`: 取消
- `taxes`: 税金集計リスト
- `payments`: 決済集計リスト
- `cash`: 現金入出金サマリー
- `receipt_text`, `journal_text`: フォーマット済みテキスト

## インデックス定義

### report_transactions
- 複合インデックス: `tenant_id + store_code + terminal_no + business_date + tran_id` (ユニーク)
- 複合インデックス: `tenant_id + store_code + business_date + open_counter`
- 単一インデックス: `event_id` (ユニーク)
- 単一インデックス: `created_at`

### report_cashinout
- 複合インデックス: `tenant_id + store_code + terminal_no + business_date`
- 複合インデックス: `tenant_id + store_code + business_date + open_counter`
- 単一インデックス: `event_id` (ユニーク)
- 単一インデックス: `created_at`

### report_open_close
- 複合インデックス: `tenant_id + store_code + terminal_no + business_date + operation_type`
- 複合インデックス: `tenant_id + store_code + business_date + open_counter`
- 単一インデックス: `event_id` (ユニーク)
- 単一インデックス: `created_at`

### report_daily_info
- 複合インデックス: `tenant_id + store_code + business_date` (ユニーク)
- 単一インデックス: `all_terminals_closed`

### report_aggregate_data
- 複合インデックス: `tenant_id + store_code + terminal_no + business_date + report_scope + report_type`
- 複合インデックス: `tenant_id + store_code + business_date + open_counter + report_scope + report_type`

## データフロー

### イベント駆動データフロー

1. **取引ログ処理**
   - トピック: `tranlog_report`
   - ソース: カートサービス
   - 処理フロー:
     1. BaseTransactionを受信
     2. event_idで重複チェック（Dapr state store使用）
     3. TransactionLogModelに変換
     4. report_transactionsに保存
     5. 集計データを更新

2. **入出金ログ処理**
   - トピック: `cashlog_report`
   - ソース: ターミナルサービス
   - 処理フロー:
     1. BaseCashInOutを受信
     2. event_idで重複チェック
     3. CashInOutLogModelに変換
     4. report_cashinoutに保存
     5. 現金移動集計を更新

3. **開閉店ログ処理**
   - トピック: `opencloselog_report`
   - ソース: ターミナルサービス
   - 処理フロー:
     1. BaseOpenCloseを受信
     2. event_idで重複チェック
     3. OpenCloseLogModelに変換
     4. report_open_closeに保存
     5. report_daily_infoを更新

### レポート生成フロー

1. **フラッシュレポート**
   - リアルタイムでイベントデータを集計
   - 端末単位またはstore全体で生成
   - report_aggregate_dataに保存（report_scope="flash"）

2. **日次レポート**
   - 全端末の閉店確認後に生成
   - report_daily_infoで状態管理
   - データ検証（ログ数の一致確認）
   - report_aggregate_dataに保存（report_scope="daily"）

## プラグインアーキテクチャ

### レポートプラグインインターフェース
```python
class IReportPlugin(ABC):
    async def generate_report(
        self,
        store_code: str,
        terminal_no: int,
        business_counter: int,
        business_date: str,
        open_counter: int,
        report_scope: str,
        report_type: str,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
    ) -> dict[str, any]
```

### 実装済みプラグイン
- **SalesReportPlugin**: 売上レポート生成
- **CategoryReportPlugin**: カテゴリー別レポート（未実装）
- **ItemReportPlugin**: 商品別レポート（未実装）

## 特記事項

1. **冪等性**: event_idによる重複防止とDapr state storeによる処理済み管理
2. **マルチテナント**: データベース名にテナントIDを含む完全分離
3. **パフォーマンス**: 適切なインデックスと集計データのキャッシュ
4. **拡張性**: プラグインアーキテクチャによる新レポートタイプの追加
5. **サーキットブレーカー**: DaprClientHelper経由で外部通信の障害対応
6. **データ整合性**: 日次レポート生成前の厳密なデータ検証