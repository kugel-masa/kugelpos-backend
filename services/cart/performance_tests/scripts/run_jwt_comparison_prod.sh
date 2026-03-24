#!/bin/bash

# JWT vs API Key Performance Comparison - Production Mode (gRPC enabled)
#
# Uses docker-compose.prod.yaml with:
#   - Production Docker images (multi-worker Uvicorn)
#   - gRPC enabled for cart → master-data communication
#   - Dapr sidecars with gRPC ports
#
# Usage:
#   ./scripts/run_jwt_comparison_prod.sh [num_users] [duration] [num_terminals]
#   ./scripts/run_jwt_comparison_prod.sh 20 3m 30
#   ./scripts/run_jwt_comparison_prod.sh              # defaults: 20 users, 3 min, 30 terminals

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
SERVICES_DIR="$(cd "${CART_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${SERVICES_DIR}/.." && pwd)"
OUTPUT_DIR="${PERF_TEST_DIR}/results"
mkdir -p "${OUTPUT_DIR}"

NUM_USERS=${1:-20}
DURATION=${2:-3m}
NUM_TERMINALS=${3:-$((NUM_USERS + 10))}
SPAWN_RATE=$((NUM_USERS / 10))
[ $SPAWN_RATE -lt 1 ] && SPAWN_RATE=1
[ $SPAWN_RATE -gt 10 ] && SPAWN_RATE=10

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COMPARISON_DIR="${OUTPUT_DIR}/jwt_comparison_prod_${TIMESTAMP}"
mkdir -p "${COMPARISON_DIR}"

echo -e "${CYAN}"
echo "========================================================================"
echo "  JWT vs API Key - Production Mode (gRPC + Multi-Worker)"
echo "========================================================================"
echo -e "  Users:      ${NUM_USERS}"
echo -e "  Duration:   ${DURATION}"
echo -e "  Terminals:  ${NUM_TERMINALS}"
echo -e "  Spawn:      ${SPAWN_RATE}/s"
echo -e "  Compose:    docker-compose.prod.yaml"
echo -e "  gRPC:       Enabled (cart → master-data)"
echo -e "  Workers:    cart=8, terminal=4, master-data=4"
echo "========================================================================"
echo -e "${NC}"

COMPOSE_FILE="${SERVICES_DIR}/docker-compose.prod.yaml"

# ---------------------------------------------------------------
# Step 0: Start production services
# ---------------------------------------------------------------
echo -e "${BLUE}[0/6] Starting production services...${NC}"
cd "${SERVICES_DIR}"

# Stop dev services if running
docker compose -f docker-compose.yaml down 2>/dev/null || true

# Start prod services
docker compose -f "${COMPOSE_FILE}" up -d 2>&1 | tail -5

# Wait for health
echo -e "${YELLOW}  Waiting for services to be ready...${NC}"
for attempt in $(seq 1 30); do
    all_healthy=true
    for port in 8000 8001 8002 8003; do
        if ! curl -sf -o /dev/null "http://localhost:${port}/health" 2>/dev/null; then
            all_healthy=false
            break
        fi
    done
    if $all_healthy; then
        echo -e "${GREEN}  ✓ All services healthy${NC}"
        break
    fi
    if [ $attempt -eq 30 ]; then
        echo -e "${RED}  ✗ Services not ready after 60s${NC}"
        docker compose -f "${COMPOSE_FILE}" logs --tail=20 cart 2>&1
        exit 1
    fi
    sleep 2
done

# Verify gRPC is enabled
echo -e "${BLUE}  Checking gRPC configuration...${NC}"
GRPC_CHECK=$(docker compose -f "${COMPOSE_FILE}" exec -T cart env 2>/dev/null | grep USE_GRPC || true)
echo -e "${GREEN}  ${GRPC_CHECK:-USE_GRPC not set (default: true)}${NC}"

# ---------------------------------------------------------------
# Step 1: Load environment
# ---------------------------------------------------------------
load_env() {
    if [ -f "${CART_DIR}/.env" ]; then
        export $(grep -v '^#' "${CART_DIR}/.env" | xargs 2>/dev/null) 2>/dev/null
    fi
    if [ -f "${ROOT_DIR}/.env.test" ]; then
        export $(grep -v '^#' "${ROOT_DIR}/.env.test" | xargs 2>/dev/null) 2>/dev/null
    fi
    export BASE_URL_CART="${BASE_URL_CART:-http://localhost:8003}"
    export BASE_URL_TERMINAL="${BASE_URL_TERMINAL:-http://localhost:8001/api/v1}"
}

# ---------------------------------------------------------------
# Step 2: Setup test data
# ---------------------------------------------------------------
echo ""
echo -e "${BLUE}[1/6] Setting up test data (${NUM_TERMINALS} terminals)...${NC}"
cd "${PERF_TEST_DIR}"
pipenv run python setup_test_data.py "${NUM_TERMINALS}" 2>&1 | tail -5
load_env

# ---------------------------------------------------------------
# Step 3: Run API Key test
# ---------------------------------------------------------------
echo ""
echo -e "${BLUE}[2/6] Running API Key authentication test (prod + gRPC)...${NC}"
echo -e "${YELLOW}       X-API-KEY header + terminal_id param${NC}"

APIKEY_PREFIX="${COMPARISON_DIR}/apikey_prod_${NUM_USERS}users"
cd "${PERF_TEST_DIR}"
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

# ---------------------------------------------------------------
# Step 4: Wait between tests
# ---------------------------------------------------------------
echo ""
echo -e "${YELLOW}  Waiting 15 seconds before JWT test...${NC}"
sleep 15

# ---------------------------------------------------------------
# Step 5: Run JWT test
# ---------------------------------------------------------------
echo ""
echo -e "${BLUE}[3/6] Running JWT authentication test (prod + gRPC)...${NC}"
echo -e "${YELLOW}       Authorization: Bearer header${NC}"

JWT_PREFIX="${COMPARISON_DIR}/jwt_prod_${NUM_USERS}users"
cd "${PERF_TEST_DIR}"
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

# ---------------------------------------------------------------
# Step 6: Generate comparison report
# ---------------------------------------------------------------
echo ""
echo -e "${BLUE}[4/6] Generating comparison report...${NC}"

REPORT_PATH="${COMPARISON_DIR}/jwt_vs_apikey_prod_comparison_${TIMESTAMP}.html"
cd "${PERF_TEST_DIR}"
pipenv run python generate_jwt_comparison_report.py \
    "${REPORT_PATH}" \
    "${APIKEY_PREFIX}_stats.csv" \
    "${JWT_PREFIX}_stats.csv"

# ---------------------------------------------------------------
# Step 7: Display results summary
# ---------------------------------------------------------------
echo ""
echo -e "${BLUE}[5/6] Results summary:${NC}"

python3 -c "
import csv, sys

def read_stats(path):
    with open(path) as f:
        return {r['Name']: r for r in csv.DictReader(f)}

apikey = read_stats('${APIKEY_PREFIX}_stats.csv')
jwt = read_stats('${JWT_PREFIX}_stats.csv')

print()
print(f\"{'Endpoint':<50} {'API Key':>10} {'JWT':>10} {'Improve':>10}\")
print('-' * 85)
for name in ['POST /api/v1/carts (Create Cart)',
             'POST /api/v1/carts/[cart_id]/lineItems (Add Item)',
             'POST /api/v1/carts/[cart_id]/cancel (Cancel Cart)',
             'Aggregated']:
    ak = apikey.get(name, {})
    jw = jwt.get(name, {})
    ak_avg = float(ak.get('Average Response Time', 0))
    jw_avg = float(jw.get('Average Response Time', 0))
    imp = ((ak_avg - jw_avg) / ak_avg * 100) if ak_avg > 0 else 0
    short = name.split('(')[1].rstrip(')') if '(' in name else name
    print(f'{short:<50} {ak_avg:>8.0f}ms {jw_avg:>8.0f}ms {imp:>+8.1f}%')
print()
" 2>/dev/null || echo "(summary generation failed)"

# ---------------------------------------------------------------
# Step 8: Cleanup
# ---------------------------------------------------------------
echo ""
echo -e "${BLUE}[6/6] Cleaning up test data...${NC}"
cd "${PERF_TEST_DIR}"
pipenv run python cleanup_test_data.py 2>/dev/null || true
rm -f "${PERF_TEST_DIR}/terminals_config.json"

# Restore dev services
echo ""
echo -e "${YELLOW}  Stopping production services...${NC}"
cd "${SERVICES_DIR}"
docker compose -f "${COMPOSE_FILE}" down 2>/dev/null || true

echo -e "${YELLOW}  Restarting development services...${NC}"
cd "${ROOT_DIR}"
./scripts/start.sh 2>&1 | grep -E "Healthy|ready" || true

echo ""
echo -e "${CYAN}"
echo "========================================================================"
echo "  Production Comparison Complete! (gRPC + Multi-Worker)"
echo "========================================================================"
echo "  Results:    ${COMPARISON_DIR}"
echo "  Report:     ${REPORT_PATH}"
echo "========================================================================"
echo -e "${NC}"
