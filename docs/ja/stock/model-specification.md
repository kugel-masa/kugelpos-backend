# 在庫サービス モデル仕様

## 概要

在庫サービスのデータモデル仕様書です。MongoDBのコレクション構造、スキーマ定義、およびデータフローについて説明します。

## データベース設計

### データベース名
- `{tenant_id}_stock` (例: `tenant001_stock`)

### コレクション一覧

| コレクション名 | 用途 | 主なデータ |
|---------------|------|------------|
| stocks | 現在在庫レベル | 商品別の在庫数量と発注情報 |
| stock_updates | 在庫更新履歴 | すべての在庫変更の監査証跡 |
| stock_snapshots | 在庫スナップショット | 特定時点の在庫状態 |
| snapshot_schedules | スナップショットスケジュール | 自動スナップショット設定 |

## 詳細スキーマ定義

### 1. stocks コレクション

現在の在庫レベルと発注管理情報を保存するコレクション。

**継承:** `AbstractDocument`

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| item_code | string | ✓ | 商品コード |
| current_quantity | float | - | 現在の在庫数量（デフォルト: 0.0、マイナス可） |
| minimum_quantity | float | - | 最小在庫アラート閾値（デフォルト: 0.0） |
| reorder_point | float | - | 発注点アラート閾値（デフォルト: 0.0） |
| reorder_quantity | float | - | 推奨発注数量（デフォルト: 0.0） |
| last_transaction_id | string | - | 最後に在庫を変更した取引ID |

**インデックス:**
- ユニーク複合: (tenant_id, store_code, item_code)
- 複合: (tenant_id, store_code, minimum_quantity)
- 複合: (tenant_id, store_code, reorder_point)

### 2. stock_updates コレクション

在庫更新の完全な履歴を保存するコレクション。

**継承:** `AbstractDocument`

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| item_code | string | ✓ | 商品コード |
| update_type | UpdateType | ✓ | 更新タイプ |
| quantity_change | float | ✓ | 数量変更（増加:正、減少:負） |
| before_quantity | float | ✓ | 更新前の在庫数量 |
| after_quantity | float | ✓ | 更新後の在庫数量 |
| reference_id | string | - | 参照ID（取引ID、調整ID等） |
| timestamp | datetime | ✓ | 更新日時 |
| operator_id | string | - | 操作実行者ID |
| note | string | - | 追加メモ |

**UpdateType列挙値:**
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

**インデックス:**
- 複合: (tenant_id, store_code, item_code, timestamp DESC)
- update_type
- timestamp DESC
- reference_id

### 3. stock_snapshots コレクション

特定時点の在庫状態を保存するコレクション。

**継承:** `AbstractDocument`

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| store_code | string | ✓ | 店舗コード |
| total_items | integer | ✓ | 商品アイテム数 |
| total_quantity | float | ✓ | 総在庫数量 |
| stocks | array[StockSnapshotItem] | - | 商品別在庫詳細リスト |
| created_by | string | ✓ | 作成者（ユーザーまたはシステム） |
| generate_date_time | string | - | 生成日時（ISO 8601形式） |

**StockSnapshotItemサブドキュメント:**

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| item_code | string | ✓ | 商品コード |
| quantity | float | ✓ | 在庫数量 |
| minimum_quantity | float | - | 最小在庫閾値 |
| reorder_point | float | - | 発注点閾値 |
| reorder_quantity | float | - | 推奨発注数量 |

**インデックス:**
- 複合: (tenant_id, store_code, created_at DESC)
- 複合: (tenant_id, store_code, generate_date_time DESC)

### 4. snapshot_schedules コレクション

自動スナップショットのスケジュール設定を保存するコレクション。テナント単位で1つのスケジュールを管理。

**継承:** `AbstractDocument`

| フィールド名 | 型 | 必須 | 説明 |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | テナント識別子 |
| enabled | boolean | - | スケジュール有効フラグ（デフォルト: true） |
| schedule_interval | string | ✓ | スケジュール間隔（"daily"/"weekly"/"monthly"） |
| schedule_hour | integer | ✓ | 実行時間（0-23） |
| schedule_minute | integer | - | 実行分（0-59、デフォルト: 0） |
| schedule_day_of_week | integer | - | 曜日（0-6、0=月曜日、weeklyの場合） |
| schedule_day_of_month | integer | - | 日（1-31、monthlyの場合） |
| retention_days | integer | - | 保持日数（デフォルト: 30） |
| target_stores | array[string] | - | 対象店舗リスト（デフォルト: ["all"]） |
| last_executed_at | datetime | - | 最終実行日時 |
| next_execution_at | datetime | - | 次回実行予定日時 |
| created_by | string | - | 作成者（デフォルト: "system"） |
| updated_by | string | - | 更新者（デフォルト: "system"） |

**インデックス:**
- ユニーク: tenant_id

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
   - APSchedulerによる定期実行
   - テナント単位で1つのスケジュール設定
   - schedule_intervalで日次/週次/月次を選択
   - target_storesで対象店舗を指定可能
   - retention_daysによる自動削除

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

### スケジュール設定例

**日次スナップショット:**
```python
{
  "tenant_id": "tenant001",
  "enabled": True,
  "schedule_interval": "daily",
  "schedule_hour": 2,
  "schedule_minute": 0,
  "retention_days": 30,
  "target_stores": ["all"]
}
```

**週次スナップショット（月曜日）:**
```python
{
  "tenant_id": "tenant001",
  "enabled": True,
  "schedule_interval": "weekly",
  "schedule_hour": 2,
  "schedule_minute": 0,
  "schedule_day_of_week": 0,  # 0=月曜日
  "retention_days": 90,
  "target_stores": ["STORE001", "STORE002"]
}
```

**月次スナップショット（1日）:**
```python
{
  "tenant_id": "tenant001",
  "enabled": True,
  "schedule_interval": "monthly",
  "schedule_hour": 2,
  "schedule_minute": 0,
  "schedule_day_of_month": 1,
  "retention_days": 365,
  "target_stores": ["all"]
}
```

## 特記事項

1. **マイナス在庫**: バックオーダー対応のためマイナス在庫を許可
2. **マルチテナント**: データベースレベルでの完全分離
3. **監査証跡**: すべての在庫変更を完全に記録
4. **パフォーマンス**: 適切なインデックスによる高速クエリ
5. **拡張性**: 水平スケーリングに対応した設計
6. **レジリエンス**: サーキットブレーカーパターンの実装