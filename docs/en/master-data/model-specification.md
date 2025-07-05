# Master Data Service Model Specification

## Overview

The Master Data service manages reference data essential to the Kugelpos POS system. It centrally manages static data such as staff information, product master data, payment methods, tax settings, system configurations, and item books (POS UI), providing them to other services. It supports multi-tenant architecture and implements hierarchical configuration management.

## Database Document Models

All document models inherit from `BaseDocumentModel`.

### 1. StaffMasterDocument (Staff Master)

Document managing staff information and authentication data.

**Collection Name:** `master_staff`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| staff_id | string | ✓ | Staff ID |
| name | string | ✓ | Staff name |
| pin | string | ✓ | Authentication PIN (bcrypt hashed) |
| roles | array[string] | - | Role list (default: []) |

**Indexes:**
- Unique: (tenant_id, staff_id)

### 2. ItemCommonMasterDocument (Common Item Master)

Document managing basic product information common to all stores.

**Collection Name:** `master_item_common`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| item_code | string | ✓ | Item code |
| description | string | ✓ | Item description |
| description_short | string | - | Short description |
| description_long | string | - | Detailed description |
| category_code | string | - | Category code |
| unit_price | float | - | Standard selling price (default: 0.0) |
| unit_cost | float | - | Cost price (default: 0.0) |
| tax_code | string | - | Tax code |
| item_details | array[ItemDetail] | - | Additional information list |
| image_urls | array[string] | - | Product image URLs |
| is_discount_restricted | boolean | - | Discount restriction flag (default: false) |

**ItemDetail Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| name | string | ✓ | Attribute name |
| value | string | ✓ | Attribute value |

**Indexes:**
- Unique: (tenant_id, item_code)
- category_code
- tax_code

### 3. ItemStoreMasterDocument (Store-specific Item Master)

Document managing store-specific product information (pricing, etc.).

**Collection Name:** `master_item_store`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| store_code | string | ✓ | Store code |
| item_code | string | ✓ | Item code |
| store_price | float | - | Store-specific price |

**Indexes:**
- Unique: (tenant_id, store_code, item_code)

### 4. ItemBookMasterDocument (Item Book Master)

Document managing POS screen UI hierarchy (categories/tabs/buttons).

**Collection Name:** `master_item_book`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| item_book_id | string | ✓ | Item book ID |
| title | string | ✓ | Title |
| categories | array[ItemBookCategory] | - | Category list |

**ItemBookCategory Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| category_number | integer | ✓ | Category number |
| title | string | ✓ | Category title |
| color | string | - | Background color |
| tabs | array[ItemBookTab] | - | Tab list |

**ItemBookTab Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tab_number | integer | ✓ | Tab number |
| title | string | ✓ | Tab title |
| color | string | - | Background color |
| buttons | array[ItemBookButton] | - | Button list |

**ItemBookButton Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| pos_x | integer | ✓ | X coordinate position |
| pos_y | integer | ✓ | Y coordinate position |
| size_x | integer | - | Width size (default: 1) |
| size_y | integer | - | Height size (default: 1) |
| item_code | string | - | Item code |
| title | string | - | Button title |
| color | string | - | Button color |
| image_url | string | - | Button image URL |

**Indexes:**
- Unique: (tenant_id, item_book_id)

### 5. PaymentMasterDocument (Payment Method Master)

Document managing available payment methods and constraints.

**Collection Name:** `master_payment`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| payment_code | string | ✓ | Payment method code |
| description | string | ✓ | Description |
| limit_amount | float | - | Maximum amount |
| can_refund | boolean | - | Refund allowed flag (default: true) |
| can_deposit_over | boolean | - | Deposit over allowed flag (default: false) |
| can_change | boolean | - | Change allowed flag (default: false) |

**Indexes:**
- Unique: (tenant_id, payment_code)

### 6. SettingsMasterDocument (Settings Master)

Document managing hierarchical system settings.

**Collection Name:** `master_settings`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| name | string | ✓ | Setting name |
| default_value | string | ✓ | Default value |
| values | array[SettingsValue] | - | Scope-specific setting values |

**SettingsValue Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| store_code | string | - | Store code (store scope) |
| terminal_no | integer | - | Terminal number (terminal scope) |
| value | string | ✓ | Setting value |

**Setting Resolution Priority:**
1. Terminal level (highest priority)
2. Store level
3. Global (default value)

**Indexes:**
- Unique: (tenant_id, name)

### 7. CategoryMasterDocument (Category Master)

Document managing product categories.

**Collection Name:** `master_category`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | ✓ | Tenant identifier |
| category_code | string | ✓ | Category code |
| description | string | ✓ | Category description |
| description_short | string | - | Short description |
| tax_code | string | - | Default tax code |

**Indexes:**
- Unique: (tenant_id, category_code)
- tax_code

### 8. TaxMasterDocument (Tax Master)

Document managing tax rates and calculation rules.

**Collection Name:** `master_tax`

**Inheritance:** `BaseDocumentModel`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tax_code | string | ✓ | Tax code |
| tax_type | string | ✓ | Tax type |
| tax_name | string | ✓ | Tax name |
| rate | float | ✓ | Tax rate (%) |
| round_digit | integer | - | Rounding digits (default: 0) |
| round_method | string | - | Rounding method |

**Indexes:**
- tax_code (unique)

## API Request/Response Schemas

All schemas inherit from `BaseSchemaModel` and provide automatic conversion from snake_case to camelCase.

### Staff Management Schemas

#### StaffCreateRequest
New staff creation request.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| staffId | string | ✓ | Staff ID |
| name | string | ✓ | Staff name |
| pin | string | ✓ | Authentication PIN |
| roles | array[string] | - | Role list |

#### StaffResponse
Staff information response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| staffId | string | Staff ID |
| name | string | Staff name |
| pin | string | Masked display ("***") |
| roles | array[string] | Role list |

### Product Management Schemas

#### ItemCommonCreateRequest
Product creation request.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| itemCode | string | ✓ | Item code |
| description | string | ✓ | Item description |
| shortDescription | string | - | Short description |
| detailDescription | string | - | Detailed description |
| categoryCode | string | - | Category code |
| unitPrice | float | - | Selling price |
| unitCost | float | - | Cost price |
| taxCode | string | - | Tax code |
| itemDetails | array[object] | - | Additional information |
| imageUrls | array[string] | - | Image URLs |
| isDiscountRestricted | boolean | - | Discount restriction |

#### ItemStoreCreateRequest
Store-specific pricing setup request.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| storeCode | string | ✓ | Store code |
| itemCode | string | ✓ | Item code |
| storePrice | float | ✓ | Store-specific price |

### Payment Method Schemas

#### PaymentResponse
Payment method response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| paymentCode | string | Payment method code |
| description | string | Description |
| limitAmount | float | Maximum amount |
| canRefund | boolean | Refund allowed flag |
| canDepositOver | boolean | Deposit over allowed flag |
| canChange | boolean | Change allowed flag |

### Settings Management Schemas

#### SettingValueResponse
Setting value retrieval response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| name | string | Setting name |
| value | string | Resolved setting value |
| scope | string | Applied scope (global/store/terminal) |

## Data Relationships

### Product Data Hierarchy
```
ItemCommonMasterDocument (basic information)
    ↓
ItemStoreMasterDocument (store-specific overrides)
    ↓
Final product information (merged result)
```

### Item Book Hierarchy
```
ItemBookMasterDocument
  └── categories[]
        └── tabs[]
              └── buttons[] → ItemCommonMasterDocument (item_code reference)
```

### Settings Resolution Hierarchy
```
SettingsMasterDocument
  ├── default_value (global)
  └── values[]
        ├── store_code specified (store level)
        └── store_code + terminal_no specified (terminal level)
```

## Multi-Tenant Implementation

1. **Database Isolation:** Tenant-specific databases in `db_master_{tenant_id}` format
2. **Authentication Integration:** Authentication via JWT tokens or API keys
3. **Data Access:** Tenant ID validation for all operations

## Performance Optimization

1. **Index Strategy:** Indexes on frequently searched fields
2. **Hierarchical Data:** Nested structures in item books reduce join operations
3. **Settings Cache:** Setting value resolution results can be cached

## Security

1. **PIN Management:** Staff PINs are hashed with bcrypt
2. **API Authentication:** JWT/API key authentication required
3. **Audit Logging:** Change tracking via created_at/updated_at