---
description: MongoDB aggregation pipelineのCartesian Product問題をレビュー
---

## Overview

MongoDB aggregation pipelineのレビュー用スキル。
**複数の$unwind操作によるCartesian Product問題**を検出します。

## CRITICAL RULE

**NEVER USE $push AFTER MULTIPLE $unwind OPERATIONS**

複数の配列を`$unwind`するとCartesian productが発生。
配列を再収集する場合は**必ず`$addToSet`**を使用。

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
