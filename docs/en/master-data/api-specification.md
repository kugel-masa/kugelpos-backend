# Master Data Service API Specification

## Overview

Master Data Service manages all static reference and configuration data in the Kugelpos POS system. It provides centralized management for product catalogs, staff information, payment methods, tax rules, categories, and system settings used across all other services.

## Base URL
- Local environment: `http://localhost:8002`
- Production environment: `https://master-data.{domain}`

## Authentication

Master Data Service supports two authentication methods:

### 1. JWT Token (Bearer Token)
- Include in header: `Authorization: Bearer {token}`
- Obtain token from: Account Service's `/api/v1/accounts/token`
- Required for administrative operations

### 2. API Key Authentication
- Include in header: `X-API-Key: {api_key}`
- Include query parameter: `terminal_id={tenant_id}-{store_code}-{terminal_no}`
- Used for POS terminal read operations

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

## API Endpoints

### Item Management

#### 1. Create Item (Common Master)
**POST** `/api/v1/tenants/{tenant_id}/items`

Create a new item in the common item master.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

**Request Body:**
```json
{
  "itemCode": "ITEM001",
  "description": "Sample Product",
  "descriptionLocal": "サンプル商品",
  "price": 19.99,
  "cost": 10.00,
  "categoryCode": "CAT001",
  "taxCode": "TAX001",
  "itemDetails": "Detailed product information",
  "imageUrl": "https://example.com/item001.jpg",
  "barcode": "4901234567890",
  "isDiscountable": true
}
```

**Field Descriptions:**
- `itemCode` (string, required): Unique item identifier
- `description` (string, required): Item description
- `descriptionLocal` (string, optional): Localized description
- `price` (number, required): Base selling price
- `cost` (number, optional): Item cost
- `categoryCode` (string, optional): Category assignment
- `taxCode` (string, optional): Tax rule code
- `itemDetails` (string, optional): Extended description
- `imageUrl` (string, optional): Product image URL
- `barcode` (string, optional): Item barcode
- `isDiscountable` (boolean, optional): Allow discounts (default: true)

**Request Example:**
```bash
curl -X POST "http://localhost:8002/api/v1/tenants/tenant001/items" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "itemCode": "ITEM001",
    "description": "Sample Product",
    "price": 19.99,
    "categoryCode": "CAT001",
    "taxCode": "TAX001"
  }'
```

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Item created successfully",
  "data": {
    "itemCode": "ITEM001",
    "description": "Sample Product",
    "descriptionLocal": "サンプル商品",
    "price": 19.99,
    "cost": 10.00,
    "categoryCode": "CAT001",
    "taxCode": "TAX001",
    "isDiscountable": true,
    "isDeleted": false,
    "createdAt": "2024-01-01T10:00:00Z",
    "updatedAt": "2024-01-01T10:00:00Z"
  },
  "operation": "create_item"
}
```

#### 2. Get Item List
**GET** `/api/v1/tenants/{tenant_id}/items`

Retrieve paginated list of items with optional filtering and sorting.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

**Query Parameters:**
- `terminal_id` (string, optional): Terminal ID for API key authentication
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 20, max: 100): Items per page
- `sort` (string, optional): Sort field and order (e.g., "itemCode:asc", "price:desc")
- `categoryCode` (string, optional): Filter by category
- `isDeleted` (boolean, optional): Include deleted items

**Request Example:**
```bash
curl -X GET "http://localhost:8002/api/v1/tenants/tenant001/items?page=1&limit=50&sort=itemCode:asc&categoryCode=CAT001" \
  -H "Authorization: Bearer {token}"
```

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Items retrieved successfully",
  "data": {
    "data": [
      {
        "itemCode": "ITEM001",
        "description": "Sample Product",
        "price": 19.99,
        "categoryCode": "CAT001",
        "taxCode": "TAX001",
        "isDiscountable": true,
        "isDeleted": false
      }
    ],
    "metadata": {
      "total": 150,
      "page": 1,
      "limit": 50,
      "sort": "itemCode:asc",
      "filter": {"categoryCode": "CAT001"}
    }
  },
  "operation": "get_items"
}
```

#### 3. Get Item Details
**GET** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Retrieve detailed information for a specific item.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `item_code` (string, required): Item code

**Query Parameters:**
- `terminal_id` (string, optional): Terminal ID for API key authentication

**Request Example:**
```bash
curl -X GET "http://localhost:8002/api/v1/tenants/tenant001/items/ITEM001" \
  -H "X-API-Key: {api_key}"
```

#### 4. Update Item
**PUT** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Update item information.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `item_code` (string, required): Item code

**Request Body:**
```json
{
  "description": "Updated Product Name",
  "price": 24.99,
  "categoryCode": "CAT002",
  "isDiscountable": false
}
```

**Note:** Only provided fields will be updated.

#### 5. Delete Item (Logical)
**DELETE** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Logically delete an item (sets isDeleted flag).

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `item_code` (string, required): Item code

### Store-Specific Item Management

#### 6. Create/Update Store Item
**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items`

Create or update store-specific item attributes (primarily pricing).

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

**Request Body:**
```json
{
  "itemCode": "ITEM001",
  "price": 22.99
}
```

**Field Descriptions:**
- `itemCode` (string, required): Item code (must exist in common master)
- `price` (number, required): Store-specific price override

#### 7. Get Store Item List
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items`

Retrieve items with store-specific pricing.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `store_code` (string, required): Store code

**Query Parameters:**
- Same as common item list endpoint

#### 8. Get Store Item Details
**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}`

Retrieve item details with store-specific attributes merged.

### Staff Management

#### 9. Create Staff
**POST** `/api/v1/tenants/{tenant_id}/staff`

Create a new staff member.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

**Request Body:**
```json
{
  "staffId": "STF001",
  "name": "John Doe",
  "nameLocal": "ジョン・ドウ",
  "pin": "1234",
  "role": "Cashier",
  "email": "john.doe@example.com",
  "phone": "555-0123",
  "isActive": true
}
```

**Field Descriptions:**
- `staffId` (string, required): Unique staff identifier
- `name` (string, required): Staff display name
- `nameLocal` (string, optional): Localized name
- `pin` (string, required): 4-6 digit PIN for authentication
- `role` (string, optional): Staff role or position
- `email` (string, optional): Contact email
- `phone` (string, optional): Contact phone
- `isActive` (boolean, optional): Active status (default: true)

**Request Example:**
```bash
curl -X POST "http://localhost:8002/api/v1/tenants/tenant001/staff" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "staffId": "STF001",
    "name": "John Doe",
    "pin": "1234",
    "role": "Cashier"
  }'
```

#### 10. Get Staff List
**GET** `/api/v1/tenants/{tenant_id}/staff`

Retrieve list of staff members.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 20): Items per page
- `sort` (string, optional): Sort field and order
- `isActive` (boolean, optional): Filter by active status

#### 11. Get Staff Details
**GET** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Retrieve specific staff member details.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `staff_id` (string, required): Staff identifier

#### 12. Update Staff
**PUT** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Update staff information.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `staff_id` (string, required): Staff identifier

**Request Body:**
```json
{
  "name": "John Smith",
  "role": "Senior Cashier",
  "pin": "5678",
  "isActive": true
}
```

#### 13. Delete Staff
**DELETE** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Delete a staff member.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier
- `staff_id` (string, required): Staff identifier

### Payment Method Management

#### 14. Create Payment Method
**POST** `/api/v1/tenants/{tenant_id}/payments`

Create a new payment method.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

**Request Body:**
```json
{
  "paymentCode": "01",
  "description": "Cash",
  "descriptionLocal": "現金",
  "canRefund": true,
  "canDepositOver": true,
  "canChange": true,
  "limitAmount": 10000.00,
  "isActive": true
}
```

**Field Descriptions:**
- `paymentCode` (string, required): Unique payment method code
- `description` (string, required): Payment method name
- `descriptionLocal` (string, optional): Localized name
- `canRefund` (boolean, optional): Allow refunds (default: true)
- `canDepositOver` (boolean, optional): Allow overpayment (default: false)
- `canChange` (boolean, optional): Give change (default: false)
- `limitAmount` (number, optional): Maximum transaction amount
- `isActive` (boolean, optional): Active status (default: true)

#### 16. Get Payment Method List
**GET** `/api/v1/tenants/{tenant_id}/payments`

Retrieve list of payment methods.

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 20): Items per page
- `isActive` (boolean, optional): Filter by active status

#### 17. Get Payment Method Details
**GET** `/api/v1/tenants/{tenant_id}/payments/{payment_code}`

Retrieve specific payment method details.

#### 18. Update Payment Method
**PUT** `/api/v1/tenants/{tenant_id}/payments/{payment_code}`

Update payment method configuration.

#### 19. Delete Payment Method
**DELETE** `/api/v1/tenants/{tenant_id}/payments/{payment_code}`

Delete a payment method.

### Tax Rule Management

#### 20. Get Tax Rule List
**GET** `/api/v1/tenants/{tenant_id}/taxes`

Retrieve list of tax rules.

**Path Parameters:**
- `tenant_id` (string, required): Tenant identifier

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 20): Items per page
- `effectiveDate` (string, optional): Filter by effective date (YYYY-MM-DD)

**Response Example:**
```json
{
  "success": true,
  "code": 200,
  "message": "Tax rules retrieved successfully",
  "data": {
    "data": [
      {
        "taxCode": "TAX001",
        "description": "Standard Tax",
        "rate": 0.10,
        "effectiveFrom": "2024-01-01",
        "effectiveTo": null,
        "isInclusive": false
      }
    ],
    "metadata": {
      "total": 5,
      "page": 1,
      "limit": 20
    }
  },
  "operation": "get_taxes"
}
```

### Category Management

#### 21. Create Category
**POST** `/api/v1/tenants/{tenant_id}/categories`

Create a new product category.

**Request Body:**
```json
{
  "categoryCode": "CAT001",
  "description": "Electronics",
  "descriptionShort": "Elec",
  "descriptionLocal": "電子機器",
  "taxCode": "TAX001",
  "parentCode": null
}
```

**Field Descriptions:**
- `categoryCode` (string, required): Unique category code
- `description` (string, required): Category name
- `descriptionShort` (string, optional): Abbreviated name
- `descriptionLocal` (string, optional): Localized name
- `taxCode` (string, optional): Default tax code
- `parentCode` (string, optional): Parent category for hierarchy

#### 22. Get Category List
**GET** `/api/v1/tenants/{tenant_id}/categories`

Retrieve list of categories.

**Query Parameters:**
- `page` (integer, default: 1): Page number
- `limit` (integer, default: 20): Items per page
- `parentCode` (string, optional): Filter by parent category

#### 23. Get Category Details
**GET** `/api/v1/tenants/{tenant_id}/categories/{category_code}`

Retrieve specific category details.

#### 24. Update Category
**PUT** `/api/v1/tenants/{tenant_id}/categories/{category_code}`

Update category information.

#### 25. Delete Category
**DELETE** `/api/v1/tenants/{tenant_id}/categories/{category_code}`

Delete a category.

### Settings Management

#### 26. Get Settings
**GET** `/api/v1/tenants/{tenant_id}/settings`

Retrieve system settings.

**Query Parameters:**
- `scope` (string, optional): Filter by scope (system, store, terminal)
- `storeCode` (string, optional): Filter by store
- `terminalNo` (string, optional): Filter by terminal

#### 27. Update Settings
**PUT** `/api/v1/tenants/{tenant_id}/settings`

Update system settings.

**Request Body:**
```json
{
  "settings": {
    "receipt.header": "Welcome to Our Store",
    "receipt.footer": "Thank You!",
    "tax.calculate": "exclusive",
    "discount.maxPercent": "20"
  },
  "scope": "store",
  "storeCode": "store001"
}
```

### Book Item Management

#### 28. Create/Update Book Item
**POST** `/api/v1/tenants/{tenant_id}/books`

Create or update book-specific item attributes.

**Request Body:**
```json
{
  "itemCode": "BOOK001",
  "isbn": "978-1234567890",
  "author": "John Author",
  "publisher": "Sample Publisher",
  "publicationDate": "2024-01-01",
  "genre": "Fiction"
}
```

### Tenant Management

#### 29. Create Tenant
**POST** `/api/v1/tenants`

Initialize master data service for a new tenant.

**Request Body:**
```json
{
  "tenantId": "tenant001"
}
```

**Authentication:** Requires JWT token

**Response Example:**
```json
{
  "success": true,
  "code": 201,
  "message": "Tenant creation completed: tenant001",
  "data": {
    "tenantId": "tenant001",
    "collectionsCreated": [
      "staff_master",
      "item_common_master",
      "item_store_master",
      "item_book_master",
      "category_master",
      "tax_master",
      "payment_master",
      "settings_master"
    ]
  },
  "operation": "create_tenant"
}
```

## System Endpoints

### 30. Health Check
**GET** `/health`

Check service health and database connectivity.

**Request Example:**
```bash
curl -X GET "http://localhost:8002/health"
```

**Response Example:**
```json
{
  "status": "healthy",
  "service": "master-data",
  "version": "1.0.0",
  "checks": {
    "mongodb": {
      "status": "healthy",
      "details": {
        "ping_time": 0.001234,
        "connection_string": "mongodb://..."
      }
    }
  }
}
```

## Error Responses

The API uses standard HTTP status codes and structured error responses:

```json
{
  "success": false,
  "code": 404,
  "message": "Item not found: ITEM999",
  "data": null,
  "operation": "get_item"
}
```

### Common Status Codes
- `200` - Success
- `201` - Created successfully
- `400` - Bad request
- `401` - Authentication error
- `403` - Access denied
- `404` - Resource not found
- `409` - Conflict (duplicate)
- `500` - Internal server error

### Error Code System

Master Data Service uses error codes in the 30XXX range:

- `30001` - Item not found
- `30002` - Staff not found
- `30003` - Payment method not found
- `30004` - Category not found
- `30005` - Tax rule not found
- `30006` - Duplicate item code
- `30007` - Duplicate staff ID
- `30008` - Invalid PIN format
- `30009` - Settings update error
- `30099` - General master data error

## Pagination

All list endpoints support pagination with metadata:

```json
{
  "data": [...],
  "metadata": {
    "total": 500,
    "page": 1,
    "limit": 20,
    "sort": "itemCode:asc",
    "filter": {...}
  }
}
```

## Sorting

List endpoints support sorting with format: `field:direction`
- Direction: `asc` (ascending) or `desc` (descending)
- Example: `sort=price:desc,itemCode:asc`

## Notes

1. **Multi-tenancy**: All operations are tenant-scoped
2. **CamelCase Convention**: All JSON fields use camelCase
3. **Timestamps**: All timestamps are in ISO 8601 format (UTC)
4. **Logical Deletion**: Items support soft delete with `isDeleted` flag
5. **PIN Security**: PINs are hashed before storage
6. **Price Override**: Store-specific prices override common prices
7. **Validation**: Comprehensive input validation on all endpoints