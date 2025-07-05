# Cart Service API Specification

## Overview

The Cart service is a microservice that manages shopping carts and transaction processing. It provides cart state management using state machine patterns, product operations, payment processing, and pluggable extension features.

## Service Information

- **Port**: 8003
- **Framework**: FastAPI
- **Authentication**: API Key Authentication
- **Database**: MongoDB (Motor async driver)
- **State Management**: State Machine Pattern
- **Plugin System**: Payment, sales promotion, and receipt data plugins

## API Endpoints

### 1. Root Endpoint

**Path**: `/`  
**Method**: GET  
**Authentication**: Not required  
**Description**: Service health check endpoint

**Response**:
```json
{
  "message": "Welcome to Kugel-POS Cart API. supoorted version: v1"
}
```

**Implementation File**: app/main.py:68-76

### 2. Health Check

**Path**: `/health`  
**Method**: GET  
**Authentication**: Not required  
**Description**: Check service health and dependency status

**Response Model**: `HealthCheckResponse`
```json
{
  "status": "healthy",
  "service": "cart",
  "version": "1.0.0",
  "checks": {
    "mongodb": {
      "status": "healthy",
      "details": {}
    },
    "dapr_sidecar": {
      "status": "healthy",
      "details": {}
    },
    "dapr_cartstore": {
      "status": "healthy",
      "details": {}
    },
    "dapr_pubsub_tranlog": {
      "status": "healthy",
      "details": {}
    },
    "background_jobs": {
      "status": "healthy",
      "details": {
        "scheduler_running": true,
        "job_count": 1,
        "job_names": ["republish_undelivered_tranlog"]
      }
    }
  }
}
```

**Implementation File**: app/main.py:79-137

## Cart API (/api/v1/carts)

### 3. Create Cart

**Path**: `/api/v1/carts`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Create a new shopping cart

**Request Model**: `CartCreateRequest`
```json
{
  "transactionType": "standard",
  "userId": "STF001",
  "userName": "山田太郎"
}
```

**Response Model**: `ApiResponse[CartCreateResponse]`
```json
{
  "success": true,
  "code": 201,
  "message": "Cart Created. cart_id: cart_20250105_001",
  "data": {
    "cartId": "cart_20250105_001"
  },
  "operation": "create_cart"
}
```

**Error Responses**:
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 422: Unprocessable Entity
- 500: Internal Server Error

**Implementation Details** (app/api/v1/cart.py:32-82):
- terminal_id is obtained through dependency injection
- Initial state is "idle" when cart is created
- User information is optional

### 4. Get Cart

**Path**: `/api/v1/carts/{cart_id}`  
**Method**: GET  
**Authentication**: Required (API Key)  
**Description**: Get detailed cart information

**Path Parameters**:
- `cart_id`: string - Cart ID

**Response Model**: `ApiResponse[Cart]`
```json
{
  "success": true,
  "code": 200,
  "message": "Cart found. cart_id: cart_20250105_001",
  "data": {
    "cartId": "cart_20250105_001",
    "status": "entering_item",
    "terminalId": "A1234-STORE01-1",
    "lineItems": [...],
    "subtotalAmount": 1000.0,
    "taxAmount": 100.0,
    "totalAmount": 1100.0,
    "balanceAmount": 1100.0
  },
  "operation": "get_cart"
}
```

**Implementation Details** (app/api/v1/cart.py:84-128):
- Model conversion via SchemasTransformerV1

### 5. Cancel Cart

**Path**: `/api/v1/carts/{cart_id}/cancel`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Transition cart to cancelled state

**Implementation Details** (app/api/v1/cart.py:131-172):
- Can be cancelled from any state
- No operations allowed after cancellation

### 6. Add Items

**Path**: `/api/v1/carts/{cart_id}/lineItems`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Add items to cart

**Request Model**: `list[Item]`
```json
[
  {
    "itemCode": "4901234567890",
    "quantity": 2.0,
    "unitPrice": 100.0
  }
]
```

**Field Descriptions**:
- `itemCode`: string - Item code (required)
- `quantity`: number - Quantity (required)
- `unitPrice`: number - Unit price (optional)

**Implementation Details** (app/api/v1/cart.py:175-220):
- Bulk addition of multiple items possible
- Automatic transition from idle to entering_item state

### 7. Cancel Item

**Path**: `/api/v1/carts/{cart_id}/lineItems/{lineNo}/cancel`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Cancel a specific item

**Path Parameters**:
- `cart_id`: string - Cart ID
- `lineNo`: integer - Line number (starts from 1)

**Implementation Details** (app/api/v1/cart.py:223-266):
- Sets cancellation flag (no physical deletion)

### 8. Update Unit Price

**Path**: `/api/v1/carts/{cart_id}/lineItems/{lineNo}/unitPrice`  
**Method**: PATCH  
**Authentication**: Required (API Key)  
**Description**: Update item unit price

**Request Model**: `ItemUnitPriceUpdateRequest`
```json
{
  "unitPrice": 150.0
}
```

**Implementation Details** (app/api/v1/cart.py:269-315):
- Automatic recalculation after price change

### 9. Update Quantity

**Path**: `/api/v1/carts/{cart_id}/lineItems/{lineNo}/quantity`  
**Method**: PATCH  
**Authentication**: Required (API Key)  
**Description**: Update item quantity

**Request Model**: `ItemQuantityUpdateRequest`
```json
{
  "quantity": 3.0
}
```

**Implementation Details** (app/api/v1/cart.py:318-364):
- Automatic recalculation after quantity change

### 10. Add Item Discount

**Path**: `/api/v1/carts/{cart_id}/lineItems/{lineNo}/discounts`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Apply discount to specific item

**Request Model**: `list[DiscountRequest]`
```json
[
  {
    "discountCode": "DISC10",
    "discountAmount": 50.0,
    "discountType": "amount"
  }
]
```

**Implementation Details** (app/api/v1/cart.py:367-415):
- Multiple discounts can be applied

### 11. Calculate Subtotal

**Path**: `/api/v1/carts/{cart_id}/subtotal`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Calculate cart subtotal and tax

**Implementation Details** (app/api/v1/cart.py:418-459):
- Subtotal calculation after item entry
- Transition from entering_item to paying state

### 12. Add Cart Discount

**Path**: `/api/v1/carts/{cart_id}/discounts`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Apply discount to entire cart

**Request Model**: `list[DiscountRequest]`

**Implementation Details** (app/api/v1/cart.py:462-508):
- Apply cart-level discounts

### 13. Add Payment

**Path**: `/api/v1/carts/{cart_id}/payments`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Add payment to cart

**Request Model**: `list[PaymentRequest]`
```json
[
  {
    "paymentCode": "01",
    "paymentAmount": 1100.0,
    "paymentDetails": {
      "tenderedAmount": 2000.0
    }
  }
]
```

**Implementation Details** (app/api/v1/cart.py:511-556):
- Multiple payment methods can be combined
- Payment processing via plugin system

### 14. Bill Transaction

**Path**: `/api/v1/carts/{cart_id}/bill`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Complete cart and finalize transaction

**Implementation Details** (app/api/v1/cart.py:559-601):
- Transition from paying to completed state
- Generate and publish transaction log
- Generate receipt data

### 15. Resume Item Entry

**Path**: `/api/v1/carts/{cart_id}/resume-item-entry`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Return from payment state to item entry state

**Implementation Details** (app/api/v1/cart.py:604-646):
- Return from paying to entering_item state
- Clear payment information

## Transaction API

### 16. Get Transaction List

**Path**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`  
**Method**: GET  
**Authentication**: Required (API Key)  
**Description**: Get list of transactions matching criteria

**Query Parameters**:
- `business_date`: string (YYYYMMDD) - Business date
- `open_counter`: integer - Open counter
- `transaction_type`: list[integer] - Transaction types
- `receipt_no`: integer - Receipt number
- `limit`: integer (default: 100) - Number of records
- `page`: integer (default: 1) - Page number
- `sort`: string - Sort conditions (e.g., "transaction_no:-1")
- `include_cancelled`: boolean (default: false) - Include cancelled transactions

**Implementation Details** (app/api/v1/tran.py:207-292)

### 17. Get Transaction Details

**Path**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}`  
**Method**: GET  
**Authentication**: Required (API Key)  
**Description**: Get detailed information for a specific transaction

**Implementation Details** (app/api/v1/tran.py:295-357)

### 18. Void Transaction

**Path**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Void a transaction

**Request Model**: `list[PaymentRequest]` - Payment methods for refund

**Implementation Details** (app/api/v1/tran.py:360-438):
- Can only be voided from the same terminal
- Requires payment processing for refund

### 19. Return Transaction

**Path**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Process transaction return

**Request Model**: `list[PaymentRequest]` - Payment methods for refund

**Implementation Details** (app/api/v1/tran.py:441-516):
- Can only be returned from within the same store
- Creates new transaction for return

### 20. Update Delivery Status

**Path**: `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/delivery-status`  
**Method**: POST  
**Authentication**: Required (JWT or internal authentication)  
**Description**: Update delivery status of transaction log

**Request Model**: `DeliveryStatusUpdateRequest`
```json
{
  "eventId": "evt_123456",
  "service": "journal",
  "status": "delivered",
  "message": "Successfully processed"
}
```

**Implementation Details** (app/api/v1/tran.py:520-594):
- Endpoint for Pub/Sub notifications
- Used for inter-service communication

## Tenant API

### 21. Create Tenant

**Path**: `/api/v1/tenants`  
**Method**: POST  
**Authentication**: Required (API Key)  
**Description**: Set up database for new tenant

**Implementation File**: app/api/v1/tenant.py

## Cache API

### 22. Update Terminal Status

**Path**: `/api/v1/cache/terminal/status`  
**Method**: PUT  
**Authentication**: Required (API Key)  
**Description**: Update terminal cache status

**Implementation File**: app/api/v1/cache.py

### 23. Clear Terminal Cache

**Path**: `/api/v1/cache/terminal`  
**Method**: DELETE  
**Authentication**: Required (API Key)  
**Description**: Clear terminal cache

**Implementation File**: app/api/v1/cache.py

## State Machine

### Cart State Transitions

**Implementation Directory**: app/services/states/

1. **InitialState** → **IdleState**
   - Initial transition when cart is created

2. **IdleState** → **EnteringItemState**
   - When first item is added

3. **EnteringItemState** → **PayingState**
   - When subtotal calculation is executed

4. **PayingState** → **CompletedState**
   - When billing process is completed

5. **PayingState** → **EnteringItemState**
   - When item entry is resumed

6. **Any State** → **CancelledState**
   - When cancellation is processed

## Plugin System

### Payment Plugins

**Implementation Directory**: app/services/strategies/payments/

- **PaymentByCash** (ID: "01"): Cash payment
- **PaymentByCashless** (ID: "11"): Cashless payment
- **PaymentByOthers** (ID: "12"): Other payment methods

### Sales Promotion Plugins

**Implementation Directory**: app/services/strategies/sales_promotions/

- **SalesPromoSample** (ID: "101"): Sample sales promotion

### Receipt Data Plugins

**Implementation Directory**: app/services/strategies/receipt_data/

- **ReceiptDataSample** (ID: "default", "32"): Receipt data generation

## Scheduled Jobs

### Republish Undelivered Messages

**Implementation File**: app/cron/republish_undelivery_message.py

- **Execution Interval**: Every 5 minutes
- **Check Period**: Past 24 hours
- **Failure Criteria**: More than 15 minutes elapsed
- **Target**: Undelivered transaction logs

## Event Publishing

### Dapr Pub/Sub Topics

1. **tranlog_report**: Transaction logs (for reporting)
2. **tranlog_status**: Transaction status updates
3. **cashlog_report**: Cash in/out logs
4. **opencloselog_report**: Open/close logs

## Error Codes

Cart service uses the following error code system:
- **30XXYY**: Cart service specific errors
  - XX: Feature identifier
  - YY: Specific error number

## Middleware

**Implementation File**: app/main.py

1. **CORS** (lines 53-59): Allow access from all origins
2. **Request Logging** (line 62): Log all HTTP requests
3. **Exception Handler** (line 65): Unified error response format

## Database

### Collections
- `carts`: Cart information
- `terminal_counter`: Terminal counters
- `tranlog`: Transaction logs
- `transaction_status`: Transaction status

### Cache
- Uses Dapr State Store (cartstore)
- Terminal information cache (TTL: 300 seconds)

## Notes

1. **API Key Authentication**: Required for all business endpoints
2. **State Machine**: Only operations following state transition rules are allowed
3. **Plugin Configuration**: Dynamic loading via plugins.json
4. **Asynchronous Processing**: All DB operations are asynchronous
5. **Event Publishing**: Asynchronous events via Dapr
6. **Multi-tenancy**: Independent database per tenant
7. **Cart Expiration**: 24 hours from creation