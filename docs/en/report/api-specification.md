# Report Service API Specification

## Overview

Report Service is responsible for generating business reports and analytics in the Kugelpos POS system. It processes transaction data from multiple sources, provides real-time flash reports during business hours, and generates comprehensive daily settlement reports using a plugin architecture for extensibility.

## Base URL
- Local environment: `http://localhost:8004`
- Production environment: `https://report.{domain}`

## Authentication

Report Service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Include in header: `Authorization: Bearer {token}`
- Obtain token from: Account Service's `/api/v1/accounts/token`
- Required for administrative report access

### 2. API Key Authentication
- Include in header: `X-API-Key: {api_key}`
- Include query parameter: `terminal_id={tenant_id}_{store_code}_{terminal_no}`
- Used for terminal-initiated reports

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

## Report Types and Scopes

### Report Scopes
- `flash` - Real-time reports during business hours
- `daily` - Settlement reports after terminal closure

### Report Types
- `sales` - Sales reports (currently implemented)
- `category` - Category analysis (planned)
- `item` - Item performance (planned)

## API Endpoints

### Report Generation

#### 1. Get Store Report
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/reports`

Generate reports for all terminals in a store.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

**Query Parameters:**
- `terminal_id` (string, optional): Terminal ID for API key authentication
- `report_scope` (string, required): Report scope ("flash" or "daily")
- `report_type` (string, required): Report type ("sales")
- `business_date` (string, required): Business date (YYYYMMDD format, e.g., "20240101")
- `open_counter` (integer, optional): Session counter for flash reports
- `business_counter` (integer, optional): Business counter
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 20, max: 100): Items per page
- `sort` (string, optional): Sort field and order (format: "field1:1,field2:-1" where 1=ascending, -1=descending)

**Request Example:**
```bash
curl -X GET "http://localhost:8004/api/v1/tenants/tenant001/stores/store001/reports?report_scope=daily&report_type=sales&business_date=20240101" \
  -H "Authorization: Bearer {token}"
```

**Response Example (Sales Report):**
```json
{
  "success": true,
  "code": 200,
  "message": "Reports generated successfully",
  "data": {
    "data": [
      {
        "tenantId": "tenant001",
        "storeCode": "store001",
        "terminalNo": 1,
        "businessDate": "2024-01-01",
        "reportScope": "daily",
        "reportType": "sales",
        "salesInfo": {
          "grossSales": {
            "amount": 1000.00,
            "quantity": 50.0,
            "count": 25
          },
          "netSales": {
            "amount": 900.00,
            "quantity": 50.0,
            "count": 25
          },
          "discounts": {
            "lineItems": {
              "amount": 50.00,
              "quantity": 10.0,
              "count": 5
            },
            "subtotal": {
              "amount": 50.00,
              "quantity": 0.0,
              "count": 5
            }
          },
          "returns": {
            "amount": 100.00,
            "quantity": 5.0,
            "count": 2
          },
          "voids": {
            "amount": 50.00,
            "quantity": 2.0,
            "count": 1
          }
        },
        "taxes": [
          {
            "taxName": "Standard Tax",
            "taxAmount": 90.00,
            "targetAmount": 900.00,
            "targetQuantity": 45.0
          }
        ],
        "payments": [
          {
            "paymentName": "Cash",
            "amount": 500.00,
            "count": 15
          },
          {
            "paymentName": "Credit Card",
            "amount": 400.00,
            "count": 10
          }
        ],
        "cashBalance": {
          "openingAmount": 500.00,
          "salesAmount": 500.00,
          "cashInAmount": 100.00,
          "cashOutAmount": 50.00,
          "logicalAmount": 1050.00,
          "physicalAmount": 1050.00,
          "differenceAmount": 0.00
        },
        "transactionCount": 25,
        "customerCount": 25,
        "receiptText": "=== DAILY REPORT ===\n...",
        "journalText": "Daily Sales Report\n...",
        "generateDateTime": "2024-01-02T00:30:00Z"
      }
    ],
    "metadata": {
      "total": 3,
      "page": 1,
      "limit": 20,
      "sort": null,
      "filter": {
        "reportScope": "daily",
        "reportType": "sales",
        "businessDate": "2024-01-01"
      }
    }
  },
  "operation": "get_store_reports"
}
```

#### 2. Get Terminal Report
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports`

Generate reports for a specific terminal.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (integer, required): Terminal number

**Query Parameters:**
- Same as store report endpoint

**Request Example:**
```bash
curl -X GET "http://localhost:8004/api/v1/tenants/tenant001/stores/store001/terminals/1/reports?report_scope=flash&report_type=sales&business_date=2024-01-01&open_counter=1" \
  -H "X-API-Key: {api_key}" \
  -H "terminal_id=tenant001-store001-001"
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
  "totalAmount": 99.00,
  "items": [
    {
      "lineNo": 1,
      "itemCode": "ITEM001",
      "quantity": 2.0,
      "unitPrice": 50.00,
      "amount": 100.00,
      "discountAmount": 10.00,
      "taxAmount": 9.00
    }
  ],
  "payments": [
    {
      "paymentMethodCode": "01",
      "amount": 100.00,
      "changeAmount": 1.00
    }
  ],
  "timestamp": "2024-01-01T10:30:00Z"
}
```

#### 4. Cash Log Handler
**POST** `/api/v1/cashlog`

Process cash in/out logs from terminal service via Dapr pub/sub.

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
  "reason": "Float Addition",
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
  "timestamp": "2024-01-01T08:00:00Z"
}
```

### Direct Transaction API

#### 6. Submit Transaction
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

Alternative REST endpoint for submitting transaction data directly.

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
  "totalAmount": 99.00,
  "items": [...],
  "payments": [...],
  "timestamp": "2024-01-01T10:30:00Z"
}
```

### System Endpoints

#### 7. Create Tenant
**POST** `/api/v1/tenants`

Initialize report service for a new tenant.

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
      "log_tran",
      "log_cash_in_out",
      "log_open_close",
      "sales_report",
      "daily_info"
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
curl -X GET "http://localhost:8004/health"
```

**Response Example:**
```json
{
  "status": "healthy",
  "service": "report",
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
    }
  }
}
```

## Report Data Structure

### Sales Report Components

#### Sales Information
```json
{
  "grossSales": {
    "amount": 1000.00,
    "quantity": 50.0,
    "count": 25
  },
  "netSales": {
    "amount": 900.00,
    "quantity": 50.0,
    "count": 25
  },
  "discounts": {
    "lineItems": {
      "amount": 50.00,
      "quantity": 10.0,
      "count": 5
    },
    "subtotal": {
      "amount": 50.00,
      "quantity": 0.0,
      "count": 5
    }
  },
  "returns": {
    "amount": 100.00,
    "quantity": 5.0,
    "count": 2
  },
  "voids": {
    "amount": 50.00,
    "quantity": 2.0,
    "count": 1
  }
}
```

#### Tax Breakdown
```json
{
  "taxes": [
    {
      "taxName": "Standard Tax",
      "taxAmount": 90.00,
      "targetAmount": 900.00,
      "targetQuantity": 45.0
    }
  ]
}
```

#### Payment Summary
```json
{
  "payments": [
    {
      "paymentName": "Cash",
      "amount": 500.00,
      "count": 15
    }
  ]
}
```

#### Cash Balance
```json
{
  "cashBalance": {
    "openingAmount": 500.00,
    "salesAmount": 500.00,
    "cashInAmount": 100.00,
    "cashOutAmount": 50.00,
    "logicalAmount": 1050.00,
    "physicalAmount": 1050.00,
    "differenceAmount": 0.00
  }
}
```

## Data Verification

### Daily Report Prerequisites

Before generating daily reports, the service verifies:

1. **Terminal Closure**: All terminals must be closed
2. **Transaction Completeness**: All transactions must be logged
3. **Cash Operation Completeness**: All cash operations must be recorded
4. **Session Completeness**: Open/close logs must match

### Verification Errors

```json
{
  "success": false,
  "code": 400,
  "message": "Terminal 1 is not closed for business date 2024-01-01",
  "data": null,
  "operation": "get_store_reports"
}
```

## Error Responses

The API uses standard HTTP status codes and structured error responses:

```json
{
  "success": false,
  "code": 404,
  "message": "No reports found for the specified criteria",
  "data": null,
  "operation": "get_terminal_reports"
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

Report Service uses error codes in the 40XXX range:

- `40001` - Report generation error
- `40002` - Data verification failure
- `40003` - Terminal not closed
- `40004` - Transaction log missing
- `40005` - Cash operation missing
- `40006` - Plugin loading error
- `40007` - Data aggregation error
- `40008` - Invalid report parameters
- `40099` - General report service error

## Plugin System

### Available Plugins

1. **SalesReportMaker** (Implemented)
   - Generates comprehensive sales reports
   - Calculates gross/net sales, discounts, taxes
   - Provides payment and cash balance summaries

2. **CategoryReportMaker** (Planned)
   - Sales analysis by product category
   - Category performance metrics

3. **ItemReportMaker** (Planned)
   - Individual item performance
   - Best/worst selling items

### Plugin Configuration

Plugins are configured in `plugins.json`:

```json
{
  "report_plugins": {
    "sales": "plugins.sales_report_maker.SalesReportMaker",
    "category": "plugins.category_report_maker.CategoryReportMaker",
    "item": "plugins.item_report_maker.ItemReportMaker"
  }
}
```

## Integration with Journal Service

When reports are generated via API key authentication (terminal-initiated), they are automatically sent to the journal service for archival:

```json
{
  "transactionType": 501,  // Report type code
  "receiptText": "=== SALES REPORT ===\n...",
  "journalText": "Sales Report Details\n..."
}
```

## Business Rules

1. **Flash Reports**: Available anytime during business hours
2. **Daily Reports**: Only available after all terminals are closed
3. **Data Completeness**: All event types must be received for accurate reports
4. **Idempotency**: Duplicate events are automatically filtered
5. **Multi-tenant**: Reports are strictly tenant-isolated

## Performance Considerations

1. **Aggregation**: Uses MongoDB aggregation pipelines for efficiency
2. **Pagination**: Large datasets are paginated
3. **Caching**: Report results can be cached (implementation-specific)
4. **Asynchronous Processing**: All operations are async
5. **Circuit Breaker**: Protection against external service failures

## Notes

1. **Business Date Format**: Always use YYYY-MM-DD format
2. **Terminal Numbers**: Integer values (not zero-padded)
3. **CamelCase Convention**: All JSON fields use camelCase
4. **Timestamps**: All timestamps are in ISO 8601 format (UTC)
5. **Amount Fields**: All monetary values are in decimal format
6. **Report Archival**: Terminal-initiated reports are archived in journal service
7. **Event Processing**: Uses Dapr pub/sub for reliable event delivery