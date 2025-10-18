#!/bin/bash

# Copyright 2025 masa@kugel
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

###############################################################################
# Performance Test Runner for Cart Service
#
# This script runs performance tests with different user patterns:
# - Pattern 1: 20 concurrent users for 5 minutes
# - Pattern 2: 40 concurrent users for 5 minutes
#
# Usage:
#   ./run_perf_test.sh [pattern1|pattern2|all]
#
# Requirements:
#   - .env.test file in project root with TENANT_ID, API_KEY, etc.
#   - Locust installed (pipenv install locust)
#   - Cart service running
###############################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CART_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${CART_DIR}/../../.." && pwd)"

# Output directory for test results
OUTPUT_DIR="${SCRIPT_DIR}/results"
mkdir -p "${OUTPUT_DIR}"

# Timestamp for this test run
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

###############################################################################
# Function: Print colored message
###############################################################################
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

###############################################################################
# Function: Load environment variables
###############################################################################
load_env() {
    print_message "${BLUE}" "Loading environment variables..."

    # Load cart service .env if exists
    if [ -f "${CART_DIR}/.env" ]; then
        export $(grep -v '^#' "${CART_DIR}/.env" | xargs)
        print_message "${GREEN}" "  ✓ Loaded ${CART_DIR}/.env"
    fi

    # Load .env.test from root
    if [ -f "${ROOT_DIR}/.env.test" ]; then
        export $(grep -v '^#' "${ROOT_DIR}/.env.test" | xargs)
        print_message "${GREEN}" "  ✓ Loaded ${ROOT_DIR}/.env.test"
    else
        print_message "${RED}" "  ✗ Error: ${ROOT_DIR}/.env.test not found"
        exit 1
    fi

    # Set default BASE_URL_CART if not set
    if [ -z "${BASE_URL_CART}" ]; then
        export BASE_URL_CART="http://localhost:8003"
        print_message "${YELLOW}" "  ! Using default BASE_URL_CART: ${BASE_URL_CART}"
    fi

    # Verify required variables
    if [ -z "${API_KEY}" ]; then
        print_message "${RED}" "  ✗ Error: API_KEY not found in environment"
        exit 1
    fi

    if [ -z "${TENANT_ID}" ]; then
        print_message "${RED}" "  ✗ Error: TENANT_ID not found in environment"
        exit 1
    fi

    print_message "${GREEN}" "  ✓ API_KEY: ${API_KEY:0:10}..."
    print_message "${GREEN}" "  ✓ TENANT_ID: ${TENANT_ID}"
    print_message "${GREEN}" "  ✓ BASE_URL_CART: ${BASE_URL_CART}"
}

###############################################################################
# Function: Run performance test with specific pattern
###############################################################################
run_test_pattern() {
    local pattern_name=$1
    local num_users=$2
    local spawn_rate=$3
    local run_time=$4

    print_message "${BLUE}" "\n${'='*80}"
    print_message "${BLUE}" "Running Performance Test: ${pattern_name}"
    print_message "${BLUE}" "  Users: ${num_users}"
    print_message "${BLUE}" "  Spawn Rate: ${spawn_rate}/s"
    print_message "${BLUE}" "  Duration: ${run_time}"
    print_message "${BLUE}" "${'='*80}\n"

    # Set environment variables for this pattern
    export PERF_TEST_NUM_USERS="${num_users}"
    export PERF_TEST_SPAWN_RATE="${spawn_rate}"
    export PERF_TEST_RUN_TIME="${run_time}"

    # Output files
    local html_report="${OUTPUT_DIR}/${pattern_name}_${TIMESTAMP}.html"
    local csv_stats="${OUTPUT_DIR}/${pattern_name}_${TIMESTAMP}_stats.csv"
    local csv_history="${OUTPUT_DIR}/${pattern_name}_${TIMESTAMP}_history.csv"
    local csv_failures="${OUTPUT_DIR}/${pattern_name}_${TIMESTAMP}_failures.csv"

    # Run Locust
    cd "${SCRIPT_DIR}"

    pipenv run locust \
        -f locustfile.py \
        --host="${BASE_URL_CART}" \
        --users="${num_users}" \
        --spawn-rate="${spawn_rate}" \
        --run-time="${run_time}" \
        --headless \
        --html="${html_report}" \
        --csv="${OUTPUT_DIR}/${pattern_name}_${TIMESTAMP}" \
        --loglevel=INFO

    local exit_code=$?

    if [ ${exit_code} -eq 0 ]; then
        print_message "${GREEN}" "\n✓ ${pattern_name} completed successfully"
        print_message "${GREEN}" "  HTML Report: ${html_report}"
        print_message "${GREEN}" "  CSV Stats: ${csv_stats}"
    else
        print_message "${RED}" "\n✗ ${pattern_name} failed with exit code ${exit_code}"
        return ${exit_code}
    fi

    # Wait before next test
    if [ "${pattern_name}" != "Pattern 2 (40 users)" ]; then
        print_message "${YELLOW}" "\nWaiting 30 seconds before next test..."
        sleep 30
    fi
}

###############################################################################
# Function: Run Pattern 1 (20 users)
###############################################################################
run_pattern1() {
    run_test_pattern "Pattern_1_20users" 20 2 "5m"
}

###############################################################################
# Function: Run Pattern 2 (40 users)
###############################################################################
run_pattern2() {
    run_test_pattern "Pattern_2_40users" 40 4 "5m"
}

###############################################################################
# Function: Run all patterns
###############################################################################
run_all() {
    print_message "${BLUE}" "\n${'='*80}"
    print_message "${BLUE}" "Running All Performance Test Patterns"
    print_message "${BLUE}" "${'='*80}\n"

    run_pattern1
    run_pattern2

    print_message "${GREEN}" "\n${'='*80}"
    print_message "${GREEN}" "All Performance Tests Completed"
    print_message "${GREEN}" "${'='*80}"
    print_message "${GREEN}" "\nResults saved to: ${OUTPUT_DIR}"
    ls -lh "${OUTPUT_DIR}/"*"${TIMESTAMP}"*
}

###############################################################################
# Function: Show usage
###############################################################################
show_usage() {
    cat << EOF
Usage: $0 [OPTION]

Run performance tests for Cart Service

OPTIONS:
    pattern1    Run Pattern 1: 20 concurrent users for 5 minutes
    pattern2    Run Pattern 2: 40 concurrent users for 5 minutes
    all         Run all test patterns (default)
    help        Show this help message

EXAMPLES:
    $0              # Run all patterns
    $0 all          # Run all patterns
    $0 pattern1     # Run only 20 users pattern
    $0 pattern2     # Run only 40 users pattern

REQUIREMENTS:
    - .env.test file in project root
    - Locust installed (pipenv install locust)
    - Cart service running and accessible

OUTPUT:
    Results are saved to: ${OUTPUT_DIR}
    - HTML reports: Pattern_*_TIMESTAMP.html
    - CSV statistics: Pattern_*_TIMESTAMP_stats.csv
    - CSV history: Pattern_*_TIMESTAMP_history.csv

EOF
}

###############################################################################
# Main execution
###############################################################################
main() {
    local command=${1:-all}

    case "$command" in
        pattern1)
            load_env
            run_pattern1
            ;;
        pattern2)
            load_env
            run_pattern2
            ;;
        all)
            load_env
            run_all
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_message "${RED}" "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
