# Category Promotion Feature Implementation Plan

## Overview

This document describes the implementation plan for the category promotion feature.
Based on the functional requirements in [spec.md](./spec.md), it defines the technical design and implementation tasks.

## Technical Context

### Existing Architecture

| Component | Technology | Description |
|-----------|------------|-------------|
| master-data service | FastAPI + MongoDB | Add new promotion master |
| cart service | FastAPI + MongoDB | Implement promotion application logic |
| journal service | FastAPI + MongoDB | Record promotion codes in transaction logs |
| report service | FastAPI + MongoDB | Implement promotion performance aggregation |
| commons library | Python | Extend shared schemas and documents |

### Related Existing Code

| File | Description |
|------|-------------|
| `services/master-data/app/models/documents/category_master_document.py` | Category master (reference) |
| `services/cart/app/services/strategies/sales_promo/abstract_sales_promo.py` | Promotion plugin base class |
| `services/cart/app/services/strategies/plugins.json` | Plugin configuration |
| `services/cart/app/services/cart_service.py` | Cart service (add plugin invocation) |
| `services/commons/src/kugel_common/models/documents/base_tranlog.py` | Transaction log base class (discount info) |

### Dependencies

- Category master (master-data): Confirmed to exist
- Product master (master-data): Confirmed category_code field exists
- sales_promo plugin structure (cart): Confirmed to exist, currently unused
- Transaction log structure (commons): Confirmed DiscountInfo class exists

## Phase 0: Investigation and Design

### Investigation Items

| Item | Result |
|------|--------|
| Plugin invocation timing | Within `add_items_to_cart_async`, after item addition and before subtotal calculation |
| Existing DiscountInfo structure | seq_no, discount_type, discount_value, discount_amount, detail |
| Method for adding promotion info | Store promotion_code in DiscountInfo.detail, or add new fields |
| master-data to cart communication | HTTP calls via DaprClientHelper |

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Promotion master placement | master-data service | Consistent with other master data |
| Promotion type implementation | promotion_type field | Support for future extensions |
| Category detail storage method | Nested within the same document | Prioritize simplicity; type-specific collections to be considered in the future |
| DiscountInfo extension | Add promotion_code and promotion_type fields | Required for performance aggregation |
| Caching strategy | No cache for initial release | Add if performance issues arise |

## Phase 1: Data Model Design

See [data-model.md](./data-model.md) for details.

### New Entities

1. **PromotionMasterDocument** (master-data)
   - Generic promotion attributes + category details

2. **DiscountInfo extension** (commons)
   - Add promotion_code and promotion_type fields

### API Design

See [contracts/](./contracts/) for details.

## Phase 2: Implementation Tasks

### Task List

| # | Service | Task | Dependencies | Priority |
|---|---------|------|--------------|----------|
| 1 | commons | Add promotion_code and promotion_type fields to DiscountInfo | - | High |
| 2 | master-data | Create PromotionMasterDocument | - | High |
| 3 | master-data | Create PromotionMasterRepository | 2 | High |
| 4 | master-data | Create PromotionMasterService | 3 | High |
| 5 | master-data | Create promotion API schemas | 2 | High |
| 6 | master-data | Create promotion API endpoints | 4, 5 | High |
| 7 | master-data | Register router in main.py | 6 | High |
| 8 | master-data | Create database indexes | 2 | Medium |
| 9 | cart | Create CategoryPromoPlugin | 1, 6 | High |
| 10 | cart | Register plugin in plugins.json | 9 | High |
| 11 | cart | Implement plugin invocation in CartService | 9, 10 | High |
| 12 | cart | Record promotion info in transaction logs | 1, 11 | High |
| 13 | report | Create promotion performance aggregation plugin | 12 | Medium |
| 14 | master-data | Promotion master unit tests | 6 | High |
| 15 | cart | Promotion application integration tests | 11 | High |
| 16 | report | Performance aggregation tests | 13 | Medium |

### Implementation Order

```
Phase 2-1: Foundation Setup
├── Task 1: DiscountInfo extension (commons)
├── Task 2: PromotionMasterDocument (master-data)
└── Task 5: API schemas (master-data)

Phase 2-2: master-data Implementation
├── Task 3: Repository
├── Task 4: Service
├── Task 6: API endpoints
├── Task 7: Router registration
├── Task 8: Indexes
└── Task 14: Unit tests

Phase 2-3: cart Implementation
├── Task 9: CategoryPromoPlugin
├── Task 10: Plugin registration
├── Task 11: Plugin invocation
├── Task 12: Transaction log recording
└── Task 15: Integration tests

Phase 2-4: report Implementation
├── Task 13: Performance aggregation plugin
└── Task 16: Aggregation tests
```

## Deliverables

| File | Description |
|------|-------------|
| `specs/1-category-promo/spec.md` | Functional specification |
| `specs/1-category-promo/spec_review.md` | Review record |
| `specs/1-category-promo/plan.md` | Implementation plan (this file) |
| `specs/1-category-promo/data-model.md` | Data model design |
| `specs/1-category-promo/contracts/` | API contracts |
| `specs/1-category-promo/tasks.md` | Detailed task list |
| `specs/1-category-promo/checklists/requirements.md` | Specification quality checklist |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Unclear invocation point for sales_promo plugin | Implementation delay | Investigate cart_service.py in detail to identify the appropriate insertion point |
| Impact scope of DiscountInfo changes | Affect existing functionality | Maintain backward compatibility (new fields are Optional) |
| Performance degradation | Degraded user experience | Conduct load testing; introduce caching as needed |

## Next Steps

1. Create `data-model.md`
2. Create API definitions in `contracts/`
3. Create detailed tasks in `tasks.md`
4. Begin implementation
