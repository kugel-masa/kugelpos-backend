# Journal Service API Specification

## Overview

Stores and manages electronic journal and transaction logs.

## Service Information

- **Port**: 8005
- **Framework**: FastAPI
- **Database**: MongoDB (Motor async driver)

## Base URL

- Local Environment: `http://localhost:8005`
- Production Environment: `https://journal.{domain}`

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

Setup the database for the tenant. This will create the required collections and indexes.

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

### Store

### 4. Get Journals

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/journals`

Retrieve journal entries with various filtering options.

This endpoint provides a flexible search interface for journal entries, allowing
filtering by terminal, transaction type, date ranges, receipt numbers, and keywords.
Results can be paginated and sorted.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminals` | array | No | - | - |
| `transaction_types` | array | No | - | Transaction type NormalSales->101, Norma |
| `business_date_from` | string | No | - | YYYYMMDD |
| `business_date_to` | string | No | - | YYYYMMDD |
| `generate_date_time_from` | string | No | - | YYYYMMDDTHHMMSS |
| `generate_date_time_to` | string | No | - | YYYYMMDDTHHMMSS |
| `receipt_no_from` | integer | No | - | - |
| `receipt_no_to` | integer | No | - | - |
| `keywords` | array | No | - | Search keywords |
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |

**Response:**

**data Field:** `array[JournalSchema]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | tenant id |
| `storeCode` | string | Yes | store code |
| `terminalNo` | integer | Yes | terminal no |
| `journalSeqNo` | integer | No | delete in future |
| `transactionNo` | integer | No | transaction_no |
| `transactionType` | integer | Yes | transaction type |
| `businessDate` | string | Yes | business date |
| `openCounter` | integer | Yes | open counter |
| `businessCounter` | integer | Yes | business counter |
| `generateDateTime` | string | Yes | generate date time |
| `receiptNo` | integer | No | receipt no |
| `amount` | number | No | total_amount_with_tax |
| `quantity` | integer | No | total_quantity |
| `staffId` | string | No | staff id |
| `userId` | string | No | user id |
| `content` | string | No | delete in future |
| `journalText` | string | Yes | journal text |
| `receiptText` | string | Yes | receipt text |

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
      "tenantId": "string",
      "storeCode": "string",
      "terminalNo": 0,
      "journalSeqNo": -1,
      "transactionNo": 0,
      "transactionType": 0,
      "businessDate": "string",
      "openCounter": 0,
      "businessCounter": 0,
      "generateDateTime": "string"
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

### 5. Receive Journals

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/journals`

Create a new journal entry.

This endpoint allows terminals to submit journal entries for storage and later retrieval.
Journal entries represent receipts, cash operations, and other terminal activities.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | tenant id |
| `storeCode` | string | Yes | store code |
| `terminalNo` | integer | Yes | terminal no |
| `journalSeqNo` | integer | No | delete in future |
| `transactionNo` | integer | No | transaction_no |
| `transactionType` | integer | Yes | transaction type |
| `businessDate` | string | Yes | business date |
| `openCounter` | integer | Yes | open counter |
| `businessCounter` | integer | Yes | business counter |
| `generateDateTime` | string | Yes | generate date time |
| `receiptNo` | integer | No | receipt no |
| `amount` | number | No | total_amount_with_tax |
| `quantity` | integer | No | total_quantity |
| `staffId` | string | No | staff id |
| `userId` | string | No | user id |
| `content` | string | No | delete in future |
| `journalText` | string | Yes | journal text |
| `receiptText` | string | Yes | receipt text |

**Request Example:**
```json
{
  "tenantId": "string",
  "storeCode": "string",
  "terminalNo": 0,
  "journalSeqNo": -1,
  "transactionNo": 0,
  "transactionType": 0,
  "businessDate": "string",
  "openCounter": 0,
  "businessCounter": 0,
  "generateDateTime": "string"
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

### Transaction

### 6. Receive Transactions

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

Direct API endpoint for receiving transaction data.

This endpoint can be used as an alternative to the Dapr pub/sub mechanism
when direct REST API calls are preferred. It requires authentication via
token or API key.

The function validates the tenant ID from the security credentials,
processes the transaction data, and generates the corresponding journal entries.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

**Response:**

**data Field:** `TranResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |

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
    "terminalNo": 0,
    "transactionNo": 0
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

### 7. Handle Cashlog

**POST** `/api/v1/cashlog`

Handle cash in/out logs received via Dapr pub/sub.

This endpoint is called by Dapr when a cash log message is published
to the 'topic-cashlog' topic. It processes the cash movement data and
generates the corresponding journal entries.

Cash logs represent non-sales cash movements like float, paid-ins, and payouts.

**Response:**

### 8. Handle Opencloselog

**POST** `/api/v1/opencloselog`

Handle terminal open/close logs received via Dapr pub/sub.

This endpoint is called by Dapr when an open/close log message is published
to the 'topic-opencloselog' topic. It processes the terminal session data
and generates the corresponding journal entries.

These logs mark the beginning and end of a terminal's business session
and include details like starting cash, ending cash, and reconciliation.

**Response:**

### 9. Handle Tranlog

**POST** `/api/v1/tranlog`

Handle transaction logs received via Dapr pub/sub.

This endpoint is called by Dapr when a transaction log message is published
to the 'topic-tranlog' topic. It processes the transaction data and generates
the corresponding journal entries.

The journal service uses this data to create human-readable receipt text
and maintains a searchable record of all transactions.

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
