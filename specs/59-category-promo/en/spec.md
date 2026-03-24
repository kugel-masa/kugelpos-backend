# Category Promotion Feature Specification

## Overview

A feature that allows setting time-limited discount promotions for product categories. When adding products to the shopping cart, the system automatically applies discounts based on the product's category and active promotion rules.

This feature is implemented as the first phase of an extensible promotion framework. The architecture assumes that other promotion types (per-item, quantity-based, etc.) can be added in the future.

## Problem Statement

The current POS system lacks the ability to run promotion campaigns at the category level. Store operators cannot:
- Create time-limited discount campaigns for specific product categories
- Automatically apply promotional discounts at checkout
- Manage multiple promotions with different validity periods simultaneously
- Measure and analyze the effectiveness of promotions

This limits marketing flexibility and requires manual discount application at the point of sale.

## User Scenarios and Tests

### Scenario 1: Store Manager Creates a Category Promotion

**Actor**: Store Manager

**Preconditions**:
- The store manager is authenticated
- Product categories exist in the system

**Flow**:
1. The store manager accesses the promotion management screen
2. The store manager creates a new promotion with the following information:
   - Promotion type: Select "Category Discount"
   - Promotion name and description
   - Target stores (e.g., "Shibuya Store, Shinjuku Store" or "All Stores")
   - Target category (e.g., "Beverages")
   - Discount rate (e.g., 10% off)
   - Start date/time and end date/time
3. The system validates the promotion data
4. The system saves the promotion as active

**Expected Result**: The promotion is created and automatically applied during the specified period.

**Acceptance Criteria**:
- A promotion can be created by filling in all required fields
- The system prevents duplicate promotions for the same category (configurable)
- The system validates the date range (end date must be after start date)

### Scenario 2: Customer Receives an Automatic Discount

**Actor**: Customer (via cashier)

**Preconditions**:
- An active promotion exists for the category
- The current time is within the promotion's validity period

**Flow**:
1. The cashier scans a product in the promotion-eligible category
2. The system detects that the product's category matches an active promotion
3. The system automatically calculates and applies the discount
4. The discount is displayed as a line-item discount with a promotion code
5. The customer sees the discounted price

**Expected Result**: The discount is automatically applied without manual intervention.

**Acceptance Criteria**:
- The discount is applied within the same transaction (no delay)
- The discount amount is calculated correctly
- The discount is displayed on the receipt with the promotion name
- Products with the "discount restricted" flag are not discounted
- **The promotion code is recorded in the transaction log**

### Scenario 3: Promotion Expiration

**Actor**: System

**Preconditions**:
- A promotion exists with an end date set
- The current time has passed the end date

**Flow**:
1. A customer purchases a product in a category that was previously under promotion
2. The system checks for active promotions
3. The system finds no active promotions (expired)
4. The product is added at the regular price

**Expected Result**: No discount is applied after the promotion expires.

**Acceptance Criteria**:
- Expired promotions are not applied
- No errors or user confusion occur when a promotion is inactive
- Past transactions retain their applied discounts

### Scenario 4: Multiple Promotions Match

**Actor**: System

**Preconditions**:
- Multiple active promotions are applicable to the same product
- The promotions have different discount rates

**Flow**:
1. The cashier scans a product eligible for multiple promotions
2. The system identifies all matching promotions
3. The system calculates the discounted price for each promotion
4. The system selects the promotion that results in the lowest price (highest discount rate)
5. The system applies only one promotion

**Expected Result**: The most favorable promotion (resulting in the lowest price) for the customer is applied.

**Acceptance Criteria**:
- Only one category promotion is applied per product
- The promotion with the highest discount rate is automatically selected
- The customer always gets the lowest price

### Scenario 5: Store Manager Reviews Promotion Performance

**Actor**: Store Manager

**Preconditions**:
- A promotion has been executed and transactions have occurred

**Flow**:
1. The store manager accesses the promotion performance screen
2. The store manager selects the target promotion and time period
3. The system aggregates transactions by promotion code
4. The system displays the following performance metrics:
   - Number of applications (transaction count, line-item count)
   - Total discount amount
   - Total eligible sales amount

**Expected Result**: The promotional effectiveness can be reviewed in numerical terms.

**Acceptance Criteria**:
- Performance can be aggregated by promotion code
- Results can be filtered by date range
- Accurate total discount amounts are displayed

## Functional Requirements

### FR-1: Promotion Master Data Management

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-1.1 | The system can identify promotion types | Promotion types can be distinguished by the type field |
| FR-1.2 | The system allows creation of category promotions | A promotion can be saved with all required fields filled in |
| FR-1.3 | The system stores the promotion code, name, and description | All fields are persisted and retrievable |
| FR-1.4 | The system supports targeting one or more categories | Multiple category codes can be associated |
| FR-1.4.1 | The system supports specifying target stores | Store codes can be specified; when unspecified, the promotion applies to all stores |
| FR-1.5 | The system supports percentage discounts | The discount rate is calculated correctly |
| FR-1.6 | The system enforces promotion start and end date/times | Promotions are only applied within the validity period |
| FR-1.7 | The system supports enabling/disabling promotions | Disabled promotions are not applied |
| FR-1.8 | The system selects the lowest price when multiple promotions match | The promotion with the highest discount rate is applied |
| FR-1.9 | The system supports soft deletion of promotions | Deleted promotions are not applied but retained as history |

### FR-2: Automatic Discount Application

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-2.1 | The system checks for active promotions when a product is added to the cart | A check is performed on every product addition |
| FR-2.2 | The system matches product categories against active promotions | Matching is performed using the category_code field |
| FR-2.2.1 | The system verifies whether the current store is targeted by the promotion | Store code is matched, or all-stores targeting is confirmed |
| FR-2.3 | The system calculates discounts based on promotion rules | Discount amount = price x quantity x discount rate |
| FR-2.4 | The system automatically applies the discount to the line item | The discount appears in line_item.discounts |
| FR-2.5 | The system respects the product's discount restriction flag | Products with is_discount_restricted=true are skipped |
| FR-2.6 | The system records the promotion code in the discount details | The promotion code is traceable |

### FR-3: Promotion Search

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-3.1 | The system provides an API to list all promotions | Returns a paginated list |
| FR-3.2 | The system provides an API to retrieve active promotions | Filtered by current time and is_active flag |
| FR-3.3 | The system provides an API to retrieve promotions by category | Filtered by target_category_codes |
| FR-3.4 | The system provides an API to retrieve promotions by type | Filtered by promotion_type |
| FR-3.5 | The system provides an API to retrieve promotions by store | Filtered by target_store_codes |

### FR-4: Promotion Recording in Sales Data

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-4.1 | The system records the promotion code in the transaction log | Applied promotions are included in the transaction data |
| FR-4.2 | The system retains the promotion code at the line-item level | Each line item's discount is linked to a promotion code |
| FR-4.3 | The system can search transactions by promotion code | Aggregation of promotion performance is possible |

### FR-5: Promotion Performance Aggregation

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-5.1 | The system can aggregate application counts by promotion code | Transaction count and line-item count are retrievable |
| FR-5.2 | The system can aggregate total discount amounts by promotion code | The sum of discount amounts is retrievable |
| FR-5.3 | The system can filter promotion performance by date range | Start date and end date range specification is supported |

## Success Criteria

| Criterion | Target | Measurement Method |
|-----------|--------|--------------------|
| Promotion creation success rate | 100% with valid data | No errors when all required fields are provided |
| Discount application accuracy | 100% accurate calculations | Verified by automated tests |
| Discount application latency | Imperceptible to users | No noticeable delay when scanning products |
| Promotion display on receipt | 100% | All applied promotions displayed with name |
| Transaction log recording rate | 100% | All applied promotions recorded in transaction logs |
| Performance aggregation accuracy | 100% | Aggregated results match the sum of individual transactions |
| Processing 100 concurrent promotions | No performance degradation | Load testing with multiple active promotions |

## Key Entities

### Promotion (Generic)

| Attribute | Description |
|-----------|-------------|
| promotion_code | Unique identifier for the promotion |
| promotion_type | Promotion type (e.g., "category_discount") |
| name | Display name of the promotion |
| description | Detailed description |
| start_datetime | Date and time when the promotion becomes active |
| end_datetime | Date and time when the promotion expires |
| is_active | Whether the promotion is enabled |

### Category Promotion Details

| Attribute | Description |
|-----------|-------------|
| target_store_codes | List of target store codes (applies to all stores if empty) |
| target_category_codes | List of category codes this promotion applies to |
| discount_rate | Discount rate (percentage, e.g., 10 = 10% off) |

### Discount Information (in Transaction Log)

| Attribute | Description |
|-----------|-------------|
| promotion_code | Code of the applied promotion |
| promotion_type | Promotion type |
| discount_rate | Applied discount rate |
| discount_amount | Discount amount |

### Relationships

- A promotion targets one or more categories (via category_code)
- A promotion is applied to line items in the cart
- Applied discounts reference the original promotion code
- Transaction logs retain the promotion code and are used for performance aggregation

## Design Principles

### Extensible Promotion Framework

The promotion system is designed with future extensibility in mind:

1. **Separation of promotion types**: Common attributes (code, name, period, active flag) are separated from type-specific attributes (category codes, discount rate, etc.)
2. **Plugin architecture**: Leverages the existing sales_promo plugin structure in the cart service, enabling new promotion types to be added as plugins
3. **Type identifier**: Processing logic is switched based on the promotion_type field

### Promotion Types That Can Be Added in the Future (Reference)

| Type | Description | Current Scope |
|------|-------------|---------------|
| category_discount | Category-level discount | **In scope** |
| item_discount | Per-item discount | Out of scope |
| quantity_discount | Quantity-based discount | Out of scope |
| bundle_discount | Bundle discount | Out of scope |

## Assumptions

1. **Single promotion per product**: Only one category-based promotion is applied per line item. Stacking of promotions is out of scope.
2. **Lowest price selection**: When multiple promotions match, the promotion with the highest discount rate (resulting in the lowest price) is automatically selected.
3. **Percentage discounts only**: Only percentage (%) discounts are supported. Fixed-amount discounts are out of scope.
4. **Tenant isolation**: Promotions are tenant-specific (multi-tenancy support is required).
5. **Timezone handling**: Promotion times are stored and compared in the tenant's local timezone.
6. **Discount restriction priority**: Product-level discount restrictions always take priority over promotion rules.
7. **No retroactive application**: Promotions are not retroactively applied to existing carts/transactions.
8. **Coexistence with manual discounts**: Category promotions can coexist with manually applied discounts on the same line item.
9. **Performance aggregation foundation**: Performance aggregation is based on promotion codes recorded in transaction logs.

## Out of Scope

- Fixed-amount discounts (only percentage discounts are supported)
- Customer-specific promotions (loyalty programs)
- Quantity-based promotions (buy X get Y free)
- Bundle promotions (multi-product sets)
- Coupon code entry
- Store-specific promotion targeting (future enhancement)
- Advanced analytics dashboards (only basic aggregation is supported)

## Dependencies

- Category master data (master-data service) - must exist
- Product master data with category_code field (master-data service) - must exist
- Cart service discount system - must support line-item discounts
- Sales promo plugin architecture (cart service) - exists but unused
- Transaction log (journal service) - destination for promotion code recording
- Report service - destination for performance aggregation implementation

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance impact from promotion checks | Checkout processing delays | Cache active promotions with a short TTL |
| Incorrect discount calculations | Financial loss | Comprehensive automated testing |
| Timezone confusion in promotion validity periods | Incorrect application times | Clear documentation and UTC storage with local conversion |
| Transaction log bloat | Storage and query performance degradation | Minimize promotion information, optimize indexes |
