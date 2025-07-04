# Cart Service API Specification

## Overview

Cart Service is the core transaction processing service in the Kugelpos POS system. It manages shopping cart operations, handles payment processing, and coordinates transaction completion using a state machine pattern to ensure proper business logic flow.

## Base URL
- Local environment: `http://localhost:8003`
- Production environment: `https://cart.{domain}`

## Authentication

Cart Service supports API key authentication for POS terminal operations:

### API Key Authentication
- Include in header: `X-API-Key: {api_key}`
- Include query parameter: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- Terminal must be in "Opened" status for cart operations

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

## Cart States

The cart follows a state machine pattern with the following states:
- `Initial` - Cart just created
- `Idle` - Empty cart ready for items
- `EnteringItem` - Cart with items, allows modifications
- `Paying` - Processing payments, limited operations
- `Completed` - Transaction finalized
- `Cancelled` - Transaction cancelled

## API Endpoints

### Cart Operations

#### 1. Create Cart
**POST** `/api/v1/carts`

Create a new shopping cart for transaction processing.

**Request Body:**
```json
{
  "transactionType": 101,
  "userId": "user001",
  "userName": "John Doe"
}
```

**Field Descriptions:**
- `transactionType` (integer, optional): Transaction type code (default: 101)
  - `101` - Normal sales
  - `102` - Return sales
- `userId` (string, optional): User/staff identifier
- `userName` (string, optional): User/staff name

**Request Example:**
```bash
curl -X POST "http://localhost:8003/api/v1/carts?terminal_id=tenant001-store001-001" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "transactionType": 101,
    "userId": "STF001",
    "userName": "John Doe"
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Cart created successfully",
  "data": {
    "cartId": "cart_123456789",
    "status": "Idle",
    "transactionType": 101,
    "terminalId": "tenant001-store001-001",
    "userId": "STF001",
    "businessDate": "2024-01-01",
    "createdAt": "2024-01-01T10:00:00Z"
  },
  "operation": "create_cart"
}
```

#### 2. Get Cart
**GET** `/api/v1/carts/{cart_id}`

Retrieve cart details including items, payments, and calculations.

**Path Parameters:**
- `cart_id` (string, required): Cart identifier

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Example:**
```bash
curl -X GET "http://localhost:8003/api/v1/carts/cart_123456789?terminal_id=tenant001-store001-001" \
  -H "X-API-Key: {api_key}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Cart retrieved successfully",
  "data": {
    "cartId": "cart_123456789",
    "status": "EnteringItem",
    "transactionType": 101,
    "subtotalAmount": 100.00,
    "discountAmount": 10.00,
    "taxAmount": 9.00,
    "totalAmount": 99.00,
    "balanceAmount": 99.00,
    "lineItems": [
      {
        "lineNo": 1,
        "itemCode": "ITEM001",
        "description": "Sample Product",
        "quantity": 2.0,
        "unitPrice": 50.00,
        "amount": 100.00,
        "discountAmount": 10.00,
        "taxAmount": 9.00,
        "isCancelled": false
      }
    ],
    "payments": [],
    "taxes": [
      {
        "taxCode": "TAX001",
        "taxName": "Standard Tax",
        "taxRate": 0.10,
        "taxableAmount": 90.00,
        "taxAmount": 9.00
      }
    ]
  },
  "operation": "get_cart"
}
```

#### 3. Cancel Cart
**POST** `/api/v1/carts/{cart_id}/cancel`

Cancel an entire cart (allowed in Initial, Idle, or EnteringItem states).

**Path Parameters:**
- `cart_id` (string, required): Cart identifier

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Example:**
```bash
curl -X POST "http://localhost:8003/api/v1/carts/cart_123456789/cancel?terminal_id=tenant001-store001-001" \
  -H "X-API-Key: {api_key}"
```

### Line Item Operations

#### 4. Add Line Item
**POST** `/api/v1/carts/{cart_id}/lineItems`

Add items to the shopping cart.

**Path Parameters:**
- `cart_id` (string, required): Cart identifier

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Body:**
```json
{
  "itemCode": "ITEM001",
  "quantity": 2.0,
  "unitPrice": null,
  "overridePrice": false,
  "overrideReason": null
}
```

**Field Descriptions:**
- `itemCode` (string, required): Product item code
- `quantity` (number, required): Quantity to add (positive number)
- `unitPrice` (number, optional): Custom unit price (if overriding)
- `overridePrice` (boolean, optional): Flag to override price
- `overrideReason` (string, optional): Reason for price override

**Request Example:**
```bash
curl -X POST "http://localhost:8003/api/v1/carts/cart_123456789/lineItems?terminal_id=tenant001-store001-001" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "itemCode": "ITEM001",
    "quantity": 2.0
  }'
```

#### 5. Cancel Line Item
**POST** `/api/v1/carts/{cart_id}/lineItems/{line_no}/cancel`

Cancel a specific line item (mark as cancelled, not removed).

**Path Parameters:**
- `cart_id` (string, required): Cart identifier
- `line_no` (integer, required): Line item number

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

#### 6. Update Line Item Quantity
**PATCH** `/api/v1/carts/{cart_id}/lineItems/{line_no}/quantity`

Update the quantity of a line item.

**Path Parameters:**
- `cart_id` (string, required): Cart identifier
- `line_no` (integer, required): Line item number

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Body:**
```json
{
  "quantity": 3.0
}
```

#### 7. Update Line Item Unit Price
**PATCH** `/api/v1/carts/{cart_id}/lineItems/{line_no}/unitPrice`

Update the unit price of a line item.

**Path Parameters:**
- `cart_id` (string, required): Cart identifier
- `line_no` (integer, required): Line item number

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Body:**
```json
{
  "unitPrice": 45.00,
  "overrideReason": "Manager discount"
}
```

#### 8. Add Line Item Discount
**POST** `/api/v1/carts/{cart_id}/lineItems/{line_no}/discounts`

Apply discount to a specific line item.

**Path Parameters:**
- `cart_id` (string, required): Cart identifier
- `line_no` (integer, required): Line item number

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Body:**
```json
{
  "discountType": "amount",
  "discountValue": 5.00,
  "discountDetail": "Customer promotion"
}
```

**Field Descriptions:**
- `discountType` (string, required): Type of discount ("amount" or "percent")
- `discountValue` (number, required): Discount value (amount in dollars or percentage)
- `discountDetail` (string, optional): Discount detail or reason

### Transaction Processing

#### 9. Calculate Subtotal
**POST** `/api/v1/carts/{cart_id}/subtotal`

Calculate cart subtotal including taxes (required before payment).

**Path Parameters:**
- `cart_id` (string, required): Cart identifier

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Subtotal calculated successfully",
  "data": {
    "subtotalAmount": 100.00,
    "discountAmount": 10.00,
    "taxAmount": 9.00,
    "totalAmount": 99.00,
    "taxes": [
      {
        "taxCode": "TAX001",
        "taxName": "Standard Tax",
        "taxRate": 0.10,
        "taxableAmount": 90.00,
        "taxAmount": 9.00
      }
    ]
  },
  "operation": "calculate_subtotal"
}
```

#### 10. Add Cart Discount
**POST** `/api/v1/carts/{cart_id}/discounts`

Apply discount to entire cart.

**Path Parameters:**
- `cart_id` (string, required): Cart identifier

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Body:**
```json
{
  "discountType": "percent",
  "discountValue": 10.0,
  "discountDetail": "Member discount"
}
```

#### 11. Process Payment
**POST** `/api/v1/carts/{cart_id}/payments`

Add payment to the cart.

**Path Parameters:**
- `cart_id` (string, required): Cart identifier

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Body:**
```json
{
  "paymentCode": "01",
  "amount": 10000,
  "detail": "Cash payment"
}
```

**Field Descriptions:**
- `paymentCode` (string, required): Payment method code
  - `01` - Cash
  - `11` - Cashless (Credit/Debit)
  - `12` - Other payment methods
- `amount` (integer, required): Payment amount in cents (e.g., 10000 = $100.00)
- `detail` (string, optional): Payment detail or reference information

**Request Example (Cash Payment):**
```bash
curl -X POST "http://localhost:8003/api/v1/carts/cart_123456789/payments?terminal_id=tenant001-store001-001" \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "paymentCode": "01",
    "amount": 10000,
    "detail": "Cash payment"
  }'
```

#### 12. Finalize Transaction (Bill)
**POST** `/api/v1/carts/{cart_id}/bill`

Complete the transaction and generate receipt.

**Path Parameters:**
- `cart_id` (string, required): Cart identifier

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Transaction completed successfully",
  "data": {
    "cartId": "cart_123456789",
    "status": "Completed",
    "transactionNo": "0001",
    "receiptNo": "R0001",
    "businessDate": "2024-01-01",
    "totalAmount": 99.00,
    "receiptText": "=== RECEIPT ===\n...",
    "journalText": "Transaction Details\n...",
    "timestamp": "2024-01-01T10:30:00Z"
  },
  "operation": "complete_transaction"
}
```

#### 13. Resume Item Entry
**POST** `/api/v1/carts/{cart_id}/resume-item-entry`

Return from payment state to continue adding items.

**Path Parameters:**
- `cart_id` (string, required): Cart identifier

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

### Transaction Management

#### 14. Query Transactions
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

Search and retrieve historical transactions.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (string, required): Terminal number

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication
- `business_date` (string, optional): Business date (YYYY-MM-DD)
- `transaction_no` (string, optional): Transaction number
- `skip` (integer, default: 0): Pagination offset
- `limit` (integer, default: 20, max: 100): Page size

**Request Example:**
```bash
curl -X GET "http://localhost:8003/api/v1/tenants/tenant001/stores/store001/terminals/001/transactions?terminal_id=tenant001-store001-001&business_date=2024-01-01" \
  -H "X-API-Key: {api_key}"
```

#### 15. Get Transaction Details
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}`

Retrieve specific transaction details.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (string, required): Terminal number
- `transaction_no` (string, required): Transaction number

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication
- `business_date` (string, required): Business date (YYYY-MM-DD)

#### 16. Void Transaction
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void`

Void a completed transaction (same terminal only).

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (string, required): Terminal number
- `transaction_no` (string, required): Transaction number

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Body:**
```json
{
  "businessDate": "2024-01-01",
  "voidReasonCode": "01",
  "voidReason": "Customer request"
}
```

**Field Descriptions:**
- `businessDate` (string, required): Original transaction business date
- `voidReasonCode` (string, optional): Void reason code
- `voidReason` (string, optional): Void reason description

#### 17. Process Return
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return`

Process a return from original transaction (any terminal in same store).

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (string, required): Original terminal number
- `transaction_no` (string, required): Original transaction number

**Query Parameters:**
- `terminal_id` (string, required): Current terminal ID for authentication

**Request Body:**
```json
{
  "businessDate": "2024-01-01",
  "returnItems": [
    {
      "lineNo": 1,
      "quantity": 1.0,
      "returnReasonCode": "01",
      "returnReason": "Defective"
    }
  ]
}
```

**Field Descriptions:**
- `businessDate` (string, required): Original transaction business date
- `returnItems` (array, required): Items to return
  - `lineNo` (integer, required): Original line item number
  - `quantity` (number, required): Quantity to return
  - `returnReasonCode` (string, optional): Return reason code
  - `returnReason` (string, optional): Return reason description

#### 18. Update Delivery Status
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/delivery-status`

Update transaction log delivery status for event tracking.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code
- `terminal_no` (string, required): Terminal number
- `transaction_no` (string, required): Transaction number

**Query Parameters:**
- `terminal_id` (string, required): Terminal ID for authentication

**Request Body:**
```json
{
  "businessDate": "2024-01-01",
  "eventId": "evt_123456",
  "delivered": true
}
```

### System Endpoints

#### 19. Create Tenant
**POST** `/api/v1/tenants`

Initialize cart service for a new tenant.

**Request Body:**
```json
{
  "tenantId": "tenant001"
}
```

**Authentication:** Requires JWT token

#### 20. Health Check
**GET** `/health`

Check service health and dependencies.

**Request Example:**
```bash
curl -X GET "http://localhost:8003/health"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Service is healthy",
  "data": {
    "status": "healthy",
    "mongodb": "connected",
    "dapr_sidecar": "connected",
    "dapr_state_store": "connected",
    "pubsub_topics": "available"
  },
  "operation": "health_check"
}
```

## Error Responses

The API uses standard HTTP status codes and structured error responses:

```json
{
  "success": false,
  "code": 400,
  "message": "Invalid cart state: Cannot add items in Paying state",
  "data": null,
  "operation": "add_line_item"
}
```

### Common Status Codes
- `200` - Success
- `201` - Created successfully
- `400` - Bad request
- `401` - Authentication error
- `403` - Access denied
- `404` - Resource not found
- `409` - State conflict
- `500` - Internal server error

### Error Code System

Cart Service uses error codes in the 30XXX range:

- `30001` - Cart not found
- `30002` - Invalid cart state for operation
- `30003` - Line item not found
- `30004` - Payment processing error
- `30005` - Transaction not found
- `30006` - Void operation not allowed
- `30007` - Return processing error
- `30008` - Invalid payment amount
- `30009` - Terminal not opened
- `30010` - Staff not signed in
- `30099` - General cart service error

## Event Publishing

The cart service publishes events to the following Dapr pub/sub topics:

### Transaction Log Events
- **Topic**: `topic-tranlog`
- **Events**: Completed transactions, voids, returns

Event structure includes:
- Transaction details
- Line items
- Payments
- Receipt and journal text

## Business Rules

1. **Terminal Requirements**:
   - Terminal must be in "Opened" status
   - Staff must be signed in

2. **State Transitions**:
   - Items can only be added in Idle or EnteringItem states
   - Payments only allowed after subtotal calculation
   - Cannot modify cart in Completed or Cancelled states

3. **Payment Rules**:
   - Total payment must equal balance amount
   - Cash payments calculate change automatically
   - Multiple payment methods supported

4. **Void Rules**:
   - Only from same terminal that created transaction
   - Only for completed transactions
   - Creates reverse transaction

5. **Return Rules**:
   - Allowed from any terminal in same store
   - Partial returns supported
   - Original transaction must exist

## Plugin System

### Payment Strategies
- **Cash (01)**: Handles physical cash with change
- **Cashless (11)**: Credit/debit card processing
- **Other (12)**: Alternative payment methods

### Promotion Strategies
- Extensible promotion system
- Configured via `plugins.json`

## Notes

1. **Cart ID**: Generated automatically as unique identifier
2. **Transaction Numbers**: Sequential per terminal per business date
3. **State Machine**: Enforces proper operation sequence
4. **CamelCase Convention**: All JSON fields use camelCase
5. **Timestamps**: All timestamps are in ISO 8601 format (UTC)
6. **Amount Calculations**: All amounts are in decimal format
7. **Idempotency**: Operations are designed to be idempotent where possible