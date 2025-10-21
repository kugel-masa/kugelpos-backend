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

# Note: set -e is NOT used here to allow tests to continue even if individual steps fail
# Errors are tracked and reported at the end

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
TEST_PATTERNS=(20 30 40 50)
TEST_DURATION="10m"

# Error tracking
declare -a FAILED_TESTS=()
declare -a PARTIAL_FAILURES=()

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
    if ! mkdir -p "${backup_subdir}"; then
        print_error "Failed to create backup directory: ${backup_subdir}"
        return 1
    fi

    # Move result files to backup directory
    local files_found=false
    if ls "${OUTPUT_DIR}"/Custom_${pattern}users_*.html >/dev/null 2>&1; then
        mv "${OUTPUT_DIR}"/Custom_${pattern}users_*.html "${backup_subdir}/" 2>/dev/null || true
        files_found=true
    fi

    if ls "${OUTPUT_DIR}"/Custom_${pattern}users_*.csv >/dev/null 2>&1; then
        mv "${OUTPUT_DIR}"/Custom_${pattern}users_*.csv "${backup_subdir}/" 2>/dev/null || true
        files_found=true
    fi

    if [ "$files_found" = false ]; then
        print_warning "No result files found to backup for ${pattern}-user test"
        return 1
    fi

    print_success "Results backed up to: ${backup_subdir}"
    return 0
}

# Function to run a single test pattern
run_test_pattern() {
    local users=$1
    local step_failed=false

    print_header "Test Pattern: ${users} Users for ${TEST_DURATION}"

    # Step 1: Cleanup previous test data
    print_info "Step 1/4: Cleaning up previous test data..."
    if bash "${SCRIPT_DIR}/run_perf_test.sh" cleanup; then
        print_success "Test data cleanup completed"
    else
        print_error "Test data cleanup failed (continuing anyway)"
        PARTIAL_FAILURES+=("${users}users: cleanup failed")
    fi
    echo ""

    # Step 2: Setup new test data
    print_info "Step 2/4: Setting up new test data..."
    if bash "${SCRIPT_DIR}/run_perf_test.sh" setup; then
        print_success "Test data setup completed"
    else
        print_error "Test data setup failed (continuing anyway)"
        PARTIAL_FAILURES+=("${users}users: setup failed")
        step_failed=true
    fi
    echo ""

    # Step 3: Run performance test
    print_info "Step 3/4: Running performance test (${users} users, ${TEST_DURATION})..."
    if bash "${SCRIPT_DIR}/run_perf_test.sh" custom "${users}" "${TEST_DURATION}"; then
        print_success "Performance test completed"
    else
        print_error "Performance test failed or incomplete"
        PARTIAL_FAILURES+=("${users}users: performance test failed")
        step_failed=true
    fi
    echo ""

    # Step 4: Backup results
    print_info "Step 4/4: Backing up test results..."
    if backup_results "${users}"; then
        print_success "Test results backed up"
    else
        print_error "Backup failed (non-critical)"
        PARTIAL_FAILURES+=("${users}users: backup failed")
    fi
    echo ""

    if [ "$step_failed" = true ]; then
        print_warning "Test pattern ${users} users completed with errors"
        FAILED_TESTS+=("${users}users")
    else
        print_success "Test pattern ${users} users completed successfully!"
    fi
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

    cd "${SCRIPT_DIR}" || {
        print_error "Failed to change directory to ${SCRIPT_DIR}"
        PARTIAL_FAILURES+=("report: failed to change directory")
        return
    }

    if pipenv run python generate_comparison_report.py "${BACKUP_DIR}" 2>&1; then
        print_success "Comparison report generated successfully!"

        # Find and display report location
        if ls "${BACKUP_DIR}"/comparison_report_*.html >/dev/null 2>&1; then
            REPORT_FILE=$(ls -t "${BACKUP_DIR}"/comparison_report_*.html | head -1)
            print_success "Report location: ${REPORT_FILE}"
        fi
    else
        print_error "Failed to generate comparison report (non-critical)"
        PARTIAL_FAILURES+=("report: generation failed")
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

    # Display error summary if any
    if [ ${#FAILED_TESTS[@]} -gt 0 ] || [ ${#PARTIAL_FAILURES[@]} -gt 0 ]; then
        print_header "Error Summary"

        if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
            print_error "Tests with failures:"
            for test in "${FAILED_TESTS[@]}"; do
                echo "  ✗ ${test}"
            done
            echo ""
        fi

        if [ ${#PARTIAL_FAILURES[@]} -gt 0 ]; then
            print_warning "Partial failures encountered:"
            for failure in "${PARTIAL_FAILURES[@]}"; do
                echo "  ⚠ ${failure}"
            done
            echo ""
        fi

        print_warning "Some tests completed with errors. Check logs above for details."
        echo ""
        echo "Note: Tests continued despite errors. Results may be partial."
        exit 1
    else
        print_success "All performance tests completed successfully!"
        exit 0
    fi
}

# Run main function
main
