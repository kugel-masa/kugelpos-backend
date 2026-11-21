# Terminal Service Model Specification

## Overview

This document describes the data model specifications for the Terminal service, including MongoDB collection structures, schema definitions, and data flow.

## Database Design

### Database Name
- `{tenant_id}_terminal` (e.g., `tenant001_terminal`)

### Collections List

| Collection Name | Purpose | Main Data |
|----------------|---------|-----------|
| tenant_info | Tenant information | Basic tenant and store information |
| terminal_info | Terminal information | Terminal details and state management |
| cash_in_out_log | Cash in/out log | Cash operation records |
| open_close_log | Open/close log | Terminal open/close records |
| terminallog_delivery_status | Delivery status | Event delivery tracking |

## Detailed Schema Definitions

### 1. tenant_info Collection

Collection for managing tenant and store information. Stores are saved as embedded documents.

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "tenant_name": "string",
  "stores": [
    {
      "store_code": "string",
      "store_name": "string",
      "status": "string (active/inactive)",
      "business_date": "string (YYYYMMDD)",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 2. terminal_info Collection

Collection for managing terminal detailed information and current state.

```json
{
  "_id": "ObjectId",
  "terminal_id": "string (tenant_id-store_code-terminal_no)",
  "tenant_id": "string",
  "store_code": "string",
  "terminal_no": "integer (1-999)",
  "description": "string",
  "function_mode": "string (MainMenu/Sales/etc)",
  "status": "string (idle/opened/closed)",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "business_counter": "integer",
  "staff": {
    "staff_id": "string",
    "staff_name": "string"
  },
  "initial_amount": "decimal",
  "physical_amount": "decimal",
  "api_key_hash": "string (SHA-256 hex)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Field Descriptions:**
- `terminal_id`: Terminal unique identifier (format: tenant_id-store_code-terminal_no)
- `function_mode`: Current function mode
- `status`: Terminal business state
- `open_counter`: Terminal open count
- `business_counter`: Business operation counter
- `api_key_hash`: SHA-256 digest of the terminal's API key. The key itself is never stored (`api_key` is absent on sealed records)

### 3. cash_in_out_log Collection

Collection for storing cash in/out operation history.

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "cashinout_id": "string",
  "staff_id": "string",
  "staff_name": "string",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "business_counter": "integer",
  "operation_type": "string (cash_in/cash_out)",
  "amount": "decimal",
  "reason": "string",
  "comment": "string",
  "receipt_text": "string",
  "journal_text": "string",
  "generate_date_time": "string (ISO 8601)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 4. open_close_log Collection

Collection for storing terminal open/close operation history.

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "store_code": "string",
  "store_name": "string",
  "terminal_no": "integer",
  "staff_id": "string",
  "staff_name": "string",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "business_counter": "integer",
  "operation": "string (open/close)",
  "generate_date_time": "string (ISO 8601)",
  "terminal_info": {
    "/* Terminal information snapshot */"
  },
  "cart_transaction_count": "integer",
  "cart_transaction_last_no": "integer",
  "cash_in_out_count": "integer",
  "cash_in_out_last_datetime": "string",
  "receipt_text": "string",
  "journal_text": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 5. terminallog_delivery_status Collection

Collection for tracking event delivery status.

```json
{
  "_id": "ObjectId",
  "event_id": "string (UUID)",
  "published_at": "datetime",
  "status": "string (published/delivered/failed)",
  "tenant_id": "string",
  "store_code": "string",
  "terminal_no": "integer",
  "business_date": "string (YYYYMMDD)",
  "open_counter": "integer",
  "payload": {
    "/* Event payload */"
  },
  "services": [
    {
      "service_name": "string",
      "delivered": "boolean",
      "delivered_at": "datetime"
    }
  ],
  "last_updated_at": "datetime",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## Index Definitions

### tenant_info
- Unique index: `tenant_id`

### terminal_info
- Unique index: `terminal_id`
- Compound index: `tenant_id + store_code + terminal_no`
- Single index: `api_key_hash` (partial: only where it is a string)

### cash_in_out_log
- Compound index: `tenant_id + store_code + terminal_no + business_date`
- Single index: `generate_date_time`

### open_close_log
- Unique compound index: `tenant_id + store_code + terminal_no + business_counter + operation` (one open and one close per business; `business_counter` is carried across a terminal re-registration and never reused. The previous key `business_date + open_counter + operation` is replaced on `POST /api/v1/tenants`)
- Single index: `generate_date_time`

### terminallog_delivery_status
- Unique index: `event_id`
- Compound index: `tenant_id + status + published_at`

## Enumeration Definitions

### Terminal Status (TerminalStatus)
- `idle`: Initial state, before business start
- `opened`: In business (opened)
- `closed`: Business ended (closed)

### Function Mode (FunctionMode)
- `MainMenu`: Main menu
- `OpenTerminal`: Terminal opening
- `Sales`: Sales processing
- `Returns`: Return processing
- `Void`: Void processing
- `Reports`: Report display
- `CloseTerminal`: Terminal closing
- `Journal`: Journal display
- `Maintenance`: Maintenance
- `CashInOut`: Cash in/out

### Store Status (StoreStatus)
- `active`: In business
- `inactive`: Not in business

### Delivery Status (DeliveryStatus)
- `published`: Event published
- `delivered`: Delivery completed
- `partially_delivered`: Partial delivery
- `failed`: Delivery failed

## Data Flow

### Terminal Lifecycle
1. **Terminal Creation**: Create with tenant, store, and terminal number specified
2. **API Key Generation**: Auto-generated; only its digest is stored, and the key is returned once in the creation response
3. **Staff Sign-in**: Associate staff information with terminal
4. **Opening Process**: Start business, set initial cash
5. **Daily Operations**: Cash in/out, sales processing
6. **Closing Process**: End business, confirm cash
7. **Business Date Update**: Switch to next business day

### Event Delivery Flow
1. **Event Generation**: Generate events during open/close and cash operations
2. **Dapr Pub/Sub**: Publish events asynchronously
3. **Delivery Tracking**: Manage delivery status with delivery_status
4. **Retry Control**: Background retry for undelivered events

### Multi-tenant Structure
```
Tenant
├── Store (embedded)
└── Terminal (separate collection)
    ├── Cash in/out log
    └── Open/close log
```

## Security

### API Key Management
- 32-byte secure random generation (`secrets.token_urlsafe(32)`)
- Stored only as its SHA-256 digest in `api_key_hash`, and verified against it in constant time. A random 256-bit key needs no slow hash, and an unsalted digest can still be looked up by index (`POST /auth/token` without a `terminal_id`)
- Readable only in the response that issues it: `POST /terminals` and `POST /terminals/{terminal_id}/api-key`. `GET /terminals/{terminal_id}` always returns it masked; its `include_api_key` parameter is deprecated and ignored
- A lost or exposed key is replaced, not retrieved: `POST /terminals/{terminal_id}/api-key` (user JWT only) issues a new key and invalidates the previous one at once. Terminal JWTs already obtained with the previous key are not revoked: each service verifies them on its own, so they stay valid until they expire (`TERMINAL_TOKEN_EXPIRE_HOURS`, 24 hours by default)
- Records written before the digest existed hold the key in plaintext in `api_key`. They keep working and are sealed (digest written, plaintext removed) the first time the key is verified, and by tenant setup, which also runs for existing tenants at startup
- Sealing is one-way: a terminal service from before the digest cannot verify a sealed key, and its writes drop `api_key_hash`, leaving the terminal without a credential. Do not run an older terminal revision beside a newer one; switch revisions instead. To keep a rollback open, set `SEAL_LEGACY_TERMINAL_API_KEYS=false` (keys are still verified, and existing records stay as they are) and turn it on once the older revision is gone. It is `true` by default, so a deployment that does not set it seals every existing key at its first startup and cannot be rolled back for them
- Even with sealing off, a terminal created, or whose key was reissued, after the upgrade holds only a digest. After a rollback it cannot authenticate, and the older revision has no way to issue it a key: roll forward again, or delete and recreate the terminal (its counters and state are lost)
- The credential changes only through creation, reissue and sealing. The writes of sign-in, sign-out, open and close leave `api_key` and `api_key_hash` out, so they cannot undo a reissue that ran while they were in progress
- The terminal service's own calls to other services carry a short-lived terminal JWT it mints, not the API key

### Data Isolation
- Database isolation per tenant
- Tenant ID validation for all operations
- Prevention of cross-tenant access

## Special Notes

1. **Terminal ID Format**: Unified format `{tenant_id}-{store_code}-{terminal_no}`
2. **Store Code Normalization**: Automatic conversion to uppercase (store001 → STORE001)
3. **Background Jobs**: Periodic retry processing for undelivered events
4. **Audit Trail**: All operations recorded with timestamps
5. **Circuit Breaker**: Failure handling for external service calls
6. **Event-driven**: Loosely coupled integration via Dapr pub/sub