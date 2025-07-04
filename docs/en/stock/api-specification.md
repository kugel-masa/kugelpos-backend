# Stock Service API Specification

## Overview

Stock Service manages inventory tracking and inventory levels in the Kugelpos POS system. It provides endpoints for inventory queries, updates, history tracking, snapshot management, reorder management, and real-time WebSocket alerts.

## Base URL
- Local environment: `http://localhost:8006`
- Production environment: `https://stock.{domain}`

## Authentication

Stock Service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Include in header: `Authorization: Bearer {token}`
- Obtain token from: Account Service's `/api/v1/accounts/token`
- Required for management operations

### 2. API Key Authentication
- Include in header: `X-API-Key: {api_key}`
- Include query parameter: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- Used for POS terminal operations

## Field Format

All API requests and responses use **camelCase** field naming conventions. The service uses `BaseSchemaModel` and transformers to automatically convert between internal snake_case and external camelCase formats.

## Common Response Format

All endpoints return responses in the following format:

```json
{
  "success": true,
  "code": 200,
  "message": "Operation completed successfully",
  "data": { ... },
  "operation": "function_name"
}
```

## Enumerations

### UpdateType (Update Types)
Inventory update types for tracking inventory changes:
- `sale` - Product sales
- `return` - Customer returns
- `void` - Sales cancellation
- `void_return` - Return cancellation
- `purchase` - Inventory procurement/receipt
- `adjustment` - Manual adjustment
- `initial` - Initial inventory setup
- `damage` - Damaged inventory
- `transfer_in` - Inventory transfer in
- `transfer_out` - Inventory transfer out

## API Endpoints

### 1. Get Store Inventory List
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock`

Retrieve all inventory items for a store with pagination.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication
  - `skip` (integer, default: 0): Number of items to skip
  - `limit` (integer, default: 100, max: 1000): Maximum number of items to return

**Request Example:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock?skip=0&limit=50" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Inventory list retrieved successfully",
  "data": {
    "items": [
      {
        "tenantId": "tenant001",
        "storeCode": "store001",
        "itemCode": "ITEM001",
        "currentQuantity": 150.0,
        "minimumQuantity": 20.0,
        "reorderPoint": 50.0,
        "reorderQuantity": 100.0,
        "lastUpdated": "2024-01-01T10:30:00Z",
        "lastTransactionId": "TRX001"
      }
    ],
    "total": 100,
    "skip": 0,
    "limit": 50
  },
  "operation": "get_store_stocks"
}
```

### 2. Get Low Stock Items
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/low`

Retrieve items with inventory below minimum quantity.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Example:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/low" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Low stock items retrieved successfully",
  "data": {
    "items": [
      {
        "tenantId": "tenant001",
        "storeCode": "store001",
        "itemCode": "ITEM002",
        "currentQuantity": 5.0,
        "minimumQuantity": 20.0,
        "reorderPoint": 30.0,
        "reorderQuantity": 50.0,
        "lastUpdated": "2024-01-01T10:30:00Z",
        "lastTransactionId": "TRX002"
      }
    ],
    "total": 3,
    "skip": 0,
    "limit": 3
  },
  "operation": "get_low_stocks"
}
```

### 3. Get Item Inventory
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}`

Retrieve current inventory information for a specific item.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
  - `item_code` (string, required): Item code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Example:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Inventory retrieved successfully",
  "data": {
    "tenantId": "tenant001",
    "storeCode": "store001",
    "itemCode": "ITEM001",
    "currentQuantity": 150.0,
    "minimumQuantity": 20.0,
    "reorderPoint": 50.0,
    "reorderQuantity": 100.0,
    "lastUpdated": "2024-01-01T10:30:00Z",
    "lastTransactionId": "TRX001"
  },
  "operation": "get_stock"
}
```

### 4. Update Inventory Quantity
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update`

Update item inventory quantity and record the update.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
  - `item_code` (string, required): Item code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Body:**
```json
{
  "quantityChange": -2.0,
  "updateType": "sale",
  "referenceId": "TRX001",
  "operatorId": "user001",
  "note": "Sales transaction"
}
```

**Field Descriptions:**
- `quantityChange` (number, required): Quantity change value (positive for increase, negative for decrease)
- `updateType` (string, required): Update type (see enumeration reference)
- `referenceId` (string, optional): Reference ID (transaction ID, etc.)
- `operatorId` (string, optional): Operator ID
- `note` (string, optional): Additional notes

**Request Example:**
```bash
curl -X PUT "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001/update" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "quantityChange": -2.0,
    "updateType": "sale",
    "referenceId": "TRX001",
    "note": "Sales transaction"
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Inventory updated successfully",
  "data": {
    "tenantId": "tenant001",
    "storeCode": "store001",
    "itemCode": "ITEM001",
    "updateType": "sale",
    "quantityChange": -2.0,
    "beforeQuantity": 150.0,
    "afterQuantity": 148.0,
    "referenceId": "TRX001",
    "timestamp": "2024-01-01T10:35:00Z",
    "operatorId": "user001",
    "note": "Sales transaction"
  },
  "operation": "update_stock"
}
```

### 5. Get Inventory Update History
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/history`

Retrieve inventory update history for an item.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
  - `item_code` (string, required): Item code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication
  - `skip` (integer, default: 0): Number of items to skip
  - `limit` (integer, default: 100, max: 1000): Maximum number of items to return

**Request Example:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001/history?skip=0&limit=20" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Inventory history retrieved successfully",
  "data": {
    "items": [
      {
        "tenantId": "tenant001",
        "storeCode": "store001",
        "itemCode": "ITEM001",
        "updateType": "sale",
        "quantityChange": -2.0,
        "beforeQuantity": 150.0,
        "afterQuantity": 148.0,
        "referenceId": "TRX001",
        "timestamp": "2024-01-01T10:35:00Z",
        "operatorId": "user001",
        "note": "Sales transaction"
      }
    ],
    "total": 50,
    "skip": 0,
    "limit": 20
  },
  "operation": "get_stock_history"
}
```

### 6. Get Reorder Alert Items
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/reorder-alerts`

Retrieve list of items below reorder point.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Example:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/reorder-alerts" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Reorder alert items retrieved successfully",
  "data": {
    "data": [
      {
        "tenantId": "tenant001",
        "storeCode": "store001",
        "itemCode": "ITEM003",
        "currentQuantity": 15.0,
        "minimumQuantity": 10.0,
        "reorderPoint": 20.0,
        "reorderQuantity": 50.0,
        "lastUpdated": "2024-01-01T10:30:00Z"
      }
    ],
    "metadata": {
      "total": 1,
      "page": 1,
      "limit": 1,
      "sort": null,
      "filter": null
    }
  },
  "operation": "get_reorder_alerts"
}
```

### 7. Set Minimum Inventory Quantity
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/minimum`

Set minimum inventory quantity for alerts.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
  - `item_code` (string, required): Item code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Body:**
```json
{
  "minimumQuantity": 25.0
}
```

**Request Example:**
```bash
curl -X PUT "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001/minimum" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"minimumQuantity": 25.0}'
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Minimum quantity set successfully",
  "data": null,
  "operation": "set_minimum_quantity"
}
```

### 8. Set Reorder Parameters
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/reorder`

Set reorder point and quantity for an item.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
  - `item_code` (string, required): Item code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Body:**
```json
{
  "reorderPoint": 50.0,
  "reorderQuantity": 100.0
}
```

**Field Descriptions:**
- `reorderPoint` (number, required): Reorder point (reorder alert triggered when inventory falls below this quantity)
- `reorderQuantity` (number, required): Reorder quantity (recommended quantity when ordering)

**Request Example:**
```bash
curl -X PUT "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/ITEM001/reorder" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "reorderPoint": 50.0,
    "reorderQuantity": 100.0
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Reorder parameters set successfully",
  "data": null,
  "operation": "set_reorder_parameters"
}
```

### 9. Create Inventory Snapshot
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

Create a snapshot of current inventory levels.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Body:**
```json
{
  "createdBy": "user001"
}
```

**Request Example:**
```bash
curl -X POST "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/snapshot" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"createdBy": "user001"}'
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Snapshot created successfully",
  "data": {
    "tenantId": "tenant001",
    "storeCode": "store001",
    "totalItems": 150,
    "totalQuantity": 5250.0,
    "stocks": [
      {
        "itemCode": "ITEM001",
        "quantity": 148.0,
        "minimumQuantity": 25.0,
        "reorderPoint": 50.0,
        "reorderQuantity": 100.0
      },
      {
        "itemCode": "ITEM002",
        "quantity": 5.0,
        "minimumQuantity": 20.0,
        "reorderPoint": 30.0,
        "reorderQuantity": 50.0
      }
    ],
    "createdBy": "user001",
    "createdAt": "2024-01-01T11:00:00Z",
    "updatedAt": null
  },
  "operation": "create_snapshot"
}
```

### 10. Get Inventory Snapshot List
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot`

Retrieve list of store inventory snapshots.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication
  - `skip` (integer, default: 0): Number of items to skip
  - `limit` (integer, default: 20, max: 100): Maximum number of items to return

**Request Example:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/snapshot?skip=0&limit=10" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Snapshots retrieved successfully",
  "data": {
    "items": [
      {
        "tenantId": "tenant001",
        "storeCode": "store001",
        "totalItems": 150,
        "totalQuantity": 5250.0,
        "stocks": [...],
        "createdBy": "user001",
        "createdAt": "2024-01-01T11:00:00Z",
        "updatedAt": null
      }
    ],
    "total": 5,
    "skip": 0,
    "limit": 10
  },
  "operation": "get_snapshots"
}
```

### 11. Get Inventory Snapshot by ID
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}`

Retrieve a specific inventory snapshot by ID.

**Parameters:**
- Path:
  - `tenant_id` (string, required): Tenant identifier
  - `store_code` (string, required): Store code
  - `snapshot_id` (string, required): Snapshot ID
- Query:
  - `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Example:**
```bash
curl -X GET "http://localhost:8006/api/v1/tenants/tenant001/stores/store001/stock/snapshot/507f1f77bcf86cd799439014" \
  -H "Authorization: Bearer {token}"
```

### 12. Create Tenant
**POST** `/api/v1/tenants`

Initialize stock service for a new tenant (requires JWT authentication).

**Request Body:**
```json
{
  "tenantId": "tenant001"
}
```

**Request Example:**
```bash
curl -X POST "http://localhost:8006/api/v1/tenants" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"tenantId": "tenant001"}'
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Tenant creation completed: tenant001",
  "data": {
    "tenantId": "tenant001"
  },
  "operation": "create_tenant"
}
```

## Internal Endpoints

### Transaction Log Handler (PubSub)
**POST** `/api/v1/tranlog`

Internal endpoint for processing transaction logs from cart service via Dapr pub/sub. This endpoint:
- Processes sales transactions to update inventory quantities
- Implements idempotency using event IDs
- Sends acknowledgment responses to cart service

This endpoint is not intended to be called directly by external clients.

## WebSocket Real-Time Notifications

**WebSocket Endpoint:** `ws://localhost:8006/api/v1/ws/{tenant_id}/{store_code}?token={jwt_token}`

Provides real-time inventory alert notifications.

### Authentication
- JWT token must be passed as a query parameter
- Header authentication cannot be used due to WebSocket protocol constraints

### Connection Example
```javascript
const token = 'your_jwt_token_here';
const ws = new WebSocket(`ws://localhost:8006/api/v1/ws/tenant001/store001?token=${token}`);

ws.onopen = function(event) {
    console.log('WebSocket connection established');
};

ws.onmessage = function(event) {
    const alert = JSON.parse(event.data);
    console.log('Alert received:', alert);
};
```

### Alert Types

#### 1. Reorder Point Alert
Sent when inventory falls below reorder point:

```json
{
  "type": "stock_alert",
  "alert_type": "reorder_point",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "item_code": "ITEM001",
  "current_quantity": 40.0,
  "reorder_point": 50.0,
  "reorder_quantity": 100.0,
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

#### 2. Minimum Stock Alert
Sent when inventory falls below minimum stock level:

```json
{
  "type": "stock_alert",
  "alert_type": "minimum_stock",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "item_code": "ITEM002",
  "current_quantity": 5.0,
  "minimum_quantity": 10.0,
  "reorder_quantity": 50.0,
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

#### 3. Connection Confirmation Message
Sent when connection is established:

```json
{
  "type": "connection",
  "status": "connected",
  "tenant_id": "tenant001",
  "store_code": "store001",
  "timestamp": "2024-01-01T12:34:56.789Z"
}
```

### Alert Control

#### Alert Cooldown
- Prevents alert spam for the same item with cooldown functionality
- Configurable via environment variable `ALERT_COOLDOWN_SECONDS` (default: 60 seconds)
- Can be set to 0 seconds in test environments

#### Multiple Client Support
- Alerts are delivered to all WebSocket connections for the same tenant/store
- Disconnected clients are automatically removed by connection management

### Error Handling

#### Authentication Errors
```javascript
ws.onclose = function(event) {
    if (event.code === 1008) {
        console.error('Authentication error:', event.reason);
        // 'No token provided' or 'Authentication failed'
    }
};
```

#### Connection Errors
```javascript
ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};
```

### Performance Characteristics

- **Connection Limit**: No implementation limit (limited by system resources)
- **Message Delivery**: Asynchronous real-time delivery
- **Memory Usage**: Proportional to number of connections
- **CPU Usage**: Increases only when alerts are generated

## Error Responses

The API uses standard HTTP status codes and structured error responses:

```json
{
  "success": false,
  "code": 404,
  "message": "Inventory not found for item ITEM999 in store store001",
  "data": null,
  "operation": "get_stock"
}
```

### Common Status Codes
- `200` - Success
- `201` - Created successfully
- `400` - Bad request
- `401` - Authentication error
- `403` - Access denied
- `404` - Resource not found
- `500` - Internal server error

### Error Code System

Stock Service uses error codes in the 60XXX range:

- `60001` - Inventory not found
- `60002` - Inventory update error
- `60003` - Snapshot creation error
- `60004` - Invalid quantity
- `60005` - Invalid update type
- `60099` - Other errors

## Notes

1. **Pagination**: List endpoints support pagination with `skip` and `limit` parameters
2. **CamelCase Convention**: All JSON fields use camelCase (e.g., `itemCode`, not `item_code`)
3. **Timestamps**: All timestamps are in ISO 8601 format (UTC)
4. **Quantity Changes**: Positive values increase inventory, negative values decrease inventory
5. **Idempotency**: Transaction processing uses event IDs to prevent duplicate updates
6. **Multi-Tenant**: Each tenant has isolated inventory data
7. **Concurrency Control**: MongoDB atomic operations ensure data consistency during concurrent updates

## Rate Limiting

Currently, Stock Service does not implement explicit rate limiting, but the following limits may be added in the future:

- 1000 requests per minute per IP address
- 10000 requests per hour per API key

## Important Notes

1. Never commit changes unless explicitly requested by the user
2. Document ID fields have been removed from API responses for consistency with other services
3. WebSocket authentication uses query parameters due to protocol limitations
4. Alert cooldown functionality prevents spam and can be configured per environment
5. All inventory changes trigger real-time alert evaluation for connected WebSocket clients