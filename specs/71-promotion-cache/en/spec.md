# Promotion Master Cache Improvement Specification

| Item | Details |
|------|---------|
| Document ID | SPEC-002 |
| Related Issue | #71 |
| Target Service | cart |
| Related Service | master-data |
| Status | Under Review |
| Created | 2026-03-30 |

## 1. Overview

Improve the cart service's promotion plugin (CategoryPromoPlugin), which currently fetches promotion master data from the master-data service via HTTP on every cart operation (e.g., adding items).

By fetching promotion master data once at cart creation time and embedding it in the cart document, we achieve improved performance and price consistency within a transaction.

## 2. Background and Issues

### 2.1 Current Behavior

```
Add item → __subtotal_async() → CategoryPromoPlugin.apply()
                                   → master-data API call (every time)
                                     GET /tenants/{id}/promotions/active
```

Each cart operation triggers `_apply_sales_promotions_async()`, which internally makes an HTTP request to the master-data service every time.

### 2.2 Affected Operations

| Operation | Method | API Calls |
|-----------|--------|-----------|
| Add item | `add_item_to_cart_async` | 1/operation |
| Update quantity | `update_line_item_quantity_in_cart_async` | 1/operation |
| Update unit price | `update_line_item_unit_price_in_cart_async` | 1/operation |
| Cancel line item | `cancel_line_item_from_cart_async` | 1/operation |
| Add line discount | `add_discount_to_line_item_in_cart_async` | 1/operation |
| Subtotal | `subtotal_async` | 1/operation |
| Add cart discount | `add_discount_to_cart_async` | 1/operation |
| Add payment | `add_payment_to_cart_async` | 1/operation |
| Bill | `bill_async` | 1/operation |
| Resume item entry | `resume_item_entry_async` | 1/operation |

### 2.3 Problems

| Problem | Description |
|---------|-------------|
| **Performance** | A typical transaction with 10 items generates ~15 HTTP API requests, repeatedly fetching the same data with the same parameters |
| **Response variance** | Response time varies per item entry depending on whether an API call was made |
| **Price consistency** | If promotion master data changes mid-transaction, different promotion conditions may be applied within the same transaction |

## 3. Improvement Strategy

### 3.1 Design Concept

Embed promotion master data in `ReferenceMasters`, following the same pattern used for item master (`items`), tax master (`taxes`), and settings master (`settings`).

```
Cart creation:
  create_cart_async()
    ├─ store_info_repo.get_store_info_async()             ← existing
    ├─ settings_master_repo.get_all_settings_async()      ← existing
    ├─ tax_master_repo.load_all_taxes()                   ← existing
    ├─ promotion_master_repo.get_active_promotions_...()  ← added (once only)
    └─ cart_repo.create_cart_async(..., promotion_master)  ← added
         └─ cart.masters.promotions = promotion_master     ← embedded
```

```
Item entry:
  add_item_to_cart_async()
    └─ __subtotal_async()
         └─ _apply_sales_promotions_async()
              └─ strategy.apply(cart_doc)
                   └─ References cart_doc.masters.promotions (no API call)
```

### 3.2 Rationale for Fetch Timing

| Option | Decision | Reason |
|--------|----------|--------|
| Fetch once at cart creation | **Adopted** | Determine all item prices using the promotion conditions at transaction start. Same approach as tax/settings master |
| Fetch per item entry (current) | Rejected | Performance issues and no guarantee of price consistency within a transaction |
| TTL-based in-memory cache | Rejected | TTL expiry could cause different promotion conditions mid-transaction |

## 4. Functional Requirements

### FR-1: Promotion Master Embedding in Cart

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-1.1 | Add `promotions` field to `ReferenceMasters` | Can hold a list of `PromotionMasterDocument` |
| FR-1.2 | Fetch active promotion master data from master-data service at cart creation | Only one API call occurs within `create_cart_async` |
| FR-1.3 | Store fetched promotion master data in `cart.masters.promotions` | Promotion data is persisted in the cart document |

### FR-2: Plugin Interface Changes

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-2.1 | Add `promotions` parameter to `AbstractSalesPromo.apply()` signature | Existing plugins can receive `promotions` |
| FR-2.2 | `_apply_sales_promotions_async()` extracts `cart_doc.masters.promotions` and passes it as an argument to `apply(cart_doc, promotions)` | Plugins do not make their own API calls |
| FR-2.3 | `CategoryPromoPlugin` uses the passed promotion list | No HTTP communication occurs within the plugin |

### FR-3: Error Handling

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-3.1 | Fail cart creation if promotion master fetch fails | `CartCannotCreateException` is raised |
| FR-3.2 | Do **not** proceed with empty list on fetch failure | Transactions do not proceed without applicable discounts |
| FR-3.3 | Client (POS terminal) can retry on error | Cart creation can be re-executed for recovery |

### FR-4: Backward Compatibility

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-4.1 | `promotions` field is Optional (default: empty list) | Existing cart documents created before this change load correctly |
| FR-4.2 | Cart creation succeeds in environments with zero promotions | Normal operation with empty list when no active promotions exist |

## 5. Scope of Changes

### 5.1 Files to Modify

| File | Change |
|------|--------|
| `cart/app/models/documents/cart_document.py` | Add `promotions` field to `ReferenceMasters` |
| `cart/app/models/repositories/cart_repository.py` | Add `promotion_master` parameter to `create_cart_async` |
| `cart/app/services/cart_service.py` | Fetch promotions at cart creation, pass promotions in `_apply_sales_promotions_async` |
| `cart/app/services/strategies/sales_promo/abstract_sales_promo.py` | Change `apply()` signature |
| `cart/app/services/strategies/sales_promo/category_promo.py` | Use passed promotions, remove repository dependency |
| `cart/app/services/strategies/sales_promo/sales_promo_sample.py` | Align `apply()` signature |
| Related test files | Test modifications for above changes |

### 5.2 Unchanged

| Target | Reason |
|--------|--------|
| master-data service promotion API | No changes to endpoint or response format |
| `PromotionMasterDocument` | No changes to the document model itself |
| `PromotionMasterWebRepository` | Still used within cart service (only the caller changes) |
| Promotion application logic (best-price selection, etc.) | No changes to business logic |

## 6. Data Model Changes

### 6.1 ReferenceMasters (After Change)

```python
class ReferenceMasters(BaseDocumentModel):
    items: Optional[list[ItemMasterDocument]] = []
    taxes: Optional[list[TaxMasterDocument]] = []
    settings: Optional[list[SettingsMasterDocument]] = []
    promotions: Optional[list[PromotionMasterDocument]] = []  # Added
```

### 6.2 Cart Document (JSON Representation)

```json
{
  "cart_id": "...",
  "status": "Idle",
  "masters": {
    "items": [...],
    "taxes": [...],
    "settings": [...],
    "promotions": [
      {
        "promotion_code": "PROMO001",
        "promotion_type": "category_discount",
        "name": "Beverages 10% OFF",
        "start_datetime": "2026-03-01T00:00:00",
        "end_datetime": "2026-04-30T23:59:59",
        "is_active": true,
        "detail": {
          "targetCategoryCodes": ["BEV"],
          "discountRate": 10.0
        }
      }
    ]
  },
  "line_items": [...]
}
```

## 7. Processing Flow

### 7.1 Cart Creation (After Change)

```
Client → POST /cart/create
           │
           ▼
     create_cart_async()
           │
           ├─ Terminal status check (existing)
           ├─ Staff sign-in check (existing)
           ├─ Event sequence check (existing)
           │
           ├─ Get store info (existing)
           ├─ Get settings master (existing)
           ├─ Get tax master (existing)
           ├─ Get promotion master ← [ADDED]
           │    ├─ Success → store in promotions
           │    └─ Failure → raise exception → cart creation fails
           │
           ├─ cart_repo.create_cart_async(
           │      ..., promotion_master=promotions)
           │
           └─ Save cart to cache
```

### 7.2 Promotion Application During Item Entry (After Change)

```
Client → POST /cart/add_item
           │
           ▼
     add_item_to_cart_async()
           │
           └─ __subtotal_async()
                │
                ├─ _apply_sales_promotions_async(cart_doc, "line_item")
                │    │
                │    └─ strategy.apply(cart_doc, cart_doc.masters.promotions)
                │         │
                │         └─ References embedded data (no API call)
                │
                └─ calc_subtotal_async()
```

## 8. Assumptions

| # | Assumption |
|---|------------|
| 1 | Within the same transaction, all item prices are determined using the promotion conditions at cart creation time |
| 2 | Changes to promotion master data are reflected from the next cart creation (new transaction) |
| 3 | Promotion master data changes during business hours are rare; mid-transaction change reflection is not required |
| 4 | Promotion data size is small (~few KB); storage impact from embedding in cart documents is minimal |

## 9. Expected Benefits

| Metric | Before | After |
|--------|--------|-------|
| Promotion API calls per transaction | ~15 | **1** |
| Price consistency within transaction | Not guaranteed | **Guaranteed** |
| Item entry response time | Variable (API latency dependent) | **Uniform** |
| Cart creation response time | Slight increase (~tens of ms) | — |
| Promotion change reflection timing | Immediate (next operation) | Next transaction start |

## 10. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cart creation unavailable on promotion fetch failure | Medium | Provide clear error messages; client-side retry. Strengthen master-data service availability monitoring |
| Promotion changes during transaction not reflected | Low | Accepted by specification (Assumption 3). Operationally, promotion changes are typically made outside business hours |
| Cart document size increase | Low | Promotion data is lightweight (~few KB). Minimal impact on storage and communication |
| Impact on existing plugins from `apply()` signature change | Medium | `promotions` parameter is Optional (default: None) for backward compatibility |

## 11. Clarifications

### Session 2026-03-30

- Q: Is a separate timeout setting needed for promotion fetch when master-data service responds slowly? → A: No. Follow the existing HTTP client shared timeout (`get_pooled_client`)

## 12. Test Strategy

| Test Type | Content |
|-----------|---------|
| Unit test | Verify promotions are stored in `ReferenceMasters` |
| Unit test | Verify `CategoryPromoPlugin.apply()` uses passed promotion list |
| Unit test | Verify cart creation raises exception on promotion fetch failure |
| Unit test | Verify cart creation succeeds with zero promotions |
| Unit test | Verify end-to-end cache flow: fetch at creation → embed → pass to plugin → single API call |
| Integration test | Verify promotions are correctly applied through the full flow: cart creation → item entry → billing |
| Integration test | Verify changing promotion master mid-transaction does not affect the current transaction |
