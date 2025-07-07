# Journal Service API Specification

## Overview

The Journal service provides electronic journal management capabilities for the Kugelpos POS system. It persistently stores all transaction records, cash operations, and terminal open/close information to meet audit and compliance requirements.

## Base URL
- Local environment: `http://localhost:8005`
- Production environment: `https://journal.{domain}`

## Authentication

The Journal service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Header: `Authorization: Bearer {token}`
- Purpose: Journal search and inquiry by administrators

### 2. API Key Authentication
- Header: `X-API-Key: {api_key}`
- Purpose: Journal creation from terminals

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

## Transaction Type Codes

| Code | Description |
|------|------|
| 101 | Standard sale |
| -101 | Standard sale cancellation |
| 102 | Return sale |
| 201 | Sale void |
| 202 | Return void |
| 301 | Cash drawer open |
| 302 | Cash drawer close |
| 401 | Cash in |
| 402 | Cash out |
| 501 | Sales report |
| 502 | Other report |

## API Endpoints

### 1. Create Journal
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/journals`

Creates a new journal entry.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (integer, required): Terminal number

**Request Body:**
```json
{
  "transactionNo": "0001",
  "transactionType": 101,
  "businessDate": "2024-01-01",
  "businessCounter": 100,
  "openCounter": 1,
  "receiptNo": "R0001",
  "amount": 99.00,
  "quantity": 2.0,
  "staffId": "STF001",
  "userId": "user001",
  "journalText": "=== Sales Transaction ===\n...",
  "receiptText": "=== Receipt ===\n..."
}
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Transaction received successfully. tenant_id: tenant001, store_code: store001, terminal_no: 1",
  "data": {
    "tenantId": "tenant001",
    "storeCode": "store001",
    "terminalNo": 1,
    "transactionNo": "0001",
    "transactionType": 101,
    "businessDate": "2024-01-01",
    "receiptNo": "R0001",
    "amount": 99.00,
    "generateDateTime": "2024-01-01T10:30:00Z"
  },
  "operation": "create_journal"
}
```

### 2. Search Journals
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/journals`

Searches journal entries with multiple criteria.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

**Query Parameters:**
- `terminals` (string): Terminal numbers (comma-separated)
- `transaction_types` (string): Transaction types (comma-separated)
- `business_date_from` (string): Start business date (YYYY-MM-DD)
- `business_date_to` (string): End business date (YYYY-MM-DD)
- `generate_date_time_from` (string): Start generation date/time (YYYYMMDDTHHMMSS)
- `generate_date_time_to` (string): End generation date/time (YYYYMMDDTHHMMSS)
- `receipt_no_from` (string): Start receipt number
- `receipt_no_to` (string): End receipt number
- `keywords` (string): Keyword search (comma-separated)
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 100, max: 1000): Page size
- `sort` (string): Sort order (e.g., "generateDateTime:-1")

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Journals found successfully. tenant_id: tenant001, store_code: store001",
  "data": [
    {
      "tenantId": "tenant001",
      "storeCode": "store001",
      "terminalNo": 1,
      "transactionNo": "0001",
      "transactionType": 101,
      "businessDate": "2024-01-01",
      "businessCounter": 100,
      "openCounter": 1,
      "receiptNo": "R0001",
      "amount": 99.00,
      "quantity": 2.0,
      "staffId": "STF001",
      "userId": "user001",
      "generateDateTime": "2024-01-01T10:30:00Z",
      "journalText": "=== Sales Transaction ===\n...",
      "receiptText": "=== Receipt ===\n..."
    }
  ],
  "metadata": {
    "total": 150,
    "page": 1,
    "limit": 50,
    "pages": 3
  },
  "operation": "search_journals"
}
```

### 3. Receive Transaction (REST)
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

REST endpoint for directly sending transaction data.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (integer, required): Terminal number

**Request Body:**
Same structure as the journal creation endpoint

### 4. Create Tenant
**POST** `/api/v1/tenants`

Initializes journal service for a new tenant.

**Request Body:**
```json
{
  "tenantId": "tenant001"
}
```

**Authentication:** JWT token required

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

### 5. Health Check
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
    "dapr_sidecar": "connected",
    "dapr_state_store": "connected",
    "pubsub_topics": "subscribed"
  },
  "operation": "health_check"
}
```

## Event Processing Endpoints (Dapr Pub/Sub)

### 6. Transaction Log Handler
**POST** `/api/v1/tranlog`

**Topic:** `tranlog_report`

Processes transaction logs from the Cart service.

### 7. Cash Log Handler
**POST** `/api/v1/cashlog`

**Topic:** `cashlog_report`

Processes cash in/out logs from the Terminal service.

### 8. Open/Close Log Handler
**POST** `/api/v1/opencloselog`

**Topic:** `opencloselog_report`

Processes terminal open/close logs from the Terminal service.

## Sort Options

Available sort fields:
- `terminalNo`: Terminal number
- `businessDate`: Business date
- `transactionNo`: Transaction number
- `receiptNo`: Receipt number
- `generateDateTime`: Generation date/time
- `amount`: Amount

Default sort order:
- `terminalNo:1, businessDate:1, receiptNo:1` (terminal number, business date, receipt number ascending)

Direction:
- `1`: Ascending
- `-1`: Descending

## Error Codes

Journal service uses error codes in the 410XX-411XX range:

### Journal Basic Operation Related (4100X)
- `410001`: Journal not found
- `410002`: Journal validation error
- `410003`: Journal creation error
- `410004`: Journal search error
- `410005`: Journal format error
- `410006`: Journal date error
- `410007`: Journal data error

### Journal Verification Related (4101X)
- `410101`: Terminal not found
- `410102`: Store not found
- `410103`: Required logs missing
- `410104`: Log sequence error
- `410105`: Transaction validation error

### Other Journal Related (411XX)
- `411001`: Receipt generation error
- `411002`: Journal text generation error
- `411003`: Export error
- `411004`: Import error
- `411005`: Transaction receipt error
- `411006`: External service error

## Special Notes

1. **Idempotency**: Duplicate processing prevention by event ID
2. **Data Retention**: Permanent storage (no automatic deletion)
3. **Full-text Search**: Keyword search support within journal_text
4. **Asynchronous Processing**: All operations executed asynchronously
5. **Circuit Breaker**: Automatic recovery during external service failures