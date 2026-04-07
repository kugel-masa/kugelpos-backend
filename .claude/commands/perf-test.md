---
description: Run performance test with standardized procedure
---

## User Input

```text
$ARGUMENTS
```

**Usage:** `/perf-test [OPTIONS]`

**Examples:**
- `/perf-test` → Standard test (300 users, 3min)
- `/perf-test 500 5m` → Custom users and duration
- `/perf-test setup-only` → Setup only (no test execution)
- `/perf-test test-only` → Test only (skip restart/setup)

## Standard Procedure

The following steps MUST be executed in order to ensure reproducible results.
Each step must complete successfully before proceeding to the next.

### Step 1: Stop all services
```bash
cd services && docker compose -f docker-compose.prod.yaml down
```

### Step 2: Start all services
```bash
cd services && docker compose -f docker-compose.prod.yaml up -d
```

### Step 3: Wait for MongoDB replica set (if volumes were deleted)
```bash
docker exec mongodb mongosh --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]})"
```
This may fail with "already initialized" — that is expected and OK.

### Step 4: Health check all 7 services
Wait until all services report `healthy`:
```bash
for port in 8000 8001 8002 8003 8004 8005 8006; do
  printf "localhost:%-5s -> " "$port"
  curl -sf "http://localhost:$port/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "NOT READY"
done
```
If any service is unhealthy due to Dapr sidecar, restart the sidecar:
```bash
docker compose -f docker-compose.prod.yaml restart <service>-dapr
```

### Step 5: Setup test data
```bash
cd services/cart/performance_tests/scripts && bash run_perf_test.sh setup 310
```

### Step 6: Redis FLUSHALL
```bash
docker exec redis redis-cli FLUSHALL
```

### Step 7: Run performance test
Default: 300 users, 3 minutes
```bash
bash run_perf_test.sh custom 300 3m
```

### Step 8: Report results
After test completion, display the final results table and append to the performance report:
- Report file: `docs/performance-test-report.md`
- Include: Avg, P50, P95, P99, req/s for each endpoint
- Compare with baseline if available

## Options

| Option | Description |
|--------|-------------|
| `<users> <duration>` | Custom user count and duration (e.g., `500 5m`) |
| `setup-only` | Run steps 1-6 only, skip test execution |
| `test-only` | Run steps 6-7 only (assumes services are already running with test data) |

## Default Parameters

| Parameter | Value |
|-----------|-------|
| Users | 300 |
| Duration | 3m |
| Terminals | 310 |
| Auth | JWT |
| Spawn rate | auto (calculated by script) |

## Important Notes

- **500 users** is near resource limit on this local environment (6 CPU, 16GB RAM). Use 300 users for stable results.
- Baseline variability at 300 users: Avg ±15-19%, req/s ±0.5%
- Always flush Redis before each test to ensure consistent starting conditions
- Full service restart ensures no residual state from previous tests
- Results are saved to `services/cart/performance_tests/results/`
