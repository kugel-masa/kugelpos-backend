# Report Service API Specification

## Overview

Generates sales reports and daily summaries. Uses plugin architecture for extensibility.

## Service Information

- **Port**: 8004
- **Framework**: FastAPI
- **Database**: MongoDB (PyMongo async API)

## Base URL

- Local Environment: `http://localhost:8004`
- Production Environment: `https://report.{domain}`

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

Create and set up a new tenant in the report service.

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

### Store

### 4. Preview Settlement

**GET** `/api/v1/internal/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/settlement-preview`

What confirming would record now, without storing anything.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `business_counter` | integer | Yes | - | - |
| `business_date` | string | Yes | - | - |
| `open_counter` | integer | Yes | - | - |
| `seq` | string | No | - | - |
| `cash_log_count` | string | No | - | - |
| `physical_amount` | string | No | - | - |

**Response:**

**data Field:** `SettlementPreviewResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `businessDate` | string | Yes | - |
| `openCounter` | integer | Yes | - |
| `settledBy` | string | No | - |
| `settledAt` | string | Yes | - |
| `declaredCount` | integer | No | - |
| `declaredSource` | string | Yes | - |
| `includedCount` | integer | Yes | - |
| `includedRanges` | array[NumberRangeSchema] | No | - |
| `missingCount` | integer | Yes | - |
| `missingRanges` | array[NumberRangeSchema] | No | - |
| `duplicateNumbers` | array[integer] | No | - |
| `serverNumberedCount` | integer | No | - |
| `declaredCashLogCount` | integer | No | - |
| `cashLogCount` | integer | Yes | - |
| `missingCashLogCount` | integer | Yes | - |
| `expectedCash` | ExpectedCashSchema | Yes | - |
| `physicalAmount` | number | No | - |
| `difference` | number | No | - |
| `settled` | boolean | Yes | - |

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
    "businessCounter": 0,
    "businessDate": "string",
    "openCounter": 0,
    "settledBy": "string",
    "settledAt": "string",
    "declaredCount": 0,
    "declaredSource": "string"
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

### 5. Confirm Settlement

**POST** `/api/v1/internal/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/settlements`

Confirm a terminal session's settlement from the logs that have arrived.

A provisional settlement is recomputed and replaced; a final one is returned
as stored. Missing or duplicate transactions never refuse the settlement;
they are recorded.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `businessCounter` | integer | Yes | - |
| `businessDate` | string | Yes | - |
| `openCounter` | integer | Yes | - |
| `settledAt` | string | Yes | - |
| `seq` | integer | No | - |
| `cashLogCount` | integer | No | - |
| `physicalAmount` | number | No | - |
| `settledBy` | string | No | - |

**Request Example:**
```json
{
  "businessCounter": 0,
  "businessDate": "string",
  "openCounter": 0,
  "settledAt": "string",
  "seq": 0,
  "cashLogCount": 0,
  "physicalAmount": 0.0,
  "settledBy": "string"
}
```

**Response:**

**data Field:** `SettlementConfirmResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `businessDate` | string | Yes | - |
| `openCounter` | integer | Yes | - |
| `settledBy` | string | No | - |
| `settledAt` | string | Yes | - |
| `declaredCount` | integer | No | - |
| `declaredSource` | string | Yes | - |
| `includedCount` | integer | Yes | - |
| `includedRanges` | array[NumberRangeSchema] | No | - |
| `missingCount` | integer | Yes | - |
| `missingRanges` | array[NumberRangeSchema] | No | - |
| `duplicateNumbers` | array[integer] | No | - |
| `serverNumberedCount` | integer | No | - |
| `declaredCashLogCount` | integer | No | - |
| `cashLogCount` | integer | Yes | - |
| `missingCashLogCount` | integer | Yes | - |
| `expectedCash` | ExpectedCashSchema | Yes | - |
| `physicalAmount` | number | No | - |
| `difference` | number | No | - |
| `settlementId` | string | Yes | - |
| `state` | string | Yes | - |
| `recordedAt` | string | Yes | - |
| `finalizedAt` | string | No | - |
| `created` | boolean | Yes | - |

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
    "businessCounter": 0,
    "businessDate": "string",
    "openCounter": 0,
    "settledBy": "string",
    "settledAt": "string",
    "declaredCount": 0,
    "declaredSource": "string"
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

### 6. Get Report For Store

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/reports`

Get a report for the entire store.

This endpoint requires either a JWT token or an API key with terminal_id.
It provides different types of reports (sales, category, item) at different
scopes (flash, daily) for the specified store.

Daily scope (#343): the report is the settled sessions' frozen reports,
merged when the scope has more than one session. A session in scope that
has a log but no final settlement refuses the report with 403 / 412101,
and data.unsettledSessions names it. A daily report returns the whole
frozen report (limit and page are not applied), carries missingCount and
missingRanges, and a date-range daily report carries the cash section.
Flash is computed live, as before.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | Terminal ID for api_key authentication |
| `report_scope` | string | Yes | - | Scope of the report: flash, daily |
| `report_type` | string | Yes | - | Type of the report: sales, category, ite |
| `business_date` | string | No | - | Business date for flash and daily (singl |
| `business_date_from` | string | No | - | Start date for date range (YYYYMMDD form |
| `business_date_to` | string | No | - | End date for date range (YYYYMMDD format |
| `open_counter` | integer | No | - | Open counter for flash and daily, None f |
| `business_counter` | integer | No | - | Business counter for the report |
| `limit` | integer | No | 100 | Limit of the number of records to return |
| `page` | integer | No | 1 | Page number to return |
| `is_terminal_service` | string | No | False | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |

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

### 7. List Settlements

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/settlements`

The store's settlement records, by business date, terminal and session.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_no` | string | No | - | - |
| `business_counter` | string | No | - | - |
| `business_date_from` | string | No | - | - |
| `business_date_to` | string | No | - | - |
| `state` | string | No | - | - |
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[SettlementRecordResponse]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `terminalNo` | integer | Yes | - |
| `businessCounter` | integer | Yes | - |
| `businessDate` | string | Yes | - |
| `openCounter` | integer | Yes | - |
| `settledBy` | string | No | - |
| `settledAt` | string | Yes | - |
| `declaredCount` | integer | No | - |
| `declaredSource` | string | Yes | - |
| `includedCount` | integer | Yes | - |
| `includedRanges` | array[NumberRangeSchema] | No | - |
| `missingCount` | integer | Yes | - |
| `missingRanges` | array[NumberRangeSchema] | No | - |
| `duplicateNumbers` | array[integer] | No | - |
| `serverNumberedCount` | integer | No | - |
| `declaredCashLogCount` | integer | No | - |
| `cashLogCount` | integer | Yes | - |
| `missingCashLogCount` | integer | Yes | - |
| `expectedCash` | ExpectedCashSchema | Yes | - |
| `physicalAmount` | number | No | - |
| `difference` | number | No | - |
| `settlementId` | string | Yes | - |
| `state` | string | Yes | - |
| `recordedAt` | string | Yes | - |
| `finalizedAt` | string | No | - |

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
      "businessCounter": 0,
      "businessDate": "string",
      "openCounter": 0,
      "settledBy": "string",
      "settledAt": "string",
      "declaredCount": 0,
      "declaredSource": "string"
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

### 8. Get Report For Terminal

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports`

Get a report for a specific terminal.

This endpoint requires either a JWT token or an API key with terminal_id.
It provides different types of reports (sales, category, item) at different
scopes (flush, daily) for the specified terminal.

Daily scope (#343): the terminal's settled sessions' frozen reports; one
session's is returned as frozen, several are merged. A session with a log
but no final settlement refuses the report with 403 / 412101, and
data.unsettledSessions names it. limit and page are not applied to a daily
report, which carries missingCount and missingRanges. Flash is live.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | Terminal ID for api_key authentication |
| `report_scope` | string | Yes | - | Scope of the report: flash, daily |
| `report_type` | string | Yes | - | Type of the report: sales, category, ite |
| `business_date` | string | No | - | Business date for flash and daily (singl |
| `business_date_from` | string | No | - | Start date for date range (YYYYMMDD form |
| `business_date_to` | string | No | - | End date for date range (YYYYMMDD format |
| `open_counter` | integer | No | - | Open counter for flash and daily, None f |
| `business_counter` | integer | No | - | Business counter for the report |
| `limit` | integer | No | 100 | Limit of the number of records to return |
| `page` | integer | No | 1 | Page number to return |
| `is_terminal_service` | string | No | False | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |

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

### 9. Receive Transactions

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

Direct API endpoint for receiving transaction data.

This endpoint can be used as an alternative to the Dapr pub/sub mechanism
when direct REST API calls are preferred. It requires authentication via
token or API key.

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

### 10. Handle Cashlog

**POST** `/api/v1/cashlog`

Handle cash in/out logs received via Dapr pub/sub.

This endpoint is called by Dapr when a cash log message is published
to the 'topic-cashlog' topic in the 'pubsub-cashlog-report' component.

**Response:**

### 11. Handle Opencloselog

**POST** `/api/v1/opencloselog`

Handle terminal open/close logs received via Dapr pub/sub.

This endpoint is called by Dapr when an open/close log message is published
to the 'topic-opencloselog' topic in the 'pubsub-opencloselog-report' component.

**Response:**

### 12. Handle Tranlog

**POST** `/api/v1/tranlog`

Handle transaction logs received via Dapr pub/sub.

This endpoint is called by Dapr when a transaction log message is published
to the 'topic-tranlog' topic in the 'pubsub-tranlog-report' component.

**Response:**

### Dead Letters

### 13. List dead letters

**GET** `/api/v1/tenants/{tenant_id}/dead-letters`

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `state` | string | No | pending | pending / replaying / replayed / discard |
| `topic` | string | No | - | - |
| `notified` | string | No | - | - |
| `dead_from` | string | No | - | - |
| `dead_to` | string | No | - | - |
| `limit` | integer | No | 50 | - |
| `page` | integer | No | 1 | - |

**Response:**

**data Field:** `array[DeadLetterSchema]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `id` | string | Yes | - |
| `service` | string | No | - |
| `topic` | string | No | - |
| `eventId` | string | Yes | - |
| `state` | string | Yes | - |
| `summary` | DeadLetterSummarySchema | No | - |
| `lastError` | string | No | - |
| `failureCount` | integer | No | - |
| `deadCount` | integer | No | - |
| `firstDeadAt` | string | No | - |
| `lastDeadAt` | string | No | - |
| `notifiedAt` | string | No | - |
| `resolvedAt` | string | No | - |
| `resolvedBy` | string | No | - |
| `resolutionNote` | string | No | - |

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
      "id": "string",
      "service": "string",
      "topic": "string",
      "eventId": "string",
      "state": "string",
      "summary": {
        "storeCode": "string",
        "terminalNo": "string",
        "transactionNo": "string",
        "businessDate": "string",
        "businessCounter": "string"
      },
      "lastError": "string",
      "failureCount": 0,
      "deadCount": 0,
      "firstDeadAt": "2025-01-01T00:00:00Z"
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

### 14. Replay several dead letters in the background

**POST** `/api/v1/tenants/{tenant_id}/dead-letters/replay`

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `ids` | array[string] | Yes | - |

**Request Example:**
```json
{
  "ids": [
    "string"
  ]
}
```

### 15. Get a dead letter

**GET** `/api/v1/tenants/{tenant_id}/dead-letters/{id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `id` | string | Yes | - |

**Response:**

**data Field:** `DeadLetterDetailSchema`

| Field | Type | Required | Description |
|------------|------|------|------|
| `id` | string | Yes | - |
| `service` | string | No | - |
| `topic` | string | No | - |
| `eventId` | string | Yes | - |
| `state` | string | Yes | - |
| `summary` | DeadLetterSummarySchema | No | - |
| `lastError` | string | No | - |
| `failureCount` | integer | No | - |
| `deadCount` | integer | No | - |
| `firstDeadAt` | string | No | - |
| `lastDeadAt` | string | No | - |
| `notifiedAt` | string | No | - |
| `resolvedAt` | string | No | - |
| `resolvedBy` | string | No | - |
| `resolutionNote` | string | No | - |
| `message` | object | No | - |

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
    "id": "string",
    "service": "string",
    "topic": "string",
    "eventId": "string",
    "state": "string",
    "summary": {
      "storeCode": "string",
      "terminalNo": "string",
      "transactionNo": "string",
      "businessDate": "string",
      "businessCounter": "string"
    },
    "lastError": "string",
    "failureCount": 0,
    "deadCount": 0,
    "firstDeadAt": "2025-01-01T00:00:00Z"
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

### 16. Discard a dead letter

**POST** `/api/v1/tenants/{tenant_id}/dead-letters/{id}/discard`

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `id` | string | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `reason` | string | Yes | - |

**Request Example:**
```json
{
  "reason": "string"
}
```

**Response:**

**data Field:** `DeadLetterSchema`

| Field | Type | Required | Description |
|------------|------|------|------|
| `id` | string | Yes | - |
| `service` | string | No | - |
| `topic` | string | No | - |
| `eventId` | string | Yes | - |
| `state` | string | Yes | - |
| `summary` | DeadLetterSummarySchema | No | - |
| `lastError` | string | No | - |
| `failureCount` | integer | No | - |
| `deadCount` | integer | No | - |
| `firstDeadAt` | string | No | - |
| `lastDeadAt` | string | No | - |
| `notifiedAt` | string | No | - |
| `resolvedAt` | string | No | - |
| `resolvedBy` | string | No | - |
| `resolutionNote` | string | No | - |

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
    "id": "string",
    "service": "string",
    "topic": "string",
    "eventId": "string",
    "state": "string",
    "summary": {
      "storeCode": "string",
      "terminalNo": "string",
      "transactionNo": "string",
      "businessDate": "string",
      "businessCounter": "string"
    },
    "lastError": "string",
    "failureCount": 0,
    "deadCount": 0,
    "firstDeadAt": "2025-01-01T00:00:00Z"
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

### 17. Replay a dead letter

**POST** `/api/v1/tenants/{tenant_id}/dead-letters/{id}/replay`

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `id` | string | Yes | - |

**Response:**

**data Field:** `ReplayResultSchema`

| Field | Type | Required | Description |
|------------|------|------|------|
| `id` | string | Yes | - |
| `outcome` | string | Yes | - |
| `error` | string | No | - |

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
    "id": "string",
    "outcome": "string",
    "error": "string"
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
