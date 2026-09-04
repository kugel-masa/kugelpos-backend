# Cart Service Model Specification

## Overview

The Cart service manages shopping cart operations and transaction processing for the Kugelpos POS system. It implements cart lifecycle management through state machine patterns, dual storage strategy (Dapr State Store + MongoDB), plugin architecture (payment & promotion), and event-driven communication. Since phase 2 (issue #156) the client holds the cart as a signed snapshot and server-side storage is no longer the authority ([Client-Carried Cart](./client-carried-cart.md)).

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
| seq | integer | - | Per-open-session transaction sequence; 0 until the first finalize (#156) |
| revision | integer | - | Monotonic cart revision, incremented once per issued snapshot (#165) |
| carry_snapshot | boolean | - | Which way the client opened this cart (#192); see below |
| receipt_counter | integer | - | The terminal's running receipt counter, from which the printed number is derived (#166) |
| transaction_datetime | string | - | Client-stamped transaction time (set at bill); source of the tranlog's generate_date_time |

**What the client carries (issue #156 onward):**

The last five fields above are all part of the **signed snapshot the client holds**. The
signature covers them, so the server can tell which generation of the cart a terminal is
holding, and which way it was opened, without reading the cache.

- `seq` / `receipt_counter` / `transaction_datetime` exist for **deterministic numbering and
  time**: a retry records the same values whichever backend it reaches (FR-012). The printed
  receipt number is not accepted from the terminal — the server derives it from
  `receipt_counter` and the configured range (#208).
- `revision` makes **rollback visible after the fact**. An older envelope carries a lower
  number. A stateless backend cannot know the high-water mark without a per-request write, so
  this is detection, not synchronous refusal (#165).
- `carry_snapshot` is **declared at creation** because the server cannot infer it (there is
  nothing to carry yet):
  - `True` — carried. **Nothing is written to the cache**, so a snapshot-less request finds no
    cart and is refused by that alone
  - `False` — not carried. Presenting it as a snapshot is refused, because the cache copy it
    would leave behind is what a later snapshot-less request would silently continue from
  - `None` — a cart created before this field existed; neither is refused

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
- created_at (TTL, expiring after `CACHE_CART_TTL_SECONDS`)

The TTL matches the Redis `cartstore` TTL and clears orphaned MongoDB fallback copies. It is
keyed on `created_at` rather than `updated_at`, which can be None on first insert and would
leave such documents unexpired.

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
- Unique: (tenant_id, store_code, terminal_no, business_counter, transaction_no)
- Unique, partial (only where `cart_id` is a string): (tenant_id, store_code, cart_id)
- Non-unique: (tenant_id, store_code, terminal_no, receipt_counter)

**`cart_id` is the transaction identity (issue #156).** `transaction_no` became the per-open
`seq` and is no longer unique on its own (a daily open resets it to 1), so the numbering tuple
includes `business_counter`. Deduplicating a repeated finalize is the partial-unique `cart_id`
index's job.

The `receipt_counter` index is **deliberately not unique**. The counter is client-owned and the
backend cannot enforce it, and gaps are expected where a terminal was replaced or an
offline-finalized transaction never arrived. It serves the high-water lookup a replacement
terminal is reseeded from, and the audit query that walks for holes.

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
| business_counter | integer | - | Business counter; with `transaction_no` it forms the identity (#156) |
| transaction_no | string | ✓ | Transaction number (the per-open seq on the carried path) |
| is_voided | boolean | - | Void status flag |
| is_refunded | boolean | - | Refund status flag |
| void_transaction_no | string | - | Void transaction number |
| void_date_time | datetime | - | Void date/time |
| void_staff_id | string | - | Void executing staff ID |
| return_transaction_no | string | - | Return transaction number |
| return_date_time | datetime | - | Return date/time |
| return_staff_id | string | - | Return executing staff ID |

**Indexes:**
- Unique: (tenant_id, store_code, terminal_no, business_counter, transaction_no)

`business_counter` is in the key because `transaction_no` became a `seq` that repeats every open
session (#156). Without it, one session's void/refund status collides with the same-numbered
transaction of another — a daily open resets seq to 1, so day 2's first sale would read day 1's
status. It mirrors the tranlog numbering tuple.

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

### 6. CartRestoreLogDocument (Snapshot Audit Trail)

One record per snapshot restore, rejection or finalize divergence (issue #148, extended to the
per-request path in #156). On the carried path the cart does not exist on the server for
stretches of its life. **What was refused, and which generation of the cart the refused terminal
was holding, is recorded nowhere else.**

**Collection Name:** `log_cart_restore`

**Inheritance:** `AbstractDocument`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier (from the authenticated context) |
| store_code | string | ✓ | Store code (same) |
| terminal_no | integer | ✓ | Terminal number (same) |
| cart_id | string | - | Target cart (from the presented snapshot) |
| result | string | ✓ | `restored` / `existing_returned` / `rejected` / `finalize_repeat_diverged` |
| api_path | string | - | Where it happened. None for the restore endpoint; the operation's path for a per-request rejection |
| reject_reason | string | - | Cart error code on rejection (e.g. 401501); None on success |
| diverged | boolean | - | True when the presented snapshot differs from an existing cart |
| snapshot_issued_at | string | - | Issue time from the envelope |
| snapshot_terminal_no | integer | - | Terminal the envelope names |
| snapshot_kid | string | - | Signing key id — what a rotation is traced by |
| snapshot_schema_version | integer | - | Envelope schema version |
| snapshot_revision | integer | - | Cart revision from the envelope (#165); says which generation was refused |
| event_datetime | string | ✓ | Record time |

**Indexes:**
- cart_id (non-unique)
- event_datetime (non-unique)

No TTL: retention follows the other log collections.

## API Request/Response Schemas

All schemas inherit from `BaseSchemaModel` (some implementations use `BaseSchemmaModel`) and provide automatic conversion from snake_case to camelCase.

### The Mutating-Request Wrapper (issue #156)

On the carried path a mutating request body is **wrapped in the signed snapshot**:

```json
{
  "signedSnapshot": { "schemaVersion": 1, "issuedAt": "...", "kid": "...",
                      "tenantId": "...", "storeCode": "...", "terminalNo": 9,
                      "cartDocument": { ... }, "signature": "..." },
  "payload": <the original request body>
}
```

An ASGI middleware (`middleware/snapshot_envelope.py`) peels `signedSnapshot` off, stashes it on
the request scope, and hands the handler `payload` as the body. **An unwrapped body — a bare
array, object or nothing, with no `signedSnapshot` key — passes straight through**, so a phase 1
client keeps working unchanged. Whether that is permitted at all is what
`CART_REQUEST_SNAPSHOT_MODE` decides.

The signature covers the canonical JSON of every field except `signature` itself, always
computed over the snake_case `model_dump(mode="json")` representation, so the camelCase aliasing
on the wire does not affect verification.

**SnapshotEnvelope:**

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| schemaVersion | integer | ✓ | Envelope schema version |
| issuedAt | string | ✓ | Issue time |
| kid | string | ✓ | Signing key id (rotation) |
| tenantId | string | ✓ | Tenant at issue time |
| storeCode | string | ✓ | Store at issue time |
| terminalNo | integer | ✓ | Terminal at issue time |
| cartDocument | dict | ✓ | The whole cart document, reference masters included |
| signature | string | ✓ | HMAC over all of the above |

### Cart Management Schemas

#### CartCreateRequest
Request to create a new shopping cart.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| transactionType | integer | - | Transaction type (default: 1 = standard sale) |
| userId | string | - | User identifier |
| userName | string | - | User name |
| carrySnapshot | boolean | - | The client's undertaking to send the snapshot with every later request (#192). Default false |

`carrySnapshot` is declared rather than inferred because creation has nothing to carry yet.
Inferring it would mean writing the cart to the cache on the chance that the client will not
carry — and that copy is what a later snapshot-less request silently continues from, having
missed everything the carried requests did. A client that does not send it means false.

#### CartCreateResponse
Cart creation response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| cartId | string | Generated cart ID |
| signedSnapshot | SnapshotEnvelope | Signed snapshot of the freshly created cart (#148) |

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

> **Since phase 2 (issue #156):** the client holds the cart as a signed snapshot and carries it on every mutating request, so **server-side storage is no longer the authority**. A request that carries a snapshot reads neither the State Store nor MongoDB. The dual storage below remains for the legacy path, where no snapshot is carried (DUAL mode). See [Client-Carried Cart](./client-carried-cart.md).

### Primary Storage: Dapr State Store
- **Purpose:** High-speed access for active carts (when no snapshot is carried)
- **Implementation:** Key-value store via Redis (component `cartstore`)
- **TTL:** `CACHE_CART_TTL_SECONDS` (default 36000 seconds)

### Secondary Storage: MongoDB
- **Purpose:** Persistence and fallback (collection `cache_cart`)
- **Implementation:** Complete document storage
- **Synchronization:** Eventual consistency with State Store
- **TTL:** a `created_at` TTL index, aligned with the State Store's

### A carried cart is written to neither (issue #192)

A cart created with `carrySnapshot=true` is **never written to the cache or to MongoDB**, because
one cart travelling both paths loses its contents silently. A cache copy left at creation is what
a later snapshot-less request would continue from, dropping everything the carried requests did.
Writing nothing means such a request is refused by "no cart found" alone.

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
| DEBUG | string | "false" | Debug mode |
| DEBUG_PORT | integer | 5678 | Debug port |

**Signed cart snapshot (issues #148 / #156):**

| Parameter Name | Type | Default Value | Description |
|------------|------|------------|-------------|
| SNAPSHOT_HMAC_KEYS | string | "" (**required**) | `kid:base64key` CSV; the first entry signs, the rest are previous generations accepted for verification only (rotation grace) |
| SNAPSHOT_ALLOW_INSECURE_KEY | boolean | false | Allow starting with the key published in this repository (local development only) |
| CART_REQUEST_SNAPSHOT_MODE | string | "DUAL" | `DUAL` = accept snapshot-less requests; `REQUIRED` = mutating requests must carry one |
| REQUEST_DECOMPRESS_MAX_BYTES | integer | None | **Deprecated** alias for `MAX_REQUEST_BODY_BYTES` (#195); kept so a deployment that set the old name is honoured rather than silently ignored |

`SNAPSHOT_HMAC_KEYS` is required: the service **refuses to start** without a usable key (#192). A
cart the client carries exists nowhere else, so a service that cannot sign cannot hand one back —
it would take the cart with it. Running degraded was survivable only while the server-side cache
was the authority.

**Master-data cache (issue #072):**

| Parameter Name | Type | Default Value | Description |
|------------|------|------------|-------------|
| MASTER_DATA_CACHE_ENABLED | boolean | true | Global switch; false bypasses the cache and always fetches |
| MASTER_DATA_CACHE_STATE_STORE | string | "masterstore" | Dapr state-store component name |
| MASTER_DATA_CACHE_TTL_SECONDS | integer | 300 | Fallback TTL when a namespace-specific one is not set |
| ITEM_MASTER_CACHE_TTL_SECONDS | integer | 300 | Item master cache TTL (seconds) |
| PAYMENT_MASTER_CACHE_TTL_SECONDS | integer | 600 | Payment master cache TTL (seconds) |
| PROMOTION_MASTER_CACHE_TTL_SECONDS | integer | 60 | Promotion master cache TTL (seconds) |
| SETTINGS_MASTER_CACHE_TTL_SECONDS | integer | 600 | Settings master cache TTL (seconds) |
| TAX_MASTER_CACHE_TTL_SECONDS | integer | 3600 | Tax master cache TTL (seconds) |

**Talking to master-data:**

| Parameter Name | Type | Default Value | Description |
|------------|------|------------|-------------|
| USE_GRPC | boolean | false | Use gRPC for item detail retrieval |
| GRPC_TIMEOUT | float | 5.0 | gRPC request timeout (seconds) |
| MASTER_DATA_GRPC_URL | string | "master-data:50051" | gRPC server URL |