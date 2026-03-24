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

echo -e "${BLUE}Starting Master-Data Service tests...${NC}"
echo "================================"

# Test files in order
test_files=(
    "tests/test_clean_data.py"
    "tests/test_setup_data.py"
    "tests/test_health.py"
    "tests/test_operations.py"
    "tests/test_promotion_master.py"
    # Unit tests
    "tests/test_master_data_exceptions.py"
    "tests/test_json_settings.py"
    "tests/test_repositories.py"
    "tests/test_master_services.py"
    "tests/test_promotion_master_service.py"
    "tests/test_item_book_master_service.py"
    "tests/test_api_tenant.py"
    "tests/test_api_category.py"
    "tests/test_api_item.py"
    "tests/test_api_item_store.py"
    "tests/test_api_payment.py"
    "tests/test_api_settings.py"
    "tests/test_api_staff.py"
    "tests/test_api_tax.py"
    # JWT auth integration tests
    "tests/test_master_data_jwt_auth.py"
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
echo -e "${BLUE}Master-Data Service Test Summary:${NC}"
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
