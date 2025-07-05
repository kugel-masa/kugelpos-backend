# Cart Service Model Specification

## Overview

The Cart service manages shopping cart operations and transaction processing for the Kugelpos POS system. It implements cart lifecycle management through state machine patterns, dual storage strategy (Dapr State Store + MongoDB), plugin architecture (payment & promotion), and event-driven communication.

## Database Document Models

### 1. CartDocument (Active Shopping Cart)

Document storing state machine-managed active shopping carts.

**Collection Name:** `cache_cart`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| cart_id | string | ✓ | Unique UUID cart identifier |
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| terminal_no | integer | ✓ | Terminal number |
| receipt_no | integer | - | Receipt number |
| transaction_no | integer | - | Transaction number |
| transaction_type | integer | - | Transaction type |
| user | UserInfoDocument | - | User information |
| staff | StaffDocument | - | Staff information |
| sales | SalesDocument | - | Sales summary information |
| cart_status | string | ✓ | Cart state (Initial/Idle/EnteringItem/Paying/Completed/Cancelled) |
| generate_date_time | datetime | - | Cart generation date/time |
| business_date | string | - | Business date (YYYYMMDD) |
| subtotal_amount | float | - | Total before tax and discounts |
| total_amount | float | - | Total amount including tax |
| total_quantity | integer | - | Total quantity |
| total_discount_amount | float | - | Total discount amount |
| deposit_amount | float | - | Deposit amount |
| change_amount | float | - | Change amount |
| balance_amount | float | - | Balance amount |
| line_items | array[LineItemDocument] | - | Cart item details |
| payments | array[PaymentDocument] | - | Payment information |
| taxes | array[TaxDocument] | - | Tax calculation information |
| subtotal_discounts | array[DiscountInfoDocument] | - | Subtotal level discounts |
| is_voided | boolean | - | Void flag |
| is_refunded | boolean | - | Refund flag |
| masters | ReferenceMasters | - | Master data cache |
| receipt_text | string | - | Receipt text |
| journal_text | string | - | Journal text |

**LineItemDocument Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| line_no | integer | ✓ | Line item number |
| item_code | string | ✓ | Item code |
| item_name | string | - | Item name |
| unit_price | float | ✓ | Unit price |
| unit_price_original | float | - | Original unit price |
| is_unit_price_changed | boolean | - | Unit price changed flag |
| quantity | float | ✓ | Quantity |
| amount | float | - | Amount |
| discount_amount | float | - | Discount amount |
| tax_amount | float | - | Tax amount |
| discounts | array[DiscountInfoDocument] | - | Line item level discounts |
| item_details | dict | - | Additional item information |
| image_urls | array[string] | - | Item image URLs |
| is_discount_restricted | boolean | - | Discount restriction flag |
| is_cancelled | boolean | - | Cancellation flag |

**PaymentDocument Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| payment_no | integer | ✓ | Payment number |
| payment_code | string | ✓ | Payment method code |
| payment_name | string | - | Payment method name |
| payment_amount | float | ✓ | Payment amount |
| payment_detail | string | - | Payment details |

**TaxDocument Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tax_no | integer | ✓ | Tax number |
| tax_code | string | - | Tax code |
| tax_type | string | ✓ | Tax type |
| tax_name | string | - | Tax name |
| tax_amount | float | ✓ | Tax amount |
| target_amount | float | - | Taxable amount |
| target_quantity | integer | - | Taxable quantity |

**Indexes:**
- cart_id (unique)
- Compound index: (tenant_id, store_code, terminal_no)
- cart_status

### 2. TranlogDocument (Transaction History)

Document storing completed transaction records.

**Collection Name:** `log_tran`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

Same field structure as CartDocument plus:

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| invoice_issue_no | string | - | Invoice issue number |

**Indexes:**
- Compound index: (tenant_id, store_code, terminal_no, business_date, transaction_no)
- invoice_issue_no

### 3. TransactionStatusDocument (Transaction Status Tracking)

Document tracking void and return operations.

**Collection Name:** `status_tran`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| terminal_no | integer | ✓ | Terminal number |
| transaction_no | string | ✓ | Transaction number |
| is_voided | boolean | - | Void status flag |
| is_refunded | boolean | - | Refund status flag |
| void_transaction_no | string | - | Void transaction number |
| void_date_time | datetime | - | Void date/time |
| void_staff_id | string | - | Void executing staff ID |
| return_transaction_no | string | - | Return transaction number |
| return_date_time | datetime | - | Return date/time |
| return_staff_id | string | - | Return executing staff ID |

**Indexes:**
- Unique index: (tenant_id, store_code, terminal_no, transaction_no)
- is_voided
- is_refunded

### 4. TerminalCounterDocument (Terminal Sequence Counters)

Document managing terminal-specific sequence counters.

**Collection Name:** `info_terminal_counter`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| terminal_id | string | ✓ | Terminal identifier |
| count_dic | dict | ✓ | Counter dictionary |

**Counter Types:**
- transaction_no: Transaction number counter
- receipt_no: Receipt number counter

**Indexes:**
- terminal_id (unique)

### 5. TranlogDeliveryStatus (Message Delivery Tracking)

Document tracking pub/sub message delivery status.

**Collection Name:** `status_tran_delivery`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| event_id | string | ✓ | Event identifier (UUID) |
| published_at | datetime | ✓ | Publication date/time |
| status | string | ✓ | Overall delivery status |
| payload | dict | ✓ | Message payload |
| services | array[ServiceStatus] | ✓ | Service-specific delivery status |

**ServiceStatus Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| service_name | string | ✓ | Service name |
| status | string | ✓ | Delivery status (pending/delivered/failed) |
| delivered_at | datetime | - | Delivery date/time |
| error_message | string | - | Error message |

**Indexes:**
- event_id (unique)
- status
- published_at

## API Request/Response Schemas

All schemas inherit from `BaseSchemaModel` (some implementations use `BaseSchemmaModel`) and provide automatic conversion from snake_case to camelCase.

### Cart Management Schemas

#### CartCreateRequest
Request to create a new shopping cart.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| transactionType | integer | - | Transaction type (default: 1 = standard sale) |
| userId | string | - | User identifier |
| userName | string | - | User name |

#### CartCreateResponse
Cart creation response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| cartId | string | Generated cart ID |

#### CartDeleteResponse
Cart deletion response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| message | string | Deletion result message |

### Item Management Schemas

#### Item
Item information to add to cart.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| itemCode | string | ✓ | Item code |
| quantity | integer | ✓ | Quantity |
| unitPrice | float | - | Unit price (for override) |

#### ItemQuantityUpdateRequest
Item quantity update request.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| quantity | integer | ✓ | New quantity |

#### ItemUnitPriceUpdateRequest
Item unit price update request.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| unitPrice | float | ✓ | New unit price |

### Payment Processing Schemas

#### PaymentRequest
Payment processing request.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| paymentCode | string | ✓ | Payment method code |
| amount | integer | ✓ | Payment amount (in smallest currency unit) |
| detail | string | - | Payment detail information |

### Transaction Representation Schemas

#### Cart (Response)
Complete cart information response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| cartId | string | Cart ID |
| cartStatus | string | Cart status |
| subtotalAmount | float | Subtotal amount |
| totalAmount | float | Total amount |
| balanceAmount | float | Balance amount |
| lineItems | array[TranLineItem] | Line items |
| payments | array[TranPayment] | Payment information |
| taxes | array[TranTax] | Tax information |

#### Tran (Response)
Transaction information response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| transactionNo | integer | Transaction number |
| businessDate | string | Business date |
| totalAmount | float | Total amount |
| lineItems | array[TranLineItem] | Line items |
| payments | array[TranPayment] | Payment information |
| taxes | array[TranTax] | Tax information |

### Delivery Status Management Schemas

#### DeliveryStatusUpdateRequest
Delivery status update request.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| eventId | string | ✓ | Event ID |
| service | string | ✓ | Service name |
| status | string | ✓ | Delivery status |
| message | string | - | Message |

#### DeliveryStatusUpdateResponse
Delivery status update response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| eventId | string | Event ID |
| service | string | Service name |
| status | string | Delivery status |
| success | boolean | Update success flag |

## State Machine Pattern

### Cart States and Transitions

**Cart States:**
1. **Initial** - Initial state
2. **Idle** - Idle state (empty cart)
3. **EnteringItem** - Item entry in progress
4. **Paying** - Payment processing
5. **Completed** - Completed (final state)
6. **Cancelled** - Cancelled (final state)

**Valid Transitions:**
- Initial → Idle
- Idle → EnteringItem (when adding items)
- Idle → Cancelled
- EnteringItem → Paying (when starting payment)
- EnteringItem → Cancelled
- Paying → EnteringItem (when resuming item entry)
- Paying → Completed (when payment completed)

## Dual Storage Strategy

### Primary Storage: Dapr State Store
- **Purpose:** High-speed access for active carts
- **Implementation:** Key-value store via Redis
- **TTL:** Terminal information cache 5 minutes (configurable)

### Secondary Storage: MongoDB
- **Purpose:** Persistence and fallback
- **Implementation:** Complete document storage
- **Synchronization:** Eventual consistency with State Store

## Plugin Architecture

### Payment Plugins (/services/strategies/payments/)
- Cash payment: Processing including change calculation
- Cashless payment: Card and electronic money processing
- Custom payment: Extensible payment methods

### Promotion Plugins
- JSON-based configuration
- Multiple promotions can be combined
- Custom discount logic implementation possible

## Event-Driven Communication

### Published Topics

#### tranlog_report
Event published when transaction is completed. Subscribed by report and journal services.

#### cashlog_report
Event published during cash in/out operations.

#### opencloselog_report
Event published during terminal open/close operations.

## Multi-Tenant Implementation

1. **Database Isolation:** Tenant-specific databases in `db_cart_{tenant_id}` format
2. **Authentication Integration:** Obtain tenant_id from JWT tokens
3. **Access Control:** Tenant validation for all operations

## Configuration Parameters

### CartSettings (settings_cart.py)

| Parameter Name | Type | Default Value | Description |
|------------|------|------------|-------------|
| UNDELIVERED_CHECK_INTERVAL_IN_MINUTES | integer | 5 | Undelivered check interval (minutes) |
| UNDELIVERED_CHECK_PERIOD_IN_HOURS | integer | 24 | Undelivered check period (hours) |
| UNDELIVERED_CHECK_FAILED_PERIOD_IN_MINUTES | integer | 15 | Failure determination period (minutes) |
| TERMINAL_CACHE_TTL_SECONDS | integer | 300 | Terminal cache TTL (seconds) |
| USE_TERMINAL_CACHE | boolean | true | Terminal cache usage flag |
| DEBUG | string | "false" | Debug mode |
| DEBUG_PORT | integer | 5678 | Debug port |