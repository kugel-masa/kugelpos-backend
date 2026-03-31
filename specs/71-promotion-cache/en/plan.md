# Promotion Master Cache Improvement — Implementation Plan

## Overview

This document describes the implementation plan for caching promotion master data by embedding it in the cart document.
Based on the functional requirements defined in [spec.md](./spec.md).

## Technical Context

### Existing Architecture

| Component | Technology | Description |
|-----------|-----------|-------------|
| cart service | FastAPI + Dapr State | Change promotion fetch timing, extend ReferenceMasters |
| master-data service | FastAPI + MongoDB | Promotion master API (no changes) |

### Related Existing Code

| File | Description |
|------|-------------|
| `services/cart/app/models/documents/cart_document.py` | CartDocument / ReferenceMasters definition |
| `services/cart/app/models/repositories/cart_repository.py` | Cart creation and caching |
| `services/cart/app/services/cart_service.py` | Cart creation, promotion application orchestration |
| `services/cart/app/services/strategies/sales_promo/abstract_sales_promo.py` | Promotion plugin base class |
| `services/cart/app/services/strategies/sales_promo/category_promo.py` | Category promotion plugin |
| `services/cart/app/models/repositories/promotion_master_web_repository.py` | master-data API call repository |
| `services/cart/app/models/documents/promotion_master_document.py` | Promotion master document model |

### Dependencies

- ReferenceMasters pattern (cart): Established with items, taxes, settings
- PromotionMasterWebRepository (cart): Exists, caller to be changed
- PromotionMasterDocument (cart): Exists, no changes needed
- master-data promotion API: Exists, no changes needed

## Phase 0: Research & Design

### Research Items

| Item | Result |
|------|--------|
| ReferenceMasters existing pattern | Fetches `settings_master`, `tax_master`, `item_master` at cart creation and embeds. `item_master` is updated as items are added |
| Cart creation flow | `create_cart_async()` fetches each master sequentially and passes to `cart_repo.create_cart_async()`. On failure: `CartCannotCreateException` |
| Plugin call interface | `AbstractSalesPromo.apply(cart_doc)` → returns `CartDocument`. `_apply_sales_promotions_async()` calls plugins by phase |
| CategoryPromoPlugin data fetch | Calls `promotion_master_repo.get_active_promotions_by_store_async()` inside `apply()` every time |
| Error handling policy | Current: proceed with empty list on fetch failure. Improved: fail cart creation |

### Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Cache method | ReferenceMasters embedding (**implemented**) | Same established pattern as tax/settings master. Guarantees consistency within transaction |
| Fetch timing | At cart creation (once) | Unify all item prices using promotion conditions at transaction start |
| TTL cache | Rejected | Risk of data changing mid-transaction at TTL expiry |
| On promotion fetch failure | Fail cart creation | Proceeding with empty list would silently skip discounts, causing customer-facing pricing errors |
| Plugin interface change | `apply(cart_doc, promotions)` | Plugins no longer need to hold repositories directly, clarifying responsibilities |
| `promotions` parameter | Optional (default: None) | Maintains backward compatibility. Preserves option for future plugins to fetch independently |

## Phase 1: Data Model Design

### Changed Entities

#### 1. ReferenceMasters (cart_document.py)

| Field | Type | Change |
|-------|------|--------|
| items | `Optional[list[ItemMasterDocument]]` | Existing |
| taxes | `Optional[list[TaxMasterDocument]]` | Existing |
| settings | `Optional[list[SettingsMasterDocument]]` | Existing |
| **promotions** | **`Optional[list[PromotionMasterDocument]]`** | **Added** |

Default value: `[]` (empty list) — maintains backward compatibility with existing cart documents created before this change.

#### 2. AbstractSalesPromo.apply() (abstract_sales_promo.py)

```python
# Before
@abstractmethod
async def apply(self, cart_doc) -> CartDocument:

# After
@abstractmethod
async def apply(self, cart_doc, promotions: list = None) -> CartDocument:
```

### API Design

No API changes. Uses existing master-data service endpoint as-is.

| Endpoint | Change |
|----------|--------|
| `GET /tenants/{tenant_id}/promotions/active` | No change (only the caller changes) |

## Phase 2: Implementation Tasks

### Task List

| # | File | Task | Depends | Priority |
|---|------|------|---------|----------|
| 1 | `cart_document.py` | Add `promotions` field to ReferenceMasters, add import | - | High |
| 2 | `cart_repository.py` | Add `promotion_master` parameter to `create_cart_async`, add storage logic | 1 | High |
| 3 | `cart_service.py` | Add promotion fetch to `create_cart_async`, move `PromotionMasterWebRepository` instantiation to service | 2 | High |
| 4 | `cart_service.py` | Add exception handling for promotion fetch failure | 3 | High |
| 5 | `abstract_sales_promo.py` | Add `promotions` parameter to `apply()` signature | - | High |
| 6 | `category_promo.py` | Change to use passed `promotions`. Remove repository dependency | 5 | High |
| 7 | `cart_service.py` | Pass `cart_doc.masters.promotions` to `apply()` in `_apply_sales_promotions_async()` | 5, 6 | High |
| 8 | `sales_promo_sample.py` | Align `apply()` signature | 5 | Low |
| 9 | Test files | Unit test: ReferenceMasters.promotions storage confirmation | 1 | High |
| 10 | Test files | Unit test: CategoryPromoPlugin.apply() uses passed promotions | 6 | High |
| 11 | Test files | Unit test: Cart creation error on promotion fetch failure | 4 | High |
| 12 | Test files | Unit test: Normal operation with zero promotions | 3 | Medium |
| 13 | Test files | Integration test: Full flow from cart creation → item entry → billing | 7 | High |

### Implementation Order

```
Phase 2-1: Data Model & Interface Changes
├── Task 1: ReferenceMasters extension (cart_document.py)
├── Task 2: cart_repository.py parameter addition
└── Task 5: AbstractSalesPromo.apply() signature change

Phase 2-2: Core Implementation
├── Task 3: cart_service.py promotion fetch addition
├── Task 4: Error handling addition
├── Task 6: CategoryPromoPlugin changes
├── Task 7: _apply_sales_promotions_async() passing
└── Task 8: SalesPromoSample signature alignment

Phase 2-3: Tests
├── Task 9:  ReferenceMasters unit test
├── Task 10: CategoryPromoPlugin unit test
├── Task 11: Error handling unit test
├── Task 12: Zero promotions unit test
└── Task 13: Integration test
```

## Artifacts

| File | Description |
|------|-------------|
| `specs/71-promotion-cache/spec.md` | Feature specification |
| `specs/71-promotion-cache/plan.md` | Implementation plan (this file) |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Impact on existing plugins from `apply()` signature change | Build errors in existing plugins | Make `promotions` Optional for backward compatibility. Update all plugins simultaneously |
| Cart creation instability from promotion fetch failure | Unable to start transactions | Strengthen master-data service availability monitoring. Provide clear error messages for retry |
| Cart document size increase | Cache/communication overhead | Promotion data is ~few KB, impact is minimal |
| Impact on existing tests | Test failures | Fix and add all tests in Phase 2-3 |

## Next Steps

1. Client approval of specification (spec.md)
2. Begin implementation from Phase 2-1
3. Add/fix tests in Phase 2-3
4. Execute integration tests
