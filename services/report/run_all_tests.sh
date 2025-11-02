#!/bin/bash
export PIPENV_IGNORE_VIRTUALENVS=1


test_files=(
    "tests/test_clean_data.py"
    "tests/test_setup_data.py"
    "tests/test_health.py"
    "tests/test_report.py"
    "tests/test_category_report.py"
    "tests/test_item_report.py"
    "tests/test_payment_report_all.py"
    "tests/test_flash_date_range_validation.py"
    "tests/test_critical_issue_78.py"  # Issue #78 critical bug verification
    "tests/test_comprehensive_aggregation.py"  # Comprehensive aggregation tests
    "tests/test_data_integrity.py"  # Data integrity tests
    "tests/test_return_transactions.py"  # Return transaction tests
    "tests/test_void_transactions.py"  # Void transaction tests
    "tests/test_edge_cases.py"  # Edge case tests (empty arrays, rounding, etc.)
    "tests/test_split_payment_bug.py"  # Run last to avoid affecting other tests
)

for test_file in "${test_files[@]}"; do
    pipenv run pytest "$test_file"
done
