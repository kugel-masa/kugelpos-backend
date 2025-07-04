# Cart Service Model Specification

## Overview

Cart Service manages shopping cart operations and transaction processing for the Kugelpos POS system. It implements a sophisticated state machine for cart lifecycle management, dual storage strategy with circuit breaker patterns, plugin architecture for payments and promotions, and event-driven communication. The service provides multi-tenant isolation with comprehensive transaction integrity and audit trails.

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

### 1. CartDocument (Active Shopping Carts)

Document for storing active shopping carts with state machine management.

**Collection Name:** `cache_cart`

**Inheritance:** Extends `BaseTransaction` from kugel_common

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| cart_id | string | - | Unique UUID cart identifier |
| status | string | - | Cart state (Initial/Idle/EnteringItem/Paying/Completed/Cancelled) |
| subtotal_amount | float | - | Sum before tax and discounts |
| balance_amount | float | - | Final amount after all calculations |
| line_items | array[CartLineItem] | - | Shopping cart items |
| masters | ReferenceMasters | - | Embedded reference data cache |

**CartLineItem Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| item_details | dict | - | Additional item information |
| image_urls | array[string] | - | Product image URLs |
| is_discount_restricted | boolean | - | Discount eligibility flag |

**ReferenceMasters Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| items | array[ItemMasterDocument] | - | Product catalog cache |
| taxes | array[TaxMasterDocument] | - | Tax rules cache |
| settings | array[SettingsMasterDocument] | - | System settings cache |

**Indexes:**
- Unique index: cart_id
- Compound index: (tenant_id, store_code, terminal_no)
- Index: status

### 2. TranlogDocument (Transaction History)

Document for storing completed transaction records.

**Collection Name:** `log_tran`

**Inheritance:** Extends `BaseTransaction` from kugel_common

**Additional Fields:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| invoice_issue_no | string | - | Invoice number reference |

**Purpose:** Permanent record of completed transactions for audit and reporting

**Indexes:**
- Compound index: (tenant_id, store_code, terminal_no, business_date, transaction_no)
- Index: invoice_issue_no

### 3. TransactionStatusDocument (Transaction Status Tracking)

Document for tracking void and return operations.

**Collection Name:** `status_tran`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| store_code | string | - | Store code |
| terminal_no | integer | - | Terminal number |
| transaction_no | string | - | Transaction number |
| is_voided | boolean | - | Void status flag |
| is_refunded | boolean | - | Return status flag |
| void_transaction_no | string | - | Voiding transaction number |
| void_date_time | datetime | - | Void operation timestamp |
| void_staff_id | string | - | Staff who voided transaction |
| return_transaction_no | string | - | Return transaction number |
| return_date_time | datetime | - | Return operation timestamp |
| return_staff_id | string | - | Staff who processed return |

**Indexes:**
- Unique index: (tenant_id, store_code, terminal_no, transaction_no)
- Index: is_voided
- Index: is_refunded

### 4. TerminalCounterDocument (Terminal Sequence Generators)

Document for managing terminal-specific sequence counters.

**Collection Name:** `info_terminal_counter`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| terminal_id | string | - | Terminal identifier |
| count_dic | dict | - | Dictionary of counter names and current values |

**Counter Types:**
- transaction_no: Transaction sequence counter
- receipt_no: Receipt sequence counter
- business_counter: Business operation counter

**Indexes:**
- Unique index: terminal_id

### 5. TranlogDeliveryStatus (Message Delivery Tracking)

Document for tracking pub/sub message delivery status.

**Collection Name:** `status_tran_delivery`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| event_id | string | - | UUID for message tracking |
| published_at | datetime | - | Publication timestamp |
| status | string | - | Overall delivery status |
| payload | dict | - | Original message content |
| services | array[ServiceStatus] | - | Per-service delivery status |

**ServiceStatus Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| service_name | string | ✓ | Target service name |
| status | string | ✓ | Delivery status (pending/delivered/failed) |
| delivered_at | datetime | - | Delivery timestamp |
| error_message | string | - | Error details if failed |

**Indexes:**
- Unique index: event_id
- Index: status
- Index: published_at

### 6. BaseTransaction Structure (Inherited by Cart & Tranlog)

Base structure inherited by both CartDocument and TranlogDocument.

**Core Transaction Fields:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| store_code | string | - | Store code |
| terminal_no | integer | - | Terminal number |
| transaction_no | string | - | Sequential transaction number |
| business_date | string | - | Business date (YYYYMMDD) |
| user | UserInfoDocument | - | User information |
| staff | Staff | - | Staff information nested class |
| sales | SalesInfo | - | Sales summary nested class |
| line_items | array[LineItem] | - | Transaction line items |
| payments | array[Payment] | - | Payment records |
| taxes | array[Tax] | - | Tax calculations |
| subtotal_discounts | array[DiscountInfo] | - | Cart-level discounts |
| is_voided | boolean | - | Void status flag |
| is_refunded | boolean | - | Return status flag |
| receipt_text | string | - | Formatted receipt text |
| journal_text | string | - | Formatted journal text |

## API Request/Response Schemas

All schemas inherit from `BaseSchemaModel` which provides automatic snake_case to camelCase conversion for JSON serialization.

### Cart Management Schemas

#### CartCreateRequest
Request to create a new shopping cart.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| transactionType | integer | ✓ | Transaction type code |
| userId | string | - | User identifier |
| userName | string | - | User display name |

#### CartCreateResponse
Response with new cart identifier.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| cartId | string | Unique cart identifier |

#### CartDeleteResponse
Response for cart deletion.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| message | string | Deletion confirmation message |

### Item Management Schemas

#### Item
Item information for cart operations.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| itemCode | string | ✓ | Product item code |
| quantity | float | ✓ | Item quantity |
| unitPrice | float | - | Unit price override |

#### ItemQuantityUpdateRequest
Request to update item quantity.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| quantity | float | ✓ | New quantity value |

#### ItemUnitPriceUpdateRequest
Request to update item unit price.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| unitPrice | float | ✓ | New unit price |

### Payment Processing Schemas

#### PaymentRequest
Request to process payment.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| paymentCode | string | ✓ | Payment method code |
| amount | integer | ✓ | Payment amount in smallest currency unit |
| detail | string | - | Payment details or reference |

### Transaction Representation Schemas

#### Cart (Response)
Complete cart information response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| cartId | string | Cart identifier |
| cartStatus | string | Current cart state |
| subtotalAmount | float | Amount before tax and discounts |
| balanceAmount | float | Final amount after calculations |
| lineItems | array[TranLineItem] | Cart items |
| payments | array[TranPayment] | Payment records |
| taxes | array[TranTax] | Tax calculations |

#### Tran (Response)
Full transaction record response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| transactionNo | string | Transaction number |
| businessDate | string | Business date (YYYYMMDD) |
| totalAmount | float | Final transaction total |
| lineItems | array[TranLineItem] | Transaction items |
| payments | array[TranPayment] | Payment records |
| taxes | array[TranTax] | Tax calculations |

#### TranLineItem (Response)
Transaction line item details.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| lineNo | integer | Line sequence number |
| itemCode | string | Product code |
| description | string | Item description |
| quantity | float | Item quantity |
| unitPrice | float | Unit price |
| amount | float | Line total amount |
| discountAmount | float | Line discount total |
| taxAmount | float | Line tax amount |

#### TranPayment (Response)
Transaction payment details.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| paymentNo | integer | Payment sequence number |
| paymentCode | string | Payment method code |
| amount | float | Payment amount |
| detail | string | Payment details |

#### TranTax (Response)
Transaction tax details.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| taxCode | string | Tax rule code |
| taxName | string | Tax display name |
| rate | float | Tax rate |
| targetAmount | float | Amount subject to tax |
| taxAmount | float | Calculated tax amount |

### Delivery Status Management Schemas

#### DeliveryStatusUpdateRequest
Request to update message delivery status.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| eventId | string | ✓ | Event identifier |
| service | string | ✓ | Service name |
| status | string | ✓ | Delivery status |
| message | string | - | Status message |

#### DeliveryStatusUpdateResponse
Response for delivery status update.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| success | boolean | Update success flag |
| message | string | Response message |

## State Machine Pattern

### Cart States and Transitions

**Cart States:**
1. **Initial** - Cart created, no operations allowed
2. **Idle** - Empty cart, ready for items
3. **EnteringItem** - Has items, can modify cart
4. **Paying** - Processing payment, limited operations
5. **Completed** - Transaction finalized (terminal state)
6. **Cancelled** - Cart abandoned (terminal state)

**Valid Transitions:**
- Initial → Idle
- Idle → EnteringItem (add first item)
- Idle → Cancelled
- EnteringItem → Paying (start payment)
- EnteringItem → Cancelled
- Paying → EnteringItem (resume item entry)
- Paying → Completed (finalize transaction)

**State Manager:** `CartStateManager` controls allowed operations per state

### State-Specific Operations

**Initial State:**
- No operations allowed
- Automatic transition to Idle

**Idle State:**
- Add first item (→ EnteringItem)
- Cancel cart (→ Cancelled)

**EnteringItem State:**
- Add/modify/remove items
- Apply discounts
- Start payment process (→ Paying)
- Cancel cart (→ Cancelled)

**Paying State:**
- Process payments
- Resume item entry (→ EnteringItem)
- Complete transaction (→ Completed)

**Completed State:**
- No operations allowed
- Transaction finalized

**Cancelled State:**
- No operations allowed
- Cart terminated

## Dual Storage Strategy

### Primary Storage: Dapr State Store (Redis)
- **Purpose:** High-performance active cart storage
- **Features:** Circuit breaker pattern for resilience
- **TTL:** 5 minutes for terminal info caching

### Fallback Storage: MongoDB
- **Purpose:** Persistent storage when state store fails
- **Features:** Complete transaction history and audit trails
- **Consistency:** Eventual consistency with state store

### Circuit Breaker Implementation
- **Failure Threshold:** 3 consecutive failures
- **Reset Timeout:** 60 seconds
- **States:** Closed → Open → Half-Open
- **Applied to:** Dapr state operations, external HTTP calls

## Plugin Architecture

### Payment Strategy Plugins
- **Cash Payment:** Handles cash transactions with change calculation
- **Cashless Payment:** Credit/debit card and digital payment processing
- **Other Payment:** Custom payment method implementations

### Sales Promotion Plugins
- **Configurable:** JSON-based promotion rule configuration
- **Extensible:** Plugin system for custom discount strategies
- **Stackable:** Support for multiple promotion combinations

### Receipt Data Plugins
- **Customizable:** Configurable receipt formatting
- **Validation:** Type-safe receipt line configuration
- **Alignment:** Support for left/center/right text alignment

## Event-Driven Communication

### Published Events

#### Transaction Log Event (`tranlog_report`)
Published when transaction completes:
```json
{
  "eventId": "uuid",
  "tenantId": "tenant001",
  "storeCode": "store001", 
  "terminalNo": 1,
  "transactionNo": "0001",
  "businessDate": "20240101",
  "totalAmount": 1500.00,
  "lineItems": [...],
  "payments": [...]
}
```

#### Transaction Status Event (`tranlog_status`)
Published for void/return operations:
```json
{
  "eventId": "uuid",
  "transactionNo": "0001",
  "statusType": "void",
  "operationDateTime": "2024-01-01T10:30:00Z"
}
```

#### Cash Log Event (`cashlog_report`)
Published for cash operations:
```json
{
  "eventId": "uuid", 
  "operationType": "cashin",
  "amount": 1000.00,
  "timestamp": "2024-01-01T10:30:00Z"
}
```

#### Terminal Log Event (`opencloselog_report`)
Published for terminal open/close:
```json
{
  "eventId": "uuid",
  "operationType": "open",
  "terminalId": "T001",
  "timestamp": "2024-01-01T09:00:00Z"
}
```

## Multi-Tenancy Implementation

1. **Database Isolation**: Each tenant uses separate database: `db_cart_{tenant_id}`
2. **Tenant Validation**: All operations validate tenant_id from authentication
3. **Data Isolation**: Cross-tenant access prevented at application level
4. **Shard Key**: `{tenant_id}_{store_code}_{business_date}`

## Validation Rules

### Cart Validation
- Terminal must be in "Opened" status
- Staff must be signed in
- Business date must match terminal business date
- State transitions must follow state machine rules

### Item Validation
- Item code must exist in master data
- Quantity must be positive
- Price overrides require authorization
- Tax calculations must be accurate

### Payment Validation
- Total payment must equal cart balance
- Payment methods must be active
- Cash change calculated automatically
- Reference numbers required for cashless payments

### Transaction Validation
- Void operations restricted to same terminal
- Return operations allowed within same store
- Return quantities cannot exceed original amounts

## Performance Considerations

1. **Indexing Strategy**: Optimized for cart lookups, transaction queries, and event processing
2. **Caching**: Terminal info and master data cached in Dapr state store
3. **Dual Storage**: High-performance state store with persistent fallback
4. **Circuit Breaker**: Resilient handling of external service failures
5. **Event Processing**: Asynchronous pub/sub for scalability

## Security Features

1. **Authentication**: API key validation and staff session verification
2. **Authorization**: Terminal-scoped operations and state-based access control
3. **Audit Trail**: Complete transaction history and operation tracking
4. **Data Integrity**: State machine enforcement and atomic operations
5. **Multi-tenant Isolation**: Complete data separation between tenants