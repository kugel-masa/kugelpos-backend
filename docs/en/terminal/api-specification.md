# Terminal Service API Specification

## Overview

Provides tenant management, store management, and terminal management functions. Manages terminal lifecycle, cash in/out operations, and staff management.

## Service Information

- **Port**: 8001
- **Framework**: FastAPI
- **Database**: MongoDB (Motor async driver)

## Base URL

- Local Environment: `http://localhost:8001`
- Production Environment: `https://terminal.{domain}`

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

Root endpoint that provides basic API information
Returns a welcome message and supported API versions

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

Create a new tenant

This endpoint sets up a new tenant in the system by:
1. Creating necessary database structures for the Terminal service
2. Initializing other services (Master Data, Cart, Report, Journal) for the tenant
3. Creating the tenant information record

This operation requires OAuth2 token authentication.

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |

**Request Example:**
```json
{
  "tenantId": "string",
  "tenantName": "string",
  "tags": [
    "string"
  ]
}
```

**Response:**

**data Field:** `Tenant`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |
| `stores` | array[BaseStore] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "tenantName": "string",
    "tags": [
      "string"
    ],
    "stores": [
      {
        "storeCode": "string",
        "storeName": "string",
        "status": "string",
        "businessDate": "string",
        "tags": [
          "string"
        ],
        "entryDatetime": "string",
        "lastUpdateDatetime": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 4. Get Tenant

**GET** `/api/v1/tenants/{tenant_id}`

Get tenant information

This endpoint retrieves detailed information about a specific tenant.
This operation can be authenticated using either:
- OAuth2 token, or
- Terminal ID + API key combination

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | - |

**Response:**

**data Field:** `Tenant`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |
| `stores` | array[BaseStore] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "tenantName": "string",
    "tags": [
      "string"
    ],
    "stores": [
      {
        "storeCode": "string",
        "storeName": "string",
        "status": "string",
        "businessDate": "string",
        "tags": [
          "string"
        ],
        "entryDatetime": "string",
        "lastUpdateDatetime": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 5. Update Tenant

**PUT** `/api/v1/tenants/{tenant_id}`

Update tenant information

This endpoint updates the details of a specific tenant.
This operation requires OAuth2 token authentication.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |

**Request Example:**
```json
{
  "tenantName": "string",
  "tags": [
    "string"
  ]
}
```

**Response:**

**data Field:** `Tenant`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |
| `stores` | array[BaseStore] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "tenantName": "string",
    "tags": [
      "string"
    ],
    "stores": [
      {
        "storeCode": "string",
        "storeName": "string",
        "status": "string",
        "businessDate": "string",
        "tags": [
          "string"
        ],
        "entryDatetime": "string",
        "lastUpdateDatetime": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 6. Delete Tenant

**DELETE** `/api/v1/tenants/{tenant_id}`

Delete a tenant

This endpoint deletes a tenant from the system.
This operation requires OAuth2 token authentication.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Response:**

**data Field:** `TenantDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |

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
    "tenantId": "string"
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

### Store

### 7. Get Stores

**GET** `/api/v1/tenants/{tenant_id}/stores`

Get a list of stores for a tenant

This endpoint retrieves a paginated list of stores for the specified tenant.
This operation can be authenticated using either:
- OAuth2 token, or
- Terminal ID + API key combination

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | - |

**Response:**

**data Field:** `array[Store]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
  "data": [
    {
      "storeCode": "string",
      "storeName": "string",
      "status": "string",
      "businessDate": "string",
      "tags": [
        "string"
      ],
      "entryDatetime": "string",
      "lastUpdateDatetime": "string"
    }
  ],
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

### 8. Add Store

**POST** `/api/v1/tenants/{tenant_id}/stores`

Add a store to a tenant

This endpoint adds a new store to the specified tenant.
This operation requires OAuth2 token authentication.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |

**Request Example:**
```json
{
  "storeCode": "string",
  "storeName": "string",
  "status": "string",
  "businessDate": "string",
  "tags": [
    "string"
  ]
}
```

**Response:**

**data Field:** `Tenant`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `tenantName` | string | Yes | - |
| `tags` | array[string] | Yes | - |
| `stores` | array[BaseStore] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "tenantName": "string",
    "tags": [
      "string"
    ],
    "stores": [
      {
        "storeCode": "string",
        "storeName": "string",
        "status": "string",
        "businessDate": "string",
        "tags": [
          "string"
        ],
        "entryDatetime": "string",
        "lastUpdateDatetime": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 9. Get Store

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Get store information

This endpoint retrieves detailed information about a specific store.
This operation can be authenticated using either:
- OAuth2 token, or
- Terminal ID + API key combination

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | - |

**Response:**

**data Field:** `Store`

| Field | Type | Required | Description |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "storeCode": "string",
    "storeName": "string",
    "status": "string",
    "businessDate": "string",
    "tags": [
      "string"
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 10. Update Store

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Update store information

This endpoint updates the details of a specific store.
This operation requires OAuth2 token authentication.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |

**Request Example:**
```json
{
  "storeName": "string",
  "status": "string",
  "businessDate": "string",
  "tags": [
    "string"
  ]
}
```

**Response:**

**data Field:** `Store`

| Field | Type | Required | Description |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `storeName` | string | Yes | - |
| `status` | string | No | - |
| `businessDate` | string | No | - |
| `tags` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "storeCode": "string",
    "storeName": "string",
    "status": "string",
    "businessDate": "string",
    "tags": [
      "string"
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 11. Delete Store

**DELETE** `/api/v1/tenants/{tenant_id}/stores/{store_code}`

Delete a store

This endpoint deletes a store from the specified tenant.
This operation requires OAuth2 token authentication.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Response:**

**data Field:** `StoreDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `storeCode` | string | Yes | - |

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
    "storeCode": "string"
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

### Terminal

### 12. Get Terminals

**GET** `/api/v1/terminals`

Get a list of terminals

This endpoint retrieves a paginated list of terminals for the authenticated tenant.
Optional filtering by store code is supported.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | Limit the number of results |
| `page` | integer | No | 1 | Page number |
| `store_code` | string | No | - | Filter by store code |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | - |

**Response:**

**data Field:** `array[Terminal]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
  "data": [
    {
      "terminalId": "string",
      "tenantId": "string",
      "storeCode": "string",
      "terminalNo": 0,
      "description": "string",
      "functionMode": "string",
      "status": "string",
      "businessDate": "string",
      "openCounter": 0,
      "businessCounter": 0
    }
  ],
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

### 13. Create Terminal

**POST** `/api/v1/terminals`

Create a new terminal

This endpoint creates a new terminal for a store with the provided details.
Requires token authentication (no terminal ID/API key needed since the terminal doesn't exist yet).

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |

**Request Example:**
```json
{
  "storeCode": "string",
  "terminalNo": 0,
  "description": "string"
}
```

**Response:**

**data Field:** `Terminal`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 14. Get Terminal

**GET** `/api/v1/terminals/{terminal_id}`

Get terminal information

This endpoint retrieves detailed information about a specific terminal.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Response:**

**data Field:** `Terminal`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 15. Delete Terminal

**DELETE** `/api/v1/terminals/{terminal_id}`

Delete a terminal

This endpoint deletes a terminal from the system.
Requires OAuth2 token authentication.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Response:**

**data Field:** `TerminalDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |

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
    "terminalId": "string"
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

### 16. Terminal Cash In

**POST** `/api/v1/terminals/{terminal_id}/cash-in`

Add cash to a terminal drawer

This endpoint records cash being added to the terminal drawer
and generates a receipt for the transaction.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `amount` | number | Yes | - |
| `description` | string | No | - |

**Request Example:**
```json
{
  "amount": 0.0,
  "description": "string"
}
```

**Response:**

**data Field:** `CashInOutResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `amount` | number | Yes | - |
| `description` | string | Yes | - |
| `receiptText` | string | Yes | - |
| `journalText` | string | Yes | - |

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
    "terminalId": "string",
    "amount": 0.0,
    "description": "string",
    "receiptText": "string",
    "journalText": "string"
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

### 17. Terminal Cash Out

**POST** `/api/v1/terminals/{terminal_id}/cash-out`

Remove cash from a terminal drawer

This endpoint records cash being removed from the terminal drawer
and generates a receipt for the transaction.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `amount` | number | Yes | - |
| `description` | string | No | - |

**Request Example:**
```json
{
  "amount": 0.0,
  "description": "string"
}
```

**Response:**

**data Field:** `CashInOutResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `amount` | number | Yes | - |
| `description` | string | Yes | - |
| `receiptText` | string | Yes | - |
| `journalText` | string | Yes | - |

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
    "terminalId": "string",
    "amount": 0.0,
    "description": "string",
    "receiptText": "string",
    "journalText": "string"
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

### 18. Terminal Close

**POST** `/api/v1/terminals/{terminal_id}/close`

Close a terminal after business operations

This endpoint transitions a terminal to the 'closed' state,
ending the current business session. It records the final
physical cash amount in the drawer and creates a closing report.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `physicalAmount` | number | No | - |

**Request Example:**
```json
{
  "physicalAmount": 0.0
}
```

**Response:**

**data Field:** `TerminalCloseResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `businessDate` | string | Yes | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `terminalInfo` | BaseTerminal | Yes | Base Terminal Information Model

Represents termin |
| `receiptText` | string | Yes | - |
| `journalText` | string | Yes | - |
| `physicalAmount` | number | No | - |

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
    "terminalId": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0,
    "initialAmount": 0.0,
    "terminalInfo": {
      "terminalId": "string",
      "tenantId": "string",
      "storeCode": "string",
      "terminalNo": 0,
      "description": "string",
      "functionMode": "string",
      "status": "string",
      "businessDate": "string",
      "openCounter": 0,
      "businessCounter": 0
    },
    "receiptText": "string",
    "journalText": "string",
    "physicalAmount": 0.0
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

### 19. Update Delivery Status

**POST** `/api/v1/terminals/{terminal_id}/delivery-status`

Update the delivery status of a transaction

This endpoint updates the delivery status of a transaction
and generates a receipt for the transaction.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `event_id` | string | Yes | - |
| `service` | string | Yes | - |
| `status` | string | Yes | - |
| `message` | string | No | - |

**Request Example:**
```json
{
  "event_id": "string",
  "service": "string",
  "status": "string",
  "message": "string"
}
```

**Response:**

**data Field:** `DeliveryStatusUpdateResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `event_id` | string | Yes | - |
| `service` | string | Yes | - |
| `status` | string | Yes | - |
| `success` | boolean | Yes | - |

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
    "event_id": "string",
    "service": "string",
    "status": "string",
    "success": true
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

### 20. Update Terminal Description

**PATCH** `/api/v1/terminals/{terminal_id}/description`

Update terminal description

This endpoint updates the description of a specific terminal.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `description` | string | Yes | - |

**Request Example:**
```json
{
  "description": "string"
}
```

**Response:**

**data Field:** `Terminal`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 21. Update Terminal Function Mode

**PATCH** `/api/v1/terminals/{terminal_id}/function_mode`

Update terminal function mode

This endpoint updates the operating mode of a terminal (e.g., Sales, Returns, etc.).
The function mode determines what operations are available on the terminal.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `functionMode` | string | Yes | - |

**Request Example:**
```json
{
  "functionMode": "string"
}
```

**Response:**

**data Field:** `Terminal`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 22. Terminal Open

**POST** `/api/v1/terminals/{terminal_id}/open`

Open a terminal for business operations

This endpoint transitions a terminal to the 'opened' state,
making it ready for sales and other business operations.
It also records the initial cash amount in the drawer.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `initialAmount` | number | No | - |

**Request Example:**
```json
{
  "initialAmount": 0.0
}
```

**Response:**

**data Field:** `TerminalOpenResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `businessDate` | string | Yes | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `terminalInfo` | BaseTerminal | Yes | Base Terminal Information Model

Represents termin |
| `receiptText` | string | Yes | - |
| `journalText` | string | Yes | - |

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
    "terminalId": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0,
    "initialAmount": 0.0,
    "terminalInfo": {
      "terminalId": "string",
      "tenantId": "string",
      "storeCode": "string",
      "terminalNo": 0,
      "description": "string",
      "functionMode": "string",
      "status": "string",
      "businessDate": "string",
      "openCounter": 0,
      "businessCounter": 0
    },
    "receiptText": "string",
    "journalText": "string"
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

### 23. Terminal Signin

**POST** `/api/v1/terminals/{terminal_id}/sign-in`

Sign in to a terminal

This endpoint associates a staff member with a terminal for the duration of their shift.
A terminal must have a staff member signed in before most operations can be performed.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `staffId` | string | Yes | - |

**Request Example:**
```json
{
  "staffId": "string"
}
```

**Response:**

**data Field:** `Terminal`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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

### 24. Terminal Signout

**POST** `/api/v1/terminals/{terminal_id}/sign-out`

Sign out from a terminal

This endpoint removes the current staff association from a terminal
at the end of their shift or when changing operators.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `terminal_id` | string | Yes | - |

**Response:**

**data Field:** `Terminal`

| Field | Type | Required | Description |
|------------|------|------|------|
| `terminalId` | string | Yes | - |
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `description` | string | Yes | - |
| `functionMode` | string | Yes | - |
| `status` | string | Yes | - |
| `businessDate` | string | No | - |
| `openCounter` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `initialAmount` | number | No | - |
| `physicalAmount` | number | No | - |
| `staff` | BaseStaff | No | - |
| `apiKey` | string | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "terminalId": "string",
    "tenantId": "string",
    "storeCode": "string",
    "terminalNo": 0,
    "description": "string",
    "functionMode": "string",
    "status": "string",
    "businessDate": "string",
    "openCounter": 0,
    "businessCounter": 0
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
