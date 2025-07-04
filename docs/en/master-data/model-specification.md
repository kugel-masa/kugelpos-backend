# Master Data Service Model Specification

## Overview

Master Data Service manages all static reference and configuration data for the Kugelpos POS system. It provides centralized management for product catalogs, staff information, payment methods, tax rules, categories, system settings, and item book layouts used across all other services. The service follows a multi-tenant architecture with comprehensive data validation and audit trails.

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

### 1. StaffMasterDocument (Staff Information)

Document for storing staff member information and authentication data.

**Collection Name:** `master_staff`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| id | string | - | Staff unique identifier |
| name | string | - | Staff display name |
| pin | string | - | Authentication PIN (hashed) |
| status | string | - | Staff status (active/inactive) |
| roles | array[string] | - | List of assigned roles |

**Indexes:**
- Unique index: (tenant_id, id)
- Index: status

### 2. CategoryMasterDocument (Product Categories)

Document for organizing products into hierarchical categories.

**Collection Name:** `master_category`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| category_code | string | - | Category unique code |
| description | string | - | Category description |
| description_short | string | - | Short description for UI |
| tax_code | string | - | Associated tax code reference |

**Indexes:**
- Unique index: (tenant_id, category_code)
- Index: tax_code

### 3. ItemCommonMasterDocument (Common Item Data)

Document for storing base item information shared across all stores.

**Collection Name:** `master_item_common`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| item_code | string | - | Item unique code |
| category_code | string | - | Category reference |
| description | string | - | Item description |
| description_short | string | - | Short description |
| description_long | string | - | Long description |
| unit_price | float | - | Standard unit price (default: 0.0) |
| unit_cost | float | - | Cost price (default: 0.0) |
| item_details | array[string] | - | Additional item details |
| image_urls | array[string] | - | Item image URLs |
| tax_code | string | - | Tax code reference |
| is_discount_restricted | boolean | - | Discount restriction flag (default: false) |
| is_deleted | boolean | - | Logical deletion flag (default: false) |

**Indexes:**
- Unique index: (tenant_id, item_code)
- Index: category_code
- Index: tax_code
- Index: is_deleted

### 4. ItemStoreMasterDocument (Store-Specific Item Data)

Document for store-specific item overrides and pricing.

**Collection Name:** `master_item_store`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| store_code | string | - | Store code |
| item_code | string | - | Item code reference |
| store_price | float | - | Store-specific price override |

**Indexes:**
- Unique index: (tenant_id, store_code, item_code)

### 5. ItemStoreDetailDocument (Combined Item View)

Virtual document combining common item data with store-specific overrides.

**Purpose:** Provides unified view of item data for specific stores

**Extends:** ItemCommonMasterDocument

**Additional Fields:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| store_code | string | - | Store code |
| store_price | float | - | Store-specific price (overrides unit_price) |

### 6. PaymentMasterDocument (Payment Methods)

Document for configuring payment method capabilities and limits.

**Collection Name:** `master_payment`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| payment_code | string | - | Payment method code |
| description | string | - | Payment method description |
| limit_amount | float | - | Maximum transaction amount (default: 0.0) |
| can_refund | boolean | - | Supports refunds (default: true) |
| can_deposit_over | boolean | - | Allows overpayment (default: false) |
| can_change | boolean | - | Can provide change (default: false) |
| is_active | boolean | - | Active status (default: true) |

**Indexes:**
- Unique index: (tenant_id, payment_code)
- Index: is_active

### 7. TaxMasterDocument (Tax Configuration)

Document for tax calculation rules and rates.

**Collection Name:** `master_tax`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tax_code | string | - | Tax code identifier |
| tax_type | string | - | Tax type (sales_tax, vat, etc.) |
| tax_name | string | - | Tax display name |
| rate | float | - | Tax rate as decimal (default: 0.0) |
| round_digit | integer | - | Rounding precision (default: 0) |
| round_method | string | - | Rounding method |

**Indexes:**
- Unique index: tax_code

### 8. SettingsMasterDocument (System Settings)

Document for hierarchical system configuration settings.

**Collection Name:** `master_settings`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| name | string | - | Setting name |
| default_value | string | - | Default value |
| values | array[SettingsValue] | - | Scope-specific values |

**SettingsValue Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| store_code | string | - | Store scope (null for tenant-level) |
| terminal_no | integer | - | Terminal scope (null for store-level) |
| value | string | ✓ | Setting value |

**Setting Resolution Order:**
1. Terminal-specific (most specific)
2. Store-specific
3. Tenant-level default

**Indexes:**
- Unique index: (tenant_id, name)

### 9. ItemBookMasterDocument (Item Book Layouts)

Document for configuring POS terminal UI layouts with hierarchical structure.

**Collection Name:** `master_item_book`

**Field Definitions:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tenant_id | string | - | Tenant identifier |
| item_book_id | string | - | Book unique identifier |
| title | string | - | Book title |
| categories | array[ItemBookCategory] | - | Categories list |

**ItemBookCategory Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| category_number | integer | - | Category number |
| title | string | - | Category title |
| color | string | - | Category color |
| tabs | array[ItemBookTab] | - | Tabs list |

**ItemBookTab Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| tab_number | integer | - | Tab number |
| title | string | - | Tab title |
| color | string | - | Tab color |
| buttons | array[ItemBookButton] | - | Buttons list |

**ItemBookButton Sub-document:**

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| pos_x | integer | - | X position on grid |
| pos_y | integer | - | Y position on grid |
| size | ButtonSize | - | Button size enum |
| image_url | string | - | Button image URL |
| color_text | string | - | Text color |
| item_code | string | - | Associated item code |

**ButtonSize Enumeration:**
- `Single` - Standard 1x1 button
- `DoubleWidth` - 2x1 button
- `DoubleHeight` - 1x2 button
- `Quad` - 2x2 button

**Indexes:**
- Unique index: (tenant_id, item_book_id)

### 10. TerminalInfoDocument (Terminal Reference)

Referenced document for terminal operations (defined in commons).

**Collection Name:** `info_terminal`

**Key Fields Used:**

| Field Name | Type | Description |
|------------|------|-------------|
| terminal_id | string | Terminal unique identifier |
| tenant_id | string | Tenant identifier |
| store_code | string | Store code |
| terminal_no | integer | Terminal number |
| status | string | Terminal status |
| staff | StaffMasterDocument | Currently signed-in staff |

## API Request/Response Schemas

All schemas inherit from `BaseSchemaModel` which provides automatic snake_case to camelCase conversion for JSON serialization.

### Staff Management Schemas

#### StaffCreateRequest
Request to create new staff member.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| id | string | ✓ | Staff unique identifier |
| name | string | ✓ | Staff display name |
| pin | string | ✓ | Authentication PIN |
| status | string | - | Staff status (default: active) |
| roles | array[string] | - | Assigned roles |

#### StaffUpdateRequest
Request to update staff information.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| name | string | - | Updated staff name |
| pin | string | - | Updated PIN |
| status | string | - | Updated status |
| roles | array[string] | - | Updated roles |

#### Staff (Response)
Staff information response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| id | string | Staff identifier |
| name | string | Staff name |
| pin | string | Masked PIN ("***") |
| status | string | Staff status |
| roles | array[string] | Assigned roles |
| createdAt | string | Creation timestamp |
| updatedAt | string | Update timestamp |

### Item Management Schemas

#### ItemCommonCreateRequest
Request to create new item.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| itemCode | string | ✓ | Item unique code |
| categoryCode | string | - | Category reference |
| description | string | ✓ | Item description |
| descriptionShort | string | - | Short description |
| descriptionLong | string | - | Long description |
| unitPrice | float | - | Standard price |
| unitCost | float | - | Cost price |
| itemDetails | array[string] | - | Additional details |
| imageUrls | array[string] | - | Image URLs |
| taxCode | string | - | Tax code |
| isDiscountRestricted | boolean | - | Discount restriction |

#### ItemCommon (Response)
Item information response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| itemCode | string | Item code |
| categoryCode | string | Category reference |
| description | string | Item description |
| descriptionShort | string | Short description |
| descriptionLong | string | Long description |
| unitPrice | float | Standard price |
| unitCost | float | Cost price |
| itemDetails | array[string] | Additional details |
| imageUrls | array[string] | Image URLs |
| taxCode | string | Tax code |
| isDiscountRestricted | boolean | Discount restriction |
| isDeleted | boolean | Deletion status |
| createdAt | string | Creation timestamp |
| updatedAt | string | Update timestamp |

### Payment Method Schemas

#### PaymentCreateRequest
Request to create payment method.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| paymentCode | string | ✓ | Payment method code |
| description | string | ✓ | Method description |
| limitAmount | float | - | Maximum amount |
| canRefund | boolean | - | Refund capability |
| canDepositOver | boolean | - | Overpayment capability |
| canChange | boolean | - | Change capability |
| isActive | boolean | - | Active status |

#### Payment (Response)
Payment method response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| paymentCode | string | Payment method code |
| description | string | Method description |
| limitAmount | float | Maximum amount |
| canRefund | boolean | Refund capability |
| canDepositOver | boolean | Overpayment capability |
| canChange | boolean | Change capability |
| isActive | boolean | Active status |
| createdAt | string | Creation timestamp |
| updatedAt | string | Update timestamp |

### Settings Management Schemas

#### SettingsCreateRequest
Request to create setting.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| name | string | ✓ | Setting name |
| defaultValue | string | ✓ | Default value |
| values | array[SettingsValueCreate] | - | Scope-specific values |

#### SettingsValueCreate
Scope-specific setting value.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| storeCode | string | - | Store scope |
| terminalNo | integer | - | Terminal scope |
| value | string | ✓ | Setting value |

### Category Management Schemas

#### CategoryCreateRequest
Request to create category.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| categoryCode | string | ✓ | Category unique code |
| description | string | ✓ | Category description |
| descriptionShort | string | - | Short description |
| taxCode | string | - | Tax code reference |

### Tax Management Schemas

#### Tax (Response)
Tax configuration response.

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| taxCode | string | Tax code |
| taxType | string | Tax type |
| taxName | string | Tax name |
| rate | float | Tax rate |
| roundDigit | integer | Rounding precision |
| roundMethod | string | Rounding method |

### Item Book Management Schemas

#### ItemBookCreateRequest
Request to create item book layout.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| itemBookId | string | ✓ | Book identifier |
| title | string | ✓ | Book title |
| categories | array[CategoryCreate] | - | Categories |

#### ItemBookCategoryCreate
Category within item book.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| categoryNumber | integer | ✓ | Category number |
| title | string | ✓ | Category title |
| color | string | - | Category color |
| tabs | array[TabCreate] | - | Tabs |

#### ItemBookTabCreate
Tab within category.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| tabNumber | integer | ✓ | Tab number |
| title | string | ✓ | Tab title |
| color | string | - | Tab color |
| buttons | array[ButtonCreate] | - | Buttons |

#### ItemBookButtonCreate
Button within tab.

| Field Name (JSON) | Type | Required | Description |
|-------------------|------|----------|-------------|
| posX | integer | ✓ | X position |
| posY | integer | ✓ | Y position |
| size | string | ✓ | Button size |
| imageUrl | string | - | Image URL |
| colorText | string | - | Text color |
| itemCode | string | - | Item reference |

## Data Relationships

### 1. Item Hierarchy
```
ItemCommonMasterDocument (base data)
  ↓
ItemStoreMasterDocument (store overrides)
  ↓
ItemStoreDetailDocument (combined view)
```

### 2. Category-Item Relationship
```
CategoryMasterDocument
  ↓ (via category_code)
ItemCommonMasterDocument
```

### 3. Tax Relationships
```
TaxMasterDocument
  ↓ (via tax_code)
CategoryMasterDocument, ItemCommonMasterDocument
```

### 4. Item Book Hierarchy
```
ItemBookMasterDocument
  └── ItemBookCategory[]
        └── ItemBookTab[]
              └── ItemBookButton[]
                    ↓ (via item_code)
                  ItemCommonMasterDocument
```

### 5. Settings Hierarchy
```
Tenant Level (default_value)
  └── Store Level (store_code + value)
        └── Terminal Level (store_code + terminal_no + value)
```

## Multi-tenancy Implementation

1. **Database Isolation**: Each tenant uses separate database: `{DB_NAME_PREFIX}_{tenant_id}`
2. **Tenant Validation**: All operations validate tenant_id
3. **Data Isolation**: Cross-tenant access prevented at application level
4. **Unique Constraints**: Most unique indexes include tenant_id

## Validation Rules

### Field Validation
- **Codes**: Alphanumeric, typically 3-20 characters
- **Prices**: Non-negative float values
- **Status**: Enum validation (active/inactive)
- **References**: Foreign key validation for linked documents

### Business Rules
- Items can only reference existing categories and tax codes
- Store-specific prices override common prices
- Setting resolution follows hierarchy (terminal > store > tenant)
- Logical deletion preserves referential integrity

## Performance Considerations

1. **Indexing Strategy**: Optimized for common query patterns
2. **Composite Views**: ItemStoreDetailDocument reduces join operations
3. **Caching**: ETag-based optimistic concurrency control
4. **Sharding**: Shard key supports horizontal scaling
5. **Reference Integrity**: Enforced at application level for performance

## Security Features

1. **PIN Hashing**: Staff PINs stored using secure hashing
2. **Audit Trail**: All changes tracked with timestamps
3. **Soft Deletion**: Logical deletion maintains history
4. **Validation**: Comprehensive input validation on all fields
5. **Multi-tenant Isolation**: Complete data separation between tenants