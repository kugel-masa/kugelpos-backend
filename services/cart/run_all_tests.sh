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

echo -e "${BLUE}Starting Cart Service tests...${NC}"
echo "================================"

# Test files in order
# First: Clean and setup
# Second: Integration tests
# Third: Unit tests
test_files=(
    # Setup tests (must run first)
    "tests/test_clean_data.py"
    "tests/test_setup_data.py"

    # Integration tests
    "tests/test_health.py"
    "tests/test_cart.py"
    "tests/test_void_return.py"
    "tests/test_payment_cashless_error.py"
    "tests/test_resume_item_entry.py"

    # Unit tests
    "tests/test_calc_subtotal_logic.py"
    "tests/test_terminal_cache.py"
    "tests/test_text_helper.py"
    "tests/test_tran_service_status.py"
    "tests/test_tran_service_unit_simple.py"
    "tests/test_transaction_status_repository.py"
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
echo -e "${BLUE}Cart Service Test Summary:${NC}"
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
