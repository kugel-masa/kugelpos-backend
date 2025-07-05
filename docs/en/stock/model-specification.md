# Stock Service Model Specification

## Overview

This document provides the data model specifications for the Stock service, including MongoDB collection structures, schema definitions, and data flows.

## Database Design

### Database Name
- `{tenant_id}_stock` (e.g., `tenant001_stock`)

### Collection List

| Collection Name | Purpose | Main Data |
|---------------|------|------------|
| stock | Current stock levels | Stock quantities and reorder information by item |
| stock_update | Stock update history | Audit trail of all stock changes |
| stock_snapshot | Stock snapshots | Stock state at specific points in time |
| snapshot_schedule | Snapshot schedules | Automatic snapshot configuration |

## Detailed Schema Definitions

### 1. stock Collection

Collection storing current stock levels and reorder management information.

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

**Field Descriptions:**
- `current_quantity`: Current stock quantity (negative allowed)
- `minimum_quantity`: Minimum stock alert threshold
- `reorder_point`: Reorder point alert threshold
- `reorder_quantity`: Recommended reorder quantity
- `last_transaction_id`: Transaction ID that last modified the stock

### 2. stock_update Collection

Collection storing complete history of stock updates.

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

**Update Type Descriptions:**
- `SALE`: Decrease due to sales
- `RETURN`: Increase due to returns
- `VOID`: Increase due to sale cancellation
- `VOID_RETURN`: Decrease due to return cancellation
- `PURCHASE`: Increase due to procurement
- `ADJUSTMENT`: Manual adjustment
- `INITIAL`: Initial stock setup
- `DAMAGE`: Decrease due to damage
- `TRANSFER_IN`: Incoming transfer from other stores
- `TRANSFER_OUT`: Outgoing transfer to other stores

### 3. stock_snapshot Collection

Collection storing stock state at specific points in time.

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

### 4. snapshot_schedule Collection

Collection storing automatic snapshot schedule configuration.

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

## Index Definitions

### stock
- Unique compound index: `tenant_id + store_code + item_code`
- Compound index: `tenant_id + store_code + minimum_quantity`
- Compound index: `tenant_id + store_code + reorder_point`

### stock_update
- Compound index: `tenant_id + store_code + item_code + timestamp`
- Compound index: `tenant_id + reference_id`
- Single index: `update_type`
- Single index: `timestamp`

### stock_snapshot
- Compound index: `tenant_id + store_code + created_at`
- Compound index: `tenant_id + store_code + generate_date_time`
- TTL index: `created_at` (automatic deletion based on retention_days)

### snapshot_schedule
- Unique index: `tenant_id`

## Data Flow

### Event-Driven Data Flow

1. **Transaction Log Processing**
   - Topic: `tranlog_stock`
   - Source: Cart service
   - Processing flow:
     1. Receive BaseTransaction
     2. Duplicate check by event_id (using Dapr state store)
     3. Update stock for each line item
     4. Record history in stock_update
     5. Evaluate alerts and WebSocket notifications
     6. Send processing completion notification to Cart service

2. **Stock Alerts**
   - Threshold check during stock updates
   - Notification to connected clients via WebSocket
   - Duplicate prevention through alert cooldown

### Snapshot Management

1. **Manual Snapshots**
   - Created immediately via API
   - Records current state of all stock

2. **Automatic Snapshots**
   - Periodic execution by scheduler
   - Configurable daily/weekly/monthly
   - Automatic deletion based on retention period

## WebSocket Real-time Notifications

### Connection Management
- Endpoint: `/ws/{tenant_id}/{store_code}`
- JWT authentication required (within 30 seconds)
- Grouped by tenant and store

### Alert Types

1. **Minimum Stock Alert**
```json
{
  "type": "low_stock",
  "itemCode": "ITEM001",
  "itemName": "Product 001",
  "currentQuantity": 15,
  "minimumQuantity": 20,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

2. **Reorder Point Alert**
```json
{
  "type": "reorder_alert",
  "itemCode": "ITEM001",
  "itemName": "Product 001",
  "currentQuantity": 25,
  "reorderPoint": 30,
  "reorderQuantity": 50,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Atomicity and Data Consistency

### Stock Update Atomicity
- Atomic updates using MongoDB `findOneAndUpdate`
- Consistency guarantee between updates and history records
- Concurrent update control through optimistic locking

### Idempotency
- Duplicate processing prevention by event_id
- Processing state management via Dapr state store
- Resilience against message retransmission

## Scheduler Architecture

### Snapshot Scheduler
- APScheduler-based implementation
- Job management per tenant
- Dynamic schedule updates
- Prevention of duplicate execution in distributed environments

### Schedule Configuration
```python
{
  "daily": {
    "enabled": True,
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "weekly": {
    "enabled": False,
    "day_of_week": 0,  # 0=Monday
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

## Special Notes

1. **Negative Stock**: Allows negative stock to support backorders
2. **Multi-tenancy**: Complete isolation at database level
3. **Audit Trail**: Complete recording of all stock changes
4. **Performance**: High-speed queries through appropriate indexes
5. **Scalability**: Design supports horizontal scaling
6. **Resilience**: Implementation of circuit breaker pattern