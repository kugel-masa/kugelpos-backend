# Report Service API Specification

## Overview

The Report service provides various report generation capabilities for the Kugelpos POS system. It generates sales reports, category reports, item reports, and provides both real-time (flash) and daily aggregated data. The service features an extensible design through plugin architecture for report types.

## Base URL
- Local environment: `http://localhost:8004`
- Production environment: `https://report.{domain}`

## Authentication

The Report service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Header: `Authorization: Bearer {token}`
- Purpose: Report viewing and generation by administrators

### 2. API Key Authentication
- Header: `X-API-Key: {api_key}`
- Purpose: Report retrieval from terminals (with journal integration)

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

## Report Types

| Type ID | Name | Description |
|----------|------|-------------|
| sales | Sales Report | Basic aggregation of sales amounts, transaction counts, etc. |
| category | Category Report | Category-wise sales aggregation (not implemented) |
| item | Item Report | Item-wise sales aggregation (not implemented) |

## Report Scopes

| Scope ID | Name | Description |
|--------|------|-------------|
| flash | Flash Report | Real-time aggregation (current session) |
| daily | Daily Report | Daily aggregation (requires all terminals closed) |

## API Endpoints

### 1. Get Store Report
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/reports`

Retrieves store-wide reports.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

**Query Parameters:**
- `report_scope` (string, required): Report scope (flash/daily)
- `report_type` (string, required): Report type (sales)
- `business_date` (string, required): Business date (YYYYMMDD)
- `open_counter` (integer): Open counter (for flash reports)
- `business_counter` (integer): Business counter
- `limit` (integer, default: 100): Page size
- `page` (integer, default: 1): Page number
- `sort` (string): Sort conditions

**Response Example (Sales Report):**
```json
{
  "success": true,
  "code": 200,
  "message": "Sales report fetched successfully",
  "data": {
    "tenantId": "tenant001",
    "storeCode": "STORE001",
    "storeName": "Store 001",
    "terminalNo": null,
    "businessDate": "20240101",
    "reportScope": "daily",
    "reportType": "sales",
    "salesGross": {
      "itemCount": 500,
      "transactionCount": 150,
      "totalAmount": 125000.00
    },
    "salesNet": {
      "itemCount": 495,
      "transactionCount": 148,
      "totalAmount": 120000.00
    },
    "discountForLineitems": {
      "itemCount": 20,
      "transactionCount": 15,
      "totalAmount": -2000.00
    },
    "discountForSubtotal": {
      "itemCount": 0,
      "transactionCount": 10,
      "totalAmount": -1000.00
    },
    "returns": {
      "itemCount": 5,
      "transactionCount": 2,
      "totalAmount": -2000.00
    },
    "taxes": [
      {
        "taxCode": "TAX_10",
        "taxType": "STANDARD",
        "taxName": "Standard Tax Rate",
        "itemCount": 400,
        "targetAmount": 100000.00,
        "taxAmount": 10000.00
      },
      {
        "taxCode": "TAX_8",
        "taxType": "REDUCED",
        "taxName": "Reduced Tax Rate",
        "itemCount": 100,
        "targetAmount": 25000.00,
        "taxAmount": 2000.00
      }
    ],
    "payments": [
      {
        "paymentCode": "CASH",
        "paymentName": "Cash",
        "transactionCount": 100,
        "totalAmount": 80000.00
      },
      {
        "paymentCode": "CREDIT",
        "paymentName": "Credit",
        "transactionCount": 50,
        "totalAmount": 45000.00
      }
    ],
    "cash": {
      "cashInCount": 5,
      "cashInAmount": 10000.00,
      "cashOutCount": 3,
      "cashOutAmount": -5000.00,
      "netCashMovement": 5000.00
    },
    "receiptText": "=== Daily Sales Report ===\n...",
    "journalText": "=== Daily Sales Report ===\n..."
  },
  "operation": "get_report_for_store"
}
```

### 2. Get Terminal Report
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports`

Retrieves reports for a specific terminal.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (integer, required): Terminal number

**Query Parameters:**
Same as store report

### 3. Receive Transaction (REST)
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

REST endpoint for directly sending transaction data.

**Request Body:**
Transaction data conforming to kugel_common BaseTransaction structure

### 4. Create Tenant
**POST** `/api/v1/tenants`

Initializes report service for a new tenant.

**Request Body:**
```json
{
  "tenantId": "tenant001"
}
```

**Authentication:** JWT token required

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
    "mongodb": "connected"
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

Processes open/close logs from the Terminal service.

## Report Structure Details

### SalesReportTemplate
Basic structure for sales aggregation:
```json
{
  "itemCount": 100,          // Number of items
  "transactionCount": 50,    // Number of transactions
  "totalAmount": 10000.00    // Total amount
}
```

### TaxReportTemplate
Tax aggregation structure:
```json
{
  "taxCode": "TAX_10",
  "taxType": "STANDARD",
  "taxName": "Standard Tax Rate",
  "itemCount": 100,
  "targetAmount": 10000.00,   // Taxable amount
  "taxAmount": 1000.00        // Tax amount
}
```

### PaymentReportTemplate
Payment method aggregation structure:
```json
{
  "paymentCode": "CASH",
  "paymentName": "Cash",
  "transactionCount": 50,
  "totalAmount": 10000.00
}
```

### CashReportTemplate
Cash in/out aggregation structure:
```json
{
  "cashInCount": 5,           // Number of cash in operations
  "cashInAmount": 10000.00,   // Cash in amount
  "cashOutCount": 3,          // Number of cash out operations
  "cashOutAmount": -5000.00,  // Cash out amount
  "netCashMovement": 5000.00  // Net cash movement
}
```

## Error Codes

Report service uses error codes in the 412XX-413XX range:

### Report Basic Operation Related (4120X)
- `412001`: Report not found
- `412002`: Report validation error
- `412003`: Report generation error
- `412004`: Invalid report type
- `412005`: Invalid report scope
- `412006`: Report date error
- `412007`: Report data error

### Report Verification Related (4121XX)
- `412101`: Terminal not closed
- `412102`: Required logs missing
- `412103`: Log count mismatch
- `412104`: Transaction log missing
- `412105`: Cash in/out log missing
- `412106`: Open/close log missing
- `412107`: Data verification failed

### Other Report Related (413XX)
- `413001`: Receipt generation error
- `413002`: Journal generation error
- `413003`: Export error
- `413004`: Import error
- `413005`: Daily info error
- `413006`: External service error

## Special Notes

1. **Daily Report Prerequisites**: All terminals must be closed
2. **Data Validation**: Before daily report generation, validates:
   - Existence of close logs for all terminals
   - Consistency of cash in/out log counts
   - Consistency of transaction log counts
3. **Idempotency**: Duplicate processing prevention by event ID
4. **Plugin Extension**: New report types can be added via plugins
5. **Journal Integration**: Reports are automatically sent to journal when using API key authentication