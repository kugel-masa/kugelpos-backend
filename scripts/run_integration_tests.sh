#!/bin/bash
# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Run integration tests for all microservices.
#
# Integration tests require MongoDB to be running but mock all other
# external dependencies (other services, Dapr, RabbitMQ). Each service
# can be tested in isolation — you do NOT need to start the full stack.
#
# Prerequisites:
#   - MongoDB available at MONGODB_URI (default mongodb://localhost:27017/)
#   - .env.test exists at project root (auto-created from .env.test.sample)
#
# Usage:
#   ./scripts/run_integration_tests.sh              # all services
#   ./scripts/run_integration_tests.sh cart account # specific services

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
        echo -e "${GREEN}✓ Created .env.test from sample${NC}"
    else
        echo "TENANT_ID=T9999" > ".env.test"
    fi
fi

# Service list (default: all)
ALL_SERVICES=("account" "terminal" "master-data" "cart" "journal" "report" "stock")
if [ $# -gt 0 ]; then
    SERVICES=("$@")
else
    SERVICES=("${ALL_SERVICES[@]}")
fi

PASSED=()
FAILED=()

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Running integration tests (MongoDB required)                 ${NC}"
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

    if pipenv run pytest -m integration --no-header -q 2>&1; then
        echo -e "${GREEN}✓ $service integration tests PASSED${NC}"
        PASSED+=("$service")
    else
        rc=$?
        if [ "$rc" = "5" ]; then
            echo -e "${YELLOW}⊘ $service has no integration tests yet (skipped)${NC}"
        else
            echo -e "${RED}✗ $service integration tests FAILED${NC}"
            FAILED+=("$service")
        fi
    fi

    cd "$PROJECT_ROOT"
done

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
