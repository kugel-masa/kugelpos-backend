# Stock Service Snapshot Specification

## Overview

The stock service snapshot functionality completely records the inventory state at specific points in time, enabling reference and analysis of historical data. It supports both manual snapshot creation and automatic scheduled execution.

## Snapshot Data Models

### StockSnapshotDocument

Document storing the complete state of stock snapshots.

**Implementation Location:** `/services/stock/app/models/documents/stock_snapshot_document.py`

```python
class StockSnapshotDocument(AbstractDocument):
    id: Optional[str] = Field(None, alias="_id")
    tenant_id: str
    store_code: str
    total_items: int
    total_quantity: float
    stocks: List[StockSnapshotItem] = Field(default_factory=list)
    created_by: str
    generate_date_time: Optional[str] = None  # ISO 8601 format
```

**StockSnapshotItem Subdocument:**
```python
class StockSnapshotItem(BaseModel):
    item_code: str
    quantity: float
    minimum_quantity: Optional[float] = None
    reorder_point: Optional[float] = None
    reorder_quantity: Optional[float] = None
```

**Field Descriptions:**
- `total_items`: Total number of items at snapshot time
- `total_quantity`: Total stock quantity at snapshot time
- `stocks`: Array of stock information for each product
- `created_by`: Snapshot creator ("system", "scheduled_system", or operator ID)
- `generate_date_time`: Snapshot generation date/time (ISO 8601 format)

### SnapshotScheduleDocument

Configuration for automatic snapshot creation schedule. One schedule per tenant.

**Implementation Location:** `/services/stock/app/models/documents/snapshot_schedule_document.py`

```python
class SnapshotScheduleDocument(AbstractDocument):
    tenant_id: str
    enabled: bool = True
    schedule_interval: str  # "daily", "weekly", "monthly"
    schedule_hour: int  # 0-23
    schedule_minute: int = 0  # 0-59
    schedule_day_of_week: Optional[int] = None  # 0-6 (for weekly, 0=Monday)
    schedule_day_of_month: Optional[int] = None  # 1-31 (for monthly)
    retention_days: int = 30
    target_stores: List[str] = ["all"]  # ["all"] or specific store codes
    last_executed_at: Optional[datetime] = None
    next_execution_at: Optional[datetime] = None
    created_by: str = "system"
    updated_by: str = "system"
```

**Field Descriptions:**
- `schedule_interval`: Schedule interval (daily/weekly/monthly)
- `schedule_hour/minute`: Execution time
- `schedule_day_of_week`: Day of week for weekly schedule (0=Monday)
- `schedule_day_of_month`: Date for monthly schedule
- `retention_days`: Snapshot retention period (days, default 30)
- `target_stores`: Target stores (["all"] for all stores)
- `enabled`: Schedule enabled/disabled
- `next_execution_at`: Next scheduled execution time
- `created_by/updated_by`: Creator/updater (default "system")

## Snapshot Operations

### 1. Manual Snapshot Creation

**Implementation Location:** `/services/stock/app/services/snapshot_service.py:20`

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
**Implementation Location:** `/services/stock/app/services/snapshot_service.py:76`

```python
async def get_snapshots_async(
    self,
    tenant_id: str,
    store_code: str,
    skip: int = 0,
    limit: int = 20
) -> Tuple[List[StockSnapshotDocument], int]
```

#### Date Range Search
**Implementation Location:** `/services/stock/app/services/snapshot_service.py:88`

```python
async def get_snapshots_by_date_range_async(
    self,
    tenant_id: str,
    store_code: str,
    start_date: datetime,
    end_date: datetime
) -> List[StockSnapshotDocument]
```

#### Generate DateTime Range Search
**Implementation Location:** `/services/stock/app/services/snapshot_service.py:104`

```python
async def get_snapshots_by_generate_date_time_async(
    self,
    tenant_id: str,
    store_code: str,
    start_date: Optional[str],
    end_date: Optional[str],
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[StockSnapshotDocument], int]
```

### 3. Schedule Management

**Implementation Location:** `/services/stock/app/services/multi_tenant_snapshot_scheduler.py`

#### Scheduler Architecture

```python
class MultiTenantSnapshotScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.tenant_jobs: Dict[str, str] = {}  # {tenant_id: job_id}
        self._lock = asyncio.Lock()  # For thread-safe operations
```

**Main Methods:**

1. **Initialize**
   ```python
   async def initialize(self, get_db_func)
   ```

2. **Add/Update Schedule**
   ```python
   async def update_tenant_schedule(self, schedule: SnapshotScheduleDocument)
   ```

3. **Remove Schedule**
   ```python
   async def remove_tenant_schedule(self, tenant_id: str)
   ```

4. **Execution Logic**
   ```python
   async def _execute_tenant_snapshot(self, tenant_id: str, schedule: SnapshotScheduleDocument)
   ```

5. **Get Status**
   ```python
   def get_status(self) -> dict
   ```

**Execution Flow:**
1. Check for duplicate execution (in-memory lock)
2. Retrieve schedule configuration
3. Determine target store list (`_get_target_stores`)
4. Create snapshots for each store (`created_by="scheduled_system"`)
5. Log execution results
6. Update `last_executed_at`

### 4. Maintenance Features

#### Delete Old Snapshots
**Implementation Location:** `/services/stock/app/services/snapshot_service.py:94`

```python
async def cleanup_old_snapshots_async(
    self,
    tenant_id: str,
    store_code: str,
    retention_days: int = 90
) -> int
```

**Automatic Deletion:**
- Automatic deletion via TTL index
- Based on `created_at` field
- Retention period follows schedule configuration

## Index Definitions

### stock_snapshots Collection

```python
class Settings:
    name = "stock_snapshots"
    indexes = [
        {"keys": [("tenant_id", 1), ("store_code", 1), ("created_at", -1)]},
        {"keys": [("tenant_id", 1), ("store_code", 1), ("generate_date_time", -1)]},
    ]
```

**TTL Index:**
- TTL index is dynamically set via `StockSnapshotRepository.ensure_ttl_index()`
- Based on `retention_days` from schedule configuration
- Implementation: `/services/stock/app/services/multi_tenant_snapshot_scheduler.py:100`

### snapshot_schedules Collection

```python
class Settings:
    name = "snapshot_schedules"
    indexes = [
        {
            "keys": [("tenant_id", 1)],
            "unique": True,
        }
    ]
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