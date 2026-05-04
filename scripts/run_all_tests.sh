#!/bin/bash
# Copyright 2025 masa@kugel
#
# Run every test tier for every service. Equivalent to running the
# three tier scripts in sequence:
#   1) scripts/run_unit_tests.sh         (no MongoDB needed)
#   2) scripts/run_integration_tests.sh  (MongoDB only)
#   3) scripts/run_e2e_tests.sh          (full docker-compose stack)
#
# For tier-by-tier feedback during development, prefer the per-tier
# scripts directly. This entry point exists for the legacy "run all
# tests against the live stack" workflow.

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Running every test tier across microservices..."

# .env.test bootstrap (mirrors what each tier script does individually)
if [ ! -f ".env.test" ]; then
    if [ -f ".env.test.sample" ]; then
        cp ".env.test.sample" ".env.test"
        sed -i 's/TENANT_ID=.*/TENANT_ID=T9999/' ".env.test" 2>/dev/null || \
            echo "TENANT_ID=T9999" >> ".env.test"
    else
        echo "TENANT_ID=T9999" > ".env.test"
    fi
fi

"${PROJECT_ROOT}/scripts/run_unit_tests.sh"
"${PROJECT_ROOT}/scripts/run_integration_tests.sh"
"${PROJECT_ROOT}/scripts/run_e2e_tests.sh"

echo "All tiers completed."
