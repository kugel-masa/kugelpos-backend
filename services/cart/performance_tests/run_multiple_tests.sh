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
# Multiple Performance Test Runner for Cart Service
#
# This script runs multiple performance test patterns sequentially:
# - Each pattern runs with cleanup and setup
# - Test results are backed up after each pattern
# - Final comparison report is generated
#
# Test Patterns:
#   - 5 concurrent users for 15 minutes
#   - 10 concurrent users for 15 minutes
#   - 15 concurrent users for 15 minutes
#   - 20 concurrent users for 15 minutes
#
# Usage:
#   ./run_multiple_tests.sh
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
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Output directory for test results
OUTPUT_DIR="${SCRIPT_DIR}/results"
BACKUP_BASE_DIR="${SCRIPT_DIR}/results_backup"

# Timestamp for this test run
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE_DIR}/${TIMESTAMP}"

# Test patterns: users and duration
#TEST_PATTERNS=(3 5 10 15)
TEST_PATTERNS=(1 3)
TEST_DURATION="3m"

# Function to print section header
print_header() {
    echo ""
    echo -e "${CYAN}================================================================================${NC}"
    echo -e "${CYAN}${BOLD}$1${NC}"
    echo -e "${CYAN}================================================================================${NC}"
    echo ""
}

# Function to print success message
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error message
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to print info message
print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Function to print warning message
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Function to backup test results for a specific pattern
backup_results() {
    local pattern=$1
    local backup_subdir="${BACKUP_DIR}/${pattern}users"

    print_info "Backing up results for ${pattern}-user test..."

    # Create backup directory
    mkdir -p "${backup_subdir}"

    # Move result files to backup directory
    if ls "${OUTPUT_DIR}"/Custom_${pattern}users_*.html >/dev/null 2>&1; then
        mv "${OUTPUT_DIR}"/Custom_${pattern}users_*.html "${backup_subdir}/" 2>/dev/null || true
    fi

    if ls "${OUTPUT_DIR}"/Custom_${pattern}users_*.csv >/dev/null 2>&1; then
        mv "${OUTPUT_DIR}"/Custom_${pattern}users_*.csv "${backup_subdir}/" 2>/dev/null || true
    fi

    print_success "Results backed up to: ${backup_subdir}"
}

# Function to run a single test pattern
run_test_pattern() {
    local users=$1

    print_header "Test Pattern: ${users} Users for ${TEST_DURATION}"

    # Step 1: Cleanup previous test data
    print_info "Step 1/4: Cleaning up previous test data..."
    bash "${SCRIPT_DIR}/run_perf_test.sh" cleanup
    print_success "Test data cleanup completed"
    echo ""

    # Step 2: Setup new test data
    print_info "Step 2/4: Setting up new test data..."
    bash "${SCRIPT_DIR}/run_perf_test.sh" setup
    print_success "Test data setup completed"
    echo ""

    # Step 3: Run performance test
    print_info "Step 3/4: Running performance test (${users} users, ${TEST_DURATION})..."
    bash "${SCRIPT_DIR}/run_perf_test.sh" custom "${users}" "${TEST_DURATION}"
    print_success "Performance test completed"
    echo ""

    # Step 4: Backup results
    print_info "Step 4/4: Backing up test results..."
    backup_results "${users}"
    print_success "Test results backed up"
    echo ""

    print_success "Test pattern ${users} users completed successfully!"
}

# Main execution
main() {
    print_header "Multiple Performance Test Execution"

    print_info "Test Configuration:"
    echo "  - Test Patterns: ${TEST_PATTERNS[*]} users"
    echo "  - Test Duration: ${TEST_DURATION}"
    echo "  - Backup Directory: ${BACKUP_DIR}"
    echo ""

    # Confirm execution
    print_warning "This will run ${#TEST_PATTERNS[@]} test patterns sequentially."
    print_warning "Estimated total time: ~$(( ${#TEST_PATTERNS[@]} * 15 )) minutes (1-1.5 hours including setup/cleanup time)"
    echo ""
    read -p "Do you want to continue? (y/n): " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Test execution cancelled by user"
        exit 0
    fi

    # Create backup base directory
    mkdir -p "${BACKUP_DIR}"

    # Run each test pattern
    local total_patterns=${#TEST_PATTERNS[@]}
    local current_pattern=0

    for users in "${TEST_PATTERNS[@]}"; do
        current_pattern=$((current_pattern + 1))

        print_header "Progress: Pattern ${current_pattern}/${total_patterns}"

        run_test_pattern "${users}"

        # Wait before next test (except for the last one)
        if [ ${current_pattern} -lt ${total_patterns} ]; then
            print_info "Waiting 10 seconds before next test pattern..."
            sleep 10
            echo ""
        fi
    done

    print_header "All Test Patterns Completed!"

    # Generate comparison report
    print_info "Generating comparison report..."

    cd "${SCRIPT_DIR}"

    if pipenv run python generate_comparison_report.py "${BACKUP_DIR}"; then
        print_success "Comparison report generated successfully!"

        # Find and display report location
        if ls "${BACKUP_DIR}"/comparison_report_*.html >/dev/null 2>&1; then
            REPORT_FILE=$(ls -t "${BACKUP_DIR}"/comparison_report_*.html | head -1)
            print_success "Report location: ${REPORT_FILE}"
        fi
    else
        print_error "Failed to generate comparison report"
        print_warning "You can manually generate the report by running:"
        echo "  cd ${SCRIPT_DIR}"
        echo "  pipenv run python generate_comparison_report.py ${BACKUP_DIR}"
    fi

    print_header "Test Execution Summary"

    echo "Test Results Backup Directory: ${BACKUP_DIR}"
    echo ""
    echo "Test Patterns Executed:"
    for users in "${TEST_PATTERNS[@]}"; do
        echo "  ✓ ${users} users for ${TEST_DURATION}"
    done
    echo ""

    print_success "All performance tests completed successfully!"
}

# Run main function
main
