# Manual Verification: Master-Data Cache Resilience

**Related**: Feature 072-master-data-cache, User Story 3 (SC-003 / FR-007)
**Purpose**: Verify that cart operations continue to succeed when the master-data cache backend (Redis) is unavailable.

This procedure complements the automated unit-level resilience tests
(`tests/unit/repositories/test_abstract_master_data_repository.py` and
`services/commons/tests/unit/test_dapr_state_cache_backend.py`) by exercising
the same fallback path against the live Docker Compose stack.

## Prerequisites

- Working `docker compose` setup for kugelpos
- `redis-cli` available (Docker container exec is fine)
- A baseline E2E run passing (`./scripts/run_e2e_tests.sh cart`)

## Procedure

### 1. Establish baseline — cache populated

```bash
./scripts/start.sh
./scripts/run_e2e_tests.sh cart
# Verify master-data cache keys exist in Redis db=3
docker compose exec redis redis-cli -n 3 KEYS 'mdcache:*'
```

Expected: At least one `mdcache:{tenant}:{store}:item_master:gen0:one:{item_code}`
entry per item exercised by the purchase scenarios.

### 2. Stop Redis and rerun cart E2E

```bash
docker compose stop redis
./scripts/run_e2e_tests.sh cart
```

Expected:
- All cart E2E scenarios still pass (opening, scanning items, payment, closing).
- Cart logs contain warnings like `master cache get unexpected error ...` or
  `master cache set failed: namespace=item_master entry_kind=one key_len=...`
  — these warnings are the documented fallback path, not errors.
- Response latencies may be slightly higher (every master-data lookup falls
  through to the master-data service) but no operation fails.

### 3. Restart Redis and verify cache resumes

```bash
docker compose start redis
# Wait a few seconds for Dapr sidecar to reconnect
./scripts/run_e2e_tests.sh cart
docker compose exec redis redis-cli -n 3 KEYS 'mdcache:*'
```

Expected: Cache repopulates and warning logs stop appearing.

### 4. Bonus — Dapr sidecar offline

To exercise the path where the Dapr HTTP endpoint itself is gone (not just
Redis):

```bash
docker compose stop dapr_cart   # or whichever sidecar service name is in use
./scripts/run_e2e_tests.sh cart
```

Same expectation: cart operations succeed via direct master-data fetch.

## Pass criteria

- [ ] Cart E2E scenarios complete with Redis stopped (SC-003)
- [ ] Cart E2E scenarios complete with Dapr sidecar stopped (FR-007)
- [ ] Warning logs are emitted on every cache miss/failure without leaking
      `logical_key` or master-data field values (FR-012)
- [ ] After restoring the backend, cache resumes serving requests on the
      next call (no service restart required)
