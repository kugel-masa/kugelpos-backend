# 在庫サービス スナップショット仕様

## 概要

在庫サービスのスナップショット機能は、特定時点の在庫状態を完全に記録し、履歴データの参照や分析を可能にします。手動スナップショット作成と自動スケジュール実行の両方をサポートしています。

## スナップショットデータモデル

### StockSnapshotDocument

在庫スナップショットの完全な状態を保存するドキュメント。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "snapshot_id": "string (UUID)",
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

**フィールド説明:**
- `snapshot_id`: スナップショットの一意識別子（UUID形式）
- `total_items`: スナップショット時点の総アイテム数
- `total_quantity`: スナップショット時点の総在庫数量
- `stocks`: 各商品の在庫情報の配列
- `created_by`: スナップショット作成者（"system"または操作者ID）
- `generate_date_time`: スナップショット生成日時（ISO 8601形式）

### SnapshotScheduleDocument

スナップショットの自動作成スケジュール設定。

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "schedule_interval": "string (daily/weekly/monthly)",
  "schedule_hour": "integer (0-23)",
  "schedule_minute": "integer (0-59)",
  "schedule_day_of_week": "integer (0-6, optional)",
  "schedule_day_of_month": "integer (1-31, optional)",
  "retention_days": "integer (30-365)",
  "target_stores": ["string"],
  "enabled": "boolean",
  "last_executed_at": "datetime",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**フィールド説明:**
- `schedule_interval`: スケジュール間隔（日次/週次/月次）
- `schedule_hour/minute`: 実行時刻
- `schedule_day_of_week`: 週次スケジュールの曜日（0=月曜日）
- `schedule_day_of_month`: 月次スケジュールの日付
- `retention_days`: スナップショット保持期間（日数）
- `target_stores`: 対象店舗（["all"]で全店舗）
- `enabled`: スケジュールの有効/無効

## スナップショット操作

### 1. 手動スナップショット作成

**実装場所:** `/services/stock/app/services/snapshot_service.py:54`

```python
async def create_snapshot_async(
    self, 
    tenant_id: str, 
    store_code: str, 
    created_by: str = "system"
) -> StockSnapshotDocument
```

**処理フロー:**
1. 指定店舗の全在庫レコードを取得
2. アイテム数と総数量を集計
3. スナップショットドキュメントを作成
4. MongoDBに保存
5. 作成されたスナップショットを返却

**特徴:**
- 最大10,000アイテムまで一括処理
- トランザクション保証なし（読み取り一貫性のみ）

### 2. スナップショット照会

#### 一覧取得
**実装場所:** `/services/stock/app/services/snapshot_service.py:94`

```python
async def get_snapshots_async(
    self, 
    tenant_id: str, 
    store_code: str,
    page: int = 1,
    limit: int = 100
) -> Tuple[List[StockSnapshotDocument], int]
```

#### 日付範囲検索
**実装場所:** `/services/stock/app/services/snapshot_service.py:134`

```python
async def get_snapshots_by_date_range_async(
    self,
    tenant_id: str,
    store_code: str,
    start_date: datetime,
    end_date: datetime,
    page: int = 1,
    limit: int = 100
) -> Tuple[List[StockSnapshotDocument], int]
```

### 3. スケジュール管理

**実装場所:** `/services/stock/app/scheduler/multi_tenant_snapshot_scheduler.py`

#### スケジューラーアーキテクチャ

```python
class MultiTenantSnapshotScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running_locks = {}  # 重複実行防止
```

**主要メソッド:**

1. **スケジュール追加/更新**
   ```python
   async def add_or_update_schedule(
       self, 
       tenant_id: str, 
       schedule: SnapshotSchedule
   )
   ```

2. **スケジュール削除**
   ```python
   async def remove_schedule(self, tenant_id: str)
   ```

3. **実行ロジック**
   ```python
   async def _execute_snapshot_job(self, tenant_id: str)
   ```

**実行フロー:**
1. 重複実行チェック（メモリ内ロック）
2. スケジュール設定を取得
3. 対象店舗リストを決定
4. 各店舗でスナップショットを作成
5. 実行結果をログ記録
6. `last_executed_at`を更新

### 4. メンテナンス機能

#### 古いスナップショットの削除
**実装場所:** `/services/stock/app/services/snapshot_service.py:184`

```python
async def cleanup_old_snapshots_async(
    self, 
    tenant_id: str, 
    retention_days: int
) -> int
```

**自動削除:**
- TTLインデックスによる自動削除
- `created_at`フィールドに基づく
- 保持期間はスケジュール設定に従う

## インデックス定義

### stock_snapshots コレクション

```javascript
// ユニークインデックス
db.stock_snapshots.createIndex(
    { "snapshot_id": 1 }, 
    { unique: true }
)

// 複合インデックス（照会用）
db.stock_snapshots.createIndex(
    { "tenant_id": 1, "store_code": 1, "generate_date_time": -1 }
)

// TTLインデックス（自動削除用）
db.stock_snapshots.createIndex(
    { "created_at": 1 }, 
    { expireAfterSeconds: variable }  // 動的に設定
)
```

### snapshot_schedules コレクション

```javascript
// ユニークインデックス
db.snapshot_schedules.createIndex(
    { "tenant_id": 1 }, 
    { unique: true }
)
```

## スケジュール設定例

### 日次スナップショット（毎日午前2時）
```json
{
  "schedule_interval": "daily",
  "schedule_hour": 2,
  "schedule_minute": 0,
  "retention_days": 90,
  "target_stores": ["all"],
  "enabled": true
}
```

### 週次スナップショット（毎週月曜日午前3時）
```json
{
  "schedule_interval": "weekly",
  "schedule_hour": 3,
  "schedule_minute": 0,
  "schedule_day_of_week": 0,
  "retention_days": 180,
  "target_stores": ["STORE001", "STORE002"],
  "enabled": true
}
```

### 月次スナップショット（毎月1日午前4時）
```json
{
  "schedule_interval": "monthly",
  "schedule_hour": 4,
  "schedule_minute": 0,
  "schedule_day_of_month": 1,
  "retention_days": 365,
  "target_stores": ["all"],
  "enabled": true
}
```

## パフォーマンス考慮事項

1. **バッチ処理**: 最大10,000アイテムを一括取得
2. **非同期実行**: スケジュールジョブは非同期で実行
3. **重複防止**: メモリ内ロックで同一テナントの重複実行を防止
4. **ストレージ最適化**: TTLインデックスによる自動クリーンアップ
5. **インデックス最適化**: 日付範囲検索に最適化された複合インデックス

## セキュリティ

1. **テナント分離**: テナントIDによる完全なデータ分離
2. **権限チェック**: JWT認証による操作権限の検証
3. **監査証跡**: `created_by`フィールドで作成者を記録

## 制限事項

1. **トランザクション**: スナップショット作成時のトランザクション保証なし
2. **サイズ制限**: MongoDBドキュメントサイズ制限（16MB）
3. **スケジュール精度**: APSchedulerの精度に依存（通常±1秒）
4. **同時実行**: 同一テナントの複数スケジュールジョブは順次実行