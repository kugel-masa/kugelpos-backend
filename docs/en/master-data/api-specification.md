# Master Data Service API Specification

## Overview

The Master Data service is a RESTful API service that manages reference data essential to the Kugelpos POS system. It centrally manages static data such as staff information, product master data, payment methods, tax settings, and system configurations, providing them to other services.

## Base URL
- Local environment: `http://localhost:8002`
- Production environment: `https://master-data.{domain}`

## Authentication

The Master Data service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Header: `Authorization: Bearer {token}`
- Purpose: Master data management by administrators

### 2. API Key Authentication
- Header: `X-API-Key: {api_key}`
- Purpose: Master data reading from terminals

## Field Format

All API requests/responses use **camelCase** format.

## Common Response Format

```json
{
  "success": true,
  "code": 200,
  "message": "Operation completed successfully",
  "data": { ... },
  "operation": "function_name"
}
```

## API Endpoints

### Staff Master Management

#### 1. Create Staff
**POST** `/api/v1/tenants/{tenant_id}/staff`

Registers a new staff member.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

**Request Body:**
```json
{
  "staffId": "STF001",
  "name": "Yamada Taro",
  "pin": "1234",
  "roles": ["cashier", "manager"]
}
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Staff created successfully",
  "data": {
    "staffId": "STF001",
    "name": "Yamada Taro",
    "roles": ["cashier", "manager"]
  },
  "operation": "create_staff"
}
```

#### 2. Get Staff
**GET** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Retrieves specific staff information.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `staff_id` (string, required): Staff ID

#### 3. Get Staff List
**GET** `/api/v1/tenants/{tenant_id}/staff`

Retrieves staff list.

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 100, max: 1000): Page size
- `sort` (string): Sort conditions

#### 4. Update Staff
**PUT** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Updates staff information.

#### 5. Delete Staff
**DELETE** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Deletes a staff member.

### Product Master Management

#### 6. Create Item
**POST** `/api/v1/tenants/{tenant_id}/items`

Registers a new product.

**Request Body:**
```json
{
  "itemCode": "ITEM001",
  "description": "Coffee (Hot)",
  "shortDescription": "Coffee",
  "detailDescription": "Blend Coffee",
  "unitPrice": 300.00,
  "unitCost": 100.00,
  "categoryCode": "BEVERAGE",
  "taxCode": "TAX_10",
  "itemDetails": [
    {"name": "size", "value": "regular"},
    {"name": "temperature", "value": "hot"}
  ],
  "imageUrls": ["https://example.com/coffee.jpg"],
  "isDiscountRestricted": false
}
```

#### 7. Get Item
**GET** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Retrieves specific product information.

#### 8. Get Item List
**GET** `/api/v1/tenants/{tenant_id}/items`

Retrieves product list.

**Query Parameters:**
- `page` (integer): Page number
- `limit` (integer): Page size
- `sort` (string): Sort conditions

#### 9. Update Item
**PUT** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Updates product information.

#### 10. Delete Item
**DELETE** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Deletes a product.

### Store-specific Product Master Management

#### 11. Set Store-specific Price
**POST** `/api/v1/tenants/{tenant_id}/item_stores`

Sets store-specific product pricing.

**Request Body:**
```json
{
  "storeCode": "STORE001",
  "itemCode": "ITEM001",
  "storePrice": 280.00
}
```

### Item Book Master Management

#### 12. Get Item Book
**GET** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}`

Retrieves POS screen UI hierarchy (categories/tabs/buttons).

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Item book retrieved successfully",
  "data": {
    "itemBookId": "BOOK001",
    "title": "Standard Layout",
    "categories": [
      {
        "categoryNumber": 1,
        "title": "Drinks",
        "tabs": [
          {
            "tabNumber": 1,
            "title": "Hot",
            "buttons": [
              {
                "posX": 0,
                "posY": 0,
                "sizeX": 1,
                "sizeY": 1,
                "itemCode": "ITEM001",
                "title": "Coffee",
                "color": "#8B4513"
              }
            ]
          }
        ]
      }
    ]
  },
  "operation": "get_item_book"
}
```

### Payment Method Master Management

#### 13. Get Payment Methods
**GET** `/api/v1/tenants/{tenant_id}/payments`

Retrieves available payment methods.

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Payment methods retrieved successfully",
  "data": [
    {
      "paymentCode": "CASH",
      "description": "Cash",
      "limitAmount": null,
      "canRefund": true,
      "canDepositOver": true,
      "canChange": true
    },
    {
      "paymentCode": "CREDIT",
      "description": "Credit Card",
      "limitAmount": 1000000,
      "canRefund": true,
      "canDepositOver": false,
      "canChange": false
    }
  ],
  "operation": "get_payment_methods"
}
```

### Configuration Master Management

#### 14. Get Setting Value
**GET** `/api/v1/tenants/{tenant_id}/settings/{name}/value`

Retrieves hierarchical configuration values (priority: global → store → terminal).

**Query Parameters:**
- `store_code` (string): Store code
- `terminal_no` (integer): Terminal number

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Setting value retrieved successfully",
  "data": {
    "name": "receipt_print_count",
    "value": "2",
    "scope": "store"
  },
  "operation": "get_setting_value"
}
```

### Category Master Management

#### 15. Get Categories
**GET** `/api/v1/tenants/{tenant_id}/categories`

Retrieves product category hierarchy.

### Tax Master Management

#### 16. Get Tax Settings
**GET** `/api/v1/tenants/{tenant_id}/taxes`

Retrieves tax rate settings.

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Tax settings retrieved successfully",  
  "data": [
    {
      "taxCode": "TAX_10",
      "taxType": "STANDARD",
      "taxName": "Standard Tax Rate",
      "rate": 10.0,
      "roundDigit": 0,
      "roundMethod": "ROUND"
    },
    {
      "taxCode": "TAX_8",
      "taxType": "REDUCED",
      "taxName": "Reduced Tax Rate",
      "rate": 8.0,
      "roundDigit": 0,
      "roundMethod": "ROUND"
    }
  ],
  "operation": "get_tax_settings"
}
```

### System Management

#### 17. Initialize Tenant
**POST** `/api/v1/tenants`

Initializes master data for a new tenant.

**Request Body:**
```json
{
  "tenantId": "tenant001"
}
```

**Authentication:** JWT token required

#### 18. Health Check
**GET** `/health`

Checks service health.

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Service is healthy",
  "data": {
    "status": "healthy",
    "mongodb": "connected"
  },
  "operation": "health_check"
}
```

## Pagination

List retrieval endpoints support common pagination format:

**Response Metadata:**
```json
{
  "metadata": {
    "total": 150,
    "page": 1,
    "limit": 50,
    "pages": 3
  }
}
```

## Error Codes

Master Data service uses error codes in the 30XXX range:

- `30001`: Resource not found
- `30002`: Validation error
- `30003`: Duplicate error
- `30004`: Authentication error
- `30005`: Authorization error
- `30099`: General service error

## Special Notes

1. **Multi-tenant Support**: All operations are executed within tenant scope
2. **Hierarchical Settings**: Setting values are resolved with priority: global → store → terminal
3. **PIN Hashing**: Staff PINs are hashed with bcrypt before storage
4. **Soft Delete**: Data is deactivated rather than physically deleted
5. **camelCase Conversion**: Internal snake_case is automatically converted to camelCase