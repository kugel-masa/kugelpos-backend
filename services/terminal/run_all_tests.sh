#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track overall success
OVERALL_SUCCESS=0
FAILED_TIERS=()
PASSED_TIERS=()
export PIPENV_IGNORE_VIRTUALENVS=1

echo -e "${BLUE}Starting Terminal Service tests...${NC}"
echo "================================"

# Tiered test execution: unit first (no deps), then e2e (full stack).
# integration/ is currently empty — tests will be promoted there as
# the in-process + respx pattern lands per-flow.
tiers=(
    "unit"
    "integration"
    "e2e"
)

for tier in "${tiers[@]}"; do
    test_dir="tests/${tier}"
    if [ ! -d "$test_dir" ]; then
        continue
    fi

    echo ""
    echo -e "${YELLOW}Running ${tier} tests...${NC}"
    echo "---------------------------------------------------"

    if pipenv run pytest "$test_dir" -m "$tier" -v; then
        echo -e "${GREEN}✓ PASSED: ${tier} tests${NC}"
        PASSED_TIERS+=("$tier")
    else
        rc=$?
        if [ "$rc" = "5" ]; then
            echo -e "${YELLOW}⊘ ${tier}: no tests collected (skipped)${NC}"
        else
            echo -e "${RED}✗ FAILED: ${tier} tests${NC}"
            FAILED_TIERS+=("$tier")
            OVERALL_SUCCESS=1
        fi
    fi
done

echo ""
echo "================================"
echo -e "${BLUE}Terminal Service Test Summary:${NC}"
echo -e "${GREEN}Passed: ${#PASSED_TIERS[@]}${NC}"
for t in "${PASSED_TIERS[@]}"; do
    echo -e "  ${GREEN}✓${NC} $t"
done

if [ ${#FAILED_TIERS[@]} -gt 0 ]; then
    echo -e "${RED}Failed: ${#FAILED_TIERS[@]}${NC}"
    for t in "${FAILED_TIERS[@]}"; do
        echo -e "  ${RED}✗${NC} $t"
    done
fi

echo "================================"
exit $OVERALL_SUCCESS
