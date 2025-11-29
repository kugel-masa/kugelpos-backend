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

echo -e "${BLUE}Starting Journal Service tests...${NC}"
echo "================================"

# Test files in order
test_files=(
    "tests/test_clean_data.py"
    "tests/test_setup_data.py"
    "tests/test_health.py"
    "tests/test_journal.py"
    "tests/test_journal_receipts.py"
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
echo -e "${BLUE}Journal Service Test Summary:${NC}"
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
