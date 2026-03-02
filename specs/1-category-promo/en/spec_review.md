# Specification Review Record

**Review date**: 2026-02-05
**Reviewer**: masa
**Subject**: Category Promotion Feature Specification

## Review Findings

### 1. Selection Logic When Multiple Promotions Match

**Finding**:
> When multiple active promotions exist, adopt the setting that results in the lowest price

**Before change**: Selection based on a priority field
**After change**: Automatically select the promotion with the highest discount rate (lowest price for the customer)

**Affected areas**:
- Scenario 4: Multiple promotions match
- FR-1.7: Lowest price selection requirement
- Removed priority field from the promotion entity

---

### 2. Simplification of Discount Types

**Finding**:
> Only percentage (%) discount is needed for the discount type

**Before change**: Support both percentage discount and fixed amount discount
**After change**: Support only percentage discount

**Affected areas**:
- FR-1.4: Changed to percentage discount only
- FR-2.3: Unified calculation formula to "Discount amount = price x quantity x discount rate"
- Removed discount_type field from promotion entity, keeping only discount_rate
- Added "Fixed amount discount" to out-of-scope section

---

### 3. Extensibility of the Promotion Framework

**Finding**:
> Please design the promotion registration assuming that types other than product category promotions will be added in the future

**Before change**: Design specific to category promotions
**After change**: Designed as an extensible promotion framework

**Affected areas**:
- Added extensibility description to the overview section
- FR-1.1: Added requirement for promotion type identification
- FR-3.4: Added type-based filtering API
- Separated main entity into "generic promotion" and "category promotion detail"
- Added new "Design Principles" section describing extensible architecture
- Added reference list of future promotion types that can be added

---

### 4. Promotion Results Aggregation Feature

**Finding**:
> Please output the promotion code in sales results so that promotion results can be aggregated

**Before change**: No results aggregation feature (listed as out-of-scope)
**After change**: Added promotion code recording and results aggregation to functional requirements

**Affected areas**:
- Added new Scenario 5 "Promotion Results Verification"
- Added new FR-4 "Recording Promotions in Sales Results" (3 requirements)
- Added new FR-5 "Promotion Results Aggregation" (3 requirements)
- Added "Recording rate in transaction logs" and "Accuracy of results aggregation" to success criteria
- Added promotion_code to the discount info entity
- Added journal service and report service to dependencies
- Removed "Promotion reports and analysis" from out-of-scope (basic aggregation is now covered)

---

### 5. Document Language

**Finding**:
> Please write all deliverables (documents) in Japanese

**Response**: All specifications and checklists created in Japanese

---

### 6. Store-Level Promotion Registration

**Finding**:
> Want to be able to register promotions per store in the promotion master

**Before change**: Promotion management only at the tenant level
**After change**: Added store specification method (target_store_codes)

**Design decision**:
- Adopted Method A (store specification method)
- Added `target_store_codes` field
- When the array is empty or omitted, the promotion applies to all stores

**Affected areas**:
- spec.md: Added FR-1.4.1, FR-2.2.1, FR-3.5
- data-model.md: Added target_store_codes field
- contracts/promotion-api.md: Added targetStoreCodes to request/response

---

## Review Results

| Finding | Status |
|---------|--------|
| Lowest price selection logic | ✅ Completed |
| Percentage discount only | ✅ Completed |
| Extensible framework design | ✅ Completed |
| Promotion results aggregation feature | ✅ Completed |
| Japanese documentation | ✅ Completed |
| Store-level promotion registration | ✅ Completed |

**Status**: All review findings have been addressed
