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

# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

echo -e "${BLUE}Starting Stock Service tests...${NC}"
echo "================================"

# Check if pipenv is installed
if ! command -v pipenv &> /dev/null; then
    echo -e "${RED}pipenv is not installed. Please install pipenv first.${NC}"
    exit 1
fi

# Install dependencies if needed
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Installing dependencies...${NC}"
    pipenv install
fi

# Test files in order
test_files=(
    "tests/test_clean_data.py"
    "tests/test_setup_data.py"
    "tests/test_stock.py"
    "tests/test_snapshot_date_range.py"
    "tests/test_snapshot_schedule_api.py"
    "tests/test_snapshot_scheduler.py"
    "tests/test_reorder_alerts.py"
    "tests/test_websocket_alerts.py"
    "tests/test_websocket_reorder_new.py"
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
echo -e "${BLUE}Stock Service Test Summary:${NC}"
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