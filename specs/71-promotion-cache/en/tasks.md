# Tasks: Promotion Master Cache Improvement

**Input**: Design documents from `/specs/71-promotion-cache/`
**Prerequisites**: plan.md, spec.md

**Tests**: Test strategy is specified in spec.md section 12, so test tasks are included.

**Organization**: This feature is a single user story (in-transaction promotion cache), so phases are organized by functional requirements (FR-1 through FR-4).

## Format: `[ID] [P?] [FR?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[FR]**: Corresponding functional requirement (FR-1: embedding, FR-2: plugin I/F, FR-3: error handling, FR-4: backward compat)
- Each task includes target file path

## Path Conventions

- `services/cart/app/` — Cart service source code
- `services/cart/tests/` — Cart service test code

---

## Phase 1: Data Model & Interface Changes

**Purpose**: Extend ReferenceMasters and change plugin interface. Foundation for subsequent phases.

**⚠️ CRITICAL**: Core implementation cannot proceed until this phase is complete.

- [X] T001 [P] [FR-1] Add `promotions` field to `ReferenceMasters` and import `PromotionMasterDocument` in `services/cart/app/models/documents/cart_document.py`
- [X] T002 [P] [FR-2] Add `promotions: list = None` parameter to `AbstractSalesPromo.apply()` in `services/cart/app/services/strategies/sales_promo/abstract_sales_promo.py`
- [X] T003 [FR-1] Add `promotion_master` parameter to `create_cart_async()` and store in `cart.masters.promotions` in `services/cart/app/models/repositories/cart_repository.py`

**Checkpoint**: Data model and interface changes complete.

---

## Phase 2: Core Implementation

**Purpose**: Move promotion fetch timing and update plugins. Core of the feature.

- [X] T004 [FR-1] Add `PromotionMasterWebRepository` instantiation to `cart_service.py` `__init__` (moved from plugin to service) in `services/cart/app/services/cart_service.py`
- [X] T005 [FR-1] Add promotion master fetch to `create_cart_async()` and pass to `cart_repo.create_cart_async()` in `services/cart/app/services/cart_service.py`
- [X] T006 [FR-3] Add `CartCannotCreateException` on promotion master fetch failure in `services/cart/app/services/cart_service.py`
- [X] T007 [FR-2] Pass `cart_doc.masters.promotions` to `strategy.apply()` in `_apply_sales_promotions_async()` in `services/cart/app/services/cart_service.py`
- [X] T008 [P] [FR-2] Update `CategoryPromoPlugin.apply()` to use passed `promotions` parameter. Remove repository creation in `configure()` and API call in `apply()` in `services/cart/app/services/strategies/sales_promo/category_promo.py`
- [X] T009 [P] [FR-2] Align `SalesPromoSample.apply()` signature to `promotions: list = None` in `services/cart/app/services/strategies/sales_promo/sales_promo_sample.py`

**Checkpoint**: Core implementation complete. Promotions fetched once at cart creation; plugins make no API calls.

---

## Phase 3: Test Modifications & Additions

**Purpose**: Fix existing tests and add new tests. Verify all functional requirements.

### Existing Test Fixes

- [X] T010 [P] Fix existing CategoryPromoPlugin tests for `apply()` signature change (add promotions parameter) in `services/cart/tests/test_category_promo_plugin.py`
- [X] T011 [P] Fix existing category promotion integration tests for `apply()` signature change in `services/cart/tests/test_category_promo.py`
- [X] T012 [P] Fix existing cart_service tests for `create_cart_async` parameter changes in `services/cart/tests/test_cart_service.py`

### New Tests

- [X] T013 [P] [FR-1] [FR-4] Unit test: Verify `ReferenceMasters` stores `promotions`, defaults to empty list, and existing cart JSON without `promotions` field deserializes correctly in `services/cart/tests/test_category_promo_plugin.py`
- [X] T014 [P] [FR-2] Unit test: Verify `CategoryPromoPlugin.apply()` uses passed `promotions` list and makes no API calls in `services/cart/tests/test_category_promo_plugin.py`
- [X] T015 [P] [FR-3] Unit test: Verify `CartCannotCreateException` is raised on promotion master fetch failure in `services/cart/tests/test_cart_service.py`
- [X] T016 [P] [FR-4] Unit test: Verify cart creation succeeds with zero promotions in `services/cart/tests/test_cart_service.py`
- [X] T017 [FR-1] [FR-2] End-to-end cache flow test: Verify promotions fetched at creation are embedded and passed to plugins with single API call in `services/cart/tests/test_cart_service.py`

**Checkpoint**: All tests passing. Acceptance criteria for FR-1 through FR-4 verified.

---

## Phase 4: Finalization

**Purpose**: Documentation updates and final verification

- [X] T018 [P] Update "cache strategy" design decision to "implemented" in plan.md in `specs/71-promotion-cache/plan.md`
- [X] T019 Run full test suite to verify no regressions to existing functionality

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Data Model & I/F)**: No dependencies — can start immediately
- **Phase 2 (Core Implementation)**: Requires Phase 1 completion
- **Phase 3 (Tests)**: Requires Phase 2 completion
- **Phase 4 (Finalization)**: Requires Phase 3 completion

### Within Each Phase

```
Phase 1:
  T001 (cart_document.py) ─┐
  T002 (abstract_sales_promo.py) ──── Parallelizable
  T003 (cart_repository.py) ← Depends on T001

Phase 2:
  T004 (cart_service.py __init__) ─→ T005 ─→ T006 ─→ T007  (Sequential)
  T008 (category_promo.py) ← Depends on T002 ──┐
  T009 (sales_promo_sample.py) ← Depends on T002 ── Parallelizable

Phase 3:
  T010, T011, T012 ── Existing test fixes (parallelizable)
  T013–T016 ── New unit tests (parallelizable)
  T017 ── End-to-end test (after above complete)
```

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 19 |
| Phase 1 (Data Model & I/F) | 3 tasks |
| Phase 2 (Core Implementation) | 6 tasks |
| Phase 3 (Tests) | 8 tasks |
| Phase 4 (Finalization) | 2 tasks |
| Parallelizable tasks | 12 tasks (63%) |
| Changed files | 6 source files + 3 test files |
