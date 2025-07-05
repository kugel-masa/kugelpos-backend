# Stock Service Snapshot Specification

## Overview

The stock service snapshot functionality completely records the inventory state at specific points in time, enabling reference and analysis of historical data. It supports both manual snapshot creation and automatic scheduled execution.

## Snapshot Data Models

### StockSnapshotDocument

Document storing the complete state of stock snapshots.

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

**Field Descriptions:**
- `snapshot_id`: Unique snapshot identifier (UUID format)
- `total_items`: Total number of items at snapshot time
- `total_quantity`: Total stock quantity at snapshot time
- `stocks`: Array of stock information for each product
- `created_by`: Snapshot creator ("system" or operator ID)
- `generate_date_time`: Snapshot generation date/time (ISO 8601 format)

### SnapshotScheduleDocument

Configuration for automatic snapshot creation schedule.

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

**Field Descriptions:**
- `schedule_interval`: Schedule interval (daily/weekly/monthly)
- `schedule_hour/minute`: Execution time
- `schedule_day_of_week`: Day of week for weekly schedule (0=Monday)
- `schedule_day_of_month`: Date for monthly schedule
- `retention_days`: Snapshot retention period (days)
- `target_stores`: Target stores (["all"] for all stores)
- `enabled`: Schedule enabled/disabled

## Snapshot Operations

### 1. Manual Snapshot Creation

**Implementation Location:** `/services/stock/app/services/snapshot_service.py:54`

```python
async def create_snapshot_async(
    self, 
    tenant_id: str, 
    store_code: str, 
    created_by: str = "system"
) -> StockSnapshotDocument
```

**Processing Flow:**
1. Retrieve all stock records for specified store
2. Aggregate item count and total quantity
3. Create snapshot document
4. Save to MongoDB
5. Return created snapshot

**Features:**
- Batch processing up to 10,000 items
- No transaction guarantee (read consistency only)

### 2. Snapshot Queries

#### Get List
**Implementation Location:** `/services/stock/app/services/snapshot_service.py:94`

```python
async def get_snapshots_async(
    self, 
    tenant_id: str, 
    store_code: str,
    page: int = 1,
    limit: int = 100
) -> Tuple[List[StockSnapshotDocument], int]
```

#### Date Range Search
**Implementation Location:** `/services/stock/app/services/snapshot_service.py:134`

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

### 3. Schedule Management

**Implementation Location:** `/services/stock/app/scheduler/multi_tenant_snapshot_scheduler.py`

#### Scheduler Architecture

```python
class MultiTenantSnapshotScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running_locks = {}  # Duplicate execution prevention
```

**Main Methods:**

1. **Add/Update Schedule**
   ```python
   async def add_or_update_schedule(
       self, 
       tenant_id: str, 
       schedule: SnapshotSchedule
   )
   ```

2. **Remove Schedule**
   ```python
   async def remove_schedule(self, tenant_id: str)
   ```

3. **Execution Logic**
   ```python
   async def _execute_snapshot_job(self, tenant_id: str)
   ```

**Execution Flow:**
1. Check for duplicate execution (in-memory lock)
2. Retrieve schedule configuration
3. Determine target store list
4. Create snapshots for each store
5. Log execution results
6. Update `last_executed_at`

### 4. Maintenance Features

#### Delete Old Snapshots
**Implementation Location:** `/services/stock/app/services/snapshot_service.py:184`

```python
async def cleanup_old_snapshots_async(
    self, 
    tenant_id: str, 
    retention_days: int
) -> int
```

**Automatic Deletion:**
- Automatic deletion via TTL index
- Based on `created_at` field
- Retention period follows schedule configuration

## Index Definitions

### stock_snapshots Collection

```javascript
// Unique index
db.stock_snapshots.createIndex(
    { "snapshot_id": 1 }, 
    { unique: true }
)

// Compound index (for queries)
db.stock_snapshots.createIndex(
    { "tenant_id": 1, "store_code": 1, "generate_date_time": -1 }
)

// TTL index (for automatic deletion)
db.stock_snapshots.createIndex(
    { "created_at": 1 }, 
    { expireAfterSeconds: variable }  // Dynamically configured
)
```

### snapshot_schedules Collection

```javascript
// Unique index
db.snapshot_schedules.createIndex(
    { "tenant_id": 1 }, 
    { unique: true }
)
```

## Schedule Configuration Examples

### Daily Snapshot (Every day at 2:00 AM)
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

### Weekly Snapshot (Every Monday at 3:00 AM)
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

### Monthly Snapshot (1st of every month at 4:00 AM)
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

## Performance Considerations

1. **Batch Processing**: Batch retrieval of up to 10,000 items
2. **Asynchronous Execution**: Schedule jobs execute asynchronously
3. **Duplicate Prevention**: In-memory locks prevent duplicate execution for same tenant
4. **Storage Optimization**: Automatic cleanup via TTL indexes
5. **Index Optimization**: Compound indexes optimized for date range searches

## Security

1. **Tenant Isolation**: Complete data isolation by tenant ID
2. **Permission Checks**: Operation permission verification via JWT authentication
3. **Audit Trail**: Creator recorded in `created_by` field

## Limitations

1. **Transactions**: No transaction guarantee during snapshot creation
2. **Size Limit**: MongoDB document size limit (16MB)
3. **Schedule Precision**: Depends on APScheduler precision (typically ±1 second)
4. **Concurrent Execution**: Multiple schedule jobs for same tenant execute sequentially