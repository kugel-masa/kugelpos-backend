# Report Service Model Specification

## Overview

Report Service is responsible for generating comprehensive business reports and managing event logs from transactions, cash operations, and terminal activities. It implements a plugin architecture for extensible report generation, uses MongoDB aggregation pipelines for complex data processing, and includes data verification mechanisms to ensure completeness before generating daily reports. The service provides robust business intelligence capabilities with multi-tenant isolation.

## Database Document Models

All document models extend `AbstractDocument` which provides common fields for auditing, caching, and sharding.

### AbstractDocument (Base Class)

Base class providing common functionality for all documents.

**Base Fields:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| shard_key | string | - | Database sharding key for horizontal scaling |
| created_at | datetime | - | Document creation timestamp |
| updated_at | datetime | - | Last modification timestamp |
| cached_on | datetime | - | Cache timestamp for invalidation |
| etag | string | - | Entity tag for optimistic concurrency control |

### 1. SalesReportDocument (Transient Report Data)

Transient document structure for API responses (not stored in database).

**Purpose:** Generated on-demand for sales report API responses

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| store_code | string | - | Store code |
| store_name | string | - | Store display name |
| terminal_no | integer | - | Terminal number (null for store-level reports) |
| business_counter | integer | - | Business counter |
| business_date | string | - | Business date (YYYYMMDD) |
| open_counter | integer | - | Terminal session counter |
| report_scope | string | - | Report scope ('flash' or 'daily') |
| report_type | string | - | Report type ('sales') |
| sales_gross | SalesReportTemplate | - | Gross sales metrics |
| sales_net | SalesReportTemplate | - | Net sales metrics |
| discount_for_lineitems | SalesReportTemplate | - | Item-level discount metrics |
| discount_for_subtotal | SalesReportTemplate | - | Transaction-level discount metrics |
| returns | SalesReportTemplate | - | Return transaction metrics |
| taxes | array[TaxReportTemplate] | - | Tax breakdown by tax code |
| payments | array[PaymentReportTemplate] | - | Payment method breakdown |
| cash | CashReportTemplate | - | Cash drawer reconciliation |
| receipt_text | string | - | Formatted receipt text |
| journal_text | string | - | Formatted journal text |
| generate_date_time | string | - | Report generation timestamp |
| staff | StaffMasterDocument | - | Staff information if available |

### 2. CashInOutLog (Cash Operation Records)

Document for storing cash in/out operation logs.

**Collection Name:** `log_cash_in_out`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| store_code | string | - | Store code |
| store_name | string | - | Store display name |
| terminal_no | integer | - | Terminal number |
| staff_id | string | - | Staff identifier who performed operation |
| staff_name | string | - | Staff display name |
| business_date | string | - | Business date (YYYYMMDD) |
| open_counter | integer | - | Terminal session counter |
| business_counter | integer | - | Business operation counter |
| generate_date_time | string | - | Event timestamp |
| amount | float | - | Operation amount (positive for cash in, negative for cash out) |
| description | string | - | Operation description |
| receipt_text | string | - | Formatted receipt text |
| journal_text | string | - | Formatted journal text |

**Indexes:**
- Compound index: (tenant_id, store_code, terminal_no, business_date)
- Index: amount

### 3. OpenCloseLog (Terminal Session Records)

Document for storing terminal open/close operation logs.

**Collection Name:** `log_open_close`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| store_code | string | - | Store code |
| store_name | string | - | Store display name |
| terminal_no | integer | - | Terminal number |
| staff_id | string | - | Staff identifier who performed operation |
| staff_name | string | - | Staff display name |
| business_date | string | - | Business date (YYYYMMDD) |
| open_counter | integer | - | Terminal session counter |
| business_counter | integer | - | Business operation counter |
| operation | string | - | Operation type ('open' or 'close') |
| generate_date_time | string | - | Event timestamp |
| terminal_info | TerminalInfoDocument | - | Terminal state information |
| cart_transaction_count | integer | - | Transaction count at close |
| cart_transaction_last_no | integer | - | Last transaction number |
| cash_in_out_count | integer | - | Cash operation count |
| cash_in_out_last_datetime | string | - | Last cash operation timestamp |
| receipt_text | string | - | Formatted receipt text |
| journal_text | string | - | Formatted journal text |

**Indexes:**
- Compound index: (tenant_id, store_code, terminal_no, business_date, open_counter)
- Index: operation

### 4. DailyInfoDocument (Daily Report Status)

Document for tracking daily report generation status and data verification.

**Collection Name:** `info_daily`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| store_code | string | - | Store code |
| terminal_no | integer | - | Terminal number |
| business_date | string | - | Business date (YYYYMMDD) |
| open_counter | integer | - | Terminal session counter |
| verified | boolean | - | Data verification status |
| verified_update_time | string | - | Last verification timestamp |
| verified_message | string | - | Verification status message |

**Purpose:** Tracks verification status for daily report generation eligibility

**Indexes:**
- Unique compound index: (tenant_id, store_code, terminal_no, business_date)
- Index: verified

### 5. Transaction Logs (From kugel_common)

Transaction data uses `BaseTransaction` from kugel_common library.

**Collection Name:** `log_tran`

**Key Fields Used:**
- Complete transaction record including line items, payments, taxes
- Transaction type codes for proper aggregation
- Business date and counter information
- Amount calculations for reporting

## Embedded Document Models

### SalesReportTemplate

Template structure for sales metrics.

**Field Definitions:**

| Field Name | Type | Description |
|------------|------|-------------|
| amount | float | Total monetary amount |
| quantity | integer | Total item quantity |
| count | integer | Transaction count |

### TaxReportTemplate

Tax breakdown structure.

**Field Definitions:**

| Field Name | Type | Description |
|------------|------|-------------|
| tax_name | string | Tax display name |
| tax_amount | float | Total tax collected |
| target_amount | float | Taxable amount base |
| target_quantity | integer | Taxable item quantity |

### PaymentReportTemplate

Payment method summary structure.

**Field Definitions:**

| Field Name | Type | Description |
|------------|------|-------------|
| payment_name | string | Payment method display name |
| amount | float | Total payment amount |
| count | integer | Payment transaction count |

### CashInOutReportTemplate

Cash operation summary structure.

**Field Definitions:**

| Field Name | Type | Description |
|------------|------|-------------|
| amount | float | Total cash operation amount |
| count | integer | Number of cash operations |

### CashReportTemplate

Cash drawer reconciliation structure.

**Field Definitions:**

| Field Name | Type | Description |
|------------|------|-------------|
| logical_amount | float | Calculated expected cash amount |
| physical_amount | float | Actual counted cash amount |
| difference_amount | float | Variance (physical - logical) |
| cash_in | CashInOutReportTemplate | Cash in operations summary |
| cash_out | CashInOutReportTemplate | Cash out operations summary |

## API Request/Response Schemas

All schemas inherit from `BaseSchemaModel` which provides automatic snake_case to camelCase conversion for JSON serialization.

### Request Schemas

#### Report Generation Request (Query Parameters)
Request parameters for generating reports.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| reportScope | string | ✓ | Report scope ('flash' or 'daily') |
| reportType | string | ✓ | Report type ('sales') |
| businessDate | string | ✓ | Business date (YYYYMMDD) |
| openCounter | integer | - | Terminal session counter |
| businessCounter | integer | - | Business counter |
| limit | integer | - | Pagination limit (default: 100) |
| page | integer | - | Page number (default: 1) |
| sort | string | - | Sort criteria (format: "field1:1,field2:-1") |

#### Tenant Creation Request
Request to create tenant database.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| tenantId | string | ✓ | Tenant identifier |

### Response Schemas

#### BaseSalesReportResponse
Sales report response structure.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| tenantId | string | Tenant identifier |
| storeCode | string | Store code |
| terminalNo | integer | Terminal number (null for store-level) |
| businessDate | string | Business date (YYYYMMDD) |
| openCounter | integer | Terminal session counter |
| businessCounter | integer | Business counter |
| salesGross | SalesReportTemplate | Gross sales metrics |
| salesNet | SalesReportTemplate | Net sales metrics |
| discountForLineitems | SalesReportTemplate | Item-level discounts |
| discountForSubtotal | SalesReportTemplate | Transaction-level discounts |
| returns | SalesReportTemplate | Return metrics |
| taxes | array[TaxReportTemplate] | Tax breakdown |
| payments | array[PaymentReportTemplate] | Payment breakdown |
| cash | CashBalanceReportTemplate | Cash reconciliation |
| receiptText | string | Formatted receipt text |
| journalText | string | Formatted journal text |

#### BaseTranResponse
Transaction data response structure.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| tenantId | string | Tenant identifier |
| storeCode | string | Store code |
| terminalNo | integer | Terminal number |
| transactionNo | integer | Transaction number |

#### BaseTenantCreateResponse
Tenant creation response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| tenantId | string | Created tenant identifier |

## Plugin Architecture

### Plugin Interface
```python
class IReportPlugin(ABC):
    @abstractmethod
    async def generate_report(
        self, store_code: str, terminal_no: int, business_counter: int,
        business_date: str, open_counter: int, report_scope: str,
        report_type: str, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> dict[str, any]:
        """Generate report based on specified parameters"""
        pass
```

### Plugin Configuration
Plugins are configured in `plugins.json`:

```json
{
    "report_makers": {
        "sales": {
            "module": "app.services.plugins.sales_report_maker",
            "class": "SalesReportMaker",
            "args": ["<tran_repository>", "<cash_in_out_log_repository>", "<open_close_log_repository>"]
        }
    }
}
```

### Sales Report Plugin
The `SalesReportMaker` plugin implements sophisticated MongoDB aggregation pipelines to:

1. **Aggregate Transaction Data**: Group transactions by type with appropriate factors
   - Normal Sales (101): Factor +1
   - Return Sales (102): Factor -1
   - Void Sales (201): Factor -1
   - Void Return (202): Factor +1

2. **Calculate Sales Metrics**: Process gross/net sales, discounts, taxes, and payments

3. **Integrate Cash Operations**: Combine transaction data with cash in/out operations

4. **Generate Formatted Output**: Create receipt and journal text with proper formatting

## Data Verification System

Before generating daily reports, the service performs comprehensive verification:

### Terminal Status Verification
- All terminals must be properly closed
- Terminal status tracked in DailyInfoDocument
- Verification prevents incomplete daily reports

### Transaction Count Verification
- Transaction count from close logs must match actual logged transactions
- Ensures all transactions are accounted for
- Prevents data loss in reporting

### Cash Operation Verification
- Cash operation count must match expectations
- Validates cash drawer reconciliation accuracy
- Ensures financial integrity

### Event Completeness Verification
- All required event types must be present
- Validates pub/sub message delivery
- Ensures complete data for reporting

## MongoDB Aggregation Pipelines

### Sales Report Aggregation Pipeline

The service uses sophisticated aggregation pipeline for sales calculations:

1. **$match**: Filter by tenant, store, terminal, date, and exclude cancelled transactions
2. **$project**: Calculate discount amounts and extract nested data from arrays
3. **$unwind**: Flatten tax and payment arrays for proper grouping
4. **$group**: Aggregate by transaction type with complex mathematical operations
5. **$sort**: Order results and support pagination
6. **$facet**: Process multiple aggregations in parallel

### Transaction Type Processing
Handles different transaction types with appropriate calculation factors:
- Applies positive/negative factors based on transaction type
- Correctly handles return and void scenarios
- Maintains financial accuracy across all operations

## Event Processing

### Dapr Pub/Sub Integration
Receives events from other services via Dapr pub/sub:

#### Transaction Log Events (`tranlog`)
- Complete transaction data from Cart Service
- Includes line items, payments, taxes, and totals
- Processed for report aggregation

#### Cash Log Events (`cashlog`)
- Cash in/out operations from Terminal Service
- Used for cash drawer reconciliation
- Integrated into daily reports

#### Open/Close Log Events (`opencloselog`)
- Terminal session events from Terminal Service
- Tracks terminal state for verification
- Required for daily report generation

### Idempotent Processing
- Uses Dapr state store for duplicate detection
- Circuit breaker pattern via `StateStoreManager`
- Ensures reliable event processing

## Journal Integration

### Automatic Journal Submission
When reports are requested with API key authentication:
- Reports are automatically sent to Journal Service
- Uses proper transaction typing (FlashReport/DailyReport)
- Provides audit trail for all generated reports
- Includes formatted receipt and journal text

## Multi-Tenancy and Security

### Database Isolation
- Each tenant uses separate database: `db_report_{tenant_id}`
- Complete data isolation between tenants
- Tenant validation on all operations

### Authentication Methods
- **JWT Token**: For administrative access and report management
- **API Key**: For terminal operations and automatic journal submission
- **Service-to-Service**: For journal integration

### Data Protection
- No cross-tenant data access
- Comprehensive audit trails
- Secure event processing

## Performance Considerations

1. **Indexing Strategy**: Optimized compound indexes for report queries and event processing
2. **Aggregation Optimization**: Pipeline stage ordering and index usage for efficiency
3. **Event Processing**: Asynchronous processing with idempotency guarantees
4. **Caching**: Strategic use of aggregation results and state store caching
5. **Pagination**: Efficient pagination support for large report datasets

## Validation Rules

### Report Generation Validation
- Flash reports: No terminal closure requirement
- Daily reports: All terminals must be verified as closed
- Business date must be valid format (YYYYMMDD)
- Report type must have corresponding registered plugin

### Event Processing Validation
- Event IDs must be unique for idempotency
- All monetary amounts must be non-negative
- Timestamps must be valid ISO format
- Terminal references must exist and be valid

### Data Integrity Validation
- Transaction counts must match between different log types
- Cash calculations must balance (opening + operations = expected)
- All required event types must be present for complete reporting

This comprehensive model specification enables the Report Service to provide accurate, reliable business intelligence with extensible plugin architecture and robust data verification mechanisms.