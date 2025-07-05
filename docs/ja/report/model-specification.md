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

取引ログを保存するコレクション。BaseTransactionをTransactionLogModelに変換して保存。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "tran_id": "string",
  "tran_seq": "integer",
  "business_date": "string (YYYYMMDD)",
  "business_counter": "integer",
  "open_counter": "integer",
  "transaction_type": "string (purchase/refund/exchange/void)",
  "transaction_time": "datetime",
  "void_flag": "boolean",
  "items": [
    {
      "item_id": "string",
      "item_name": "string",
      "quantity": "integer",
      "unit_price": "decimal",
      "amount": "decimal",
      "discount_amount": "decimal",
      "tax_info": {
        "tax_code": "string",
        "tax_type": "string",
        "tax_name": "string",
        "target_amount": "decimal",
        "tax_amount": "decimal"
      }
    }
  ],
  "transaction_discount": "decimal",
  "item_total": "decimal",
  "excluded_tax_total": "decimal",
  "included_tax_total": "decimal",
  "tax_total": "decimal",
  "discount_total": "decimal",
  "total_amount": "decimal",
  "payments": [
    {
      "payment_code": "string",
      "payment_name": "string",
      "amount": "decimal",
      "change_amount": "decimal"
    }
  ],
  "tax_aggregation": [
    {
      "tax_code": "string",
      "tax_type": "string",
      "tax_name": "string",
      "item_count": "integer",
      "target_amount": "decimal",
      "tax_amount": "decimal"
    }
  ],
  "staff_id": "string",
  "customer_id": "string",
  "event_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 2. report_cashinout コレクション

入出金ログを保存するコレクション。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "cashinout_id": "string",
  "business_date": "string (YYYYMMDD)",
  "business_counter": "integer",
  "open_counter": "integer",
  "operation_type": "string (cash_in/cash_out)",
  "operation_time": "datetime",
  "amount": "decimal",
  "reason": "string",
  "staff_id": "string",
  "comment": "string",
  "event_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 3. report_open_close コレクション

開閉店ログを保存するコレクション。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "business_date": "string (YYYYMMDD)",
  "business_counter": "integer",
  "open_counter": "integer",
  "operation_type": "string (open/close)",
  "operation_time": "datetime",
  "cash_amount": "decimal",
  "staff_id": "string",
  "open_time": "datetime (closeの場合のみ)",
  "close_time": "datetime (closeの場合のみ)",
  "event_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 4. report_daily_info コレクション

日次情報を保存するコレクション。端末ごとの状態を管理。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "business_date": "string (YYYYMMDD)",
  "terminal_info": [
    {
      "terminal_no": "integer",
      "is_closed": "boolean",
      "close_time": "datetime",
      "transaction_count": "integer",
      "cashinout_count": "integer",
      "last_open_counter": "integer",
      "last_business_counter": "integer"
    }
  ],
  "all_terminals_closed": "boolean",
  "daily_report_generated": "boolean",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 5. report_aggregate_data コレクション

集計データを保存する汎用コレクション。フラッシュ・日次両方のレポートを格納。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer (nullは店舗合計)",
  "business_date": "string (YYYYMMDD)",
  "business_counter": "integer",
  "open_counter": "integer (flashのみ)",
  "report_scope": "string (flash/daily)",
  "report_type": "string (sales/category/item)",
  "report_data": {
    "sales_gross": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "sales_net": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "discount_for_lineitems": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "discount_for_subtotal": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "returns": {
      "item_count": "integer",
      "transaction_count": "integer",
      "total_amount": "decimal"
    },
    "taxes": [
      {
        "tax_code": "string",
        "tax_type": "string",
        "tax_name": "string",
        "item_count": "integer",
        "target_amount": "decimal",
        "tax_amount": "decimal"
      }
    ],
    "payments": [
      {
        "payment_code": "string",
        "payment_name": "string",
        "transaction_count": "integer",
        "total_amount": "decimal"
      }
    ],
    "cash": {
      "cash_in_count": "integer",
      "cash_in_amount": "decimal",
      "cash_out_count": "integer",
      "cash_out_amount": "decimal",
      "net_cash_movement": "decimal"
    },
    "receipt_text": "string",
    "journal_text": "string"
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

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