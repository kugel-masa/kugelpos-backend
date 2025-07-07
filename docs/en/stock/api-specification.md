# Stock Service API Specification

## Overview

The Stock service provides inventory management capabilities for the Kugelpos POS system. It implements real-time stock tracking, stock alerts, snapshot management, and transaction-linked stock updates. Key features include real-time alerts via WebSocket and Cart service integration via Dapr pub/sub.

## Base URL
- Local environment: `http://localhost:8006`
- Production environment: `https://stock.{domain}`

## Authentication

The Stock service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Header: `Authorization: Bearer {token}`
- Purpose: Inventory management operations by administrators

### 2. API Key Authentication
- Header: `X-API-Key: {api_key}`
- Purpose: Stock inquiry from terminals (limited endpoints)

## Field Format

All API requests/responses use **camelCase** format.

## Common Response Format

```json
{
  "success": true,
  "code": 200,
  "message": "Operation completed successfully",
  "data": { ... },
  "operation": "function_name"
}
```

## Stock Update Types

| Type ID | Name | Description |
|----------|------|-------------|
| SALE | Sale | Stock decrease due to sales |
| RETURN | Return | Stock increase due to returns |
| VOID | Void | Stock increase due to sale cancellation |
| VOID_RETURN | Return Void | Stock decrease due to return cancellation |
| PURCHASE | Purchase | Stock increase due to procurement |
| ADJUSTMENT | Adjustment | Manual stock adjustment |
| INITIAL | Initial | Initial stock setup |
| DAMAGE | Damage | Stock decrease due to damage |
| TRANSFER_IN | Transfer In | Incoming transfer from other stores |
| TRANSFER_OUT | Transfer Out | Outgoing transfer to other stores |

## API Endpoints

### 1. Get Stock List
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock`

Retrieves all stock items for a store.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 100): Page size
- `terminal_id` (integer): Terminal ID (for API key authentication)

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stock items retrieved successfully",
  "data": {
    "items": [
      {
        "itemCode": "ITEM001",
        "itemName": "Product 001",
        "storeCode": "STORE001",
        "currentQuantity": 100,
        "minimumQuantity": 20,
        "reorderPoint": 30,
        "reorderQuantity": 50,
        "lastUpdated": "2024-01-01T12:00:00Z",
        "updateType": "PURCHASE"
      }
    ],
    "total": 150,
    "page": 1,
    "limit": 100
  },
  "operation": "get_all_stock"
}
```

### 2. Get Individual Stock Item
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}`

Retrieves stock information for a specific product.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `item_code` (string, required): Item code

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stock item retrieved successfully",
  "data": {
    "itemCode": "ITEM001",
    "itemName": "Product 001",
    "storeCode": "STORE001",
    "currentQuantity": 100,
    "minimumQuantity": 20,
    "reorderPoint": 30,
    "reorderQuantity": 50,
    "lastUpdated": "2024-01-01T12:00:00Z",
    "updateType": "PURCHASE"
  },
  "operation": "get_stock"
}
```

### 3. Update Stock
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update`

Updates stock quantity.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `item_code` (string, required): Item code

**Request Body:**
```json
{
  "quantity": -1,
  "updateType": "SALE",
  "reason": "Sales processing",
  "staffId": "STAFF001",
  "referenceNo": "TRAN001"
}
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stock updated successfully",
  "data": {
    "itemCode": "ITEM001",
    "previousQuantity": 100,
    "newQuantity": 99,
    "quantityChange": -1,
    "updateType": "SALE"
  },
  "operation": "update_stock"
}
```

### 4. Get Stock History
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/history`

Retrieves stock update history for a product.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `item_code` (string, required): Item code

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 100): Page size

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stock history retrieved successfully",
  "data": {
    "history": [
      {
        "id": "507f1f77bcf86cd799439011",
        "timestamp": "2024-01-01T12:00:00Z",
        "previousQuantity": 100,
        "newQuantity": 99,
        "quantityChange": -1,
        "updateType": "SALE",
        "reason": "Sales processing",
        "staffId": "STAFF001",
        "referenceNo": "TRAN001"
      }
    ],
    "total": 50,
    "page": 1,
    "limit": 100
  },
  "operation": "get_stock_history"
}
```

### 5. Set Minimum Quantity
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/minimum`

Sets minimum stock quantity.

**Request Body:**
```json
{
  "minimumQuantity": 20
}
```

### 6. Set Reorder Point
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/reorder`

Sets reorder point and quantity.

**Request Body:**
```json
{
  "reorderPoint": 30,
  "reorderQuantity": 50
}
```

### 7. Get Low Stock Items
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/low`

Retrieves items below minimum quantity.

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Low stock items retrieved successfully",
  "data": {
    "items": [
      {
        "itemCode": "ITEM001",
        "itemName": "Product 001",
        "currentQuantity": 15,
        "minimumQuantity": 20,
        "shortageQuantity": 5
      }
    ],
    "total": 5
  },
  "operation": "get_low_stock"
}
```

### 8. Get Reorder Alerts
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/reorder-alerts`

Retrieves items that have reached reorder point.

### 9. WebSocket Connection (Real-time Alerts)
**WebSocket** `/ws/{tenant_id}/{store_code}`

Receives stock alerts in real-time.

**Connection Steps:**
1. Establish WebSocket connection (JWT token must be provided as query parameter)
   - URL example: `/ws/{tenant_id}/{store_code}?token=JWT_TOKEN`
2. Receive alert messages

**Alert Message Example:**
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

### 10. Create Snapshot
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

Manually creates stock snapshot.

**Request Body:**
```json
{
  "description": "Monthly inventory count",
  "takenBy": "STAFF001"
}
```

### 11. Get Snapshot List
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshots`

Retrieves snapshot list.

**Query Parameters:**
- `start_date` (string): Start date (YYYY-MM-DD)
- `end_date` (string): End date (YYYY-MM-DD)
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 100): Page size

### 12. Get Snapshot Details
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}`

Retrieves details of a specific snapshot.

### 13. Get Snapshot Schedule
**GET** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

Retrieves automatic snapshot schedule configuration.

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Snapshot schedule retrieved successfully",
  "data": {
    "daily": {
      "enabled": true,
      "time": "02:00",
      "timezone": "Asia/Tokyo"
    },
    "weekly": {
      "enabled": false,
      "dayOfWeek": 0,
      "time": "02:00",
      "timezone": "Asia/Tokyo"
    },
    "monthly": {
      "enabled": true,
      "dayOfMonth": 1,
      "time": "02:00",
      "timezone": "Asia/Tokyo"
    },
    "retentionDays": 90
  },
  "operation": "get_snapshot_schedule"
}
```

### 14. Update Snapshot Schedule
**PUT** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

Updates automatic snapshot schedule.

**Request Body:**
```json
{
  "daily": {
    "enabled": true,
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "weekly": {
    "enabled": false,
    "dayOfWeek": 0,
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "monthly": {
    "enabled": true,
    "dayOfMonth": 1,
    "time": "02:00",
    "timezone": "Asia/Tokyo"
  },
  "retentionDays": 90
}
```

### 15. Delete Snapshot Schedule
**DELETE** `/api/v1/tenants/{tenant_id}/stock/snapshot-schedule`

Deletes custom schedule and reverts to default settings.

### 16. Create Tenant
**POST** `/api/v1/tenants`

Initializes stock service for a new tenant.

**Request Body:**
```json
{
  "tenantId": "tenant001"
}
```

**Authentication:** JWT token required

### 17. Health Check
**GET** `/health`

Checks service health.

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Service is healthy",
  "data": {
    "status": "healthy",
    "mongodb": "connected",
    "dapr": "connected",
    "scheduler": "running"
  },
  "operation": "health_check"
}
```

## Event Processing Endpoints (Dapr Pub/Sub)

### 18. Transaction Log Handler
**POST** `/api/v1/tranlog`

**Topic:** `topic-tranlog`

Processes transaction logs from Cart service and updates stock.

### 19. Dapr Subscribe
**GET** `/dapr/subscribe`

Returns Dapr subscription configuration.

## Error Codes

Stock service uses error codes in the 41XXX range:

- `41401`: Stock item not found
- `41402`: Insufficient stock
- `41403`: Invalid update type
- `41404`: Invalid quantity
- `41405`: Snapshot not found
- `41406`: Schedule configuration error
- `41499`: General service error

## Special Notes

1. **Stock Atomicity**: Implements atomic operations to prevent concurrent updates
2. **Negative Stock**: Allows negative stock to support backorders
3. **Alert Cooldown**: Alerts for the same item are limited to 60-second intervals
4. **Idempotency**: Duplicate processing prevention by event ID
5. **WebSocket Authentication**: Token must be provided as query parameter during connection
6. **Snapshot Retention**: Default retention period is 90 days