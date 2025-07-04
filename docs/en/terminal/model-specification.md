# Terminal Service Model Specification

## Overview

Terminal Service manages the data models for POS terminals, stores, and cash operations in the Kugelpos POS system. The service handles terminal lifecycle management, staff authentication, business session control, and maintains comprehensive audit trails through various log collections.

## Database Document Models

### 1. TenantInfoDocument (Tenant Information)

Main document for storing tenant and embedded store information.

**Collection Name:** `info_tenant`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Unique identifier for the tenant |
| tenant_name | string | ✓ | Display name of the tenant |
| stores | array[StoreInfo] | ✓ | List of stores belonging to this tenant |
| tags | array[string] | - | Additional tags for categorization |
| _id | ObjectId | ✓ | MongoDB document ID (inherited) |
| entry_datetime | datetime | ✓ | Document creation timestamp (inherited) |
| last_update_datetime | datetime | - | Last update timestamp (inherited) |
| shard_key | string | ✓ | Sharding key (inherited) |

**Indexes:**
- Unique index: tenant_id
- Index: tags

### 2. StoreInfo (Store Information - Embedded)

Embedded document within TenantInfoDocument representing individual stores.

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| store_code | string | ✓ | Unique store code within tenant |
| store_name | string | ✓ | Display name of the store |
| status | string | - | Store status (Active/Inactive) |
| business_date | string | - | Current business date (YYYYMMDD) |
| tags | array[string] | - | Additional tags for categorization |
| created_at | datetime | ✓ | Store creation timestamp |
| updated_at | datetime | - | Last update timestamp |

### 3. TerminalInfoDocument (Terminal Information)

Document for storing individual terminal information. This model is defined in the commons library and shared across services.

**Collection Name:** `info_terminal`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| terminal_id | string | ✓ | Unique ID: {tenant_id}-{store_code}-{terminal_no} |
| tenant_id | string | ✓ | Tenant that owns this terminal |
| store_code | string | ✓ | Store where terminal is located |
| terminal_no | integer | ✓ | Terminal number within store (1-999) |
| description | string | - | Terminal description |
| function_mode | string | ✓ | Current function mode |
| status | string | ✓ | Terminal status (Idle/Opened/Closed) |
| business_date | string | - | Current business date (YYYYMMDD) |
| open_counter | integer | ✓ | Terminal open session counter |
| business_counter | integer | ✓ | Business operation counter |
| staff | StaffMasterDocument | - | Currently signed-in staff |
| initial_amount | float | - | Initial cash amount |
| physical_amount | float | - | Physical cash count |
| api_key | string | ✓ | API key for authentication |
| tags | array[string] | - | Additional tags |
| _id | ObjectId | ✓ | MongoDB document ID (inherited) |
| entry_datetime | datetime | ✓ | Creation timestamp (inherited) |
| last_update_datetime | datetime | - | Update timestamp (inherited) |
| shard_key | string | ✓ | Sharding key (inherited) |

**Indexes:**
- Unique index: terminal_id
- Compound index: (tenant_id, store_code, terminal_no)
- Index: api_key

### 4. CashInOutLog (Cash Transaction Log)

Document for recording cash drawer transactions.

**Collection Name:** `log_cash_in_out`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| store_name | string | ✓ | Store name for display |
| terminal_no | integer | ✓ | Terminal number |
| staff_id | string | ✓ | Staff who performed transaction |
| staff_name | string | ✓ | Staff name for display |
| business_date | string | ✓ | Business date (YYYYMMDD) |
| open_counter | integer | ✓ | Terminal open counter |
| business_counter | integer | ✓ | Business counter |
| generate_date_time | string | ✓ | Transaction timestamp |
| amount | float | ✓ | Amount (positive=in, negative=out) |
| description | string | - | Transaction description |
| receipt_text | string | ✓ | Formatted receipt text |
| journal_text | string | ✓ | Formatted journal text |
| _id | ObjectId | ✓ | MongoDB document ID (inherited) |
| entry_datetime | datetime | ✓ | Creation timestamp (inherited) |
| last_update_datetime | datetime | - | Update timestamp (inherited) |
| shard_key | string | ✓ | Sharding key (inherited) |

**Indexes:**
- Compound index: (tenant_id, store_code, terminal_no, business_date)
- Index: generate_date_time

### 5. OpenCloseLog (Terminal Session Log)

Document for recording terminal open/close operations.

**Collection Name:** `log_open_close`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| store_name | string | ✓ | Store name for display |
| terminal_no | integer | ✓ | Terminal number |
| staff_id | string | ✓ | Staff who performed operation |
| staff_name | string | ✓ | Staff name for display |
| business_date | string | ✓ | Business date (YYYYMMDD) |
| open_counter | integer | ✓ | Terminal open counter |
| business_counter | integer | ✓ | Business counter |
| operation | string | ✓ | Operation type: 'open' or 'close' |
| generate_date_time | string | ✓ | Operation timestamp |
| terminal_info | TerminalInfoDocument | ✓ | Terminal state snapshot |
| cart_transaction_count | integer | ✓ | Number of transactions in session |
| cart_transaction_last_no | integer | - | Last transaction number |
| cash_in_out_count | integer | ✓ | Number of cash operations |
| cash_in_out_last_datetime | string | - | Last cash operation timestamp |
| receipt_text | string | ✓ | Formatted receipt text |
| journal_text | string | ✓ | Formatted journal text |
| _id | ObjectId | ✓ | MongoDB document ID (inherited) |
| entry_datetime | datetime | ✓ | Creation timestamp (inherited) |
| last_update_datetime | datetime | - | Update timestamp (inherited) |
| shard_key | string | ✓ | Sharding key (inherited) |

**Indexes:**
- Compound index: (tenant_id, store_code, terminal_no, business_date, operation)
- Index: generate_date_time

### 6. TerminallogDeliveryStatus (Event Delivery Tracking)

Document for tracking pub/sub event delivery status.

**Collection Name:** `status_terminal_delivery`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| event_id | string | ✓ | Event UUID |
| published_at | datetime | ✓ | Event publication timestamp |
| status | string | ✓ | Delivery status |
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| terminal_no | integer | ✓ | Terminal number |
| business_date | string | ✓ | Business date (YYYYMMDD) |
| open_counter | integer | ✓ | Terminal open counter |
| payload | object | ✓ | Event message body |
| services | array[ServiceStatus] | ✓ | Service delivery statuses |
| last_updated_at | datetime | ✓ | Last update timestamp |
| _id | ObjectId | ✓ | MongoDB document ID (inherited) |
| entry_datetime | datetime | ✓ | Creation timestamp (inherited) |
| last_update_datetime | datetime | - | Update timestamp (inherited) |
| shard_key | string | ✓ | Sharding key (inherited) |

## API Request/Response Schemas

All schemas inherit from `BaseSchemmaModel` which automatically converts field names from snake_case to camelCase for JSON serialization.

### Terminal Management Schemas

#### TerminalCreateRequest
Request to create a new terminal.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| storeCode | string | ✓ | Store code where terminal will be created |
| terminalNo | integer | ✓ | Terminal number (1-999) |
| description | string | ✓ | Terminal description |

#### TerminalUpdateRequest
Request to update terminal information.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| description | string | ✓ | New terminal description |

#### Terminal (Response)
Terminal information response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| terminalId | string | Unique terminal identifier |
| tenantId | string | Tenant identifier |
| storeCode | string | Store code |
| terminalNo | integer | Terminal number |
| description | string | Terminal description |
| functionMode | string | Current function mode |
| status | string | Terminal status |
| businessDate | string | Current business date |
| openCounter | integer | Open session counter |
| businessCounter | integer | Business counter |
| initialAmount | float | Initial cash amount |
| physicalAmount | float | Physical cash count |
| staff | object | Signed-in staff info |
| apiKey | string | Terminal API key |
| entryDatetime | string | Creation timestamp |
| lastUpdateDatetime | string | Update timestamp |

### Terminal Operation Schemas

#### TerminalSignInRequest
Request for staff sign-in.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| staffId | string | ✓ | Staff identifier |

#### TerminalOpenRequest
Request to open terminal for business.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| initialAmount | float | ✓ | Initial cash drawer amount |

#### TerminalOpenResponse
Response after terminal open.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| terminalId | string | Terminal identifier |
| businessDate | string | Assigned business date |
| openCounter | integer | Open session counter |
| businessCounter | integer | Business counter |
| initialAmount | float | Initial cash amount |
| terminalInfo | object | Full terminal information |
| receiptText | string | Formatted receipt text |
| journalText | string | Formatted journal text |

#### TerminalCloseRequest
Request to close terminal.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| physicalAmount | float | ✓ | Counted cash amount |

#### TerminalCloseResponse
Response after terminal close.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| terminalId | string | Terminal identifier |
| businessDate | string | Business date |
| openCounter | integer | Open session counter |
| businessCounter | integer | Business counter |
| physicalAmount | float | Final cash amount |
| terminalInfo | object | Full terminal information |
| receiptText | string | Formatted receipt text |
| journalText | string | Formatted journal text |

### Cash Operation Schemas

#### CashInOutRequest
Request for cash drawer operations.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| amount | float | ✓ | Amount (positive=in, negative=out) |
| description | string | - | Operation description |

#### CashInOutResponse
Response after cash operation.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| terminalId | string | Terminal identifier |
| amount | float | Transaction amount |
| description | string | Operation description |
| receiptText | string | Formatted receipt text |
| journalText | string | Formatted journal text |

## Enumerations

### Terminal Status
- `Idle` - Terminal not opened for business
- `Opened` - Terminal active and ready
- `Closed` - Terminal closed for the day

### Function Modes
- `MainMenu` - Default display mode
- `OpenTerminal` - Terminal opening operations
- `Sales` - Sales transaction processing
- `Returns` - Return transaction processing
- `Void` - Transaction voiding
- `Reports` - Report generation
- `CloseTerminal` - Terminal closing operations
- `Journal` - Transaction history viewing
- `Maintenance` - System maintenance
- `CashInOut` - Cash drawer operations

### Store Status
- `Active` - Store is operational
- `Inactive` - Store is not operational

### Delivery Status
- `published` - Event published to pub/sub
- `delivered` - All services received event
- `partially_delivered` - Some services received event
- `failed` - Delivery failed

## Data Flow and Relationships

### 1. Terminal Lifecycle
```
Terminal Creation → API Key Generation → Staff Sign-in → Terminal Open
    ↓
Daily Operations (Sales, Cash In/Out) → Terminal Close → New Business Date
```

### 2. Multi-tenancy Structure
```
Tenant
  └── Stores (embedded)
        └── Terminals (separate collection)
              └── Transaction Logs
```

### 3. Event Publishing Flow
```
Terminal Operation → Generate Log → Publish to Dapr → Track Delivery Status
```

## Security Features

1. **API Key Management**: 
   - Generated using `secrets.token_urlsafe(32)`
   - Stored securely in terminal document
   - Used for terminal authentication

2. **Multi-tenant Isolation**:
   - Separate databases per tenant
   - Database name format: `{DB_NAME_PREFIX}_{tenant_id}`
   - Tenant ID validation on all operations

3. **Audit Trail**:
   - All operations logged with timestamps
   - Staff identification on all transactions
   - Immutable log entries

## Performance Considerations

1. **Embedded Documents**: Stores are embedded within tenant documents to reduce queries
2. **Indexes**: Optimized for common query patterns (by terminal, by date, by status)
3. **Sharding**: Support for horizontal scaling via shard_key
4. **Event Delivery**: Asynchronous pub/sub for scalability