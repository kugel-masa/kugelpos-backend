# Journal Service API Specification

## Overview

Journal Service manages electronic journal storage and transaction log archival in the Kugelpos POS system. It provides a permanent, searchable record of all POS operations including sales transactions, cash movements, terminal activities, and generated reports for regulatory compliance and audit requirements.

## Base URL
- Local environment: `http://localhost:8005`
- Production environment: `https://journal.{domain}`

## Authentication

Journal Service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Include in header: `Authorization: Bearer {token}`
- Obtain token from: Account Service's `/api/v1/accounts/token`
- Required for administrative journal access

### 2. API Key Authentication
- Include in header: `X-API-Key: {api_key}`
- Include query parameter: `terminal_id={tenant_id}_{store_code}_{terminal_no}`
- Used for terminal-initiated journal entries

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

## Transaction Type Codes

Journal entries are categorized by transaction type:

| Code | Description |
|------|-------------|
| 101 | Normal Sales |
| -101 | Normal Sales Cancel |
| 102 | Return Sales |
| 201 | Void Sales |
| 202 | Void Return |
| 301 | Terminal Open |
| 302 | Terminal Close |
| 401 | Cash In |
| 402 | Cash Out |
| 501 | Sales Report |
| 502 | Other Reports |

## API Endpoints

### Journal Management

#### 1. Create Journal Entry
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/journals`

Create a new journal entry for archival.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (integer, required): Terminal number

**Query Parameters:**
- `terminal_id` (string, optional): Terminal ID for API key authentication

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
  "journalText": "=== SALES TRANSACTION ===\n...",
  "receiptText": "=== RECEIPT ===\n..."
}
```

**Field Descriptions:**
- `transactionNo` (string, optional): Transaction number
- `transactionType` (integer, required): Transaction type code
- `businessDate` (string, required): Business date (YYYY-MM-DD)
- `businessCounter` (integer, optional): Business operation counter
- `openCounter` (integer, optional): Terminal session counter
- `receiptNo` (string, optional): Receipt number
- `amount` (number, optional): Transaction amount
- `quantity` (number, optional): Item quantity
- `staffId` (string, optional): Staff identifier
- `userId` (string, optional): User identifier
- `journalText` (string, required): Formatted journal display text
- `receiptText` (string, optional): Formatted receipt text

**Request Example:**
```bash
curl -X POST "http://localhost:8005/api/v1/tenants/tenant001/stores/store001/terminals/1/journals" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "transactionNo": "0001",
    "transactionType": 101,
    "businessDate": "2024-01-01",
    "receiptNo": "R0001",
    "amount": 99.00,
    "journalText": "=== SALES TRANSACTION ===\n...",
    "receiptText": "=== RECEIPT ===\n..."
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Journal entry created successfully",
  "data": {
    "journalId": "507f1f77bcf86cd799439011",
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

#### 2. Search/Retrieve Journals
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/journals`

Search and retrieve journal entries with flexible filtering.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

**Query Parameters:**
- `terminal_id` (string, optional): Terminal ID for API key authentication
- `terminals` (string, optional): Filter by terminal numbers (comma-separated list)
- `transaction_types` (string, optional): Filter by transaction types (comma-separated list)
- `business_date_from` (string, optional): Start business date (YYYY-MM-DD)
- `business_date_to` (string, optional): End business date (YYYY-MM-DD)
- `generate_date_time_from` (string, optional): Start generation datetime (YYYY-MM-DD)
- `generate_date_time_to` (string, optional): End generation datetime (YYYY-MM-DD)
- `receipt_no_from` (string, optional): Start receipt number
- `receipt_no_to` (string, optional): End receipt number
- `keywords` (string, optional): Search keywords in journal text (comma-separated list)
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 20, max: 100): Page size
- `sort` (string, optional): Sort field and order (format: "field1:1,field2:-1" where 1=ascending, -1=descending)

**Request Example:**
```bash
curl -X GET "http://localhost:8005/api/v1/tenants/tenant001/stores/store001/journals?terminals=1,2&transaction_types=101,102&business_date_from=2024-01-01&business_date_to=2024-01-31&limit=50&page=1" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Journals retrieved successfully",
  "data": [
    {
      "journalId": "507f1f77bcf86cd799439011",
      "tenantId": "tenant001",
      "storeCode": "store001",
      "terminalNo": 1,
      "transactionNo": "0001",
      "transactionType": 101,
      "transactionTypeName": "Normal Sales",
      "businessDate": "2024-01-01",
      "businessCounter": 100,
      "openCounter": 1,
      "receiptNo": "R0001",
      "amount": 99.00,
      "quantity": 2.0,
      "staffId": "STF001",
      "userId": "user001",
      "generateDateTime": "2024-01-01T10:30:00Z",
      "journalText": "=== SALES TRANSACTION ===\n...",
      "receiptText": "=== RECEIPT ===\n..."
    }
  ],
  "metadata": {
    "totalItems": 150,
    "totalPages": 3,
    "currentPage": 1,
    "itemsPerPage": 50
  },
  "operation": "search_journals"
}
```

### Event Processing Endpoints (Dapr Pub/Sub)

#### 3. Transaction Log Handler
**POST** `/api/v1/tranlog`

Process transaction logs from cart service via Dapr pub/sub.

**Topic:** `topic-tranlog`

**Event Structure:**
```json
{
  "eventId": "evt_123456",
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
  "receiptText": "=== RECEIPT ===\n...",
  "journalText": "=== SALES TRANSACTION ===\n...",
  "timestamp": "2024-01-01T10:30:00Z"
}
```

**Response:**
The service acknowledges receipt and notifies the source service:
```json
{
  "success": true,
  "eventId": "evt_123456",
  "message": "Transaction log processed successfully"
}
```

#### 4. Cash Log Handler
**POST** `/api/v1/cashlog`

Process cash operation logs from terminal service via Dapr pub/sub.

**Topic:** `topic-cashlog`

**Event Structure:**
```json
{
  "eventId": "evt_789012",
  "tenantId": "tenant001",
  "storeCode": "store001",
  "terminalNo": 1,
  "operationType": "cash_in",
  "amount": 100.00,
  "businessDate": "2024-01-01",
  "businessCounter": 100,
  "openCounter": 1,
  "receiptNo": "CI001",
  "reason": "Float Addition",
  "staffId": "STF001",
  "receiptText": "=== CASH IN ===\n...",
  "journalText": "Cash In Operation\n...",
  "timestamp": "2024-01-01T09:00:00Z"
}
```

#### 5. Open/Close Log Handler
**POST** `/api/v1/opencloselog`

Process terminal open/close logs from terminal service via Dapr pub/sub.

**Topic:** `topic-opencloselog`

**Event Structure:**
```json
{
  "eventId": "evt_345678",
  "tenantId": "tenant001",
  "storeCode": "store001",
  "terminalNo": 1,
  "operationType": "open",
  "businessDate": "2024-01-01",
  "businessCounter": 100,
  "openCounter": 1,
  "initialAmount": 500.00,
  "staffId": "STF001",
  "receiptText": "=== TERMINAL OPEN ===\n...",
  "journalText": "Terminal Open\n...",
  "timestamp": "2024-01-01T08:00:00Z"
}
```

### Direct Transaction API

#### 6. Receive Transaction
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

Alternative REST endpoint for direct transaction submission.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (integer, required): Terminal number

**Query Parameters:**
- `terminal_id` (string, optional): Terminal ID for API key authentication

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
  "receiptText": "=== RECEIPT ===\n...",
  "journalText": "=== SALES TRANSACTION ===\n..."
}
```

### System Endpoints

#### 7. Create Tenant
**POST** `/api/v1/tenants`

Initialize journal service for a new tenant.

**Request Body:**
```json
{
  "tenantId": "tenant001"
}
```

**Authentication:** Requires JWT token

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Tenant creation completed: tenant001",
  "data": {
    "tenantId": "tenant001",
    "collectionsCreated": [
      "journal",
      "log_tran",
      "log_cash_in_out",
      "log_open_close"
    ]
  },
  "operation": "create_tenant"
}
```

#### 8. Health Check
**GET** `/health`

Check service health and dependencies.

**Request Example:**
```bash
curl -X GET "http://localhost:8005/health"
```

**Response Example:**
```json
{
  "status": "healthy",
  "service": "journal",
  "version": "1.0.0",
  "checks": {
    "mongodb": {
      "status": "healthy",
      "details": {
        "ping_time": 0.001234,
        "connection_string": "mongodb://..."
      }
    },
    "dapr_sidecar": {
      "status": "healthy",
      "details": {
        "components": ["statestore", "pubsub"]
      }
    },
    "dapr_state_store": {
      "status": "healthy",
      "details": {
        "name": "statestore",
        "configured": true
      }
    }
  }
}
```

## Journal Search Features

### Search by Terminal Numbers
```
GET /api/v1/tenants/tenant001/stores/store001/journals?terminals=1,2,3
```

### Search by Transaction Types
```
GET /api/v1/tenants/tenant001/stores/store001/journals?transaction_types=101,102,201
```

### Search by Date Range
```
GET /api/v1/tenants/tenant001/stores/store001/journals?business_date_from=2024-01-01&business_date_to=2024-01-31
```

### Search by Receipt Number Range
```
GET /api/v1/tenants/tenant001/stores/store001/journals?receipt_no_from=R0001&receipt_no_to=R0100
```

### Full-text Search
```
GET /api/v1/tenants/tenant001/stores/store001/journals?keywords=ITEM001
```

### Combined Search
```
GET /api/v1/tenants/tenant001/stores/store001/journals?terminals=1&transaction_types=101&business_date_from=2024-01-01&keywords=cash&sort=generateDateTime:-1&limit=50
```

## Sorting Options

Sort parameter format: `field:direction`

Available sort fields:
- `generateDateTime` - Journal creation timestamp
- `businessDate` - Business date
- `transactionNo` - Transaction number
- `receiptNo` - Receipt number
- `amount` - Transaction amount

Directions:
- `asc` - Ascending order
- `desc` - Descending order (default for generateDateTime)

## Error Responses

The API uses standard HTTP status codes and structured error responses:

```json
{
  "success": false,
  "code": 404,
  "message": "No journal entries found for the specified criteria",
  "data": null,
  "operation": "search_journals"
}
```

### Common Status Codes
- `200` - Success
- `201` - Created successfully
- `400` - Bad request
- `401` - Authentication error
- `403` - Access denied
- `404` - No data found
- `500` - Internal server error

### Error Code System

Journal Service uses error codes in the 50XXX range:

- `50001` - Journal entry creation error
- `50002` - Journal search error
- `50003` - Transaction log processing error
- `50004` - Cash log processing error
- `50005` - Terminal log processing error
- `50006` - Data validation error
- `50007` - External service communication error
- `50008` - Duplicate event processing
- `50099` - General journal service error

## Event Processing Features

### Idempotent Processing
- Uses event IDs to prevent duplicate processing
- Stores processed event IDs in Dapr state store
- Returns same response for duplicate events

### Service Notification
After processing events, the journal service notifies the source service:

```python
# For cart service transactions
POST /api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/delivery-status

# For terminal service operations
POST /api/v1/terminals/{terminal_id}/delivery-status
```

### Circuit Breaker
- Protects against cascading failures
- Automatic retry with exponential backoff
- Graceful degradation when external services unavailable

## Data Retention

Journal entries are permanent records for audit and compliance:
- No automatic deletion
- Manual archival processes required
- Compliance with local regulations

## Performance Considerations

1. **Pagination**: Use skip/limit for large result sets
2. **Indexing**: Optimized indexes on search fields
3. **Full-text Search**: MongoDB text indexes on journal_text
4. **Async Processing**: All operations are asynchronous
5. **Connection Pooling**: Efficient database connections

## Integration Examples

### Creating Journal from Terminal
```javascript
// After completing a transaction
const journalEntry = {
  transactionNo: "0001",
  transactionType: 101,
  businessDate: "2024-01-01",
  receiptNo: "R0001",
  amount: 99.00,
  journalText: formatJournalText(transaction),
  receiptText: formatReceiptText(transaction)
};

const response = await fetch(
  `/api/v1/tenants/${tenantId}/stores/${storeCode}/terminals/${terminalNo}/journals`,
  {
    method: 'POST',
    headers: {
      'X-API-Key': apiKey,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(journalEntry)
  }
);
```

### Searching Journals
```javascript
// Search for today's sales transactions
const params = new URLSearchParams({
  transaction_type: '101',
  business_date_from: '2024-01-01',
  business_date_to: '2024-01-01',
  sort: 'generateDateTime:-1',
  limit: '100'
});

const response = await fetch(
  `/api/v1/tenants/${tenantId}/stores/${storeCode}/journals?${params}`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
```

## Notes

1. **Journal Text Format**: Should be human-readable for audit purposes
2. **Receipt Text Format**: Formatted for receipt printer output
3. **Transaction Types**: Use standard codes for consistency
4. **CamelCase Convention**: All JSON fields use camelCase
5. **Timestamps**: All timestamps are in ISO 8601 format (UTC)
6. **Idempotency**: Event processing is idempotent
7. **Compliance**: Designed for regulatory audit requirements