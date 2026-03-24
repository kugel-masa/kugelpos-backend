#!/bin/bash

# JWT vs API Key Performance Comparison Test
#
# Runs the same cart scenario with both authentication methods
# and generates a comparison report.
#
# Usage:
#   ./scripts/run_jwt_comparison.sh [num_users] [duration] [num_terminals]
#   ./scripts/run_jwt_comparison.sh 20 3m 30      # 20 users, 3 min, 30 terminals
#   ./scripts/run_jwt_comparison.sh               # defaults: 20 users, 3 min, 30 terminals

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERF_TEST_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CART_DIR="$(cd "${PERF_TEST_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${CART_DIR}/../.." && pwd)"
OUTPUT_DIR="${PERF_TEST_DIR}/results"
mkdir -p "${OUTPUT_DIR}"

# Parameters
NUM_USERS=${1:-20}
DURATION=${2:-3m}
NUM_TERMINALS=${3:-$((NUM_USERS + 10))}
SPAWN_RATE=$((NUM_USERS / 10))
[ $SPAWN_RATE -lt 1 ] && SPAWN_RATE=1
[ $SPAWN_RATE -gt 10 ] && SPAWN_RATE=10

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COMPARISON_DIR="${OUTPUT_DIR}/jwt_comparison_${TIMESTAMP}"
mkdir -p "${COMPARISON_DIR}"

echo -e "${CYAN}"
echo "========================================================================"
echo "  JWT vs API Key Authentication Performance Comparison"
echo "========================================================================"
echo -e "  Users:     ${NUM_USERS}"
echo -e "  Duration:  ${DURATION}"
echo -e "  Terminals: ${NUM_TERMINALS}"
echo -e "  Spawn:     ${SPAWN_RATE}/s"
echo "========================================================================"
echo -e "${NC}"

# Load environment
load_env() {
    if [ -f "${CART_DIR}/.env" ]; then
        export $(grep -v '^#' "${CART_DIR}/.env" | xargs)
    fi
    if [ -f "${ROOT_DIR}/.env.test" ]; then
        export $(grep -v '^#' "${ROOT_DIR}/.env.test" | xargs)
    fi
    export BASE_URL_CART="${BASE_URL_CART:-http://localhost:8003}"
    export BASE_URL_TERMINAL="${BASE_URL_TERMINAL:-http://localhost:8001/api/v1}"
}

# Setup test data
echo -e "${BLUE}[1/5] Setting up test data (${NUM_TERMINALS} terminals)...${NC}"
cd "${PERF_TEST_DIR}"
pipenv run python setup_test_data.py "${NUM_TERMINALS}"
load_env

echo ""
echo -e "${BLUE}[2/5] Running API Key authentication test...${NC}"
echo -e "${YELLOW}       (locustfile.py - X-API-KEY header + terminal_id param)${NC}"
echo ""

APIKEY_PREFIX="${COMPARISON_DIR}/apikey_${NUM_USERS}users"
pipenv run locust \
    -f "locustfile.py" \
    --host="${BASE_URL_CART}" \
    --users="${NUM_USERS}" \
    --spawn-rate="${SPAWN_RATE}" \
    --run-time="${DURATION}" \
    --headless \
    --html="${APIKEY_PREFIX}.html" \
    --csv="${APIKEY_PREFIX}" \
    --loglevel=WARNING

echo -e "${GREEN}  ✓ API Key test completed${NC}"

# Wait between tests
echo ""
echo -e "${YELLOW}  Waiting 15 seconds before JWT test...${NC}"
sleep 15

echo ""
echo -e "${BLUE}[3/5] Running JWT authentication test...${NC}"
echo -e "${YELLOW}       (locustfile_jwt.py - Authorization: Bearer header)${NC}"
echo ""

JWT_PREFIX="${COMPARISON_DIR}/jwt_${NUM_USERS}users"
pipenv run locust \
    -f "locustfile_jwt.py" \
    --host="${BASE_URL_CART}" \
    --users="${NUM_USERS}" \
    --spawn-rate="${SPAWN_RATE}" \
    --run-time="${DURATION}" \
    --headless \
    --html="${JWT_PREFIX}.html" \
    --csv="${JWT_PREFIX}" \
    --loglevel=WARNING

echo -e "${GREEN}  ✓ JWT test completed${NC}"

# Generate comparison
echo ""
echo -e "${BLUE}[4/5] Generating comparison report...${NC}"

REPORT_PATH="${COMPARISON_DIR}/jwt_vs_apikey_comparison_${TIMESTAMP}.html"
pipenv run python generate_jwt_comparison_report.py \
    "${REPORT_PATH}" \
    "${APIKEY_PREFIX}_stats.csv" \
    "${JWT_PREFIX}_stats.csv"

echo -e "${GREEN}  ✓ Comparison report generated${NC}"

# Cleanup
echo ""
echo -e "${BLUE}[5/5] Cleaning up test data...${NC}"
pipenv run python cleanup_test_data.py 2>/dev/null || true
rm -f "${PERF_TEST_DIR}/terminals_config.json"
echo -e "${GREEN}  ✓ Cleanup completed${NC}"

echo ""
echo -e "${CYAN}"
echo "========================================================================"
echo "  Comparison Complete!"
echo "========================================================================"
echo -e "  Results: ${COMPARISON_DIR}"
echo ""
echo "  Files:"
echo "    API Key HTML:  ${APIKEY_PREFIX}.html"
echo "    JWT HTML:      ${JWT_PREFIX}.html"
echo "    Comparison:    ${REPORT_PATH}"
echo "========================================================================"
echo -e "${NC}"
