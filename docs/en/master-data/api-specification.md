# Master Data Service API Specification

## Overview

Manages reference data including product master, payment methods, tax settings, and staff information.

## Service Information

- **Port**: 8002
- **Framework**: FastAPI
- **Database**: MongoDB (Motor async driver)

## Base URL

- Local Environment: `http://localhost:8002`
- Production Environment: `https://master-data.{domain}`

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

Root endpoint that returns a welcome message.

This endpoint serves as a simple health check to verify that the service is running
and responding to requests. It can be used by monitoring tools or load balancers
to determine if the service is available.

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

Setup the database for the tenant. This will create the required collections and indexes.

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

### 4. Get Categories

**GET** `/api/v1/tenants/{tenant_id}/categories`

Retrieve all product categories for a tenant.

This endpoint returns a paginated list of all categories for the specified tenant.
The results can be sorted and paginated as needed. This is typically used to populate
category selection screens or to view all available categories for administration.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[CategoryMasterResponse]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
      "categoryCode": "string",
      "description": "string",
      "descriptionShort": "string",
      "taxCode": "string",
      "entryDatetime": "string",
      "lastUpdateDatetime": "string"
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

### 5. Create Category

**POST** `/api/v1/tenants/{tenant_id}/categories`

Create a new product category record.

This endpoint allows creating a new category with its code, description,
short description, and associated tax code. Categories are used to organize
products and can have implications for tax calculations.

Categories provide a hierarchical structure for products in the POS system,
making it easier to organize and find items during sales operations.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |

**Request Example:**
```json
{
  "categoryCode": "string",
  "description": "string",
  "descriptionShort": "string",
  "taxCode": "string"
}
```

**Response:**

**data Field:** `CategoryMasterResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "categoryCode": "string",
    "description": "string",
    "descriptionShort": "string",
    "taxCode": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 6. Get Category

**GET** `/api/v1/tenants/{tenant_id}/categories/{category_code}`

Retrieve a specific product category by its code.

This endpoint retrieves the details of a category identified by its unique code.
It returns all attributes of the category including its description and tax code.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `category_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `CategoryMasterResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "categoryCode": "string",
    "description": "string",
    "descriptionShort": "string",
    "taxCode": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 7. Update Category

**PUT** `/api/v1/tenants/{tenant_id}/categories/{category_code}`

Update an existing product category.

This endpoint allows updating the details of an existing category identified
by its code. It can be used to modify the description, short description, or tax code.

The category_code itself cannot be changed, as it serves as a unique identifier.
Updating a category will affect all products assigned to this category.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `category_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |

**Request Example:**
```json
{
  "description": "string",
  "descriptionShort": "string",
  "taxCode": "string"
}
```

**Response:**

**data Field:** `CategoryMasterResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |
| `description` | string | Yes | - |
| `descriptionShort` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "categoryCode": "string",
    "description": "string",
    "descriptionShort": "string",
    "taxCode": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 8. Delete Category

**DELETE** `/api/v1/tenants/{tenant_id}/categories/{category_code}`

Delete a product category.

This endpoint allows removing a category completely from the system.
Caution should be exercised as deleting categories that have products assigned
to them may cause inconsistencies in the data. It's recommended to reassign
products to other categories before deleting a category.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `category_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `CategoryMasterDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `categoryCode` | string | Yes | - |

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
    "categoryCode": "string"
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

### 9. Get All Item Books

**GET** `/api/v1/tenants/{tenant_id}/item_books`

Retrieve all item book records for a tenant.

This endpoint returns a paginated list of item book records for the specified tenant.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[ItemBookResponse]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
      "title": "string",
      "categories": [],
      "itemBookId": "string",
      "entryDatetime": "string",
      "lastUpdateDatetime": "string"
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

### 10. Create Item Book

**POST** `/api/v1/tenants/{tenant_id}/item_books`

Create a new item book record.

This endpoint allows creating a new item book with its details including title and categories.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Input] | No | - |

**Request Example:**
```json
{
  "title": "string",
  "categories": []
}
```

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 11. Get Item Book By Id

**GET** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}`

Retrieve an item book record by its ID.

This endpoint retrieves the details of an item book identified by its unique ID.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `store_code` | string | No | - | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 12. Update Item Book

**PUT** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}`

Update an existing item book record.

This endpoint allows updating the details of an existing item book identified
by its ID. Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Input] | No | - |

**Request Example:**
```json
{
  "title": "string",
  "categories": []
}
```

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 13. Delete Item Book

**DELETE** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}`

Delete an item book record.

This endpoint allows removing an item book identified by its unique ID.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemBookDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemBookId` | string | Yes | - |

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
    "itemBookId": "string"
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

### 14. Add Category To Item Book

**POST** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories`

Add a category to an item book.

This endpoint allows adding a new category to an existing item book identified by its ID.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `categoryNumber` | integer | Yes | - |
| `title` | string | Yes | - |
| `color` | string | Yes | - |
| `tabs` | array[BaseItemBookTab-Input] | No | - |

**Request Example:**
```json
{
  "categoryNumber": 0,
  "title": "string",
  "color": "string",
  "tabs": []
}
```

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 15. Update Category In Item Book

**PUT** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}`

Update a category in an item book.

This endpoint allows updating an existing category in an item book identified by its ID and category number.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `categoryNumber` | integer | Yes | - |
| `title` | string | Yes | - |
| `color` | string | Yes | - |
| `tabs` | array[BaseItemBookTab-Input] | No | - |

**Request Example:**
```json
{
  "categoryNumber": 0,
  "title": "string",
  "color": "string",
  "tabs": []
}
```

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 16. Delete Category From Item Book

**DELETE** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}`

Delete a category from an item book.

This endpoint allows removing a category from an item book identified by its ID and category number.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemBookCategoryDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemBookId` | string | Yes | - |
| `categoryNumber` | integer | Yes | - |

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
    "itemBookId": "string",
    "categoryNumber": 0
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

### 17. Add Tab To Category In Item Book

**POST** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs`

Add a tab to a category in an item book.

This endpoint allows adding a new tab to an existing category in an item book identified by its ID and category number.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `tabNumber` | integer | Yes | - |
| `title` | string | Yes | - |
| `color` | string | Yes | - |
| `buttons` | array[BaseItemBookButton] | No | - |

**Request Example:**
```json
{
  "tabNumber": 0,
  "title": "string",
  "color": "string",
  "buttons": []
}
```

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 18. Update Tab In Category In Item Book

**PUT** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}`

Update a tab in a category in an item book.

This endpoint allows updating an existing tab in a category in an item book identified by its ID, category number, and tab number.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `tabNumber` | integer | Yes | - |
| `title` | string | Yes | - |
| `color` | string | Yes | - |
| `buttons` | array[BaseItemBookButton] | No | - |

**Request Example:**
```json
{
  "tabNumber": 0,
  "title": "string",
  "color": "string",
  "buttons": []
}
```

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 19. Delete Tab From Category In Item Book

**DELETE** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}`

Delete a tab from a category in an item book.

This endpoint allows removing a tab from a category in an item book identified by its ID, category number, and tab number.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemBookTabDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemBookId` | string | Yes | - |
| `categoryNumber` | integer | Yes | - |
| `tabNumber` | integer | Yes | - |

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
    "itemBookId": "string",
    "categoryNumber": 0,
    "tabNumber": 0
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

### 20. Add Button To Tab In Category In Item Book

**POST** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons`

Add a button to a tab in a category in an item book.

This endpoint allows adding a new button to an existing tab in a category in an item book identified by its ID, category number, and tab number.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `posX` | integer | Yes | - |
| `posY` | integer | Yes | - |
| `size` | ButtonSize | Yes | - |
| `imageUrl` | string | Yes | - |
| `colorText` | string | Yes | - |
| `itemCode` | string | Yes | - |
| `unitPrice` | number | No | - |
| `description` | string | No | - |

**Request Example:**
```json
{
  "posX": 0,
  "posY": 0,
  "size": "Single",
  "imageUrl": "string",
  "colorText": "string",
  "itemCode": "string",
  "unitPrice": 0.0,
  "description": "string"
}
```

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 21. Update Button In Tab In Category In Item Book

**PUT** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons/pos_x/{pos_x}/pos_y/{pos_y}`

Update a button in a tab in a category in an item book.

This endpoint allows updating an existing button in a tab in a category in an item book identified by its ID, category number, tab number, and button position.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `pos_x` | integer | Yes | - |
| `pos_y` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `posX` | integer | Yes | - |
| `posY` | integer | Yes | - |
| `size` | ButtonSize | Yes | - |
| `imageUrl` | string | Yes | - |
| `colorText` | string | Yes | - |
| `itemCode` | string | Yes | - |
| `unitPrice` | number | No | - |
| `description` | string | No | - |

**Request Example:**
```json
{
  "posX": 0,
  "posY": 0,
  "size": "Single",
  "imageUrl": "string",
  "colorText": "string",
  "itemCode": "string",
  "unitPrice": 0.0,
  "description": "string"
}
```

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 22. Delete Button From Tab In Category In Item Book

**DELETE** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons/pos_x/{pos_x}/pos_y/{pos_y}`

Delete a button from a tab in a category in an item book.

This endpoint allows removing a button from a tab in a category in an item book identified by its ID, category number, tab number, and button position.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `category_number` | integer | Yes | - |
| `tab_number` | integer | Yes | - |
| `pos_x` | integer | Yes | - |
| `pos_y` | integer | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemBookButtonDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemBookId` | string | Yes | - |
| `categoryNumber` | integer | Yes | - |
| `tabNumber` | integer | Yes | - |
| `posX` | integer | Yes | - |
| `posY` | integer | Yes | - |

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
    "itemBookId": "string",
    "categoryNumber": 0,
    "tabNumber": 0,
    "posX": 0,
    "posY": 0
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

### 23. Get Item Book Detail By Id

**GET** `/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/detail`

Retrieve detailed information of an item book by its ID.

This endpoint retrieves detailed information of an item book identified by its unique ID.
Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_book_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `store_code` | string | Yes | - | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemBookResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `title` | string | Yes | - |
| `categories` | array[BaseItemBookCategory-Output] | No | - |
| `itemBookId` | string | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "title": "string",
    "categories": [],
    "itemBookId": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 24. Get Item Master All Async

**GET** `/api/v1/tenants/{tenant_id}/items`

Retrieve all item master records for a tenant.

This endpoint returns a paginated list of all active items for the specified tenant.
The results can be sorted and paginated as needed. Optionally filter by category code.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `category_code` | string | No | - | Filter by category code |
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[ItemResponse]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
      "itemCode": "string",
      "description": "string",
      "unitPrice": 0.0,
      "unitCost": 0.0,
      "itemDetails": [
        "string"
      ],
      "imageUrls": [
        "string"
      ],
      "categoryCode": "string",
      "taxCode": "string",
      "isDiscountRestricted": true,
      "isDeleted": true
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

### 25. Create Item Master Async

**POST** `/api/v1/tenants/{tenant_id}/items`

Create a new item master record.

This endpoint allows creating a new item with common attributes like code,
description, price, cost, and category. These items are tenant-specific and
can be used across all stores within the tenant.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | No | - |

**Request Example:**
```json
{
  "itemCode": "string",
  "description": "string",
  "unitPrice": 0.0,
  "unitCost": 0.0,
  "itemDetails": [
    "string"
  ],
  "imageUrls": [
    "string"
  ],
  "categoryCode": "string",
  "taxCode": "string",
  "isDiscountRestricted": false
}
```

**Response:**

**data Field:** `ItemResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "itemCode": "string",
    "description": "string",
    "unitPrice": 0.0,
    "unitCost": 0.0,
    "itemDetails": [
      "string"
    ],
    "imageUrls": [
      "string"
    ],
    "categoryCode": "string",
    "taxCode": "string",
    "isDiscountRestricted": true,
    "isDeleted": true
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

### 26. Get Item Master Async

**GET** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Retrieve a specific item master record by its code.

This endpoint retrieves the details of an item identified by its unique code.
By default, it only returns active items, but setting is_logical_deleted to true
allows retrieving logically deleted items as well.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `is_logical_deleted` | boolean | No | False | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "itemCode": "string",
    "description": "string",
    "unitPrice": 0.0,
    "unitCost": 0.0,
    "itemDetails": [
      "string"
    ],
    "imageUrls": [
      "string"
    ],
    "categoryCode": "string",
    "taxCode": "string",
    "isDiscountRestricted": true,
    "isDeleted": true
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

### 27. Update Item Master Async

**PUT** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Update an existing item master record.

This endpoint allows updating the details of an existing item identified by its code.
Only the provided fields will be updated, and the item_code cannot be changed.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | No | - |

**Request Example:**
```json
{
  "description": "string",
  "unitPrice": 0.0,
  "unitCost": 0.0,
  "itemDetails": [
    "string"
  ],
  "imageUrls": [
    "string"
  ],
  "categoryCode": "string",
  "taxCode": "string",
  "isDiscountRestricted": false
}
```

**Response:**

**data Field:** `ItemResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "itemCode": "string",
    "description": "string",
    "unitPrice": 0.0,
    "unitCost": 0.0,
    "itemDetails": [
      "string"
    ],
    "imageUrls": [
      "string"
    ],
    "categoryCode": "string",
    "taxCode": "string",
    "isDiscountRestricted": true,
    "isDeleted": true
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

### 28. Delete Item Master Async

**DELETE** `/api/v1/tenants/{tenant_id}/items/{item_code}`

Delete an item master record.

This endpoint allows deleting an item either logically or physically.
Logical deletion marks the item as deleted but keeps it in the database,
while physical deletion completely removes it from the database.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `is_logical` | boolean | No | False | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `isLogical` | boolean | Yes | - |

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
    "itemCode": "string",
    "isLogical": true
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

### 29. Get All Payments

**GET** `/api/v1/tenants/{tenant_id}/payments`

Retrieve all payment methods for a tenant.

This endpoint returns a paginated list of all payment methods for the specified tenant.
The results can be sorted and paginated as needed. This is typically used to populate
payment method selection screens or to view all available payment methods for administration.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[PaymentResponse]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
      "paymentCode": "string",
      "description": "string",
      "limitAmount": 0.0,
      "canRefund": true,
      "canDepositOver": true,
      "canChange": true,
      "isActive": true,
      "entryDatetime": "string",
      "lastUpdateDatetime": "string"
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

### 30. Create Payment

**POST** `/api/v1/tenants/{tenant_id}/payments`

Create a new payment method record.

This endpoint allows creating a new payment method with its code, description,
and various flags that control its behavior in the POS system such as whether
it can handle refunds, allow deposits over the amount, give change, etc.

Payment methods are essential for transaction processing and define how sales
are settled in the POS system (cash, credit card, gift card, etc.).

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |

**Request Example:**
```json
{
  "paymentCode": "string",
  "description": "string",
  "limitAmount": 0.0,
  "canRefund": true,
  "canDepositOver": true,
  "canChange": true,
  "isActive": true
}
```

**Response:**

**data Field:** `PaymentResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "paymentCode": "string",
    "description": "string",
    "limitAmount": 0.0,
    "canRefund": true,
    "canDepositOver": true,
    "canChange": true,
    "isActive": true,
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 31. Get Payment

**GET** `/api/v1/tenants/{tenant_id}/payments/{payment_code}`

Retrieve a specific payment method by its code.

This endpoint retrieves the details of a payment method identified by its unique code.
It returns all attributes of the payment method including its description and behavior flags.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `payment_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `PaymentResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "paymentCode": "string",
    "description": "string",
    "limitAmount": 0.0,
    "canRefund": true,
    "canDepositOver": true,
    "canChange": true,
    "isActive": true,
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 32. Update Payment

**PUT** `/api/v1/tenants/{tenant_id}/payments/{payment_code}`

Update an existing payment method.

This endpoint allows updating the details of an existing payment method identified
by its code. It can be used to modify the description, limit amount, or behavior flags
such as whether the payment method can be used for refunds or allows giving change.

The payment_code itself cannot be changed, as it serves as a unique identifier.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `payment_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |

**Request Example:**
```json
{
  "description": "string",
  "limitAmount": 0.0,
  "canRefund": true,
  "canDepositOver": true,
  "canChange": true,
  "isActive": true
}
```

**Response:**

**data Field:** `PaymentResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |
| `description` | string | Yes | - |
| `limitAmount` | number | Yes | - |
| `canRefund` | boolean | Yes | - |
| `canDepositOver` | boolean | Yes | - |
| `canChange` | boolean | Yes | - |
| `isActive` | boolean | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "paymentCode": "string",
    "description": "string",
    "limitAmount": 0.0,
    "canRefund": true,
    "canDepositOver": true,
    "canChange": true,
    "isActive": true,
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 33. Delete Payment

**DELETE** `/api/v1/tenants/{tenant_id}/payments/{payment_code}`

Delete a payment method.

This endpoint allows removing a payment method completely from the system.
Caution should be exercised as deleting payment methods that were used in
past transactions can cause reporting and analysis issues.

It's generally recommended to deactivate payment methods (setting is_active to false)
rather than deleting them if they have been used in transactions.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `payment_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `PaymentDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `paymentCode` | string | Yes | - |

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
    "paymentCode": "string"
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

### 34. Get Settings Master Async

**GET** `/api/v1/tenants/{tenant_id}/settings`

Retrieve all system settings for a tenant.

This endpoint returns a paginated list of all settings for the specified tenant.
The results can be sorted and paginated as needed. This is typically used by
administrative interfaces to view and manage all system settings.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[SettingsMasterResponse]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
      "name": "string",
      "defaultValue": "string",
      "values": [
        {
          "storeCode": "string",
          "terminalNo": 0,
          "value": "string"
        }
      ],
      "entryDatetime": "string",
      "lastUpdateDatetime": "string"
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

### 35. Create Settings Master Async

**POST** `/api/v1/tenants/{tenant_id}/settings`

Create a new system settings record.

This endpoint allows creating a new settings entry with a name, default value,
and specific values for different store/terminal combinations. System settings
control the behavior of various aspects of the POS system.

Each settings entry can have different values for different stores or terminals,
allowing for fine-grained configuration of the system behavior.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |

**Request Example:**
```json
{
  "name": "string",
  "defaultValue": "string",
  "values": [
    {
      "storeCode": "string",
      "terminalNo": 0,
      "value": "string"
    }
  ]
}
```

**Response:**

**data Field:** `SettingsMasterResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "name": "string",
    "defaultValue": "string",
    "values": [
      {
        "storeCode": "string",
        "terminalNo": 0,
        "value": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 36. Get Settings Master By Name Async

**GET** `/api/v1/tenants/{tenant_id}/settings/{name}`

Retrieve a specific system setting by its name.

This endpoint retrieves the details of a setting identified by its unique name.
It returns the complete setting information including default value and all specific
values configured for different store/terminal combinations.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `SettingsMasterResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "name": "string",
    "defaultValue": "string",
    "values": [
      {
        "storeCode": "string",
        "terminalNo": 0,
        "value": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 37. Update Settings Master Async

**PUT** `/api/v1/tenants/{tenant_id}/settings/{name}`

Update an existing system setting.

This endpoint allows updating the default value and specific values of an existing setting.
It can be used to modify the behavior of the system without requiring code changes.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |

**Request Example:**
```json
{
  "defaultValue": "string",
  "values": [
    {
      "storeCode": "string",
      "terminalNo": 0,
      "value": "string"
    }
  ]
}
```

**Response:**

**data Field:** `SettingsMasterResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `defaultValue` | string | Yes | - |
| `values` | array[BaseSettingsMasterValue] | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "name": "string",
    "defaultValue": "string",
    "values": [
      {
        "storeCode": "string",
        "terminalNo": 0,
        "value": "string"
      }
    ],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 38. Delete Settings Master Async

**DELETE** `/api/v1/tenants/{tenant_id}/settings/{name}`

Delete a system setting.

This endpoint allows removing a setting completely from the system.
Caution should be exercised as removing critical settings may cause
system malfunctions if the code expects those settings to exist.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `SettingsMasterDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |

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
    "name": "string"
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

### 39. Get Settings Value By Name Async

**GET** `/api/v1/tenants/{tenant_id}/settings/{name}/value`

Retrieve the effective value of a setting for a specific store and terminal.

This endpoint is critical for runtime configuration, as it resolves the effective
value of a setting for a specific store/terminal combination. It first looks for
a value specific to the store and terminal, then for a store-wide value, and finally
falls back to the default value.

This is typically used by the POS terminals to get their configuration values at startup
or when refreshing settings.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `store_code` | string | Yes | - | - |
| `terminal_no` | integer | Yes | - | - |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `SettingsMasterValueResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `value` | string | Yes | - |

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
    "value": "string"
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

### 40. Get Taxes

**GET** `/api/v1/tenants/{tenant_id}/taxes`

Retrieve all tax records for a tenant.

This endpoint returns a paginated list of all tax rates for the specified tenant.
The results can be sorted and paginated as needed. This is useful for getting a list
of all available tax rates for administration or selection purposes.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[TaxMasterResponse]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `taxCode` | string | Yes | - |
| `taxType` | string | Yes | - |
| `taxName` | string | Yes | - |
| `rate` | number | Yes | - |
| `roundDigit` | integer | Yes | - |
| `roundMethod` | string | No | - |
| `entryDatetime` | string | No | - |
| `lastUpdateDatetime` | string | No | - |

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
      "taxCode": "string",
      "taxType": "string",
      "taxName": "string",
      "rate": 0.0,
      "roundDigit": 0,
      "roundMethod": "string",
      "entryDatetime": "string",
      "lastUpdateDatetime": "string"
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

### 41. Get Tax

**GET** `/api/v1/tenants/{tenant_id}/taxes/{tax_code}`

Retrieve a specific tax record by its code.

This endpoint retrieves the details of a tax rate identified by its unique code.
It returns information including the description, rate value, and tax type.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tax_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `TaxMasterResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `taxCode` | string | Yes | - |
| `taxType` | string | Yes | - |
| `taxName` | string | Yes | - |
| `rate` | number | Yes | - |
| `roundDigit` | integer | Yes | - |
| `roundMethod` | string | No | - |
| `entryDatetime` | string | No | - |
| `lastUpdateDatetime` | string | No | - |

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
    "taxCode": "string",
    "taxType": "string",
    "taxName": "string",
    "rate": 0.0,
    "roundDigit": 0,
    "roundMethod": "string",
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### Store

### 42. Get Item Store Master All Async

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items`

Retrieve all store-specific item records for a specific store.

This endpoint returns a paginated list of all store-specific item data for
the specified store. The results can be sorted and paginated as needed.
This is useful for getting a list of all items with store-specific prices
or other overrides.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[ItemStoreResponse]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
      "itemCode": "string",
      "storePrice": 0.0,
      "entryDatetime": "string",
      "lastUpdateDatetime": "string"
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

### 43. Create Item Master Async

**POST** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items`

Create a new store-specific item master record.

This endpoint allows creating store-specific information for an existing common item.
Store-specific details typically include a store-specific price that may differ
from the default price defined in the common item master.

This allows individual stores within a tenant to have unique pricing for the same items.
The item must already exist in the common item master before store-specific data can be added.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |

**Request Example:**
```json
{
  "itemCode": "string",
  "storePrice": 0.0
}
```

**Response:**

**data Field:** `ItemStoreResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "itemCode": "string",
    "storePrice": 0.0,
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 44. Get Item Store Master Async

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}`

Retrieve a specific store-specific item record by its code.

This endpoint retrieves the store-specific details of an item identified by its unique code.
This provides only the store-specific information like price overrides, not the complete
item details from the common master.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemStoreResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "itemCode": "string",
    "storePrice": 0.0,
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 45. Update Item Store Master Async

**PUT** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}`

Update an existing store-specific item record.

This endpoint allows updating the store-specific details of an item identified
by its code. It can be used to modify the store-specific price override.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `storePrice` | number | Yes | - |

**Request Example:**
```json
{
  "storePrice": 0.0
}
```

**Response:**

**data Field:** `ItemStoreResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `storePrice` | number | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "itemCode": "string",
    "storePrice": 0.0,
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 46. Delete Item Store Master Async

**DELETE** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}`

Delete a store-specific item record.

This endpoint allows removing store-specific item data completely from the system.
This does not delete the item from the common item master, only the store-specific
overrides. After deletion, the store will use the default values from the common
item master.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemStoreDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |

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
    "itemCode": "string"
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

### 47. Get Item Store Master Detail Async

**GET** `/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}/details`

Retrieve detailed item information combining common and store-specific data.

This endpoint provides a comprehensive view of an item by combining the
common item data (from item_common_master) with any store-specific overrides
(from item_store_master). This is particularly useful for POS terminals
that need complete item information including both common attributes and
any store-specific pricing.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `item_code` | string | Yes | - |
| `store_code` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `ItemStoreDetailResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `itemCode` | string | Yes | - |
| `description` | string | Yes | - |
| `unitPrice` | number | Yes | - |
| `unitCost` | number | Yes | - |
| `storePrice` | number | No | - |
| `itemDetails` | array[string] | Yes | - |
| `imageUrls` | array[string] | Yes | - |
| `categoryCode` | string | Yes | - |
| `taxCode` | string | Yes | - |
| `isDiscountRestricted` | boolean | Yes | - |
| `isDeleted` | boolean | Yes | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "itemCode": "string",
    "description": "string",
    "unitPrice": 0.0,
    "unitCost": 0.0,
    "storePrice": 0.0,
    "itemDetails": [
      "string"
    ],
    "imageUrls": [
      "string"
    ],
    "categoryCode": "string",
    "taxCode": "string",
    "isDiscountRestricted": true
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

### Staff

### 48. Get Staff Master All Async

**GET** `/api/v1/tenants/{tenant_id}/staff`

Retrieve all staff records for a tenant.

This endpoint returns a paginated list of all staff members for the specified tenant.
The results can be sorted and paginated as needed. This is useful for getting a list
of all available staff members for administration or selection purposes.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `limit` | integer | No | 100 | - |
| `page` | integer | No | 1 | - |
| `sort` | string | No | - | ?sort=field1:1,field2:-1 |
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `array[StaffResponse]`

| Field | Type | Required | Description |
|------------|------|------|------|
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
      "id": "string",
      "name": "string",
      "pin": "string",
      "roles": [],
      "entryDatetime": "string",
      "lastUpdateDatetime": "string"
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

### 49. Create Staff Master Async

**POST** `/api/v1/tenants/{tenant_id}/staff`

Create a new staff record in the master data.

This endpoint allows creating a new staff member with their ID, name, PIN code,
and assigned roles. Staff records are essential for authentication, authorization,
and tracking operations in the POS system.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | Yes | - |

**Request Example:**
```json
{
  "id": "string",
  "name": "string",
  "pin": "string",
  "roles": [
    "string"
  ]
}
```

**Response:**

**data Field:** `StaffResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "id": "string",
    "name": "string",
    "pin": "string",
    "roles": [],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 50. Get Staff Master Async

**GET** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Retrieve a specific staff record by their ID.

This endpoint retrieves the details of a staff member identified by their unique ID.
It returns information including name, roles, and other attributes (PIN is not returned).

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `staff_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `StaffResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "id": "string",
    "name": "string",
    "pin": "string",
    "roles": [],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 51. Update Staff Master Async

**PUT** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Update an existing staff record.

This endpoint allows updating the details of an existing staff member identified by their ID.
Only the provided fields will be updated. This can be used to change a staff member's name,
PIN code, or assigned roles.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `staff_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Request Body:**

| Field | Type | Required | Description |
|------------|------|------|------|
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | Yes | - |

**Request Example:**
```json
{
  "name": "string",
  "pin": "string",
  "roles": [
    "string"
  ]
}
```

**Response:**

**data Field:** `StaffResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `id` | string | Yes | - |
| `name` | string | Yes | - |
| `pin` | string | Yes | - |
| `roles` | array[string] | No | - |
| `entryDatetime` | string | Yes | - |
| `lastUpdateDatetime` | string | No | - |

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
    "id": "string",
    "name": "string",
    "pin": "string",
    "roles": [],
    "entryDatetime": "string",
    "lastUpdateDatetime": "string"
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

### 52. Delete Staff Master Async

**DELETE** `/api/v1/tenants/{tenant_id}/staff/{staff_id}`

Delete a staff record.

This endpoint allows deleting a staff member from the system. This operation
is permanent and cannot be undone. Once a staff member is deleted, they will no
longer be able to log in or access the POS system.

Authentication is required via token or API key. The tenant ID in the path must match
the one in the security credentials.

**Path Parameters:**

| Parameter | Type | Required | Description |
|------------|------|------|------|
| `staff_id` | string | Yes | - |
| `tenant_id` | string | Yes | - |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|------------|------|------|------------|------|
| `terminal_id` | string | No | - | terminal_id should be provided by query  |
| `is_terminal_service` | string | No | False | - |

**Response:**

**data Field:** `StaffDeleteResponse`

| Field | Type | Required | Description |
|------------|------|------|------|
| `staffId` | string | Yes | - |

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
    "staffId": "string"
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
