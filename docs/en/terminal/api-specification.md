# Terminal Service API Specification

## Overview

The Terminal service provides tenant management, store management, and terminal management capabilities for the Kugelpos POS system. It implements terminal lifecycle management, cash in/out operations, staff management, and basic functions required for store operations.

## Base URL
- Local environment: `http://localhost:8001`
- Production environment: `https://terminal.{domain}`

## Authentication

The Terminal service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Header: `Authorization: Bearer {token}`
- Purpose: Tenant, store, and terminal management operations by administrators

### 2. Terminal ID + API Key Authentication
- Header: `X-API-Key: {api_key}`
- Query parameter: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- Purpose: Terminal operations (sign-in, opening, cash management, etc.)

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

## Terminal States

| State | Description |
|-------|-------------|
| idle | Initial state, before business start |
| opened | In business (opened) |
| closed | Business ended (closed) |

## Function Modes

| Mode | Description |
|------|-------------|
| MainMenu | Main menu |
| OpenTerminal | Terminal opening |
| Sales | Sales processing |
| Returns | Return processing |
| Void | Void processing |
| Reports | Report display |
| CloseTerminal | Terminal closing |
| Journal | Journal display |
| Maintenance | Maintenance |
| CashInOut | Cash in/out |

## API Endpoints

### Tenant Management

#### 1. Create Tenant
**POST** `/api/v1/tenants`

Creates a new tenant and initializes each service.

**Authentication:** JWT token required

**Request Body:**
```json
{
  "tenantId": "tenant001",
  "tenantName": "Sample Corporation"
}
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Tenant created successfully",
  "data": {
    "tenantId": "tenant001",
    "tenantName": "Sample Corporation",
    "createdAt": "2024-01-01T10:00:00Z"
  },
  "operation": "create_tenant"
}
```

#### 2. Get Tenant Information
**GET** `/api/v1/tenants/{tenant_id}`

Retrieves detailed tenant information.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

#### 3. Update Tenant
**PUT** `/api/v1/tenants/{tenant_id}`

Updates tenant information.

**Request Body:**
```json
{
  "tenantName": "Sample Corporation (Updated)"
}
```

#### 4. Delete Tenant
**DELETE** `/api/v1/tenants/{tenant_id}`

Deletes tenant and related data.

### Store Management

#### 5. Add Store
**POST** `/api/v1/tenants/{tenant_id}/stores`

Adds a new store to the tenant.

**Request Body:**
```json
{
  "storeCode": "STORE001",
  "storeName": "Main Store"
}
```

#### 6. Get Store List
**GET** `/api/v1/tenants/{tenant_id}/stores`

Retrieves list of stores for the tenant.

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 100): Page size

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Stores retrieved successfully",
  "data": {
    "stores": [
      {
        "storeCode": "STORE001",
        "storeName": "Main Store",
        "status": "active",
        "businessDate": "2024-01-01",
        "createdAt": "2024-01-01T10:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "limit": 100
  },
  "operation": "list_stores"
}
```

#### 7. Get Store Information
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Retrieves detailed information for a specific store.

#### 8. Update Store
**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Updates store information.

**Request Body:**
```json
{
  "storeName": "Main Store (Updated)",
  "status": "active",
  "businessDate": "2024-01-02"
}
```

#### 9. Delete Store
**DELETE** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Deletes a store.

### Terminal Management

#### 10. Create Terminal
**POST** `/api/v1/terminals`

Creates a new terminal.

**Authentication:** JWT token required

**Request Body:**
```json
{
  "storeCode": "STORE001",
  "terminalNo": 1,
  "description": "Register #1"
}
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Terminal created successfully",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "tenantId": "tenant001",
    "storeCode": "STORE001",
    "terminalNo": 1,
    "description": "Register #1",
    "status": "idle",
    "apiKey": "sk_live_1234567890abcdef",
    "createdAt": "2024-01-01T10:00:00Z"
  },
  "operation": "create_terminal"
}
```

#### 11. Get Terminal List
**GET** `/api/v1/terminals`

Retrieves list of terminals.

**Authentication:** JWT token required

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 100): Page size
- `store_code` (string): Filter by store code
- `status` (string): Filter by status

#### 12. Get Terminal Information
**GET** `/api/v1/terminals/{terminal_id}`

Retrieves detailed terminal information.

**Path Parameters:**
- `terminal_id` (string, required): Terminal ID (format: tenant_id-store_code-terminal_no)

#### 13. Delete Terminal
**DELETE** `/api/v1/terminals/{terminal_id}`

Deletes a terminal.

**Authentication:** JWT token required

#### 14. Update Terminal Description
**PATCH** `/api/v1/terminals/{terminal_id}/description`

Updates terminal description.

**Request Body:**
```json
{
  "description": "Register #1 (Maintenance Complete)"
}
```

#### 15. Update Function Mode
**PATCH** `/api/v1/terminals/{terminal_id}/function_mode`

Updates terminal function mode.

**Request Body:**
```json
{
  "functionMode": "Sales"
}
```

### Terminal Operations

#### 16. Staff Sign-in
**POST** `/api/v1/terminals/{terminal_id}/sign-in`

Staff signs into the terminal.

**Request Body:**
```json
{
  "staffId": "STAFF001",
  "staffName": "Yamada Taro"
}
```

#### 17. Staff Sign-out
**POST** `/api/v1/terminals/{terminal_id}/sign-out`

Staff signs out of the terminal.

**Request Body:**
```json
{
  "staffId": "STAFF001"
}
```

#### 18. Open Terminal
**POST** `/api/v1/terminals/{terminal_id}/open`

Opens the terminal for business.

**Request Body:**
```json
{
  "staffId": "STAFF001",
  "staffName": "Yamada Taro",
  "cashAmount": 50000
}
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Terminal opened successfully",
  "data": {
    "terminalId": "tenant001-STORE001-1",
    "status": "opened",
    "businessDate": "2024-01-01",
    "openCounter": 1,
    "openTime": "2024-01-01T09:00:00Z",
    "receiptText": "=== OPEN ===\n...",
    "journalText": "Terminal open processing\n..."
  },
  "operation": "open_terminal"
}
```

#### 19. Close Terminal
**POST** `/api/v1/terminals/{terminal_id}/close`

Closes the terminal for business.

**Request Body:**
```json
{
  "staffId": "STAFF001",
  "staffName": "Yamada Taro",
  "cashAmount": 125000
}
```

### Cash Management

#### 20. Cash In
**POST** `/api/v1/terminals/{terminal_id}/cash-in`

Deposits cash.

**Request Body:**
```json
{
  "amount": 10000,
  "reason": "Change replenishment",
  "staffId": "STAFF001",
  "staffName": "Yamada Taro",
  "comment": "Afternoon change replenishment"
}
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Cash in completed successfully",
  "data": {
    "cashInOutId": "CI-20240101-001",
    "amount": 10000,
    "receiptText": "=== CASH IN ===\n...",
    "journalText": "Cash in processing\n..."
  },
  "operation": "cash_in"
}
```

#### 21. Cash Out
**POST** `/api/v1/terminals/{terminal_id}/cash-out`

Withdraws cash.

**Request Body:**
```json
{
  "amount": 50000,
  "reason": "Sales collection",
  "staffId": "STAFF001",
  "staffName": "Yamada Taro",
  "comment": "Intermediate collection"
}
```

### System Management

#### 22. Update Delivery Status
**POST** `/api/v1/terminals/{terminal_id}/delivery-status`

Updates event delivery status (internal use).

**Request Body:**
```json
{
  "eventId": "evt_123456",
  "eventType": "cashlog",
  "delivered": true
}
```

### 23. Health Check
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
    "mongodb": "connected"
  },
  "operation": "health_check"
}
```

## Event Notifications (Dapr Pub/Sub)

### Cash In/Out Events
**Topic:** `cashlog_report`

Events published during cash in/out operations.

### Open/Close Events
**Topic:** `opencloselog_report`

Events published during terminal open/close operations.

## Error Codes

Terminal service uses error codes in the 20XXX range:

- `20001`: Tenant not found
- `20002`: Store not found
- `20003`: Terminal not found
- `20004`: Terminal already exists
- `20005`: Invalid terminal state
- `20006`: Staff not found
- `20007`: Invalid API key
- `20008`: Terminal already opened
- `20009`: Terminal not opened
- `20099`: General service error

## Special Notes

1. **Terminal ID Format**: Uses `{tenant_id}-{store_code}-{terminal_no}` format
2. **API Key**: Auto-generated during terminal creation and stored as hash
3. **Background Jobs**: Periodic retransmission of undelivered messages
4. **Multi-tenancy**: Complete isolation at database level
5. **Event-driven**: Asynchronous event delivery via Dapr pub/sub
6. **Circuit Breaker**: Failure handling for external service calls