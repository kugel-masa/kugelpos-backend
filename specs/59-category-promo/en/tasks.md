# Implementation Task List

## Overview

Detailed implementation tasks for the category promotion feature.

## Task List

### Phase 2-1: Foundation Setup

#### Task 1: DiscountInfo Extension

**Service**: commons
**File**: `services/commons/src/kugel_common/models/documents/base_tranlog.py`
**Priority**: High
**Dependencies**: None

**Description**:
- Add the following fields to the `DiscountInfo` class:
  - `promotion_code: Optional[str] = None`
  - `promotion_type: Optional[str] = None`
- Maintain backward compatibility (do not modify existing fields)

**Acceptance Criteria**:
- [x] New fields are added
- [x] Existing tests pass
- [x] Type hints are correct

---

#### Task 2: PromotionMasterDocument Creation

**Service**: master-data
**File**: `services/master-data/app/models/documents/promotion_master_document.py`
**Priority**: High
**Dependencies**: None

**Description**:
- Create the `PromotionMasterDocument` class
- Create the `CategoryPromoDetail` nested class
- Inherit from AbstractDocument

**Acceptance Criteria**:
- [x] All fields are defined
- [x] Validation rules are applied
- [x] Type hints are correct

---

#### Task 3: API Schema Creation

**Service**: master-data
**Files**:
- `services/master-data/app/api/common/schemas.py`
- `services/master-data/app/api/v1/schemas.py`

**Priority**: High
**Dependencies**: Task 2

**Description**:
- Create request/response schemas
  - `PromotionCreateRequest`
  - `PromotionUpdateRequest`
  - `PromotionResponse`
  - `PromotionDeleteResponse`
  - `CategoryPromoDetail`

**Acceptance Criteria**:
- [x] All schemas are defined
- [x] camelCase/snake_case conversion is configured
- [x] Validation rules are configured

---

### Phase 2-2: master-data Implementation

#### Task 4: PromotionMasterRepository Creation

**Service**: master-data
**File**: `services/master-data/app/models/repositories/promotion_master_repository.py`
**Priority**: High
**Dependencies**: Task 2

**Description**:
- Inherit from AbstractRepository
- Implement the following methods:
  - `create_promotion_async`
  - `get_promotion_by_code_async`
  - `get_promotions_by_filter_async`
  - `get_promotions_by_filter_paginated_async`
  - `get_active_promotions_async`
  - `get_active_promotions_by_category_async`
  - `get_active_promotions_by_store_async` # Filter by store code
  - `update_promotion_async`
  - `delete_promotion_async`

**Acceptance Criteria**:
- [x] All methods are implemented
- [x] Query for retrieving active promotions is correct
- [x] Error handling is appropriate

---

#### Task 5: PromotionMasterService Creation

**Service**: master-data
**File**: `services/master-data/app/services/promotion_master_service.py`
**Priority**: High
**Dependencies**: Task 4

**Description**:
- Implement business logic
  - Promotion code duplication check
  - Date range validation
  - Discount rate validation
- Call the Repository

**Acceptance Criteria**:
- [x] All methods are implemented
- [x] Validation is appropriate
- [x] Exception handling is appropriate

---

#### Task 6: API Endpoint Creation

**Service**: master-data
**File**: `services/master-data/app/api/v1/promotion_master.py`
**Priority**: High
**Dependencies**: Task 3, Task 5

**Description**:
- Create a FastAPI router
- Implement the following endpoints:
  - `POST /promotions`
  - `GET /promotions`
  - `GET /promotions/active`
  - `GET /promotions/{promotion_code}`
  - `PUT /promotions/{promotion_code}`
  - `DELETE /promotions/{promotion_code}`

**Acceptance Criteria**:
- [x] All endpoints are implemented
- [x] OpenAPI specification is correct
- [x] Error responses are appropriate

---

#### Task 7: Router Registration

**Service**: master-data
**File**: `services/master-data/app/main.py`
**Priority**: High
**Dependencies**: Task 6

**Description**:
- Import the promotion_master router
- Register it with app.include_router()

**Acceptance Criteria**:
- [x] Router is registered
- [x] Endpoints are visible at /docs

---

#### Task 8: Database Index Creation

**Service**: master-data
**File**: `services/master-data/app/database/database_setup.py`
**Priority**: Medium
**Dependencies**: Task 2

**Description**:
- Create the `create_master_promotion_collection` function
- Define required indexes
- Call it from `setup_database`

**Acceptance Criteria**:
- [x] Indexes are created
- [x] Unique index for duplication check is configured

---

#### Task 9: Promotion Master Unit Tests

**Service**: master-data
**File**: `services/master-data/tests/test_promotion_master.py`
**Priority**: High
**Dependencies**: Task 6

**Description**:
- Tests for CRUD operations
- Tests for validation errors
- Tests for retrieving active promotions

**Acceptance Criteria**:
- [x] Tests exist for all endpoints
- [x] Tests cover both success and error cases
- [x] Tests pass

---

### Phase 2-3: cart Implementation

#### Task 10: CategoryPromoPlugin Creation

**Service**: cart
**File**: `services/cart/app/services/strategies/sales_promo/category_promo.py`
**Priority**: High
**Dependencies**: Task 1, Task 6

**Description**:
- Inherit from AbstractSalesPromo
- Override the `configure` method:
  - Receive `tenant_id` and `terminal_info`, and internally create a `PromotionMasterWebRepository`
  - CartService does not need to know plugin-specific types (Open/Closed Principle)
- Implement the `apply` method:
  - Retrieve active promotions from master-data (specifying store code)
  - Check whether the current store is a promotion target (target_store_codes)
  - Check the category_code of each line_item
  - Apply matching promotions (select the maximum discount rate)
  - Check is_discount_restricted
  - Set promotion_code and promotion_type in DiscountInfo

**Acceptance Criteria**:
- [x] `configure()` self-creates the repository
- [x] Promotion application logic is correct
- [x] Store targeting works correctly (specific stores only, or all stores)
- [x] Lowest price selection works correctly
- [x] Discount restrictions are respected

---

#### Task 11: Plugin Registration

**Service**: cart
**File**: `services/cart/app/services/strategies/plugins.json`
**Priority**: High
**Dependencies**: Task 10

**Description**:
- Register the CategoryPromoPlugin

```json
{
  "sales_promo_strategies": [
    {
      "module": "app.services.strategies.sales_promo.category_promo",
      "class": "CategoryPromoPlugin",
      "args": ["category_promo"],
      "kwargs": {}
    }
  ]
}
```

**Acceptance Criteria**:
- [x] Plugin is registered
- [x] No errors occur at service startup

---

#### Task 12: Plugin Invocation Implementation (Two-Phase Model)

**Service**: cart
**Files**:
- `services/cart/app/services/strategies/sales_promo/abstract_sales_promo.py`
- `services/cart/app/services/cart_service.py`

**Priority**: High
**Dependencies**: Task 10, Task 11

**Description**:
- Add `execution_phase` property to `AbstractSalesPromo` (default: `"line_item"`)
- Add `phase` parameter to `_apply_sales_promotions_async()` to filter plugins by phase
- Change `__subtotal_async()` to a two-phase model:
  1. Apply line_item-phase promotions → calculate subtotal
  2. Only if subtotal-phase plugins exist: apply subtotal-phase promotions → recalculate
- No base code changes (cart_service.py) needed when adding new plugins

**Acceptance Criteria**:
- [x] `execution_phase` property is added to AbstractSalesPromo
- [x] Plugins are filtered based on phase
- [x] Second pass is skipped when no subtotal-phase plugins exist
- [x] Existing category promotion tests pass
- [x] Error handling is appropriate

---

#### Task 13: Recording Promotion Information in Transaction Logs

**Service**: cart
**File**: `services/cart/app/services/tran_service.py`
**Priority**: High
**Dependencies**: Task 1, Task 12

**Description**:
- During conversion from CartDocument to TransactionLog
- Preserve promotion_code and promotion_type from line_item.discounts

**Acceptance Criteria**:
- [x] Promotion information is recorded in transaction logs
- [x] Available for performance aggregation

---

#### Task 14: Promotion Application Integration Tests

**Service**: cart
**File**: `services/cart/tests/test_category_promo.py`
**Priority**: High
**Dependencies**: Task 12

**Description**:
- Integration tests for promotion application
- Store-specific promotion tests (applied only to target stores)
- All-store promotion tests
- Lowest price selection tests with multiple promotions
- Discount restriction tests
- Expired promotion tests

**Acceptance Criteria**:
- [x] Tests exist for all scenarios
- [x] Tests pass

---

### Phase 2-4: report Implementation

#### Task 15: Promotion Performance Aggregation Plugin Creation

**Service**: report
**File**: `services/report/app/services/plugins/promotion_report_maker.py`
**Priority**: Medium
**Dependencies**: Task 13

**Description**:
- Implement promotion performance aggregation logic
- Use MongoDB Aggregation Pipeline
- Group by promotion_code

**Acceptance Criteria**:
- [x] Aggregation logic is correct
- [x] Performance is adequate

---

#### Task 16: Performance Aggregation Tests

**Service**: report
**File**: `services/report/tests/test_promotion_report.py`
**Priority**: Medium
**Dependencies**: Task 15

**Description**:
- Tests for performance aggregation
- Tests for date range filtering
- Tests for aggregation result accuracy

**Acceptance Criteria**:
- [x] Tests pass
- [x] Aggregation results are accurate

---

## Dependency Diagram

```
Task 1 (commons: DiscountInfo Extension)
    │
    ├──────────────────────────────────┐
    │                                  │
Task 2 (master-data: Document)         │
    │                                  │
    ├── Task 3 (Schemas)               │
    │       │                          │
    ├── Task 4 (Repository)            │
    │       │                          │
    │       └── Task 5 (Service)       │
    │               │                  │
    │               └── Task 6 (API) ──┤
    │                       │          │
    │                       ├── Task 7 (Router)
    │                       │          │
    │                       └── Task 9 (Test)
    │                                  │
    └── Task 8 (Index)                 │
                                       │
Task 10 (cart: Plugin) ────────────────┘
    │
    ├── Task 11 (Plugin Registration)
    │       │
    │       └── Task 12 (Invocation)
    │               │
    │               ├── Task 13 (Transaction Log)
    │               │       │
    │               │       └── Task 15 (Report Aggregation)
    │               │               │
    │               │               └── Task 16 (Test)
    │               │
    │               └── Task 14 (Test)
```

## Estimates

| Phase | Number of Tasks | Estimated Effort |
|-------|----------------|-----------------|
| Phase 2-1 | 3 | Foundation setup |
| Phase 2-2 | 6 | master-data implementation |
| Phase 2-3 | 5 | cart implementation |
| Phase 2-4 | 2 | report implementation |
| **Total** | **16** | - |
