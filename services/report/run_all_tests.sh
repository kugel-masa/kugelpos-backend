#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track overall success
OVERALL_SUCCESS=0
FAILED_TESTS=()
PASSED_TESTS=()
export PIPENV_IGNORE_VIRTUALENVS=1

echo -e "${BLUE}Starting Report Service tests...${NC}"
echo "================================"

# Test files in order
test_files=(
    "tests/test_clean_data.py"
    "tests/test_setup_data.py"
    "tests/test_health.py"
    "tests/test_report.py"
    "tests/test_issue_88_receipt_data.py"  # Issue #88: Receipt data validation
    "tests/test_category_report.py"
    "tests/test_item_report.py"
    "tests/test_payment_report_all.py"
    "tests/test_flash_date_range_validation.py"
    "tests/test_critical_issue_78.py"  # Issue #78 critical bug verification
    "tests/test_issue_90_internal_tax_not_deducted.py"  # Issue #90: Internal tax not deducted from sales_net
    "tests/test_sales_report_formula_external_tax.py"  # Issue #85: External tax formula verification
    "tests/test_sales_report_formula_internal_tax.py"  # Issue #85: Internal tax formula verification
    "tests/test_comprehensive_aggregation.py"  # Comprehensive aggregation tests
    "tests/test_data_integrity.py"  # Data integrity tests
    "tests/test_return_transactions.py"  # Return transaction tests
    "tests/test_void_transactions.py"  # Void transaction tests
    "tests/test_void_with_discount.py"  # Void transaction with discount tests
    "tests/test_void_cancels_everything.py"  # Void transaction cancels everything test
    "tests/test_sale_return_void_return.py"  # Sale → Return → Void Return scenario test
    "tests/test_edge_cases.py"  # Edge case tests (empty arrays, rounding, etc.)
    "tests/test_cancelled_transactions.py"  # Cancelled transaction handling tests
    "tests/test_split_payment_bug.py"  # Run last to avoid affecting other tests
)

TOTAL_TESTS=${#test_files[@]}
CURRENT_TEST=0

for test_file in "${test_files[@]}"; do
    CURRENT_TEST=$((CURRENT_TEST + 1))
    echo ""
    echo -e "${YELLOW}[${CURRENT_TEST}/${TOTAL_TESTS}] Running: ${test_file}${NC}"
    echo "---------------------------------------------------"
    
    if pipenv run pytest "$test_file" -v; then
        echo -e "${GREEN}✓ PASSED: ${test_file}${NC}"
        PASSED_TESTS+=("$test_file")
    else
        echo -e "${RED}✗ FAILED: ${test_file}${NC}"
        FAILED_TESTS+=("$test_file")
        OVERALL_SUCCESS=1
    fi
done

echo ""
echo "================================"
echo -e "${BLUE}Report Service Test Summary:${NC}"
echo -e "${GREEN}Passed: ${#PASSED_TESTS[@]}${NC}"
for test in "${PASSED_TESTS[@]}"; do
    echo -e "  ${GREEN}✓${NC} $test"
done

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo -e "${RED}Failed: ${#FAILED_TESTS[@]}${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "  ${RED}✗${NC} $test"
    done
fi

echo "================================"
exit $OVERALL_SUCCESS
