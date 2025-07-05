# Journal Service Model Specification

## Overview

The Journal service is the electronic journal and transaction log management system for the Kugelpos POS system. It manages persistent, searchable records of all POS operations (transactions, cash operations, terminal open/close) to meet audit and compliance requirements. It implements event-driven architecture, idempotency guarantees, and multi-tenant isolation.

## Database Document Models

All document models inherit from `BaseDocumentModel`.

### 1. JournalDocument (Unified Journal Storage)

Main document storing unified journal entries for all POS operations.

**Collection Name:** `journal`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| terminal_no | integer | ✓ | Terminal number |
| transaction_no | string | - | Transaction number (for sales transactions) |
| transaction_type | integer | ✓ | Transaction type code |
| business_date | string | ✓ | Business date (YYYYMMDD format) |
| open_counter | integer | - | Terminal session counter |
| business_counter | integer | - | Business operation counter |
| receipt_no | integer | - | Receipt number |
| amount | float | - | Amount (positive/negative) |
| quantity | float | - | Total quantity |
| staff_id | string | - | Staff identifier |
| user_id | string | - | User identifier |
| generate_date_time | datetime | ✓ | Generation date/time |
| journal_text | string | ✓ | Human-readable journal text |
| receipt_text | string | - | Formatted receipt text |

**Indexes:**
- Unique compound: (tenant_id, store_code, terminal_no, transaction_type, generate_date_time)
- Compound: (tenant_id, store_code, business_date)
- Compound: (tenant_id, store_code, terminal_no, business_date)
- transaction_type
- receipt_no
- journal_text (text)
- generate_date_time

### 2. CashInOutLog (Cash Operation Records)

Document storing detailed logs of cash in/out operations.

**Collection Name:** `log_cash_in_out`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| store_name | string | - | Store name |
| terminal_no | integer | ✓ | Terminal number |
| staff_id | string | - | Staff identifier |
| staff_name | string | - | Staff name |
| business_date | string | ✓ | Business date (YYYYMMDD) |
| open_counter | integer | ✓ | Session counter |
| business_counter | integer | ✓ | Business counter |
| generate_date_time | datetime | ✓ | Operation date/time |
| amount | float | ✓ | Amount (positive: cash in, negative: cash out) |
| description | string | - | Operation reason/description |
| receipt_text | string | - | Receipt text |
| journal_text | string | - | Journal text |

**Indexes:**
- Compound: (tenant_id, store_code, terminal_no, business_date)
- amount

### 3. OpenCloseLog (Terminal Open/Close Records)

Document storing terminal open/close operation logs.

**Collection Name:** `log_open_close`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| store_name | string | - | Store name |
| terminal_no | integer | ✓ | Terminal number |
| staff_id | string | - | Staff identifier |
| staff_name | string | - | Staff name |
| business_date | string | ✓ | Business date (YYYYMMDD) |
| open_counter | integer | ✓ | Session counter |
| business_counter | integer | ✓ | Business counter |
| operation | string | ✓ | Operation type ('open'/'close') |
| generate_date_time | datetime | ✓ | Operation date/time |
| terminal_info | TerminalInfoDocument | - | Terminal information snapshot |
| cart_transaction_count | integer | - | Transaction count (at close) |
| cart_transaction_last_no | integer | - | Last transaction number (at close) |
| cash_in_out_count | integer | - | Cash operation count (at close) |
| cash_in_out_last_datetime | datetime | - | Last cash operation date/time (at close) |
| receipt_text | string | - | Receipt text |
| journal_text | string | - | Journal text |

**Indexes:**
- Compound: (tenant_id, store_code, terminal_no, business_date, open_counter)
- operation

### 4. TranlogDocument (Transaction Logs)

Document storing complete transaction data from Cart service.

**Collection Name:** `log_tran`

**Inheritance:** References `BaseTransaction` structure from kugel_common

**Key Fields:**
- Complete transaction data including line items, payments, and tax information
- Transaction type codes
- Business date and counter information
- Amount and quantity totals

## Transaction Type Definitions

| Code | Description | Source |
|------|------|--------|
| 101 | Standard sale | Cart service |
| -101 | Standard sale cancellation | Cart service |
| 102 | Return sale | Cart service |
| 201 | Sale void | Cart service |
| 202 | Return void | Cart service |
| 301 | Cash drawer open | Terminal service |
| 302 | Cash drawer close | Terminal service |
| 401 | Cash in | Terminal service |
| 402 | Cash out | Terminal service |
| 501 | Sales report | Report service |
| 502 | Other report | Report service |

## API Request/Response Schemas

All schemas inherit from `BaseSchemaModel` and provide automatic conversion from snake_case to camelCase.

### Request Schemas

#### CreateJournalRequest
For manual journal entry creation.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| transactionNo | string | - | Transaction number |
| transactionType | integer | ✓ | Transaction type code |
| businessDate | string | ✓ | Business date (YYYY-MM-DD) |
| openCounter | integer | - | Session counter |
| businessCounter | integer | - | Business counter |
| receiptNo | string | - | Receipt number |
| amount | float | - | Amount |
| quantity | float | - | Quantity |
| staffId | string | - | Staff ID |
| userId | string | - | User ID |
| journalText | string | ✓ | Journal text |
| receiptText | string | - | Receipt text |

#### SearchJournalRequest (Query Parameters)
Parameters for journal search.

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| terminals | string | - | Terminal numbers (comma-separated) |
| transaction_types | string | - | Transaction types (comma-separated) |
| business_date_from | string | - | Start business date (YYYY-MM-DD) |
| business_date_to | string | - | End business date (YYYY-MM-DD) |
| generate_date_time_from | string | - | Start generation date/time (YYYYMMDDTHHMMSS) |
| generate_date_time_to | string | - | End generation date/time (YYYYMMDDTHHMMSS) |
| receipt_no_from | string | - | Start receipt number |
| receipt_no_to | string | - | End receipt number |
| keywords | string | - | Keyword search (comma-separated) |
| page | integer | - | Page number (default: 1) |
| limit | integer | - | Page size (default: 100, max: 1000) |
| sort | string | - | Sort conditions (e.g., "generateDateTime:-1") |

### Response Schemas

#### JournalResponse
Individual journal entry response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| journalId | string | Journal ID |
| tenantId | string | Tenant ID |
| storeCode | string | Store code |
| terminalNo | integer | Terminal number |
| transactionNo | string | Transaction number |
| transactionType | integer | Transaction type code |
| transactionTypeName | string | Transaction type name |
| businessDate | string | Business date |
| openCounter | integer | Session counter |
| businessCounter | integer | Business counter |
| receiptNo | string | Receipt number |
| amount | float | Amount |
| quantity | float | Quantity |
| staffId | string | Staff ID |
| userId | string | User ID |
| generateDateTime | string | Generation date/time |
| journalText | string | Journal text |
| receiptText | string | Receipt text |

## Event-Driven Architecture

### Dapr Pub/Sub Topics

#### tranlog_report
- **Source:** Cart service
- **Endpoint:** `/api/v1/tranlog`
- **Content:** Complete transaction data
- **Processing:** Creates transaction log and journal entry

#### cashlog_report
- **Source:** Terminal service
- **Endpoint:** `/api/v1/cashlog`
- **Content:** Cash in/out operation data
- **Processing:** Creates cash log and journal entry

#### opencloselog_report
- **Source:** Terminal service
- **Endpoint:** `/api/v1/opencloselog`
- **Content:** Terminal open/close operation data
- **Processing:** Creates open/close log and journal entry

### Idempotency Processing

1. **Event ID Management:** Records processed event IDs in Dapr State Store
2. **Duplicate Prevention:** Prevents reprocessing of same event ID
3. **Atomicity Guarantee:** MongoDB transactions ensure writes to multiple collections
4. **Circuit Breaker:** Automatic recovery during external service failures

## Multi-Tenant Implementation

### Database Isolation
- **Database Name:** `db_journal_{tenant_id}`
- **Tenant Validation:** Tenant ID validation for all operations
- **Data Access:** Cross-tenant data access is not possible

### Authentication & Authorization
- **JWT Authentication:** For search and inquiry by administrators
- **API Key Authentication:** For journal creation from terminals
- **Inter-service Authentication:** Dedicated tokens for event processing

## Data Retention and Archiving

### Immutability Guarantee
- Journal entries cannot be modified after creation
- Update and delete operations are not supported
- Guarantees audit trail integrity

### Archiving Strategy
- Business date-based partitioning
- Configurable retention policies per tenant
- Long-term storage according to regulatory requirements

## Search Functionality

### Search Criteria
- Terminal number range
- Transaction types
- Business date range
- Generation date/time range
- Receipt number range
- Keyword search (within journal_text)

### Performance Optimization
- Query optimization through compound indexes
- Full-text search through text indexes
- Large data handling through pagination
- Flexible sort condition specification

## Error Handling

### Error Code System
Journal service uses error codes in the 50XXX range:
- 50001-50099: General journal operation errors
- 50101-50199: Validation errors
- 50201-50299: External service communication errors

### Failure Notification
- Slack notifications for critical errors
- Automatic failure isolation through Circuit Breaker
- Detailed error context recording