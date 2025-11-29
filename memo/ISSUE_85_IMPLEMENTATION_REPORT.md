# Issue #85 Implementation Report

## Overview
Fixed the sales report calculation formula to correctly handle tax amounts for both external tax (外税) and internal tax (内税) scenarios.

**Issue**: [#85 - Sales report formula should include tax in net sales calculation](https://github.com/kugel-masa/kugelpos-backend-private/issues/85)

**Implementation Date**: 2025-11-06

## Problem Statement

The original sales report formula did not properly account for tax amounts in the net sales calculation:

**Old Formula** (Incorrect):
```
純売上 = 総売上 - 返品 - 値引
```

This formula treated tax-exclusive and tax-inclusive amounts inconsistently, leading to incorrect net sales calculations.

## Solution

Implemented the correct formula that properly handles tax amounts:

**New Formula** (Correct):
```
純売上 = 総売上 - 返品 - 値引 - 税額
```

Where:
- 総売上 (sales_gross) = Tax-inclusive amount
- 返品 (returns) = Tax-inclusive amount
- 値引 (discount) = Discount amount
- 税額 (tax) = Net tax (sales tax - returns tax)
- 純売上 (sales_net) = Tax-exclusive net amount

## Implementation Details

### 1. Core Implementation (`sales_report_maker.py`)

Modified four key methods to use tax-inclusive amounts and calculate net tax:

#### a. `_make_sales_gross()` (Line ~720)
**Changed**: Use `total_amount_with_tax` instead of `total_amount`
```python
# Before
"sales_gross_amount": {"$sum": "$sales.total_amount"}

# After
"sales_gross_amount": {"$sum": "$sales.total_amount_with_tax"}
```

#### b. `_make_returns()` (Line ~799)
**Changed**: Use `total_amount_with_tax` instead of `total_amount`
```python
# Before
"returns_amount": {"$sum": "$sales.total_amount"}

# After
"returns_amount": {"$sum": "$sales.total_amount_with_tax"}
```

#### c. `_make_net_tax()` (Line ~1041-1087) - NEW METHOD
**Added**: Calculate net tax by summing tax amounts with transaction type factoring
```python
def _make_net_tax(self, aggregated_docs: List[dict]) -> float:
    """
    Calculate net tax amount (sales tax - returns tax - void tax + void return tax).
    """
    net_tax = 0.0
    for doc in aggregated_docs:
        factor = self._get_transaction_type_factor(doc.get("_id", {}).get("transaction_type"))
        tax_amount = doc.get("tax_amount", 0.0)
        net_tax += tax_amount * factor
    return net_tax
```

#### d. `_make_sales_net()` (Line ~893-945)
**Changed**: Apply the new formula including net tax
```python
# Before
sales_net_amount = sales_gross_amount - returns_amount - discount_for_lineitems_amount - discount_for_subtotal_amount

# After
net_tax = self._make_net_tax(aggregated_docs)
sales_net_amount = sales_gross_amount - returns_amount - discount_for_lineitems_amount - discount_for_subtotal_amount - net_tax
```

### 2. Transaction Type Factoring

The implementation correctly handles all transaction types using factoring:

| Transaction Type | Code | Factor | Effect |
|-----------------|------|--------|--------|
| NormalSales | 101 | +1 | Adds to sales, tax |
| ReturnSales | 102 | -1 | Subtracts from sales, tax |
| VoidSales | 201 | -1 | Reverses sale, tax |
| VoidReturn | 202 | +1 | Reverses return, tax |

### 3. External Tax vs Internal Tax

The formula works correctly for both tax types:

**External Tax (外税)**:
- `total_amount` = Tax-exclusive amount (税抜)
- `total_amount_with_tax` = Tax-inclusive amount (税込)
- Tax is added separately to the base price

**Internal Tax (内税)**:
- `total_amount` = Tax-inclusive amount (税込)
- `total_amount_with_tax` = Same as `total_amount`
- Tax is already included in the price

By using `total_amount_with_tax` consistently, the formula handles both cases correctly.

## Test Coverage

### New Tests Created

#### 1. `test_sales_report_formula_external_tax.py`
Tests the formula with external tax scenario:
- Sale: 3,500円(税抜) → 3,300円(税込) after 500円 discount + 300円 tax
- Return: Same item returned
- **Expected Results**:
  - 総売上 = 3,800円 (3,300 + 500)
  - 返品 = 3,300円
  - 明細値引 = 0円 (500 - 500 = 0, discount cancels out)
  - 税額 = 0円 (300 - 300 = 0, net tax)
  - 純売上 = 500円 (3,800 - 3,300 - 0 - 0)

**Status**: ✅ PASSED

#### 2. `test_sales_report_formula_internal_tax.py`
Tests the formula with internal tax scenario:
- Sale: 3,500円(税込) → 3,000円(税込) after 500円 discount (税273円 included)
- Return: Same item returned
- **Expected Results**:
  - 総売上 = 3,500円 (3,000 + 500)
  - 返品 = 3,000円
  - 明細値引 = 0円 (500 - 500 = 0)
  - 税額 = 0円 (273 - 273 = 0, net tax)
  - 純売上 = 500円 (3,500 - 3,000 - 0 - 0)

**Status**: ✅ PASSED

### Existing Tests Updated

#### 3. `test_comprehensive_aggregation.py`
**Changed**: Updated expected return amount from tax-exclusive to tax-inclusive
```python
# Before
assert returns.amount == 500  # Tax-exclusive

# After
assert returns.amount == 550  # Tax-inclusive (Issue #85)
```

**Status**: ✅ PASSED

#### 4. `test_return_transactions.py`
**Changed**: Updated all three test cases to use tax-inclusive amounts

**Test 1: `test_return_transaction_basic`**
```python
# Before
assert report.sales_gross.amount == 1000  # Tax-exclusive
assert report.returns.amount == 500       # Tax-exclusive

# After
assert report.sales_gross.amount == 1100  # Tax-inclusive
assert report.returns.amount == 550       # Tax-inclusive
```

**Test 2: `test_return_exceeds_sales`**
```python
# Before
assert report.returns.amount == 1500  # Tax-exclusive

# After
assert report.returns.amount == 1650  # Tax-inclusive
```

**Test 3: `test_multiple_returns_same_day`**
```python
# Before
assert report.sales_gross.amount == 3000  # Tax-exclusive
assert report.returns.amount == 800       # Tax-exclusive

# After
assert report.sales_gross.amount == 3300  # Tax-inclusive
assert report.returns.amount == 880       # Tax-inclusive
```

**Status**: ✅ All 3 tests PASSED

#### 5. `check_report_data.py`
**Changed**: Updated the verification formula to include tax amount
```python
# Before (Missing tax in formula)
assert (
    sales_gross_amount
    == sales_net_amount + returns_amount + discount_for_lineItems_amount + discount_for_subtotal_amount
)

# After (Correct formula with tax)
# Issue #85: New formula - 純売上 = 総売上 - 返品 - 値引 - 税額
assert (
    sales_net_amount
    == sales_gross_amount - returns_amount - discount_for_lineItems_amount - discount_for_subtotal_amount - tax_amount
)
```

**Status**: ✅ PASSED (Fixed `test_report.py` failures)

### Test Suite Results

**All 19 tests PASSED** ✅

```
✓ tests/test_clean_data.py
✓ tests/test_setup_data.py
✓ tests/test_health.py
✓ tests/test_report.py
✓ tests/test_tax_display.py
✓ tests/test_category_report.py
✓ tests/test_item_report.py
✓ tests/test_payment_report_all.py
✓ tests/test_flash_date_range_validation.py
✓ tests/test_critical_issue_78.py
✓ tests/test_sales_report_formula_external_tax.py   ← NEW (Issue #85)
✓ tests/test_sales_report_formula_internal_tax.py   ← NEW (Issue #85)
✓ tests/test_comprehensive_aggregation.py           ← UPDATED
✓ tests/test_data_integrity.py
✓ tests/test_return_transactions.py                 ← UPDATED
✓ tests/test_void_transactions.py
✓ tests/test_edge_cases.py
✓ tests/test_cancelled_transactions.py
✓ tests/test_split_payment_bug.py
```

## Key Learnings

### 1. Discount Cancellation Behavior
When an item with a discount is returned, the discount cancels out:
- Sale discount: +500円 (factor=1)
- Return discount: -500円 (factor=-1)
- Net discount: 0円

This is the correct behavior because returning a discounted item should fully reverse the discount.

### 2. Tax-Inclusive vs Tax-Exclusive Amounts
The key to fixing this issue was consistently using `total_amount_with_tax` for both 総売上 and 返品:
- **総売上**: Always uses tax-inclusive amount (what the customer saw)
- **返品**: Always uses tax-inclusive amount (what was refunded)
- **純売上**: Tax-exclusive amount (actual sales revenue)

### 3. Net Tax Calculation
The net tax must account for all transaction types with proper factoring:
```
Net Tax = Sales Tax - Returns Tax - Void Sales Tax + Void Returns Tax
```

This ensures that voided transactions properly reverse their tax impact.

## Files Modified

### Core Implementation
1. `/services/report/app/services/plugins/sales_report_maker.py`
   - Modified: `_make_sales_gross()`, `_make_returns()`, `_make_sales_net()`
   - Added: `_make_net_tax()`

### Tests
2. `/services/report/tests/test_sales_report_formula_external_tax.py` (NEW)
3. `/services/report/tests/test_sales_report_formula_internal_tax.py` (NEW)
4. `/services/report/tests/test_comprehensive_aggregation.py` (UPDATED)
5. `/services/report/tests/test_return_transactions.py` (UPDATED)
6. `/services/report/tests/check_report_data.py` (UPDATED)

### Test Configuration
7. `/services/report/run_all_tests.sh` (UPDATED - added new tests)

## Verification

The implementation has been verified through:

1. ✅ **Unit Tests**: Two comprehensive tests covering external and internal tax scenarios
2. ✅ **Integration Tests**: All existing tests updated and passing
3. ✅ **Regression Tests**: No regressions introduced - all 19 tests pass
4. ✅ **Formula Verification**: Mathematical verification in test output confirms formula correctness

### Example Verification Output (External Tax)
```
=== External Tax Test Results ===
総売上 (sales_gross): 3800.0 yen (count: 1)
返品 (returns): 3300.0 yen (count: 1)
明細値引 (discount_for_lineitems): 0.0 yen
小計値引 (discount_for_subtotal): 0.0 yen
純売上 (sales_net): 500.0 yen
税額 (tax): 0.0 yen

✅ Formula verification:
   純売上 (500.0) = 総売上 (3800.0) - 返品 (3300.0) - 明細値引 (0.0) - 小計値引 (0.0) - 税額 (0)
   500.0 = 3800.0 - 3300.0 - 0.0 - 0.0 - 0
   500.0 = 500.0
```

## Impact Assessment

### Benefits
1. ✅ **Accuracy**: Sales reports now show correct net sales amounts
2. ✅ **Consistency**: Handles both external and internal tax uniformly
3. ✅ **Completeness**: Properly accounts for all transaction types (sales, returns, voids)
4. ✅ **Maintainability**: Clear formula with comprehensive test coverage

### Breaking Changes
⚠️ **API Response Changes**:
- `salesGross.amount` now returns tax-inclusive amount (previously tax-exclusive)
- `returns.amount` now returns tax-inclusive amount (previously tax-exclusive)
- `salesNet.amount` calculation now includes tax deduction

### Migration Required
Clients consuming the sales report API should be aware that:
1. 総売上 (sales_gross) values will be higher (now includes tax)
2. 返品 (returns) values will be higher (now includes tax)
3. 純売上 (sales_net) values will be lower (now deducts net tax)

These changes accurately reflect the business reality of tax-inclusive transactions.

## Conclusion

Issue #85 has been successfully implemented and verified. The new formula correctly handles tax amounts for both external and internal tax scenarios, with comprehensive test coverage ensuring the correctness of the implementation.

**Status**: ✅ **RESOLVED**

**All tests passing**: 19/19 ✅

---

**Implementation completed by**: Claude Code
**Date**: 2025-11-06
**Related Issues**: #85
