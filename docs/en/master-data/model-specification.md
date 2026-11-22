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
| pos_x | integer | - | X coordinate position |
| pos_y | integer | - | Y coordinate position |
| size | ButtonSize | - | Button size (Single/DoubleWidth/DoubleHeight/Quad) |
| item_code | string | - | Item code |
| color_text | string | - | Button text color |
| image_url | string | - | Button image URL |
| unit_price | float | - | Item price (resolved on read, not stored) |
| description | string | - | Item description (resolved on read, not stored) |

**Note:** `unit_price` and `description` are never stored and are not accepted on write. Only `GET .../item_books/{item_book_id}/detail` fills them from the item master (the store price when the store has one); every other route returns null, and so does `/detail` for a button whose item is not in the item master.

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
| limit_amount | float | - | Maximum amount (default: 0.0, no limit) |
| can_refund | boolean | - | Refund allowed flag (default: true) |
| can_deposit_over | boolean | - | Deposit over allowed flag (default: false) |
| can_change | boolean | - | Change allowed flag (default: false) |
| variants | PaymentVariant[] | - | Variants (sub-codes) of the payment method (default: empty) |

**Indexes:**
- Unique: (tenant_id, payment_code)

**PaymentVariant (embedded):** one classification of the payments the method takes, such as a card brand under cashless (issue #311). A variant carries only its identity; the behaviour stays with the payment method.

| Field Name | Type | Required | Description |
|------------|------|----------|-------------|
| variant_code | string | ✓ | Free format (`^[A-Za-z0-9_-]{1,20}$`, case-sensitive), unique within the payment method; cannot be changed |
| name | string | ✓ | Name; a payment line recorded with the variant is named after it |
| is_active | boolean | - | A stopped variant takes no new payment (default: true) |
| created_at / updated_at | datetime | - | Registration and last change |

Variants are added and changed through `/tenants/{tenant_id}/payments/{payment_code}/variants` and are never deleted: one no longer used is stopped. Updating the payment method keeps its variants; deleting it takes them with it. Uniqueness within a method is held by one conditional update, not an index.

**Deployment order:** register variants only after commons, cart and report run the version that knows them. An older cart ignores the variants and records payments without one. cart caches payment masters (600 s by default); `DELETE /api/v1/cache/master-data?namespace=payment_master` on cart (privileged caller) makes a change take effect at once.

**How cart applies these settings:**

| Setting | On a payment | On a return |
|---------|--------------|-------------|
| `can_deposit_over` false | A deposit above the balance is refused (403004) | - |
| `can_deposit_over` true, `can_change` true | The payment covers the balance and the excess is given as change | - |
| `can_deposit_over` true, `can_change` false | The payment covers the balance; the excess stays on the line as deposit and no change is given | - |
| `limit_amount` > 0 | What the method covers in one cart, its lines together, may not exceed it (403017) | What the method refunds may not exceed it (403015) |
| `can_refund` false | - | The method cannot be used to refund (403014) |

A `limit_amount` of 0 or less means no limit. A void is not checked: it reverses the original payments as they were. The usual settings are `can_deposit_over` and `can_change` true for cash, and false for cashless methods.

**How cart uses variants (issue #311):** a payment may name a variant. A named variant must be an active variant of that method (403018 unknown, 403019 stopped). With none named, a method with one active variant records it, one with several refuses the payment (403020), and one with none records no variant. A void names the sale's tenders (method and variant) for what the sale took by each; a return refunds by a tender of the sale, up to what the sale took by it (403022), or by cash (`01`), and by nothing else (403021).

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
4. The consuming service's own configuration, when no record exists at all

Step 4 is invisible over the API — the endpoint answers 404 rather than the
value the service would use. Tenant setup therefore **seeds the settings a POS
terminal must be able to read** (`RECEIPT_NO_START_VALUE` /
`RECEIPT_NO_END_VALUE`, issue #174) with the shipped defaults, so those lookups
always answer. Seeding is insert-if-absent: re-running tenant setup never
overwrites a value an operator has set. Note that once seeded the value is an
explicit record, so a later change to a service's shipped default reaches new
tenants only.

The seeded value is resolved from master-data's own environment (`.env` /
environment variables), not from the shipped constant — a seeded record
outranks a service's own configuration, so a deployment that raises the range
by environment must set the same variable for master-data, or configure the
tenant setting directly. Otherwise seeding would quietly put the shipped
default above the configured one.

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
| variants | PaymentVariantResponse[] | Variants, in variant code order, stopped ones included |

#### PaymentVariantResponse
Payment variant response (issue #311).

| Field Name (JSON) | Type | Description |
|-------------------|------|-------------|
| variantCode | string | Variant code |
| name | string | Name |
| isActive | boolean | Active flag |
| entryDatetime | string | Registration datetime |
| lastUpdateDatetime | string | Last change datetime (null until changed) |

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