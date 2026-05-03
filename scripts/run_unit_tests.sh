#!/bin/bash
# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Run unit tests for all microservices.
#
# Unit tests have NO external dependencies — they do not require MongoDB,
# Redis, Dapr, RabbitMQ, or any other service to be running. They mock all
# I/O at the boundary (DB, HTTP, Dapr) and exercise only in-process logic.
#
# Usage:
#   ./scripts/run_unit_tests.sh              # all services
#   ./scripts/run_unit_tests.sh cart account # specific services

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Service list (default: all)
ALL_SERVICES=("account" "commons" "terminal" "master-data" "cart" "journal" "report" "stock")
if [ $# -gt 0 ]; then
    SERVICES=("$@")
else
    SERVICES=("${ALL_SERVICES[@]}")
fi

PASSED=()
FAILED=()

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Running unit tests (no external dependencies required)       ${NC}"
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

    if pipenv run pytest -m unit --no-header -q 2>&1; then
        echo -e "${GREEN}✓ $service unit tests PASSED${NC}"
        PASSED+=("$service")
    else
        # rc=5 from pytest means "no tests collected" — treat as skip during migration
        rc=$?
        if [ "$rc" = "5" ]; then
            echo -e "${YELLOW}⊘ $service has no unit tests yet (skipped)${NC}"
        else
            echo -e "${RED}✗ $service unit tests FAILED${NC}"
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
