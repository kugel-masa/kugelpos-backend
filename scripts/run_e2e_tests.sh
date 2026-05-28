#!/bin/bash
# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Run end-to-end tests across the full microservice stack.
#
# E2E tests require ALL services running via docker-compose, including:
#   - account, terminal, master-data, cart, journal, report, stock
#   - Dapr sidecars
#   - MongoDB, Redis, RabbitMQ
#
# Prerequisites:
#   - ./scripts/start.sh has been run and all services are healthy
#   - .env.test exists at project root
#
# This script collects e2e tests from each service's tests/e2e/ directory
# AND from the repo-root tests/e2e/ directory if present (cross-service).
#
# Usage:
#   ./scripts/run_e2e_tests.sh              # all e2e tests
#   ./scripts/run_e2e_tests.sh cart account # specific services' e2e

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Ensure .env.test exists
if [ ! -f ".env.test" ]; then
    if [ -f ".env.test.sample" ]; then
        cp ".env.test.sample" ".env.test"
        sed -i 's/TENANT_ID=.*/TENANT_ID=T9999/' ".env.test" 2>/dev/null || \
            echo "TENANT_ID=T9999" >> ".env.test"
    else
        echo "TENANT_ID=T9999" > ".env.test"
    fi
fi

# Order matters for e2e. master-data must precede terminal: terminal sign-in
# authenticates against staff (e.g. S001) that master-data's setup creates, and
# cart depends on both a signed-in terminal and master-data items.
ORDERED_SERVICES=("account" "master-data" "terminal" "journal" "stock" "report" "cart")
if [ $# -gt 0 ]; then
    SERVICES=("$@")
else
    SERVICES=("${ORDERED_SERVICES[@]}")
fi

PASSED=()
FAILED=()

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Running e2e tests (full docker-compose stack required)       ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

for service in "${SERVICES[@]}"; do
    service_dir="$PROJECT_ROOT/services/$service"
    if [ ! -d "$service_dir" ]; then
        echo -e "${YELLOW}⚠ Skipping unknown service: $service${NC}"
        continue
    fi

    echo ""
    echo -e "${YELLOW}┌─ $service ─────────────────────────────────────────${NC}"
    cd "$service_dir"

    if pipenv run pytest -m e2e --no-header -q 2>&1; then
        echo -e "${GREEN}✓ $service e2e tests PASSED${NC}"
        PASSED+=("$service")
    else
        rc=$?
        if [ "$rc" = "5" ]; then
            echo -e "${YELLOW}⊘ $service has no e2e tests yet (skipped)${NC}"
        else
            echo -e "${RED}✗ $service e2e tests FAILED${NC}"
            FAILED+=("$service")
        fi
    fi

    cd "$PROJECT_ROOT"
done

# Run repo-root tests/e2e/ if it has both a Pipfile (managed venv) and
# any test_*.py files. Skips silently if absent.
if [ -d "$PROJECT_ROOT/tests/e2e" ] && \
   [ -f "$PROJECT_ROOT/tests/e2e/Pipfile" ] && \
   compgen -G "$PROJECT_ROOT/tests/e2e/test_*.py" > /dev/null 2>&1; then
    echo ""
    echo -e "${YELLOW}┌─ tests/e2e/ (cross-service scenarios) ────────────────${NC}"
    cd "$PROJECT_ROOT/tests/e2e"
    if pipenv run pytest -m e2e --no-header -q 2>&1; then
        echo -e "${GREEN}✓ Cross-service e2e tests PASSED${NC}"
        PASSED+=("tests/e2e")
    else
        rc=$?
        if [ "$rc" = "5" ]; then
            echo -e "${YELLOW}⊘ tests/e2e/ has no tests yet (skipped)${NC}"
        else
            echo -e "${RED}✗ Cross-service e2e tests FAILED${NC}"
            FAILED+=("tests/e2e")
        fi
    fi
    cd "$PROJECT_ROOT"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Passed: ${#PASSED[@]}${NC}  ${RED}Failed: ${#FAILED[@]}${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

if [ ${#FAILED[@]} -gt 0 ]; then
    for s in "${FAILED[@]}"; do
        echo -e "  ${RED}✗${NC} $s"
    done
    exit 1
fi
exit 0
