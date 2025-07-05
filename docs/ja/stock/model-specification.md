# 在庫サービス モデル仕様

## 概要

在庫サービスのデータモデル仕様書です。MongoDBのコレクション構造、スキーマ定義、およびデータフローについて説明します。

## データベース設計

### データベース名
- `{tenant_id}_stock` (例: `tenant001_stock`)

### コレクション一覧

| コレクション名 | 用途 | 主なデータ |
|---------------|------|------------|
| stock | 現在在庫レベル | 商品別の在庫数量と発注情報 |
| stock_update | 在庫更新履歴 | すべての在庫変更の監査証跡 |
| stock_snapshot | 在庫スナップショット | 特定時点の在庫状態 |
| snapshot_schedule | スナップショットスケジュール | 自動スナップショット設定 |

## 詳細スキーマ定義

### 1. stock コレクション

現在の在庫レベルと発注管理情報を保存するコレクション。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "item_code": "string",
  "current_quantity": "decimal",
  "minimum_quantity": "decimal",
  "reorder_point": "decimal",
  "reorder_quantity": "decimal",
  "last_transaction_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**フィールド説明:**
- `current_quantity`: 現在の在庫数量（マイナス可）
- `minimum_quantity`: 最小在庫アラート閾値
- `reorder_point`: 発注点アラート閾値
- `reorder_quantity`: 推奨発注数量
- `last_transaction_id`: 最後に在庫を変更した取引ID

### 2. stock_update コレクション

在庫更新の完全な履歴を保存するコレクション。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "item_code": "string",
  "update_type": "string (SALE/RETURN/VOID/VOID_RETURN/PURCHASE/ADJUSTMENT/INITIAL/DAMAGE/TRANSFER_IN/TRANSFER_OUT)",
  "quantity_change": "decimal",
  "before_quantity": "decimal",
  "after_quantity": "decimal",
  "reference_id": "string",
  "operator_id": "string",
  "note": "string",
  "timestamp": "datetime",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**更新タイプ説明:**
- `SALE`: 販売による減少
- `RETURN`: 返品による増加
- `VOID`: 販売取消による増加
- `VOID_RETURN`: 返品取消による減少
- `PURCHASE`: 仕入による増加
- `ADJUSTMENT`: 手動調整
- `INITIAL`: 初期在庫設定
- `DAMAGE`: 破損による減少
- `TRANSFER_IN`: 他店舗からの移動入庫
- `TRANSFER_OUT`: 他店舗への移動出庫

### 3. stock_snapshot コレクション

特定時点の在庫状態を保存するコレクション。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "total_items": "integer",
  "total_quantity": "decimal",
  "stocks": [
    {
      "item_code": "string",
      "quantity": "decimal",
      "minimum_quantity": "decimal",
      "reorder_point": "decimal",
      "reorder_quantity": "decimal"
    }
  ],
  "created_by": "string",
  "generate_date_time": "string (ISO 8601)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 4. snapshot_schedule コレクション

自動スナップショットのスケジュール設定を保存するコレクション。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "daily": {
    "enabled": "boolean",
    "time": "string (HH:mm)",
    "timezone": "string"
  },
  "weekly": {
    "enabled": "boolean",
    "day_of_week": "integer (0-6)",
    "time": "string (HH:mm)",
    "timezone": "string"
  },
  "monthly": {
    "enabled": "boolean",
    "day_of_month": "integer (1-31)",
    "time": "string (HH:mm)",
    "timezone": "string"
  },
  "retention_days": "integer",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## インデックス定義

### stock
- ユニーク複合インデックス: `tenant_id + store_code + item_code`
- 複合インデックス: `tenant_id + store_code + minimum_quantity`
- 複合インデックス: `tenant_id + store_code + reorder_point`

### stock_update
- 複合インデックス: `tenant_id + store_code + item_code + timestamp`
- 複合インデックス: `tenant_id + reference_id`
- 単一インデックス: `update_type`
- 単一インデックス: `timestamp`

### stock_snapshot
- 複合インデックス: `tenant_id + store_code + created_at`
- 複合インデックス: `tenant_id + store_code + generate_date_time`
- TTLインデックス: `created_at` (retention_daysに基づく自動削除)

### snapshot_schedule
- ユニークインデックス: `tenant_id`

## データフロー

### イベント駆動データフロー

1. **取引ログ処理**
   - トピック: `tranlog_stock`
   - ソース: カートサービス
   - 処理フロー:
     1. BaseTransactionを受信
     2. event_idで重複チェック（Dapr state store使用）
     3. 各明細項目の在庫を更新
     4. stock_updateに履歴を記録
     5. アラート評価とWebSocket通知
     6. カートサービスに処理完了通知

2. **在庫アラート**
   - 在庫更新時に閾値チェック
   - WebSocketで接続クライアントに通知
   - アラートクールダウンで重複防止

### スナップショット管理

1. **手動スナップショット**
   - API経由で即座に作成
   - 全在庫の現在状態を記録

2. **自動スナップショット**
   - スケジューラーによる定期実行
   - 日次/週次/月次の設定可能
   - 保持期間による自動削除

## WebSocketリアルタイム通知

### 接続管理
- エンドポイント: `/ws/{tenant_id}/{store_code}`
- JWT認証必須（30秒以内）
- テナント・店舗単位でグループ化

### アラートタイプ

1. **最小在庫アラート**
```json
{
  "type": "low_stock",
  "itemCode": "ITEM001",
  "itemName": "商品001",
  "currentQuantity": 15,
  "minimumQuantity": 20,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

2. **発注点アラート**
```json
{
  "type": "reorder_alert",
  "itemCode": "ITEM001",
  "itemName": "商品001",
  "currentQuantity": 25,
  "reorderPoint": 30,
  "reorderQuantity": 50,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 原子性とデータ整合性

### 在庫更新の原子性
- MongoDB `findOneAndUpdate`による原子的更新
- 更新と履歴記録の一貫性保証
- 楽観的ロックによる同時更新制御

### 冪等性
- event_idによる重複処理防止
- Dapr state storeでの処理済み管理
- メッセージ再送に対する耐性

## スケジューラーアーキテクチャ

### スナップショットスケジューラー
- APSchedulerベースの実装
- テナント単位のジョブ管理
- 動的なスケジュール更新
- 分散環境での重複実行防止

### スケジュール設定
```python
{
  "daily": {
    "enabled": True,
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "weekly": {
    "enabled": False,
    "day_of_week": 0,  # 0=月曜日
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "monthly": {
    "enabled": True,
    "day_of_month": 1,
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "retention_days": 90
}
```

## 特記事項

1. **マイナス在庫**: バックオーダー対応のためマイナス在庫を許可
2. **マルチテナント**: データベースレベルでの完全分離
3. **監査証跡**: すべての在庫変更を完全に記録
4. **パフォーマンス**: 適切なインデックスによる高速クエリ
5. **拡張性**: 水平スケーリングに対応した設計
6. **レジリエンス**: サーキットブレーカーパターンの実装