# Stock Service API Specification

## Overview

Manages inventory tracking. Provides snapshot functionality and reorder point management.

## Service Information

- **Port**: 8006
- **Framework**: FastAPI
- **Database**: MongoDB (Motor async driver)

## Base URL

- Local Environment: `http://localhost:8006`
- Production Environment: `https://stock.{domain}`

## Authentication

The following authentication methods are supported:

### API Key Authentication
- Header: `X-API-Key: {api_key}`
- Usage: API calls from terminals

### JWT Token Authentication
- Header: `Authorization: Bearer {token}`
- Usage: System operations by administrators

## Common Response Format

```json
{
  "success": true,
  "code": 200,
  "message": "Operation completed successfully",
  "data": {
    "...": "..."
  },
  "operation": "operation_name"
}
```

## API Endpoints

### System

### 1. Root

**GET** `/`

Root endpoint that returns a welcome message.
Useful for health checks and API verification.

**Response:**

### 2. Health Check

**GET** `/health`

Health check endpoint for monitoring service health.

**Response:**

**Response Example:**
```json
{
  "status": "healthy",
  "timestamp": "string",
  "service": "string",
  "version": "string",
  "checks": {}
}
```

### Tenant

### 3. Create Tenant

**POST** `/api/v1/tenants`

Create and set up a new tenant in the stock service.

This endpoint initializes the database for a new tenant by creating all required
collections, indexes, and other necessary structures. It is typically called during
tenant onboarding after the tenant has been created in the account service.

Authentication is required and the authenticated user must belong to the tenant
being created. This ensures only authorized users can set up tenant resources.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |

**Request Example:**
```json
{
  "tenantId": "string"
}
```

**Response:**

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 4. Get snapshot schedule configuration

**GET** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

Get the snapshot schedule configuration for a tenant

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `SnapshotScheduleResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `enabled` | boolean | No | - |
| `schedule_interval` | string | Yes | Schedule interval: daily, weekly, monthly |
| `schedule_hour` | integer | Yes | Execution hour (0-23) |
| `schedule_minute` | integer | No | Execution minute (0-59) |
| `schedule_day_of_week` | integer | No | Day of week for weekly schedule (0=Monday, 6=Sunda |
| `schedule_day_of_month` | integer | No | Day of month for monthly schedule (1-31) |
| `retention_days` | integer | No | Snapshot retention days |
| `target_stores` | array[string] | No | Target stores: ['all'] or specific store codes |
| `tenant_id` | string | Yes | - |
| `last_executed_at` | string | No | - |
| `next_execution_at` | string | No | - |
| `created_at` | string | No | - |
| `updated_at` | string | No | - |
| `created_by` | string | No | - |
| `updated_by` | string | No | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "enabled": true,
    "schedule_interval": "string",
    "schedule_hour": 0,
    "schedule_minute": 0,
    "schedule_day_of_week": 0,
    "schedule_day_of_month": 0,
    "retention_days": 30,
    "target_stores": [
      "all"
    ],
    "tenant_id": "string",
    "last_executed_at": "2025-01-01T00:00:00Z"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 5. Update snapshot schedule configuration

**PUT** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

Update the snapshot schedule configuration for a tenant

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `enabled` | boolean | No | - |
| `schedule_interval` | string | Yes | Schedule interval: daily, weekly, monthly |
| `schedule_hour` | integer | Yes | Execution hour (0-23) |
| `schedule_minute` | integer | No | Execution minute (0-59) |
| `schedule_day_of_week` | integer | No | Day of week for weekly schedule (0=Monday, 6=Sunda |
| `schedule_day_of_month` | integer | No | Day of month for monthly schedule (1-31) |
| `retention_days` | integer | No | Snapshot retention days |
| `target_stores` | array[string] | No | Target stores: ['all'] or specific store codes |

**Request Example:**
```json
{
  "enabled": true,
  "schedule_interval": "string",
  "schedule_hour": 0,
  "schedule_minute": 0,
  "schedule_day_of_week": 0,
  "schedule_day_of_month": 0,
  "retention_days": 30,
  "target_stores": [
    "all"
  ]
}
```

**Response:**

**data Field:** `SnapshotScheduleResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `enabled` | boolean | No | - |
| `schedule_interval` | string | Yes | Schedule interval: daily, weekly, monthly |
| `schedule_hour` | integer | Yes | Execution hour (0-23) |
| `schedule_minute` | integer | No | Execution minute (0-59) |
| `schedule_day_of_week` | integer | No | Day of week for weekly schedule (0=Monday, 6=Sunda |
| `schedule_day_of_month` | integer | No | Day of month for monthly schedule (1-31) |
| `retention_days` | integer | No | Snapshot retention days |
| `target_stores` | array[string] | No | Target stores: ['all'] or specific store codes |
| `tenant_id` | string | Yes | - |
| `last_executed_at` | string | No | - |
| `next_execution_at` | string | No | - |
| `created_at` | string | No | - |
| `updated_at` | string | No | - |
| `created_by` | string | No | - |
| `updated_by` | string | No | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "enabled": true,
    "schedule_interval": "string",
    "schedule_hour": 0,
    "schedule_minute": 0,
    "schedule_day_of_week": 0,
    "schedule_day_of_month": 0,
    "retention_days": 30,
    "target_stores": [
      "all"
    ],
    "tenant_id": "string",
    "last_executed_at": "2025-01-01T00:00:00Z"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 6. Delete snapshot schedule configuration

**DELETE** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

Delete the snapshot schedule configuration for a tenant (reverts to defaults)

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### Stock

### 7. Get stock list for a store

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock`

Get all stock items for a store with pagination

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `page` | integer | No | 1 | Page number |
| `limit` | integer | No | 100 | Maximum number of items to return |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `PaginatedResult_StockResponse_`

| Field | Type | Required | Description |
|------------|------|------|------|
| `data` | array[StockResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "itemCode": "string",
        "currentQuantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0,
        "lastUpdated": "2025-01-01T00:00:00Z",
        "lastTransactionId": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 8. Get low stock items

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/low`

Get items with stock below minimum quantity

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `PaginatedResult_StockResponse_`

| Field | Type | Required | Description |
|------------|------|------|------|
| `data` | array[StockResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "itemCode": "string",
        "currentQuantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0,
        "lastUpdated": "2025-01-01T00:00:00Z",
        "lastTransactionId": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 9. Get reorder alert items

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/reorder-alerts`

Get items with stock at or below reorder point

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `PaginatedResult_StockResponse_`

| Field | Type | Required | Description |
|------------|------|------|------|
| `data` | array[StockResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "itemCode": "string",
        "currentQuantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0,
        "lastUpdated": "2025-01-01T00:00:00Z",
        "lastTransactionId": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 10. Create stock snapshot

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

Create a snapshot of current stock levels

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `createdBy` | string | No | User or system that created the snapshot |

**Request Example:**
```json
{
  "createdBy": "system"
}
```

**Response:**

**data Field:** `StockSnapshotResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | Tenant ID |
| `storeCode` | string | Yes | Store code |
| `totalItems` | integer | Yes | Total number of items |
| `totalQuantity` | number | Yes | Total stock quantity |
| `stocks` | array[StockSnapshotItemResponse] | Yes | Stock details by item |
| `createdBy` | string | Yes | User or system that created the snapshot |
| `createdAt` | string | Yes | Creation timestamp |
| `updatedAt` | string | No | Last update timestamp |
| `generateDateTime` | string | No | Snapshot generation datetime in ISO format |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "totalItems": 0,
    "totalQuantity": 0.0,
    "stocks": [
      {
        "itemCode": "string",
        "quantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0
      }
    ],
    "createdBy": "string",
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-01T00:00:00Z",
    "generateDateTime": "string"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 11. Get stock snapshot by ID

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}`

Get a specific stock snapshot by its ID

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `snapshot_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `StockSnapshotResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | Tenant ID |
| `storeCode` | string | Yes | Store code |
| `totalItems` | integer | Yes | Total number of items |
| `totalQuantity` | number | Yes | Total stock quantity |
| `stocks` | array[StockSnapshotItemResponse] | Yes | Stock details by item |
| `createdBy` | string | Yes | User or system that created the snapshot |
| `createdAt` | string | Yes | Creation timestamp |
| `updatedAt` | string | No | Last update timestamp |
| `generateDateTime` | string | No | Snapshot generation datetime in ISO format |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "totalItems": 0,
    "totalQuantity": 0.0,
    "stocks": [
      {
        "itemCode": "string",
        "quantity": 0.0,
        "minimumQuantity": 0.0,
        "reorderPoint": 0.0,
        "reorderQuantity": 0.0
      }
    ],
    "createdBy": "string",
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-01T00:00:00Z",
    "generateDateTime": "string"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 12. Get stock snapshots by date range

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshots`

Get list of stock snapshots filtered by generate_date_time range

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `start_date` | string | No | - | Start date in ISO format |
| `end_date` | string | No | - | End date in ISO format |
| `page` | integer | No | 1 | Page number |
| `limit` | integer | No | 100 | Maximum number of items to return |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `PaginatedResult_StockSnapshotResponse_`

| Field | Type | Required | Description |
|------------|------|------|------|
| `data` | array[StockSnapshotResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "totalItems": 0,
        "totalQuantity": 0.0,
        "stocks": [
          {
            "itemCode": "...",
            "quantity": "...",
            "minimumQuantity": "...",
            "reorderPoint": "...",
            "reorderQuantity": "..."
          }
        ],
        "createdBy": "string",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "generateDateTime": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 13. Get stock for an item

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}`

Get current stock information for a specific item

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `StockResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | Tenant ID |
| `storeCode` | string | Yes | Store code |
| `itemCode` | string | Yes | Item code |
| `currentQuantity` | number | Yes | Current stock quantity |
| `minimumQuantity` | number | Yes | Minimum stock quantity for alerts |
| `reorderPoint` | number | Yes | Reorder point - quantity that triggers reorder |
| `reorderQuantity` | number | Yes | Quantity to order when reorder point is reached |
| `lastUpdated` | string | Yes | Last update timestamp |
| `lastTransactionId` | string | No | Last transaction reference |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "itemCode": "string",
    "currentQuantity": 0.0,
    "minimumQuantity": 0.0,
    "reorderPoint": 0.0,
    "reorderQuantity": 0.0,
    "lastUpdated": "2025-01-01T00:00:00Z",
    "lastTransactionId": "string"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 14. Get stock update history

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/history`

Get stock update history for an item

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `page` | integer | No | 1 | Page number |
| `limit` | integer | No | 100 | Maximum number of items to return |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `PaginatedResult_StockUpdateResponse_`

| Field | Type | Required | Description |
|------------|------|------|------|
| `data` | array[StockUpdateResponse] | Yes | - |
| `metadata` | Metadata | Yes | Metadata Model

Represents metadata for paginated  |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "data": [
      {
        "tenantId": "string",
        "storeCode": "string",
        "itemCode": "string",
        "updateType": "sale",
        "quantityChange": 0.0,
        "beforeQuantity": 0.0,
        "afterQuantity": 0.0,
        "referenceId": "string",
        "timestamp": "2025-01-01T00:00:00Z",
        "operatorId": "string"
      }
    ],
    "metadata": {
      "total": 0,
      "page": 0,
      "limit": 0,
      "sort": "string",
      "filter": {}
    }
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 15. Set minimum stock quantity

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/minimum`

Set minimum stock quantity for alerts

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `minimumQuantity` | number | Yes | Minimum stock quantity for alerts |

**Request Example:**
```json
{
  "minimumQuantity": 0.0
}
```

**Response:**

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 16. Set reorder parameters

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/reorder`

Set reorder point and quantity for an item

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `reorderPoint` | number | Yes | Reorder point - quantity that triggers reorder |
| `reorderQuantity` | number | Yes | Quantity to order when reorder point is reached |

**Request Example:**
```json
{
  "reorderPoint": 0.0,
  "reorderQuantity": 0.0
}
```

**Response:**

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 17. Update stock quantity

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update`

Update stock quantity for an item and record the update

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `item_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `quantityChange` | number | Yes | Quantity change (positive for increase, negative f |
| `updateType` | UpdateType | Yes | - |
| `referenceId` | string | No | Reference ID (transaction, adjustment, etc.) |
| `operatorId` | string | No | User who performed the update |
| `note` | string | No | Additional notes |

**Request Example:**
```json
{
  "quantityChange": 0.0,
  "updateType": "sale",
  "referenceId": "string",
  "operatorId": "string",
  "note": "string"
}
```

**Response:**

**data Field:** `StockUpdateResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | Tenant ID |
| `storeCode` | string | Yes | Store code |
| `itemCode` | string | Yes | Item code |
| `updateType` | UpdateType | Yes | - |
| `quantityChange` | number | Yes | Quantity change |
| `beforeQuantity` | number | Yes | Stock quantity before update |
| `afterQuantity` | number | Yes | Stock quantity after update |
| `referenceId` | string | No | Reference ID |
| `timestamp` | string | Yes | Update timestamp |
| `operatorId` | string | No | User who performed the update |
| `note` | string | No | Additional notes |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "itemCode": "string",
    "updateType": "sale",
    "quantityChange": 0.0,
    "beforeQuantity": 0.0,
    "afterQuantity": 0.0,
    "referenceId": "string",
    "timestamp": "2025-01-01T00:00:00Z",
    "operatorId": "string"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### Event Processing

### 18. Handle transaction log from cart service

**POST** `/api/v1/tranlog`

Process transaction log to update stock quantities

**Response:**

## Error Codes

Error responses are returned in the following format:

```json
{
  "success": false,
  "code": 400,
  "message": "Error message",
  "errorCode": "ERROR_CODE",
  "operation": "operation_name"
}
```
