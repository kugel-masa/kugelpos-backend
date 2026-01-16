# Cart Service API Specification

## Overview

Manages shopping cart and transaction processing. Provides cart state management using state machine pattern.

## Service Information

- **Port**: 8003
- **Framework**: FastAPI
- **Database**: MongoDB (Motor async driver)

## Base URL

- Local Environment: `http://localhost:8003`
- Production Environment: `https://cart.{domain}`

## Authentication

The following authentication methods are supported:

### API Key Authentication
- Header: `X-API-Key: {api_key}`
- Usage: API calls from terminals

### JWT Token Authentication
- Header: `Authorization: Bearer {token}`
- Usage: System operations by administrators

## Common Response Format

```json
{
  "success": true,
  "code": 200,
  "message": "Operation completed successfully",
  "data": {
    "...": "..."
  },
  "operation": "operation_name"
}
```

## API Endpoints

### System

### 1. Root

**GET** `/`

Root endpoint that returns a welcome message and API version information.

**Response:**

### 2. Health Check

**GET** `/health`

Health check endpoint for monitoring service health.

**Response:**

**Response Example:**
```json
{
  "status": "healthy",
  "timestamp": "string",
  "service": "string",
  "version": "string",
  "checks": {}
}
```

### Tenant

### 3. Create Tenant

**POST** `/api/v1/tenants`

Create a new tenant with the specified tenant ID.

This endpoint sets up the necessary database collections and indexes for a new tenant.
The tenant ID in the request body must match the tenant ID extracted from the authentication token.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |

**Request Example:**
```json
{
  "tenantId": "string"
}
```

**Response:**

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### Cart

### 4. Create Cart

**POST** `/api/v1/carts`

Create a new shopping cart.

Initializes a new cart for the current terminal with optional user information
and transaction type.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `transactionType` | integer | No | - |
| `userId` | string | No | - |
| `userName` | string | No | - |

**Request Example:**
```json
{
  "transactionType": 101,
  "userId": "string",
  "userName": "string"
}
```

**Response:**

**data Field:** `CartCreateResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `cartId` | string | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "cartId": "string"
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 5. Get Cart

**GET** `/api/v1/carts/{cart_id}`

Retrieve a cart by its ID.

Fetches the cart with the specified ID and returns its full details.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 6. Bill

**POST** `/api/v1/carts/{cart_id}/bill`

Finalize a cart into a billable transaction.

Completes the cart processing, finalizing the transaction and preparing
it for receipt generation and storage.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 7. Cancel Transaction

**POST** `/api/v1/carts/{cart_id}/cancel`

Cancel a transaction/cart.

Marks the cart as cancelled, preventing further modifications or processing.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 8. Discount To Cart

**POST** `/api/v1/carts/{cart_id}/discounts`

Add discount to the entire cart.

Applies one or more discounts at the cart level, affecting the total price.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Request Body:**

**Request Example:**
```json
[
  {
    "discountType": "string",
    "discountValue": 0.0,
    "discountDetail": "string"
  }
]
```

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 9. Add Items

**POST** `/api/v1/carts/{cart_id}/lineItems`

Add items to a cart.

Adds one or more items to the specified cart.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Request Body:**

**Request Example:**
```json
[
  {
    "itemCode": "string",
    "quantity": 0,
    "unitPrice": 0.0
  }
]
```

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 10. Cancel Line Item

**POST** `/api/v1/carts/{cart_id}/lineItems/{lineNo}/cancel`

Cancel a specific line item in a cart.

Marks the specified line item as cancelled without removing it from the cart.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `lineNo` | integer | Yes | - |
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 11. Add Discount To Line Item

**POST** `/api/v1/carts/{cart_id}/lineItems/{lineNo}/discounts`

Add discount to a specific line item in a cart.

Applies one or more discounts to the specified item in the cart.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `lineNo` | integer | Yes | - |
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Request Body:**

**Request Example:**
```json
[
  {
    "discountType": "string",
    "discountValue": 0.0,
    "discountDetail": "string"
  }
]
```

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 12. Update Item Quantity

**PATCH** `/api/v1/carts/{cart_id}/lineItems/{lineNo}/quantity`

Update the quantity of a cart line item.

Changes the quantity of the specified item in the cart.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `lineNo` | integer | Yes | - |
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `quantity` | integer | Yes | - |

**Request Example:**
```json
{
  "quantity": 0
}
```

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 13. Update Item Unit Price

**PATCH** `/api/v1/carts/{cart_id}/lineItems/{lineNo}/unitPrice`

Update the unit price of a cart line item.

Changes the unit price of the specified item in the cart.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `lineNo` | integer | Yes | - |
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `unitPrice` | number | Yes | - |

**Request Example:**
```json
{
  "unitPrice": 0.0
}
```

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 14. Payments

**POST** `/api/v1/carts/{cart_id}/payments`

Add payments to a cart.

Processes one or more payment methods against the cart.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Request Body:**

**Request Example:**
```json
[
  {
    "paymentCode": "string",
    "amount": 0,
    "detail": "string"
  }
]
```

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 15. Resume Item Entry

**POST** `/api/v1/carts/{cart_id}/resume-item-entry`

Resume item entry from paying state.

Transitions the cart from Paying state back to EnteringItem state,
clearing any payment information and allowing additional items to be added.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 16. Subtotal

**POST** `/api/v1/carts/{cart_id}/subtotal`

Calculate the subtotal for a cart.

Updates the cart with calculated subtotals and tax information.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `cart_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |

**Response:**

**data Field:** `Cart`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |
| `cartId` | string | Yes | - |
| `cartStatus` | string | Yes | - |
| `subtotalAmount` | number | Yes | - |
| `balanceAmount` | number | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### Transaction

### 17. Get Transactions By Query

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions`

Get transactions based on query parameters.

Retrieves a paginated list of transactions matching the specified filters.
The tenant ID in the path must match the tenant ID from the authentication token.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `business_date` | string | No | - | - |
| `open_counter` | integer | No | - | - |
| `transaction_type` | array | No | - | - |
| `receipt_no` | integer | No | - | - |
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `include_cancelled` | boolean | No | False | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | Yes | - | - |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[Tran]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": [
    {
      "tenantId": "string",
      "storeCode": "string",
      "storeName": "string",
      "terminalNo": 0,
      "totalAmount": 0.0,
      "totalAmountWithTax": 0.0,
      "totalQuantity": 0,
      "totalDiscountAmount": 0.0,
      "depositAmount": 0.0,
      "changeAmount": 0.0
    }
  ],
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 18. Get Transaction By Tranasction No

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}`

Get a single transaction by its transaction number.

Retrieves detailed information about a specific transaction identified by its number.
The tenant ID in the path must match the tenant ID from the authentication token.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |
| `transaction_no` | integer | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `Tran`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 19. Notify Delivery Status

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/delivery-status`

Notify the delivery status of a transaction.

Updates the delivery status of a specific transaction based on the provided information.
The terminal making this request must be in the same store as the original transaction.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `event_id` | string | Yes | - |
| `service` | string | Yes | - |
| `status` | string | Yes | - |
| `message` | string | No | - |

**Request Example:**
```json
{
  "event_id": "string",
  "service": "string",
  "status": "string",
  "message": "string"
}
```

**Response:**

**data Field:** `DeliveryStatusUpdateResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `event_id` | string | Yes | - |
| `service` | string | Yes | - |
| `status` | string | Yes | - |
| `success` | boolean | Yes | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "event_id": "string",
    "service": "string",
    "status": "string",
    "success": true
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 20. Return Transaction By Transaction No

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return`

Process a transaction return.

Creates a return transaction based on an original transaction and processes any required refund payments.
The terminal making this request must be in the same store as the original transaction.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |
| `transaction_no` | integer | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

**Request Example:**
```json
[
  {
    "paymentCode": "string",
    "amount": 0,
    "detail": "string"
  }
]
```

**Response:**

**data Field:** `Tran`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 21. Void Transaction By Transaction No

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void`

Void (cancel) a transaction.

Marks a transaction as voided and processes any required refund payments.
The terminal making this request must match the terminal that created the transaction.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |
| `store_code` | string | Yes | - |
| `terminal_no` | integer | Yes | - |
| `transaction_no` | integer | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | Yes | - | - |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

**Request Example:**
```json
[
  {
    "paymentCode": "string",
    "amount": 0,
    "detail": "string"
  }
]
```

**Response:**

**data Field:** `Tran`

| Field | Type | Required | Description |
|------------|------|------|------|
| `tenantId` | string | Yes | - |
| `storeCode` | string | Yes | - |
| `storeName` | string | No | - |
| `terminalNo` | integer | Yes | - |
| `totalAmount` | number | Yes | - |
| `totalAmountWithTax` | number | Yes | - |
| `totalQuantity` | integer | Yes | - |
| `totalDiscountAmount` | number | Yes | - |
| `depositAmount` | number | Yes | - |
| `changeAmount` | number | Yes | - |
| `stampDutyAmount` | number | No | - |
| `receiptNo` | integer | Yes | - |
| `transactionNo` | integer | Yes | - |
| `transactionType` | integer | Yes | - |
| `businessDate` | string | No | - |
| `generateDateTime` | string | No | - |
| `lineItems` | array[BaseTranLineItem] | No | - |
| `payments` | array[BaseTranPayment] | No | - |
| `taxes` | array[BaseTranTax] | No | - |
| `subtotalDiscounts` | array[BaseDiscount] | No | - |
| `receiptText` | string | No | - |
| `journalText` | string | No | - |
| `staff` | BaseTranStaff | No | - |
| `status` | BaseTranStatus | No | - |

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {
    "tenantId": "string",
    "storeCode": "string",
    "storeName": "string",
    "terminalNo": 0,
    "totalAmount": 0.0,
    "totalAmountWithTax": 0.0,
    "totalQuantity": 0,
    "totalDiscountAmount": 0.0,
    "depositAmount": 0.0,
    "changeAmount": 0.0
  },
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### Cache

### 22. Clear terminal cache

**DELETE** `/api/v1/cache/terminal`

Clear all entries from the terminal information cache

**Response:**

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

### 23. Get terminal cache status

**GET** `/api/v1/cache/terminal/status`

Get current status of the terminal information cache

**Response:**

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "string",
  "userError": {
    "code": "string",
    "message": "string"
  },
  "data": {},
  "metadata": {
    "total": 0,
    "page": 0,
    "limit": 0,
    "sort": "string",
    "filter": {}
  },
  "operation": "string"
}
```

## Error Codes

Error responses are returned in the following format:

```json
{
  "success": false,
  "code": 400,
  "message": "Error message",
  "errorCode": "ERROR_CODE",
  "operation": "operation_name"
}
```
