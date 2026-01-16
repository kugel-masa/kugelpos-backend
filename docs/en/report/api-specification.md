# Report Service API Specification

## Overview

Generates sales reports and daily summaries. Uses plugin architecture for extensibility.

## Service Information

- **Port**: 8004
- **Framework**: FastAPI
- **Database**: MongoDB (Motor async driver)

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

### 4. Get Report For Store

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/reports`

Get a report for the entire store.

This endpoint requires either a JWT token or an API key with terminal_id.
It provides different types of reports (sales, category, item) at different
scopes (flash, daily) for the specified store.

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

### 5. Get Report For Terminal

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports`

Get a report for a specific terminal.

This endpoint requires either a JWT token or an API key with terminal_id.
It provides different types of reports (sales, category, item) at different
scopes (flush, daily) for the specified terminal.

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

### 6. Receive Transactions

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

### 7. Handle Cashlog

**POST** `/api/v1/cashlog`

Handle cash in/out logs received via Dapr pub/sub.

This endpoint is called by Dapr when a cash log message is published
to the 'topic-cashlog' topic in the 'pubsub-cashlog-report' component.

**Response:**

### 8. Handle Opencloselog

**POST** `/api/v1/opencloselog`

Handle terminal open/close logs received via Dapr pub/sub.

This endpoint is called by Dapr when an open/close log message is published
to the 'topic-opencloselog' topic in the 'pubsub-opencloselog-report' component.

**Response:**

### 9. Handle Tranlog

**POST** `/api/v1/tranlog`

Handle transaction logs received via Dapr pub/sub.

This endpoint is called by Dapr when a transaction log message is published
to the 'topic-tranlog' topic in the 'pubsub-tranlog-report' component.

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
