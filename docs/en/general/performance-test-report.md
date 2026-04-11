# Performance Test Report

## Test Environment

| Item | Value |
|------|-------|
| VM | Lima (single host) |
| CPU | 6 cores |
| Memory | 16GB |
| OS | Linux 6.8.0-101-generic |
| Auth | JWT |

### Service Configuration (docker-compose.prod.yaml)

| Service | Workers |
|---------|---------|
| account | 2 |
| terminal | 4 |
| master-data | 4 |
| **cart** | **8** |
| report | 2 |
| journal | 2 |
| stock | 1 |

### Test Conditions

- **Users**: 300
- **Duration**: 3 minutes
- **Terminals**: 310 (multi-terminal mode)
- **Pre-test procedure**: Full service restart → test data setup → Redis FLUSHALL

---

## Summary

| # | Change | Effect | Notes |
|---|--------|--------|-------|
| 1 | Baseline stability (2 runs) | — | req/s stable at ±0.5%. Avg varies ±15–19%; differences within this range are not statistically significant |
| 2 | Redis persistence (RDB) disabled | **No effect** | RDB uses fork()-based async writes; main process is not blocked. 3 runs with 0 errors and no performance difference |
| 3 | Cart cache deletion (delete on bill/cancel) | **No effect** | No visible effect in 3-min test. Longer tests may reveal Redis memory reduction from cart accumulation |
| 4 | pub/sub publish async (`asyncio.create_task()`) | **Significant degradation** | All endpoints Avg +63–121%, P95 +119–300%. Background tasks saturate the event loop. Counterproductive on single VM |
| 5 | Redis activedefrag + THP disabled | **No effect** | No difference in short tests. Recommended as preventive measure for production. THP change was `madvise` → `never` (minimal impact) |
| 6 | Create Cart asyncio.gather() (4 master data fetches in parallel) | **No effect** | Create Cart Avg -2 to +2%, req/s +0.2%. Individual HTTP calls are lightweight; parallelization benefit is negligible |
| 7 | Cancel Cart setting value asyncio.gather() (5 settings in parallel) | **No effect to slight improvement** | Cancel Cart Avg -15 to -5%, Add Item Avg -9 to -24%, req/s +0.6%. Within variance but consistent improvement across all metrics |
| 8 | Worker count tuning (master-data 4w→8w) | **No effect to slight degradation** | Create Cart Avg +1 to +16%, Cancel Cart Avg +8 to +20%, req/s -0.4%. Increased CPU contention; excessive for 6-core environment |
| 9–22 | (See Japanese report for full details) | — | Ordering effect investigation, batch writes, stability tests, 8GB optimization, WiredTiger cache, worker rebalancing |
| 23 | Buffer size tuning (sync insert_many) | **No effect** | buffer 50/500/1000 compared. Avg 34–38ms, req/s 105.1–105.2, no significant difference. Large buffers (500/1000) cause Max spikes 610–1,119ms. 100 is optimal |
| 24 | Async insert_many (create_task fire-and-forget) | **No effect** | buffer 100/1000 compared. Avg/req/s identical to sync. buffer=1000 Max spike 1,130ms not resolved. No benefit from async; keep sync await + buffer=100 |
| 25 | Env var support 180min stability test | **Stable, no leak** | 1,162,021 requests/180min, 0 errors. Avg 33ms, 107.6 req/s stable throughout. Cart memory plateau at 810MB, no leak. Redis linear growth (~4.7MB/min) requires attention for long runs |
| 26 | Redis maxmemory 1GB + 4GB swap long test | **Failed at 345min** | 2,324,979 requests, 228 errors (0.01%). Avg 34ms stable until failure. Redis hit 1GB at ~211min, eviction started. At 345min, active carts (item 2-3) evicted → 404 errors in 16-second burst. Root cause: Redis data on swap degrades LRU accuracy — newly created carts incorrectly evicted. Redis must not use swap. Swap extended runtime 3.3x (104→345min) but Redis eviction behavior becomes unpredictable |
| 27 | maxLenApprox 50000 + Redis container memory limit 360min | **6h complete, 0 errors** | 1,650,915 requests/360min, 0 errors, 0 evictions. Redis memory stabilized at ~813MB after ~170min (Stream capped at 50,000 entries). Stream accounts for ~95% of Redis memory (~750MB); cart cache is only ~3MB. `deleteAfterDeliver` does not exist in Dapr Redis pub/sub. Redis on swap (~80MB) remains structural risk. Recommends pub/sub migration to RabbitMQ (#99) |

---

## Test 1: Baseline Stability

**Date**: 2026-04-07
**Purpose**: Verify baseline reproducibility (test condition validation)
**Code**: main (no changes)
**Redis**: Persistence enabled (default)

### Run 1

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 159 | 130 | 350 | 610 | 5.00 |
| Add Item | 53 | 29 | 180 | 360 | 81.81 |
| Cancel Cart | 419 | 350 | 830 | 1100 | 3.34 |
| **Aggregated** | **72** | **33** | **290** | **570** | **90.16** |

### Run 2

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 183 | 130 | 460 | 1400 | 5.01 |
| Add Item | 63 | 32 | 210 | 550 | 81.35 |
| Cancel Cart | 466 | 400 | 900 | 1600 | 3.34 |
| **Aggregated** | **85** | **37** | **330** | **730** | **89.69** |

### Stability Assessment

| Metric | Run 1 | Run 2 | Variance |
|--------|-------|-------|----------|
| Create Cart Avg | 159ms | 183ms | ±15% |
| Add Item Avg | 53ms | 63ms | ±19% |
| Cancel Cart Avg | 419ms | 466ms | ±11% |
| Aggregated req/s | 90.16 | 89.69 | ±0.5% |

**req/s is highly stable** (±0.5%). Average response times vary ±15–19%, which is acceptable at 300 users.

---

## Test 2: Redis Persistence Disabled

**Date**: 2026-04-07
**Purpose**: Assess performance impact of disabling Redis RDB persistence
**Code**: main (no changes)

### Redis Configuration

```
command: ["redis-server", "--save", "", "--appendonly", "no"]
```

### Run 1

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 236 | 150 | 720 | 1200 | 5.01 |
| Add Item | 77 | 37 | 290 | 530 | 80.88 |
| Cancel Cart | 606 | 500 | 1300 | 2100 | 3.34 |
| **Aggregated** | **105** | **44** | **430** | **830** | **89.22** |

### Run 2

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 184 | 130 | 500 | 900 | 5.01 |
| Add Item | 62 | 33 | 220 | 400 | 81.52 |
| Cancel Cart | 472 | 390 | 1100 | 1400 | 3.34 |
| **Aggregated** | **84** | **39** | **320** | **600** | **89.87** |

### Persistence Enabled vs Disabled (Run 2 comparison)

| Endpoint | Enabled | Disabled | Diff |
|----------|---------|----------|------|
| Create Cart Avg | 183ms | 184ms | +0.5% |
| Add Item Avg | 63ms | 62ms | -1.6% |
| Cancel Cart Avg | 466ms | 472ms | +1.3% |
| req/s | 89.69 | 89.87 | +0.2% |

### Run 3 (Re-test: standard procedure)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 188 | 130 | 480 | 1300 | 5.00 |
| Add Item | 64 | 30 | 240 | 520 | 81.37 |
| Cancel Cart | 473 | 380 | 1000 | 1800 | 3.34 |
| **Aggregated** | **86** | **35** | **340** | **670** | **89.71** |

### Conclusion

**No difference with or without RDB. All 3 runs completed with 0 errors.**

- Redis RDB persistence uses fork()-based async writes. The main process is not blocked.
- In a 3-minute test, persistence triggers only a few times, resulting in negligible impact.

---

## Test 3: Cache Deletion (delete cart on bill/cancel)

**Date**: 2026-04-07
**Purpose**: Evaluate the effect of deleting Redis cache instead of saving completed/cancelled state after bill/cancel
**Code**: `feature/89-async-parallelization` branch cache deletion only
**Redis**: Persistence enabled (default)

### Changes

Two locations in `services/cart/app/services/cart_service.py`:
- **cancel_transaction_async**: `__cache_cart_async(Cancelled)` → `__remove_cached_cart_async()`
- **bill_async**: `__cache_cart_async(Completed)` → `__remove_cached_cart_async()`

Deleting completed carts from Redis instead of saving them, reducing Redis memory usage and improving tail latency.

### After (Cache Deletion)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 194 | 140 | 520 | 900 | 5.00 |
| Add Item | 64 | 32 | 230 | 480 | 81.33 |
| Cancel Cart | 483 | 400 | 1000 | 1400 | 3.34 |
| **Aggregated** | **86** | **38** | **340** | **680** | **89.67** |

### Before/After Comparison

| Endpoint | Baseline Run 1 | Baseline Run 2 | Cache Deletion | Assessment |
|----------|---------------|---------------|---------------|------------|
| Create Cart Avg | 159ms | 183ms | 194ms | Within variance |
| Add Item Avg | 53ms | 63ms | 64ms | Within variance |
| Cancel Cart Avg | 419ms | 466ms | 483ms | Within variance |
| req/s | 90.16 | 89.69 | 89.67 | Within variance |

| Endpoint | Baseline P99 Range | Cache Deletion P99 | Assessment |
|----------|-------------------|-------------------|------------|
| Create Cart | 610–1400ms | 900ms | Within variance |
| Add Item | 360–550ms | 480ms | Within variance |
| Cancel Cart | 1100–1600ms | 1400ms | Within variance |

### Conclusion

**No effect in a 3-minute test.**

Cart accumulation is too low in 3 minutes for the deletion effect to manifest. Longer tests may reveal Redis memory reduction benefits from reduced cart accumulation.

---

## Test 4: Cancel/Bill pub/sub Publish Async

**Date**: 2026-04-07
**Purpose**: Evaluate the effect of making pub/sub publish fire-and-forget using `asyncio.create_task()` in `create_tranlog_async`
**Code**: main + single change in `tran_service.py` (Issue #89 proposal 3)
**Redis**: Persistence enabled (default)

### Changes

In `services/cart/app/services/tran_service.py`, `create_tranlog_async`:
```python
# Before
await self._publish_tranlog_async(event_message)

# After
asyncio.create_task(self._publish_tranlog_async(event_message))
```

Fire-and-forget pub/sub publishing after DB transaction (tranlog + delivery_status) is committed.
Failures are tracked via delivery_status and retried by cron job every 5 minutes.

### After (pub/sub async)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 345 | 150 | 1400 | 2300 | 5.00 |
| Add Item | 103 | 37 | 460 | 820 | 79.81 |
| Cancel Cart | 924 | 620 | 2800 | 4000 | 3.34 |
| **Aggregated** | **148** | **45** | **610** | **1400** | **88.15** |

### Before/After Comparison

| Endpoint | Baseline Avg (Run1/Run2) | pub/sub async | Change | Assessment |
|----------|------------------------|--------------|--------|------------|
| Create Cart | 159 / 183ms | 345ms | +88–117% | **Significant degradation** |
| Add Item | 53 / 63ms | 103ms | +63–94% | **Significant degradation** |
| Cancel Cart | 419 / 466ms | 924ms | +98–121% | **Significant degradation** |
| req/s | 90.16 / 89.69 | 88.15 | -2% | Slight decrease |

| Endpoint | Baseline P95 (Run1/Run2) | pub/sub async P95 | Change |
|----------|------------------------|-------------------|--------|
| Create Cart | 350 / 460ms | 1400ms | +204–300% |
| Add Item | 180 / 210ms | 460ms | +119–156% |
| Cancel Cart | 830 / 900ms | 2800ms | +211–237% |

### Conclusion

**All endpoints degraded significantly, far exceeding baseline variance.**

`asyncio.create_task()` background pub/sub saturates the event loop, impacting other request processing. P95 degraded 2–4x, with particularly severe tail latency impact. pub/sub async is counterproductive in a single-VM environment.

---

## Test 5: Redis activedefrag + THP Disabled

**Date**: 2026-04-07
**Purpose**: Evaluate Redis memory fragmentation countermeasures
**Code**: main (no changes)
**Redis**: Persistence enabled + `activedefrag yes`
**OS**: THP (Transparent Huge Pages) set to `never`

### Changes

```bash
# Enable Redis active defrag
docker exec redis redis-cli CONFIG SET activedefrag yes

# Disable THP (madvise → never)
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
```

#### activedefrag

Redis feature that automatically repairs memory fragmentation during idle time. Disabled by default. When enabled, it performs automatic memory relocation when `mem_fragmentation_ratio` is high.

#### THP (Transparent Huge Pages)

A Linux memory management feature that automatically uses 2MB large pages instead of standard 4KB pages. While this improves TLB cache hit rates for applications with large contiguous memory access, **it is counterproductive for Redis**.

Redis frequently allocates and deallocates small memory regions (one cart document ≈ 16KB). With THP enabled:

- Redis modifies 16KB → OS COW-copies the **entire 2MB page** (vs. only 4 pages at 4KB)
- RDB fork COW unit becomes 2MB, causing memory usage spikes
- 4KB of changes trigger 2MB of copying = **~500x overhead**

| Setting | Behavior | Redis Compatibility |
|---------|----------|-------------------|
| `always` | Always use large pages | **Poor** |
| `madvise` | Only when explicitly requested by application (Redis does not request) | Minimal impact |
| `never` | Do not use large pages | **Redis recommended** |

This environment was changed from `madvise` → `never`, so the impact is minimal. Changing from `always` would show a larger difference.

### After (activedefrag + THP disabled)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 215 | 140 | 580 | 1700 | 5.01 |
| Add Item | 72 | 35 | 240 | 620 | 81.14 |
| Cancel Cart | 555 | 430 | 1300 | 3100 | 3.34 |
| **Aggregated** | **98** | **42** | **380** | **870** | **89.49** |

### Before/After Comparison

| Endpoint | Baseline Avg (Run1/Run2) | activedefrag+THP | Assessment |
|----------|------------------------|-----------------|------------|
| Create Cart | 159 / 183ms | 215ms | Within variance (slightly high) |
| Add Item | 53 / 63ms | 72ms | Within variance |
| Cancel Cart | 419 / 466ms | 555ms | Within variance (slightly high) |
| req/s | 90.16 / 89.69 | 89.49 | Within variance |

### Conclusion

**Approximately equal to baseline in 3-minute test (within variance).**

activedefrag and THP disabling are measures that take effect during long-running operations when data accumulation and fragmentation progress. They show no difference in short tests. These measures are effective as **preventive measures** and recommended for production deployment.

---

## Test 6: Create Cart asyncio.gather() (Master Data Parallel Fetch)

**Date**: 2026-04-07
**Purpose**: Evaluate parallelizing 4 sequential master data fetches in `create_cart_async` using `asyncio.gather()`
**Code**: main + `cart_service.py` `create_cart_async` only
**Redis**: Persistence enabled (default)

### Changes

In `services/cart/app/services/cart_service.py`, `create_cart_async`:
- `store_info_repo.get_store_info_async()`
- `settings_master_repo.get_all_settings_async()`
- `tax_master_repo.load_all_taxes()`
- `promotion_master_repo.get_active_promotions_by_store_async()`

Changed 4 sequential awaits to parallel execution with `asyncio.gather()`.

### After (asyncio.gather applied)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 156 | 130 | 350 | 620 | 5.01 |
| Add Item | 52 | 28 | 170 | 380 | 82.00 |
| Cancel Cart | 424 | 380 | 780 | 1100 | 3.34 |
| **Aggregated** | **71** | **32** | **290** | **540** | **90.34** |

### Before/After Comparison

| Endpoint | Baseline Avg (Run1/Run2) | gather applied | Change | Assessment |
|----------|------------------------|---------------|--------|------------|
| Create Cart | 159 / 183ms | 156ms | -2 to -15% | Within variance |
| Add Item | 53 / 63ms | 52ms | -2 to -17% | Within variance |
| Cancel Cart | 419 / 466ms | 424ms | +1 to -9% | Within variance |
| req/s | 90.16 / 89.69 | 90.34 | +0.2 to +0.7% | Within variance |

### Conclusion

**No significant difference (within baseline variance).**

All 4 master data fetches are Dapr-proxied HTTP calls with individually short response times (a few ms to tens of ms), so the parallelization benefit is negligible. Create Cart accounts for a low proportion of total req/s (5 req/s) and is not a bottleneck. However, parallelization is a reasonable design improvement for code readability and extensibility.

---

## Test 7: Cancel Cart Setting Value asyncio.gather() (Parallel Setting Fetch)

**Date**: 2026-04-07
**Purpose**: Evaluate parallelizing 5 sequential setting value fetches in `create_tranlog_async` using `asyncio.gather()`
**Code**: main + `tran_service.py` `create_tranlog_async` only
**Redis**: Persistence enabled (default)

### Changes

In `services/cart/app/services/tran_service.py`, `create_tranlog_async`:
- `RECEIPT_NO_START_VALUE`
- `RECEIPT_NO_END_VALUE`
- `INVOICE_REGISTRATION_NUMBER`
- `RECEIPT_HEADERS`
- `RECEIPT_FOOTERS`

Changed 5 sequential `_get_setting_value_async()` calls to batch fetch with `asyncio.gather()` at function start.

### After (asyncio.gather applied)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 157 | 130 | 380 | 630 | 5.01 |
| Add Item | 48 | 27 | 160 | 330 | 81.88 |
| Cancel Cart | 396 | 350 | 740 | 1100 | 3.34 |
| **Aggregated** | **67** | **30** | **270** | **480** | **90.22** |

### Before/After Comparison

| Endpoint | Baseline Avg (Run1/Run2) | gather applied | Change | Assessment |
|----------|------------------------|---------------|--------|------------|
| Create Cart | 159 / 183ms | 157ms | -1 to -14% | Within variance |
| Add Item | 53 / 63ms | 48ms | -9 to -24% | Within variance (improvement trend) |
| Cancel Cart | 419 / 466ms | 396ms | -5 to -15% | Within variance (improvement trend) |
| req/s | 90.16 / 89.69 | 90.22 | +0.1 to +0.6% | Within variance |

| Endpoint | Baseline P95 (Run1/Run2) | gather P95 | Change |
|----------|------------------------|-----------|--------|
| Create Cart | 350 / 460ms | 380ms | Within variance |
| Add Item | 180 / 210ms | 160ms | -11 to -24% |
| Cancel Cart | 830 / 900ms | 740ms | -11 to -18% |

### Conclusion

**Within baseline variance, but consistent improvement trend across all metrics.**

Cancel Cart (Avg -5 to -15%) and Add Item (Avg -9 to -24%) show improvement. Parallelizing 5 setting value fetches reduces tranlog creation latency. However, a single test run cannot be considered "significant" given the variance. Recommended for adoption from a code quality perspective as well.

---

## Test 8: Worker Count Tuning (master-data 4w→8w)

**Date**: 2026-04-07
**Purpose**: Evaluate the effect of increasing master-data service workers from 4 to 8
**Code**: main (no changes)
**Redis**: Persistence enabled (default)

### Changes

`services/docker-compose.prod.yaml`:
- master-data: `UVICORN_WORKERS: 4` → `UVICORN_WORKERS: 8`
- cart remains at 8w (unchanged)

### Service Configuration

| Service | Workers |
|---------|---------|
| account | 2 |
| terminal | 4 |
| **master-data** | **8** (changed from 4) |
| cart | 8 |
| report | 2 |
| journal | 2 |
| stock | 1 |

### After (master-data 8w)

| Endpoint | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| Create Cart | 185 | 130 | 470 | 1000 | 5.00 |
| Add Item | 58 | 30 | 210 | 420 | 81.44 |
| Cancel Cart | 503 | 410 | 1200 | 1800 | 3.34 |
| **Aggregated** | **82** | **35** | **330** | **630** | **89.78** |

### Before/After Comparison

| Endpoint | Baseline Avg (Run1/Run2) | 8w applied | Change | Assessment |
|----------|------------------------|-----------|--------|------------|
| Create Cart | 159 / 183ms | 185ms | +1 to +16% | Within variance |
| Add Item | 53 / 63ms | 58ms | -8 to +9% | Within variance |
| Cancel Cart | 419 / 466ms | 503ms | +8 to +20% | Within variance to slight degradation |
| req/s | 90.16 / 89.69 | 89.78 | -0.4 to +0.1% | Within variance |

| Endpoint | Baseline P95 (Run1/Run2) | 8w P95 | Change |
|----------|------------------------|--------|--------|
| Create Cart | 350 / 460ms | 470ms | Within variance |
| Add Item | 180 / 210ms | 210ms | Within variance |
| Cancel Cart | 830 / 900ms | 1200ms | +33 to +45% |

### Conclusion

**Equal to or slightly worse than baseline. Cancel Cart P95 degraded +33–45%.**

Increasing master-data to 8 workers on a 6-core environment results in cart (8w) + master-data (8w) = 16 workers, significantly exceeding the physical core count. Context switching overhead increases, particularly affecting Cancel Cart P95 where master data references are frequent. 4 workers is appropriate for master-data on a 6-core environment.

---

## Test Procedure Notes

### Standard Test Procedure (for consistent conditions)

1. Stop all services: `docker compose -f docker-compose.prod.yaml down`
2. Start all services: `docker compose -f docker-compose.prod.yaml up -d`
3. Verify health check (all 7 services healthy)
4. Setup test data: `bash run_perf_test.sh setup 310`
5. Redis FLUSHALL: `docker exec redis redis-cli FLUSHALL`
6. Run test: `bash run_perf_test.sh custom 300 3m`

### Notes

- If MongoDB volumes were deleted, replica set initialization is required
  ```bash
  docker exec mongodb mongosh --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]})"
  ```
- Dapr sidecars may need restart depending on timing
- 500 users is near resource limit on this local environment (6 CPU, 16GB RAM). 300 users is recommended for stable results
