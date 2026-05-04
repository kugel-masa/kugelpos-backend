#!/bin/bash

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"
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

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Progress tracking
# 7 per-service suites + 1 repo-root cross-service e2e suite when present.
HAS_CROSS_SERVICE_E2E=false
if [ -d "$PROJECT_ROOT/tests/e2e" ] && \
   [ -f "$PROJECT_ROOT/tests/e2e/Pipfile" ] && \
   compgen -G "$PROJECT_ROOT/tests/e2e/test_*.py" > /dev/null 2>&1; then
    HAS_CROSS_SERVICE_E2E=true
fi
if [ "$HAS_CROSS_SERVICE_E2E" = "true" ]; then
    TOTAL_SERVICES=8
else
    TOTAL_SERVICES=7
fi
CURRENT_SERVICE=0
FAILED_SERVICES=()
PASSED_SERVICES=()

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}       Running all tests for microservices (${TOTAL_SERVICES} services)      ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Note: Do not set SECRET_KEY or PUBSUB_NOTIFY_API_KEY here
# Each service uses its own configuration from docker-compose.yaml
# Setting these variables globally would break JWT authentication between services

# Check and create .env.test file if needed
echo -e "${YELLOW}Checking .env.test file...${NC}"
if [ ! -f ".env.test" ]; then
    echo -e "${YELLOW}.env.test file not found. Creating from .env.test.sample...${NC}"
    
    if [ -f ".env.test.sample" ]; then
        # Copy sample file to .env.test
        cp ".env.test.sample" ".env.test"
        echo -e "${GREEN}✓ Copied .env.test.sample to .env.test${NC}"
        
        # Modify TENANT_ID to T9999
        if grep -q "TENANT_ID" ".env.test"; then
            sed -i 's/TENANT_ID=.*/TENANT_ID=T9999/' ".env.test"
            echo -e "${GREEN}✓ Updated TENANT_ID to T9999 in .env.test${NC}"
        else
            # If TENANT_ID doesn't exist, add it
            echo "TENANT_ID=T9999" >> ".env.test"
            echo -e "${GREEN}✓ Added TENANT_ID=T9999 to .env.test${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Warning: .env.test.sample file not found. Creating minimal .env.test...${NC}"
        echo "TENANT_ID=TEST_9999" > ".env.test"
        echo -e "${GREEN}✓ Created minimal .env.test with TENANT_ID=TEST_9999${NC}"
    fi
else
    echo -e "${GREEN}✓ .env.test file already exists${NC}"
fi

echo ""

# List of microservices
MICROSERVICES=("account" "master-data" "journal" "report" "stock" "terminal" "cart")

# Function to display progress bar
display_progress() {
    local current=$1
    local total=$2
    local percent=$((current * 100 / total))
    local filled=$((percent / 2))
    
    printf "\rOverall Progress: ["
    printf "%${filled}s" | tr ' ' '█'
    printf "%$((50 - filled))s" | tr ' ' '░'
    printf "] %d%% (%d/%d)" $percent $current $total
}

# Run tests for each service
for service in "${MICROSERVICES[@]}"; do
    CURRENT_SERVICE=$((CURRENT_SERVICE + 1))
    
    echo ""
    echo -e "${YELLOW}┌───────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${YELLOW}│ [${CURRENT_SERVICE}/${TOTAL_SERVICES}] Testing: ${service}${NC}"
    echo -e "${YELLOW}└───────────────────────────────────────────────────────────────┘${NC}"
    
    cd "$PROJECT_ROOT/services/$service"
    
    # Run tests and capture output
    if ./run_all_tests.sh > test_output.log 2>&1; then
        echo -e "${GREEN}✓ ${service} - All tests PASSED${NC}"
        PASSED_SERVICES+=("$service")
        
        # Show per-tier test summary if available
        if grep -q "passed" test_output.log; then
            awk '/Running [a-z0-9]+ tests\.\.\./{tier=$2}
                 /[0-9]+ passed/{gsub(/=/,""); gsub(/^ +| +$/,""); print "  └─ " tier ": " $0}' test_output.log
        fi
    else
        echo -e "${RED}✗ ${service} - Tests FAILED${NC}"
        FAILED_SERVICES+=("$service")
        
        # Show failure summary
        if grep -q "FAILED" test_output.log; then
            echo -e "${RED}  └─ $(grep -E "FAILED|failed" test_output.log | tail -3 | head -1)${NC}"
        fi
    fi
    
    # Clean up log file
    rm -f test_output.log
    
    cd ..
    
    # Update progress bar
    display_progress $CURRENT_SERVICE $TOTAL_SERVICES
    echo ""
done

# Cross-service e2e (repo-root tests/e2e/) — runs after every per-service
# suite has finished, against the same live stack. Skipped if the
# directory is absent or has no tests.
if [ "$HAS_CROSS_SERVICE_E2E" = "true" ]; then
    CURRENT_SERVICE=$((CURRENT_SERVICE + 1))

    echo ""
    echo -e "${YELLOW}┌───────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${YELLOW}│ [${CURRENT_SERVICE}/${TOTAL_SERVICES}] Testing: tests/e2e (cross-service)${NC}"
    echo -e "${YELLOW}└───────────────────────────────────────────────────────────────┘${NC}"

    cd "$PROJECT_ROOT/tests/e2e"

    if pipenv run pytest -m e2e --no-header -q > test_output.log 2>&1; then
        echo -e "${GREEN}✓ tests/e2e - All tests PASSED${NC}"
        PASSED_SERVICES+=("tests/e2e")

        if grep -q "passed" test_output.log; then
            grep -oE "[0-9]+ passed[^,]*" test_output.log | tail -1 | sed 's/^/  └─ e2e: /'
        fi
    else
        echo -e "${RED}✗ tests/e2e - Tests FAILED${NC}"
        FAILED_SERVICES+=("tests/e2e")

        if grep -q "FAILED" test_output.log; then
            echo -e "${RED}  └─ $(grep -E "FAILED|failed" test_output.log | tail -3 | head -1)${NC}"
        fi
    fi

    rm -f test_output.log
    cd "$PROJECT_ROOT"

    display_progress $CURRENT_SERVICE $TOTAL_SERVICES
    echo ""
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                        TEST SUMMARY                           ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Display summary
echo -e "${GREEN}Passed: ${#PASSED_SERVICES[@]}${NC}"
for service in "${PASSED_SERVICES[@]}"; do
    echo -e "  ${GREEN}✓${NC} $service"
done

if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
    echo -e "${RED}Failed: ${#FAILED_SERVICES[@]}${NC}"
    for service in "${FAILED_SERVICES[@]}"; do
        echo -e "  ${RED}✗${NC} $service"
    done
    exit 1
else
    echo ""
    echo -e "${GREEN}All tests completed successfully.${NC}"
    echo -e "${GREEN}kugelpos is ready!${NC}"
    exit 0
fi
