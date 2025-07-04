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
TOTAL_SERVICES=7
CURRENT_SERVICE=0
FAILED_SERVICES=()
PASSED_SERVICES=()

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}       Running all tests for microservices (${TOTAL_SERVICES} services)      ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Set required environment variables for testing
echo -e "${YELLOW}Setting required environment variables for testing...${NC}"
export SECRET_KEY="test-secret-key-123456789"
export PUBSUB_NOTIFY_API_KEY="test-api-key-123456789"

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
    
    # Run tests and capture output with environment variables
    if SECRET_KEY="$SECRET_KEY" PUBSUB_NOTIFY_API_KEY="$PUBSUB_NOTIFY_API_KEY" ./run_all_tests.sh > test_output.log 2>&1; then
        echo -e "${GREEN}✓ ${service} - All tests PASSED${NC}"
        PASSED_SERVICES+=("$service")
        
        # Show test summary if available
        if grep -q "passed" test_output.log; then
            echo -e "  └─ $(grep -E "[0-9]+ passed" test_output.log | tail -1)"
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
