---
description: Review MongoDB aggregation pipeline for Cartesian Product issues
---

## Overview

Skill for reviewing MongoDB aggregation pipelines.
**Detects Cartesian Product issues caused by multiple $unwind operations.**

## CRITICAL RULE

**NEVER USE $push AFTER MULTIPLE $unwind OPERATIONS**

Multiple `$unwind` operations on arrays cause Cartesian products.
When re-collecting arrays, **always use `$addToSet`**.

### Example

```python
# Original: 2 payments × 2 taxes
# After $unwind both: 2 × 2 = 4 documents!

# ❌ WRONG: $push collects duplicates
"payments": {"$push": "$payments"}  # [pay1, pay1, pay2, pay2]
# Sum: 4360 (WRONG!)

# ✅ CORRECT: $addToSet eliminates duplicates
"payments": {"$addToSet": "$payments"}  # [pay1, pay2]
# Sum: 2180 (CORRECT!)
```

## Code Review Checklist

### 1. Search for $unwind operations

```bash
grep -n "\$unwind" services/report/app/services/plugins/*.py
```

### 2. If multiple $unwind exist, verify $addToSet usage

```bash
grep -n "\$push" services/report/app/services/plugins/*.py
```

### 3. Pattern to follow

```python
pipeline = [
    {"$unwind": "$payments"},
    {"$unwind": "$taxes"},
    # CRITICAL: Group immediately after unwinds
    {"$group": {
        "_id": "$transaction_no",
        "total_amount": {"$first": "$sales.total_amount"},  # $first!
        "payments": {"$addToSet": "$payments"},  # $addToSet!
        "taxes": {"$addToSet": "$taxes"}         # $addToSet!
    }}
]
```

## Testing Requirements

- [ ] Multiple payments (minimum 2)
- [ ] Multiple taxes (minimum 2)
- [ ] Multiple terminals (for store-wide reports)
- [ ] Assertions: `count == 1` (NOT count × Cartesian size)

## Red Flags - Reject PR

- Multiple `$unwind` followed by `$push`
- No tests with multiple payments AND taxes
- Magic multipliers: `expected * 2`, `expected * 4`

## Reference

- Issue #78 (RESOLVED)
- Files: `sales_report_maker.py:493-494`
- Tests: `test_critical_issue_78.py`
