# Journal Service Model Specification

## Overview

Journal Service serves as the electronic journal and transaction log storage system for the Kugel POS platform. It acts as a permanent, searchable record keeper for all POS operations, converting raw transaction data into human-readable journal entries and receipts. The service implements a dual storage pattern, sophisticated event processing with idempotency guarantees, and comprehensive search capabilities for audit compliance. All operations are designed for multi-tenant isolation with enterprise-grade data integrity and regulatory compliance features.

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

### 1. JournalDocument (Primary Journal Storage)

Main document for storing electronic journal entries with searchable, formatted content.

**Collection Name:** `journal`

**Purpose:** Unified storage for all POS operations with searchable, human-readable format

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| terminal_no | integer | ✓ | Terminal number |
| transaction_no | string | - | Transaction number (null for non-sales operations) |
| transaction_type | integer | ✓ | Transaction type code (101=sales, 401=cash-in, etc.) |
| business_date | string | ✓ | Business date (YYYYMMDD format) |
| open_counter | integer | - | Terminal session counter |
| business_counter | integer | - | Daily business operation counter |
| receipt_no | integer | - | Receipt number for sales transactions |
| amount | float | - | Transaction amount (positive/negative based on operation type) |
| quantity | integer | - | Total item quantity for sales transactions |
| staff_id | string | - | Staff identifier who performed the operation |
| user_id | string | - | User identifier (legacy field, typically null) |
| generate_date_time | string | ✓ | Actual timestamp of journal creation (ISO format) |
| journal_text | string | ✓ | Human-readable journal entry for audit display |
| receipt_text | string | - | Formatted receipt content for printing |

**Indexes:**
- Unique compound index: (tenant_id, store_code, terminal_no, transaction_type, generate_date_time)
- Compound index: (tenant_id, store_code, business_date)
- Compound index: (tenant_id, store_code, terminal_no, business_date)
- Index: transaction_type
- Index: receipt_no
- Text index: journal_text (for keyword search)
- Index: generate_date_time

### 2. CashInOutLog (Cash Operation Records)

Document for storing cash movement operation logs from terminal service.

**Collection Name:** `log_cash_in_out`

**Purpose:** Detailed records of non-sales cash movements (float, paid-ins, payouts)

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| store_name | string | - | Store display name |
| terminal_no | integer | ✓ | Terminal number |
| staff_id | string | - | Staff identifier who performed operation |
| staff_name | string | - | Staff display name |
| business_date | string | ✓ | Business date (YYYYMMDD) |
| open_counter | integer | ✓ | Terminal session counter |
| business_counter | integer | ✓ | Business operation counter |
| generate_date_time | string | ✓ | Event timestamp (ISO format) |
| amount | float | ✓ | Operation amount (positive for cash-in, negative for cash-out) |
| description | string | - | Operation reason/description |
| receipt_text | string | - | Formatted receipt text |
| journal_text | string | - | Formatted journal text |

**Indexes:**
- Compound index: (tenant_id, store_code, terminal_no, business_date)
- Index: amount

### 3. OpenCloseLog (Terminal Session Records)

Document for storing terminal open/close operation logs from terminal service.

**Collection Name:** `log_open_close`

**Purpose:** Records of terminal session boundaries with transaction count reconciliation

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| store_name | string | - | Store display name |
| terminal_no | integer | ✓ | Terminal number |
| staff_id | string | - | Staff identifier who performed operation |
| staff_name | string | - | Staff display name |
| business_date | string | ✓ | Business date (YYYYMMDD) |
| open_counter | integer | ✓ | Terminal session counter |
| business_counter | integer | ✓ | Business operation counter |
| operation | string | ✓ | Operation type ('open' or 'close') |
| generate_date_time | string | ✓ | Event timestamp (ISO format) |
| terminal_info | TerminalInfoDocument | - | Complete terminal configuration snapshot |
| cart_transaction_count | integer | - | Number of transactions in session (close only) |
| cart_transaction_last_no | integer | - | Last transaction number (close only) |
| cash_in_out_count | integer | - | Number of cash operations in session (close only) |
| cash_in_out_last_datetime | string | - | Last cash operation timestamp (close only) |
| receipt_text | string | - | Formatted receipt text |
| journal_text | string | - | Formatted journal text |

**Indexes:**
- Compound index: (tenant_id, store_code, terminal_no, business_date, open_counter)
- Index: operation

### 4. Transaction Logs (from kugel_common)

Transaction data references `BaseTransaction` from kugel_common library.

**Collection Name:** `log_tran`

**Purpose:** References to complete transaction records for cross-service validation

**Key Fields Used:**
- Complete transaction record including line items, payments, taxes
- Transaction type codes for proper categorization
- Business date and counter information for session tracking
- Amount and quantity totals for reconciliation

## Transaction Type Intelligence

### Automatic Transaction Type Conversion

The service implements intelligent transaction type processing:

**Sales Transactions:**
- Normal Sales (101) → Cancelled Sales (-101) when `is_cancelled=true`
- Return Sales (102) → Processed with negative factor
- Void Sales (201) → Processed with cancellation logic
- Void Return (202) → Processed with return cancellation logic

**Cash Operations:**
- Cash amount > 0 → Cash-In (401)
- Cash amount < 0 → Cash-Out (402)

**Terminal Operations:**
- Terminal 'open' operation → Open (301)
- Terminal 'close' operation → Close (302)

**Report Operations:**
- Flash reports → Flash Report (701)
- Daily reports → Daily Report (702)

## API Request/Response Schemas

All schemas inherit from `BaseSchemaModel` which provides automatic snake_case to camelCase conversion for JSON serialization.

### Request Schemas

#### CreateJournalRequest

Manual journal entry creation request.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| transactionNo | string | - | Transaction number (optional for non-sales) |
| transactionType | integer | ✓ | Transaction type code |
| businessDate | string | ✓ | Business date (YYYYMMDD) |
| openCounter | integer | - | Terminal session counter |
| businessCounter | integer | - | Business operation counter |
| receiptNo | integer | - | Receipt number |
| amount | float | - | Transaction amount |
| quantity | integer | - | Item quantity |
| staffId | string | - | Staff identifier |
| userId | string | - | User identifier (legacy) |
| journalText | string | ✓ | Human-readable journal entry |
| receiptText | string | - | Formatted receipt text |

#### SearchJournalRequest (Query Parameters)

Journal search parameters with extensive filtering capabilities.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| terminalNo | string | - | Comma-separated terminal numbers |
| transactionType | string | - | Comma-separated transaction type codes |
| businessDateFrom | string | - | Start business date (YYYYMMDD) |
| businessDateTo | string | - | End business date (YYYYMMDD) |
| generateDateFrom | string | - | Start generation date (YYYY-MM-DD) |
| generateDateTo | string | - | End generation date (YYYY-MM-DD) |
| receiptNoFrom | integer | - | Start receipt number |
| receiptNoTo | integer | - | End receipt number |
| keyword | string | - | Keyword search in journal text |
| skip | integer | - | Pagination offset (default: 0) |
| limit | integer | - | Page size (default: 100, max: 100) |
| sort | string | - | Sort criteria (format: "field:direction") |

#### DirectTransactionRequest

Direct transaction submission for legacy compatibility.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| transactionNo | string | ✓ | Transaction number |
| transactionType | integer | ✓ | Transaction type code |
| businessDate | string | ✓ | Business date (YYYYMMDD) |
| openCounter | integer | ✓ | Terminal session counter |
| businessCounter | integer | ✓ | Business operation counter |
| receiptNo | integer | ✓ | Receipt number |
| amount | float | ✓ | Transaction amount |
| quantity | integer | - | Item quantity |
| staffId | string | - | Staff identifier |
| userId | string | - | User identifier |
| receiptText | string | - | Receipt text |
| journalText | string | ✓ | Journal text |

### Response Schemas

#### JournalResponse

Individual journal entry response format.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| journalId | string | Journal entry unique identifier |
| tenantId | string | Tenant identifier |
| storeCode | string | Store code |
| terminalNo | integer | Terminal number |
| transactionNo | string | Transaction number (null for non-sales) |
| transactionType | integer | Transaction type code |
| transactionTypeName | string | Human-readable transaction type |
| businessDate | string | Business date (YYYYMMDD) |
| openCounter | integer | Terminal session counter |
| businessCounter | integer | Business operation counter |
| receiptNo | integer | Receipt number |
| amount | float | Transaction amount |
| quantity | integer | Item quantity |
| staffId | string | Staff identifier |
| userId | string | User identifier |
| generateDateTime | string | Journal creation timestamp |
| journalText | string | Human-readable journal entry |
| receiptText | string | Formatted receipt text |

#### JournalListResponse

Paginated journal search results.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| items | array[JournalResponse] | Journal entries |
| total | integer | Total count matching criteria |
| skip | integer | Pagination offset |
| limit | integer | Page size |

#### EventAcknowledgement

Pub/sub event processing confirmation.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| success | boolean | Processing status |
| eventId | string | Event identifier |
| message | string | Status message |

## Event-Driven Architecture

### Dapr Pub/Sub Integration

The service subscribes to three critical event streams with robust idempotency and error handling:

#### Transaction Log Events (`topic-tranlog`)
- **Source**: Cart Service
- **Endpoint**: `/api/v1/tranlog`
- **Content**: Complete transaction data with line items, payments, taxes
- **Processing**: Creates both transaction log and unified journal entry

#### Cash Log Events (`topic-cashlog`)
- **Source**: Terminal Service  
- **Endpoint**: `/api/v1/cashlog`
- **Content**: Cash in/out operations with amounts and descriptions
- **Processing**: Creates cash operation log and corresponding journal entry

#### Open/Close Log Events (`topic-opencloselog`)
- **Source**: Terminal Service
- **Endpoint**: `/api/v1/opencloselog`
- **Content**: Terminal session events with transaction count reconciliation
- **Processing**: Creates session log and terminal operation journal entry

### Idempotent Event Processing

**Duplicate Prevention Strategy:**
- **State Store Tracking**: Uses Dapr state store to track processed event IDs
- **Unique Event IDs**: Each event must have globally unique identifier
- **Circuit Breaker Pattern**: Handles external service failures gracefully
- **Retry Logic**: Automatic retry for transient failures
- **Health Check Filtering**: Ignores health check events

**Processing Flow:**
1. Receive event via Dapr pub/sub
2. Check Dapr state store for previous processing
3. If not processed, create log entry and journal entry atomically
4. Mark event as processed in state store
5. Send acknowledgement with processing status

### Atomic Transaction Processing

**MongoDB Transaction Pattern:**
```python
async with await self.db.client.start_session() as session:
    async with session.start_transaction():
        # Create specialized log entry (transaction/cash/open-close)
        log_result = await log_collection.insert_one(log_data, session=session)
        
        # Create unified journal entry
        journal_result = await journal_collection.insert_one(journal_data, session=session)
        
        # Mark event as processed
        await state_store.save_state(event_id, processed_data, session=session)
```

## Dual Storage Architecture

### Storage Pattern Rationale

The Journal Service implements a sophisticated dual storage pattern:

**1. Specialized Log Storage**
- Type-specific collections (`log_tran`, `log_cash_in_out`, `log_open_close`)
- Detailed operational data for service-specific processing
- Cross-service validation and reconciliation

**2. Unified Journal Storage**
- Single `journal` collection for all operations
- Standardized searchable format
- Human-readable audit trail

### Benefits of Dual Storage

**Operational Efficiency:**
- Specialized queries on type-specific collections
- Unified search across all operation types
- Optimized indexing strategies per data type

**Data Integrity:**
- Cross-reference validation between log and journal
- Atomic creation ensures consistency
- Comprehensive audit trail preservation

**Search Performance:**
- Journal collection optimized for search operations
- Log collections optimized for operational queries
- Text indexing for keyword search capabilities

## Advanced Search Capabilities

### Search Features

**Multi-Field Filtering:**
- Terminal number ranges
- Transaction type categories
- Business date ranges
- Generation timestamp ranges
- Receipt number ranges

**Text Search:**
- Keyword search within journal text using MongoDB text indexes
- Case-insensitive matching
- Relevance scoring
- Regex pattern support

**Flexible Sorting:**
- Multiple field sorting
- Ascending/descending direction control
- Date-based default sorting

**Pagination Support:**
- Configurable page sizes (max 100)
- Total count metadata
- Efficient skip/limit implementation

### Search Optimization

**Index Strategy:**
- Compound indexes for common query patterns
- Text indexes for full-text search
- Date-based indexes for range queries
- Unique indexes for data integrity

**Performance Considerations:**
- Projection limiting for large datasets
- Index usage optimization
- Query plan analysis and optimization

## Multi-Tenancy and Security

### Database Isolation

**Tenant Separation:**
- Each tenant uses separate database: `db_journal_{tenant_id}`
- Complete data isolation between tenants
- Tenant validation on all operations
- Shard key prefixing with tenant identifier

**Collection Structure Per Tenant:**
Each tenant database contains identical collection structure:
- `journal`: Unified journal entries
- `log_tran`: Transaction logs
- `log_cash_in_out`: Cash operation logs
- `log_open_close`: Terminal session logs

### Authentication and Authorization

**Dual Authentication Support:**
- **JWT Tokens**: Primary authentication for administrative access
- **API Keys**: Terminal operations and legacy compatibility
- **Service-to-Service**: Inter-service communication with service tokens

**Authorization Levels:**
- **Administrative**: Full journal search and management
- **Terminal**: Create journal entries for specific terminal
- **Service**: Inter-service communication for event processing

**Security Validation:**
- Tenant ID path validation
- Terminal access restrictions
- Staff/user authorization checks

### Data Protection

**Audit Compliance:**
- Immutable journal entries (no updates allowed)
- Complete operation history preservation
- Regulatory compliance support
- Tamper-evident record keeping

**Access Control:**
- No cross-tenant data access
- Operation-level authorization
- Comprehensive audit trails
- Secure event processing

## External Service Integration

### Service Communication

**Journal Status Notifications:**
When events are processed, the service sends status callbacks to originating services using:
- **Service-to-Service JWT tokens** for authentication
- **Circuit breaker pattern** for failure resilience
- **HTTP client helper** with retry logic
- **Notification endpoints** in source services

**Notification Content:**
- Event processing status (success/failure)
- Event ID for correlation
- Error details for failed processing
- Timestamp information

### Error Handling and Monitoring

**Exception Hierarchy:**
Structured error codes (410xxx format):
- **410001-410007**: Journal operations
- **410101-410105**: Validation errors
- **411001-411006**: External service issues

**Health Monitoring:**
Multi-component health checks:
- MongoDB connectivity and replica set status
- Dapr sidecar connectivity
- State store availability
- Event processing queue status

**Critical Failure Notification:**
- Slack integration for critical failures
- Detailed error context in notifications
- Service identification and error correlation
- Original transaction data for debugging

## Performance Considerations

### Sharding Strategy

**Intelligent Sharding:**
All documents use composite shard keys:
```
shard_key = tenant_id + store_code + terminal_no + business_date
```

**Benefits:**
- Distributes load across tenant/store/terminal boundaries
- Optimizes queries within business date ranges
- Enables efficient data archival strategies
- Supports horizontal scaling

### Query Optimization

**Index Design:**
- Compound indexes aligned with query patterns
- Text indexes for full-text search requirements
- Date-range indexes for temporal queries
- Unique indexes for data integrity constraints

**Query Performance:**
- Projection optimization for large result sets
- Pagination efficiency with indexed skip/limit
- Sort operation optimization using indexes
- Query plan analysis and monitoring

### Caching Strategy

**State Store Caching:**
- Event processing status caching
- Duplicate prevention with TTL
- Circuit breaker state management
- Performance metrics caching

## Validation Rules

### Journal Entry Validation

**Business Rules:**
- Transaction type must be valid code from enumeration
- Business date must be valid YYYYMMDD format
- Journal text required and non-empty for all entries
- Amount can be negative for returns/voids/cash-out operations
- Receipt numbers must be unique within terminal/business date scope

**Data Consistency:**
- Event IDs must be globally unique
- Timestamps must be valid ISO format
- Required fields validation based on transaction type
- Cross-reference validation between log and journal entries

### Search Request Validation

**Parameter Validation:**
- Date ranges must be logical (end date ≥ start date)
- Terminal numbers must be valid integers
- Transaction types must be valid enumeration values
- Pagination limits enforced (max 100 per page)
- Sort fields must be valid document fields

**Security Validation:**
- Tenant access authorization
- Terminal access restrictions
- Date range limitations for large datasets
- Query complexity limitations

## Data Archival and Lifecycle

### Record Retention

**Immutability Guarantee:**
- Journal entries cannot be modified after creation
- No update operations supported on journal collection
- Audit trail integrity permanently preserved
- Regulatory compliance through immutable records

**Archival Strategy:**
- Business date-based partitioning enables efficient archival
- Configurable retention policies per tenant
- Automated archival to long-term storage
- Compressed storage for historical data

### Data Lifecycle Management

**Active Data:**
- Current and recent business dates in primary collections
- Optimized indexes for operational queries
- Full search capabilities available

**Archived Data:**
- Historical data moved to archive collections
- Read-only access with limited search capabilities
- Compressed storage with extended retention periods
- Compliance-driven retention schedules

This comprehensive model specification demonstrates the Journal Service's role as an enterprise-grade transaction logging system with sophisticated event processing, robust data integrity, comprehensive search capabilities, and regulatory compliance features. The dual storage pattern, idempotent event processing, and multi-tenant architecture provide a scalable, reliable foundation for POS audit trail management.