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
| 9 | Ordering effect root cause analysis | **Root cause identified** | Consecutive test runs caused Avg +60% degradation. Root cause: `log_requests` middleware firing `asyncio.create_task()` for MongoDB writes (~200/sec). Task backlog saturates the event loop, worsening as data accumulates |
| 10 | DB accumulation vs ordering effect isolation | **DB accumulation is not the cause** | Compared `down` (volumes retained) vs `down -v` (volumes deleted). MongoDB data accumulation itself does not affect performance |
| 11 | #3/#5 long test (30min x3, reverse order) | **Ordering effect dominant** | Reversed execution order (#5->#3->#1). First-run #5 performed best, last-run #1 worst. Degradation is due to execution order, not the measures. req/s 103.6-104.7, nearly identical |
| 12 | REQUEST_LOG_TO_DB=false (DB write disabled) | **Ordering effect resolved** | Avg stable at 41->44ms (+7%). req/s constant at 97.5-97.6. Confirms DB writes are the primary cause of the ordering effect |
| 13 | await synchronous write | **Significant degradation** | Changed create_task to await. Avg 85->393ms (+362%), req/s 95.8->85.9. MongoDB insert latency directly impacts response time — worst result |
| 14 | Batch write (insert_many 100 docs/5 sec) | **Improvement (partial)** | Run 1-3 stable at Avg 53->58ms. However, Run 4-5 degraded to 96->140ms. create_task frequency reduced to ~2/sec, but insert_many latency accumulates over time |
| 15 | unique constraint removal / index deletion | **No effect** | Without unique: +77%, without indexes: +116%. Index presence does not affect ordering effect. Root cause is create_task firing frequency itself |
| 16 | Host reboot baseline / WriteConcern w=0 | **w=0 no effect** | Re-verified under clean conditions after host reboot. w=0 still showed +131% degradation first half to second half. MongoDB response wait is not the primary cause |
| 17 | Batch write (re-verification after host reboot) | **Ordering effect fully resolved** | insert_many 100 docs/5 sec. 5min x5 consecutive: Avg 37-40ms (+-3%). create_task frequency reduction is the fundamental fix |
| 18 | Batch write 6-hour stability test | **Stable, no leak** | 154,655 requests/6 hours, 0 errors. Avg 38ms stable throughout. Cart memory plateaus at 979MB, no memory leak |
| 19 | 8GB memory environment test (worker optimization) | **Viable** | 8GB/300 users/60min. 383,751 requests, 3 errors (0.00%). Avg 49ms, 106.6 req/s. cart:4w optimal; 8w causes memory exhaustion |
| 20 | WiredTiger cache limit (1.5GB) | **Memory stabilized, errors resolved** | Memory fluctuation 70-95% -> 71-76% stabilized. Errors 3 -> 0. Avg 67ms (+37%) is a tradeoff. req/s 104.5 (-2%) |
| 21 | Worker rebalancing (cart:6, md:2, t:1) | **Avg/P50 improved** | Avg 67->60ms (-10%), P50 24->19ms (-21%), req/s 106.3 (+2%). 0 errors. Memory usage equivalent. Optimal 8GB configuration |
| 22 | cart:8w verification (md:2, t:1) | **Diminishing returns** | P50 17ms (best) but Avg/P95/req/s equivalent to cart:6w. Cart memory +22% (1,055MB), host free 1.6GB. Low cost-effectiveness; 6w is optimal |
| 23 | Buffer size tuning (sync insert_many) | **No effect** | buffer 50/500/1000 compared. Avg 34–38ms, req/s 105.1–105.2, no significant difference. Large buffers (500/1000) cause Max spikes 610–1,119ms. 100 is optimal |
| 24 | Async insert_many (create_task fire-and-forget) | **No effect** | buffer 100/1000 compared. Avg/req/s identical to sync. buffer=1000 Max spike 1,130ms not resolved. No benefit from async; keep sync await + buffer=100 |
| 25 | Env var support 180min stability test | **Stable, no leak** | 1,162,021 requests/180min, 0 errors. Avg 33ms, 107.6 req/s stable throughout. Cart memory plateau at 810MB, no leak. Redis linear growth (~4.7MB/min) requires attention for long runs |
| 26 | Redis maxmemory 1GB + 4GB swap long test | **Failed at 345min** | 2,324,979 requests, 228 errors (0.01%). Avg 34ms stable until failure. Redis hit 1GB at ~211min, eviction started. At 345min, active carts (item 2-3) evicted → 404 errors in 16-second burst. Root cause: Redis data on swap degrades LRU accuracy — newly created carts incorrectly evicted. Redis must not use swap. Swap extended runtime 3.3x (104→345min) but Redis eviction behavior becomes unpredictable |
| 27 | maxLenApprox 50000 + Redis container memory limit 360min | **6h complete, 0 errors** | 1,650,915 requests/360min, 0 errors, 0 evictions. Redis memory stabilized at ~813MB after ~170min (Stream capped at 50,000 entries). Stream accounts for ~95% of Redis memory (~750MB); cart cache is only ~3MB. `deleteAfterDeliver` does not exist in Dapr Redis pub/sub. Redis on swap (~80MB) remains structural risk. Recommends pub/sub migration to RabbitMQ (#99) |
| 28 | pub/sub RabbitMQ migration (cart:6w) | **Throughput equivalent, Redis memory 99.8% reduced** | Redis pub/sub → RabbitMQ. Redis memory ~800MB → ~5MB. 300users/3min×3: Avg 40ms, P95 127ms, req/s 98.9. Swap 0. Max 629ms (improved from 1,700ms with Redis) |
| 29 | RabbitMQ + cart:4w user count verification | **200 users optimal** | cart:4w with 150/200/300 users. 150u: Avg 35ms/Max 375ms (stable). 200u: Avg 36ms/Max 410ms (stable). 300u: Avg 92ms/Max 3,850ms (swap degradation). 200 users is optimal for 8GB/cart:4w |
| 30 | RabbitMQ + cart:4w 180min stability test | **3h complete, 0 errors** | 775,665 requests/180min. Avg 32ms, P50 15ms, P95 120ms, Max 1,228ms. Add Item Avg 19ms/P50 14ms. Redis memory ~15MB. Achieved equivalent or better latency than Test #25 (Redis, 300u, 6w) with 200u/4w |

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

## Test 9: Ordering Effect Root Cause Analysis

**Date**: 2026-04-09
**Purpose**: Identify the root cause of the "ordering effect" where performance degrades during consecutive test runs

### Background

When running tests #1 -> #3 -> #5 consecutively, Avg worsened progressively with each subsequent test. It was necessary to determine whether this was due to differences between measures or a side effect of test execution order.

### 9-1: DB Accumulation Impact Check (3min x3)

Compared `down` (volumes retained) vs `down -v` (volumes deleted).

| Run | Condition | Avg (ms) | req/s |
|-----|-----------|---------|-------|
| 1 | down -v (clean) | 56 | 90.65 |
| 2 | down (DB accumulated) | 52 | 90.74 |
| 3 | down -v (re-clean) | 41 | 90.75 |

**Conclusion**: DB accumulation itself does not affect performance.

### 9-2: #5->#3->#1 Reverse Order Test (30min x3, down -v each time)

Executed measures in reverse order to verify the ordering effect.

| Order | Test | Avg (ms) | P50 | P95 | P99 | req/s |
|-------|------|---------|-----|-----|-----|-------|
| 1st | #5 activedefrag+THP | **69** | 25 | 280 | 560 | 104.72 |
| 2nd | #3 Cache Deletion | 80 | 28 | 330 | 660 | 104.35 |
| 3rd | #1 Baseline | **100** | 33 | 410 | 900 | 103.61 |

**Conclusion**: The first-run #5 performed best, last-run #1 worst — completely reversed from the previous order. Degradation is due to execution order (ordering effect), not differences between measures.

### 9-3: Baseline 5 Consecutive Runs (5min x5, no down -v)

Ran the same baseline 5 times consecutively to reproduce the ordering effect.

| Run | Avg (ms) | P50 | P95 | P99 | req/s |
|-----|---------|-----|-----|-----|-------|
| 1 | **48** | 23 | 200 | 340 | 97.37 |
| 2 | 59 | 27 | 240 | 420 | 97.13 |
| 3 | 71 | 29 | 280 | 560 | 96.81 |
| 4 | 68 | 30 | 270 | 510 | 96.71 |
| 5 | **77** | 32 | 310 | 580 | 96.45 |

Avg degraded +60% from Run 1 to 5, while req/s decreased only -0.9% (nearly stable).

### 9-4: Root Cause Identified — log_requests Middleware

Investigation revealed the following code in `kugel_common/middleware/log_requests.py` as the cause:

```python
asyncio.create_task(_output_request_log_to_db_async(request_log))
```

- Every HTTP request fires `asyncio.create_task()` for fire-and-forget MongoDB writes
- 2 inserts per request (commons DB + tenant DB) = ~200 tasks/sec
- Tasks fire faster than they complete, causing pending task backlog
- Event loop scheduling cost increases, delaying request processing
- MongoDB data accumulation (163K records/645MB across 5 tests) slows inserts, creating a vicious cycle

### 9-5: Time-Series Degradation Within a 30-Minute Test

Avg by 5-minute intervals during 30-minute test (#5, create_task version):

| Interval | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|---------|-----|-----|-----|-------|
| 0-5min | 48.4 | 27 | 174 | 319 | 106.2 |
| 5-10min | 49.5 | 21 | 214 | 363 | 107.0 |
| 10-15min | 52.5 | 21 | 227 | 398 | 107.2 |
| 15-20min | 57.8 | 22 | 245 | 450 | 105.7 |
| 20-25min | 63.2 | 24 | 265 | 488 | 105.7 |
| 25-30min | 67.5 | 25 | 278 | 534 | 105.9 |

**Within a single test, Avg degraded from 48 to 68ms (+39%) over time.**

"First 5 minutes" Avg progression across 3 consecutive tests: #5(48.4) -> #3(51.3) -> #1(52.5)ms. Accumulation from the previous test carries over to the next test's starting point.

---

## Tests 10-15: Countermeasure Verification

**Date**: 2026-04-09
**Purpose**: Verify methods to resolve the ordering effect

### Approach Comparison (5min x5 consecutive, Aggregated Avg)

| Run | create_task (original) | await (sync) | Batch insert_many | DB disabled |
|-----|:----------------------:|:------------:|:-----------------:|:-----------:|
| 1 | 48 | 85 | 53 | **41** |
| 2 | 59 | 138 | 59 | **43** |
| 3 | 71 | 145 | 58 | **51** |
| 4 | 68 | 167 | 96 | **49** |
| 5 | 77 | 393 | 140 | **44** |

### Approach Comparison (req/s)

| Run | create_task (original) | await (sync) | Batch insert_many | DB disabled |
|-----|:----------------------:|:------------:|:-----------------:|:-----------:|
| 1 | 97.37 | 95.76 | 97.46 | **97.63** |
| 2 | 97.13 | 94.06 | 97.21 | **97.53** |
| 3 | 96.81 | 93.90 | 97.38 | **97.51** |
| 4 | 96.71 | 93.36 | 96.11 | **97.50** |
| 5 | 96.45 | 85.93 | 94.69 | **97.54** |

### Ordering Effect Comparison (Run 1 -> 5)

| Approach | Avg Change | req/s Change | Assessment |
|----------|-----------|-------------|------------|
| create_task (original) | 48->77 (+60%) | -0.9% | Ordering effect present |
| **await (sync)** | **85->393 (+362%)** | **-10.3%** | **Worst** |
| Batch insert_many | 53->140 (+164%) | -2.8% | Run 1-3 stable, Run 4-5 degraded |
| **DB disabled** | **41->44 (+7%)** | **-0.1%** | **Ordering effect resolved** |

### Index Impact Check (10-minute test, first 5min vs last 5min)

Performed on log_request collections across all 7 services.

| Pattern | First 5min Avg | Last 5min Avg | Degradation |
|---------|---------------|--------------|-------------|
| unique removed (indexes remain) | 72.2ms | 127.6ms | +77% |
| Indexes deleted | 90.5ms | 195.2ms | +116% |

**Index presence/unique constraints do not affect the ordering effect.**
Deleting indexes actually worsened performance (loss of WiredTiger's index-based insert optimization).

### Approach Details

#### REQUEST_LOG_TO_DB Environment Variable

Added `REQUEST_LOG_TO_DB: bool = True` to `kugel_common/config/settings_app.py`.
Set `REQUEST_LOG_TO_DB: ${REQUEST_LOG_TO_DB:-true}` in `docker-compose.prod.yaml` for all services.
Middleware controls DB writes with `if settings.REQUEST_LOG_TO_DB:`.
File logs are always output regardless of this setting.

#### Batch Write (RequestLogBuffer)

Implemented in `kugel_common/middleware/request_log_buffer.py`.
- Accumulates RequestLog entries in an in-memory buffer
- Flushes via `insert_many` when 100 entries reached or 5 seconds elapsed since last request
- Shutdown hook flushes remaining entries (added to `close_event()` in all 7 services)
- `create_task` frequency reduced from ~200/sec to ~2/sec

---

## Conclusion and Future Direction

### Root Cause of the Ordering Effect

The `log_requests` middleware fires `asyncio.create_task()` for ~200 MongoDB inserts per second
in a fire-and-forget pattern. Tasks fire faster than they complete, causing pending task backlog.
Event loop scheduling cost increases, compounded by insert latency from data accumulation,
creating a vicious cycle of degradation.

### Impact on Performance Testing

Performance tests aim to measure response times for production business operations.
Request log DB writes are not part of the business processing under test.
It is recommended to set `REQUEST_LOG_TO_DB=false` during tests to eliminate noise from log writes.

### Production Countermeasures (Not Yet Implemented — Under Consideration)

| Countermeasure | Status | Effect |
|----------------|--------|--------|
| Batch write (insert_many) | Implemented, not merged | Reduces create_task frequency by 1/100 |
| unique constraint removal | Code modified, not merged | Reduces uniqueness check overhead (minor effect) |
| REQUEST_LOG_TO_DB env var | Implemented, not merged | Disables DB writes during testing |

Batch write is the most promising for production, but it shows degradation after 25+ minutes,
requiring tuning of batch size and timer intervals.
Alternatives under consideration include process separation via Dapr pub/sub and batch import from file logs.

---

## Test 16: Baseline Re-measurement After Host Reboot

**Date**: 2026-04-09
**Purpose**: Establish an accurate ordering effect baseline under clean conditions after host reboot

Baseline could not be measured correctly due to host fatigue (load average 6.8, buff/cache saturated)
from repeated long-running tests, so re-measurement was performed after a host reboot.

### 10-Minute Test: First 5min vs Last 5min Comparison

| Pattern | First 5min Avg | Last 5min Avg | Change | log_request count |
|---------|---------------|--------------|--------|-------------------|
| Original code (create_task, w=1) | 51.8ms | 107.2ms | **+107%** | — |
| WriteConcern w=0 | 46.0ms | 106.4ms | **+131%** | 67,336 |
| DB log disabled | 49.9ms | 47.7ms | **-4.5%** | 0 |

### Details: Original Code (Baseline)

| | Avg | P50 | P95 | P99 | req/s |
|--|-----|-----|-----|-----|-------|
| First 5min | 51.8 | 27 | 189 | 350 | 105.6 |
| Last 5min | 107.2 | 27 | 470 | 1097 | 101.7 |

### Details: WriteConcern w=0

Overrode `initialize()` in `RequestLogRepository` to apply
`WriteConcern(w=0)` only to the log_request collection.
Other repositories are unaffected.

| | Avg | P50 | P95 | P99 | req/s |
|--|-----|-----|-----|-----|-------|
| First 5min | 46.0 | 26 | 158 | 305 | 105.9 |
| Last 5min | 106.4 | 27 | 478 | 1074 | 101.5 |

With w=0, MongoDB acknowledges writes immediately, but the ordering effect persists.
This confirms that MongoDB response latency is not the cause.

### Details: DB Log Disabled

Commented out the `create_task()` line in `log_requests.py`.
File logs are maintained.

| | Avg | P50 | P95 | P99 | req/s |
|--|-----|-----|-----|-----|-------|
| First 5min | 49.9 | 29 | 175 | 294 | 106.3 |
| Last 5min | 47.7 | 22 | 203 | 332 | 107.4 |

With DB logging disabled, performance was completely stable over 10 minutes (slightly improved in the second half).

### Conclusion

The root cause of the ordering effect is not MongoDB write performance, but rather
**the firing frequency of `create_task()` (~200/sec) and the processing cost within each task**
(DB connection acquisition, object creation, serialization via `model_dump()`)
saturating the event loop.

Since `w=0` (eliminating MongoDB response wait) had no effect, the solution direction is confirmed as
**reducing task firing frequency** (batch writes) or **complete isolation from the event loop**
(delegation to a separate process).

---

## Test 17: Batch Write (Re-verification After Host Reboot)

**Date**: 2026-04-09
**Purpose**: Confirm the batch write effect under clean conditions after host reboot

### Implementation

Implemented `RequestLogBuffer` class in `kugel_common/middleware/request_log_buffer.py`.

- Middleware adds `request_log` to an in-memory buffer (`await buffer.add()`)
- Flushes via `insert_many` when 100 entries reached or 5 seconds elapsed since last request
- Shutdown hook flushes remaining entries (added to `close_event()` in all 7 services)
- `create_task` frequency: ~200/sec -> ~2/sec (only 1 timer task)

### 10-Minute Test: First 5min vs Last 5min Comparison

| Pattern | First 5min Avg | Last 5min Avg | Change | log_request count |
|---------|---------------|--------------|--------|-------------------|
| Original code (create_task, w=1) | 51.8ms | 107.2ms | **+107%** | — |
| WriteConcern w=0 | 46.0ms | 106.4ms | +131% | 67,336 |
| **Batch insert_many** | **47.4ms** | **43.0ms** | **-9.3%** | **69,155** |
| DB log disabled | 49.9ms | 47.7ms | -4.5% | 0 |

### Details: Batch insert_many

| | Avg | P50 | P95 | P99 | req/s |
|--|-----|-----|-----|-----|-------|
| First 5min | 47.4 | 30 | 153 | 275 | 106.4 |
| Last 5min | 43.0 | 22 | 167 | 292 | 108.0 |

### Conclusion

**Batch writes fully resolved the ordering effect.**

- First to second half: -9.3% (actually improved). Nearly as stable as DB log disabled (-4.5%)
- 69,155 request logs were saved to DB successfully with no data loss
- First half Avg 47.4ms is faster than the original code's 51.8ms (due to reduced create_task overhead)

Reducing `create_task` frequency from ~200/sec to ~2/sec fundamentally resolved the event loop saturation.

### 5min x5 Consecutive Test (Stability Verification)

After host reboot, ran the batch write version 5 times consecutively.

| Run | Avg (ms) | req/s |
|-----|---------|-------|
| 1 | 38 | 97.54 |
| 2 | 40 | 97.44 |
| 3 | 39 | 97.55 |
| 4 | 39 | 97.57 |
| 5 | 37 | 97.60 |

Comparison with original code (create_task):

| Run | Original Avg | Batch Avg | Improvement |
|-----|:----------:|:--------:|:-----------:|
| 1 | 48 | 38 | -21% |
| 2 | 59 | 40 | -32% |
| 3 | 71 | 39 | -45% |
| 4 | 68 | 39 | -43% |
| 5 | 77 | 37 | -52% |

- Avg change from Run 1 to 5: Original 48->77ms (**+60%**), Batch 38->37ms (**+-3%**)
- req/s across all runs: 97.44-97.60 (+-0.1%)
- Batch version is faster than the original's Run 1 (48ms) across all runs

**The ordering effect is fully resolved, and performance remains constant across consecutive runs.**

---

## Test 18: Batch Write 6-Hour Stability Test (Memory Leak Verification)

**Date**: 2026-04-10
**Purpose**: Verify long-term stability and absence of memory leaks with the batch write version
**Conditions**: Clean start (`stop --clean` -> `start --prod`), 310 terminals, **20 users**, JWT auth
**Environment**: Lima VM **16GB** memory, 6-core CPU

### Test Results

| Endpoint | Requests | Error Rate | Avg (ms) | P50 | P95 | P99 | Max |
|----------|----------|------------|---------|-----|-----|-----|-----|
| Create Cart | 7,040 | 0% | 88 | 84 | 130 | 140 | 170 |
| Add Item | 140,595 | 0% | 26 | 27 | 51 | 57 | 140 |
| Cancel Cart | 7,020 | 0% | 226 | 220 | 270 | 280 | 320 |
| **Aggregated** | **154,655** | **0%** | **38** | **28** | **120** | **240** | **320** |

### Performance Stability

Avg/Med remained constant throughout all 6 hours. The ordering effect is fully resolved.

| Time Period | Total Requests | Avg (ms) | Med (ms) | Errors |
|-------------|---------------|---------|---------|--------|
| 0-30min | 9,006 | 43 | 35 | 0 |
| 0-1h | 26,033 | 40 | 29 | 0 |
| 0-2h | 52,070 | 39 | 28 | 0 |
| 0-3h | 77,990 | 38 | 28 | 0 |
| 0-4.5h | 116,812 | 38 | 28 | 0 |
| 0-6h | 154,655 | 38 | 28 | 0 |

### Memory Progression (Memory Leak Verification)

Container memory recorded at 5-minute intervals. 72 samples total.

| Elapsed | cart (MB) | terminal (MB) | master-data (MB) | mongodb (MB) | redis (MB) |
|---------|---------|-------------|-----------------|-------------|-----------|
| 0min | 632 | 370 | 328 | 330 | 393 |
| 30min | 770 | 452 | 340 | 543 | 403 |
| 1h | 835 | 508 | 343 | 580 | 413 |
| 1.5h | 871 | 538 | 347 | 674 | 423 |
| 2h | 893 | 576 | 349 | 754 | 431 |
| 3h | 941 | 615 | 353 | 871 | 451 |
| 4h | 945 | 635 | 354 | 979 | 458 |
| 4.5h | 970 | 662 | 354 | 1,041 | 480 |
| 5h | 970 | 675 | 355 | 1,242 | 486 |
| 5.5h | 972 | 676 | 356 | 1,272 | 495 |
| 6h | 979 | 682 | 357 | 1,293 | 508 |

### Cart Memory Growth Rate

| Interval | Growth/30min | Assessment |
|----------|------------|------------|
| 0->30min | +138 MB | Warm-up |
| 30->60min | +65 MB | Warm-up |
| 60->90min | +36 MB | Converging |
| 90->120min | +22 MB | Converging |
| 120->180min | +16 MB/30min | Approaching plateau |
| 180->270min | +10 MB/30min | Plateau |
| 270->360min | **+3 MB/30min** | **Stable** |

### Other Metrics

| Item | Value |
|------|-------|
| DB log_request count (cart) | 173,803 |
| DB log_request count (commons) | 174,864 |
| Disk usage | 40GB / 193GB (21%) |
| account memory | 142->143 MB (+1MB, fully stable) |
| stock memory | 80->87 MB (+7MB, stable) |

### Conclusion

1. **Ordering effect**: Maintained Avg 38ms over 6 hours and 154,655 requests. **Fully resolved**
2. **Memory leak**: Cart grew from 632->979MB then reached a plateau. Only +9MB in the last 90 minutes. **No leak**
3. **Batch write reliability**: 173,803 request logs saved to DB successfully. No data loss
4. **Error rate**: 0% — No failures over 6 hours of continuous operation

Batch writes (`RequestLogBuffer`) have been confirmed to be production-ready quality.

---

## Test 19: 8GB Memory Environment Test (Worker Optimization)

**Date**: 2026-04-10
**Purpose**: Optimize worker counts and verify stability under an 8GB memory constraint
**Environment**: Lima VM 8GB (changed from 16GB), 6-core CPU

### Worker Optimization

Reduced the 16GB worker configuration (23 total) for 8GB.

| Service | 16GB Config | 8GB Config | Reason |
|---------|-------------|------------|--------|
| account | 2 | **1** | Nearly unused during tests (CPU 0.1%) |
| terminal | 4 | **2** | JWT acquisition only (CPU 0.3%) |
| master-data | 4 | 4 | Frequently called by cart (CPU 17%) |
| **cart** | **8** | **4** | Bottleneck (CPU 89%) |
| report | 2 | **1** | pub/sub receive only (CPU 0.1%) |
| journal | 2 | **1** | pub/sub receive only (CPU 0.1%) |
| stock | 1 | 1 | No change |
| **Total** | **23** | **14** | |

### Cart Worker Count Verification (300 users / 5min)

| cart Workers | Avg (ms) | P50 | P95 | req/s | Errors | Memory (host) |
|---|---|---|---|---|---|---|
| **4** | **101** | **24** | **410** | **99.3** | **0%** | **69%** |
| 8 | 465 | 190 | 1,700 | 87.5 | 0% | 97% |
| 8 (retry) | — | — | — | — | Cancel 100% failed | 97% |

Cart with 8 workers caused **memory exhaustion** (81MB free) in the 8GB environment, severely degrading performance.
Cart with 4 workers is the optimal value for 8GB.

### 60-Minute Stability Test (300 users / cart 4 workers)

**Conditions**: Clean start (`down -v`), 310 terminals, JWT auth

#### Final Results

| Endpoint | Requests | Errors | Avg (ms) | P50 | P95 | P99 | Max | req/s |
|----------|----------|--------|---------|-----|-----|-----|-----|-------|
| Create Cart | 17,603 | 0 | 138 | 110 | 300 | 750 | 3,921 | 4.89 |
| Add Item | 348,810 | 0 | 30 | 18 | 85 | 190 | 1,849 | 96.90 |
| Cancel Cart | 17,338 | 3 | 339 | 260 | 690 | 1,800 | 4,992 | 4.82 |
| **Aggregated** | **383,751** | **3 (0.00%)** | **49** | **20** | **210** | **400** | **5,000** | **106.60** |

#### Error Details

- Only 3 errors in Cancel Cart (0.02%)
- Cause: `Cannot call abortTransaction after calling commitTransaction`
- Temporary transaction contention during MongoDB memory pressure (host at 95% usage)

#### Performance Progression (5-minute intervals)

| Elapsed | Requests | Avg (ms) | P50 | req/s |
|---------|----------|---------|-----|-------|
| 20min | 60,590 | 80 | 23 | 129 |
| 30min | 125,431 | 63 | 21 | 115 |
| 40min | 190,464 | 56 | 21 | 107 |
| 50min | 255,486 | 53 | 21 | 100 |
| 60min | 320,606 | 51 | 21 | 98 |
| 65min | 353,170 | 50 | 20 | 100 |

Avg converged from 80->50ms. P50 was stable at 20-23ms throughout.

#### Memory Progression

| Elapsed | Host Usage | cart | mongodb |
|---------|-----------|------|---------|
| Start | 52% | 314 MB | 195 MB |
| 20min | 77% | 628 MB | 1,631 MB |
| 30min | 94% | 608 MB | 2,891 MB |
| 35min | 95% | 633 MB | 2,871 MB |
| 45min | 72% | 640 MB | 1,204 MB |
| 55min | 92% | 597 MB | 2,675 MB |
| 65min | 79% | 627 MB | 1,692 MB |

- Cart memory stable at 597-683 MB (**no leak**)
- MongoDB releases and rebuilds cache in response to OS memory pressure (fluctuates between 942MB-2.9GB)
- Host usage fluctuates between 70-95%. No OOM occurred

### 16GB vs 8GB Comparison

| Item | 16GB (Test #18) | 8GB (Test #19) |
|------|-----------------|----------------|
| Users | 20 | 300 |
| Test duration | 6 hours | 60 minutes |
| Total requests | 154,655 | 383,751 |
| Avg | 38ms | 49ms |
| P50 | 28ms | 20ms |
| P95 | 120ms | 210ms |
| Error rate | 0% | 0.00% |
| req/s | 7.2 | 106.6 |
| cart Workers | 8 | 4 |

### Conclusion

1. **8GB is viable for 300 users/60min** (383,751 requests, 0.00% error rate)
2. **Worker optimization is essential**: cart 8w -> 4w for stability. 14 total workers is appropriate for 8GB
3. **MongoDB is the memory bottleneck**: WiredTiger cache fluctuates with OS memory pressure, but performance impact is limited
4. **Room for improvement**: Reducing terminal 2->1, master-data 4->2 and using the freed memory for cart 4->6w could alleviate the CPU bottleneck (88.8%)

---

## Test 20: WiredTiger Cache Limit (1.5GB)

**Date**: 2026-04-10
**Purpose**: Verify memory stabilization by limiting MongoDB WiredTiger cache size
**Environment**: 8GB, 300 users, 15min, cart:4w / master-data:4w / terminal:2w (14w total)

### Changes

```yaml
# docker-compose.prod.yaml
command: mongod --replSet rs0 --bind_ip_all --wiredTigerCacheSizeGB 1.5
```

Limited from default (3.4GB) to 1.5GB. In an 8GB environment, the default is excessive and causes OS memory pressure.

### Results

| Endpoint | Requests | Errors | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|----------|--------|---------|-----|-----|-----|-------|
| Create Cart | 4,477 | 0 | 186 | 120 | 470 | 1,300 | 4.98 |
| Add Item | 85,324 | 0 | 40 | 21 | 120 | 240 | 94.82 |
| Cancel Cart | 4,200 | 0 | 487 | 330 | 1,200 | 2,800 | 4.67 |
| **Aggregated** | **94,001** | **0** | **67** | **24** | **250** | **680** | **104.46** |

### Comparison with Test #19 (No WT Limit)

| Metric | No WT limit | WT 1.5GB | Change |
|--------|-------------|----------|--------|
| Avg | 49ms | 67ms | +37% |
| P50 | 20ms | 24ms | +20% |
| req/s | 106.6 | 104.5 | -2% |
| **Errors** | **3** | **0** | **Resolved** |
| Host usage | 70-95% fluctuation | 71-76% stable | **Stabilized** |
| MongoDB memory | 942MB-2.9GB | 1.1-1.5GB | **Stabilized** |

### Conclusion

- **0 errors achieved** — Transaction errors from memory pressure resolved
- **Memory stabilized** — Dramatic host usage fluctuations eliminated
- **Avg slightly worse** — Cache miss increase from WT cache reduction (acceptable tradeoff)
- **req/s nearly equivalent**

---

## Test 21: Worker Rebalancing (cart:6, master-data:2, terminal:1)

**Date**: 2026-04-10
**Purpose**: Alleviate the cart CPU bottleneck (88.8%) by rebalancing workers from other services
**Environment**: 8GB, 300 users, 15min, WT 1.5GB

### Worker Configuration

| Service | Test #20 | Test #21 | Reason |
|---------|----------|----------|--------|
| terminal | 2 | **1** | CPU 0.3% during tests |
| master-data | 4 | **2** | CPU 17%, ample headroom |
| **cart** | **4** | **6** | CPU 88.8% is bottleneck |
| Others (account, report, journal, stock) | 1 each | 1 each | No change |
| **Total** | **14** | **12** | |

### Results

| Endpoint | Requests | Errors | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|----------|--------|---------|-----|-----|-----|-------|
| Create Cart | 4,500 | 0 | 191 | 120 | 510 | 1,600 | 5.00 |
| Add Item | 86,963 | 0 | 33 | 17 | 100 | 260 | 96.64 |
| Cancel Cart | 4,200 | 0 | 495 | 310 | 1,500 | 2,900 | 4.67 |
| **Aggregated** | **95,663** | **0** | **60** | **19** | **250** | **650** | **106.31** |

### Comparison with Test #20 (cart:4w)

| Metric | cart:4w | cart:6w | Change |
|--------|---------|---------|--------|
| Avg | 67ms | 60ms | **-10%** |
| P50 | 24ms | 19ms | **-21%** |
| P95 | 250ms | 250ms | +-0% |
| P99 | 680ms | 650ms | -4% |
| req/s | 104.5 | 106.3 | +2% |
| Errors | 0 | 0 | — |
| cart CPU | 89% | 153% | Load distributed across more workers |
| cart memory | 623MB | 865MB | +39% |
| Host usage | 71-76% | 71-76% | Equivalent |

### Conclusion

1. **Avg -10%, P50 -21% improvement** — Increasing cart workers is effective
2. **Memory usage equivalent** — Reduction from terminal/master-data offsets cart increase
3. **0 errors** — Stable in combination with WT cache limit
4. **P95/P99 equivalent** — Tail latency is dominated by MongoDB I/O

### Recommended Final Configuration for 8GB

```
account:1, terminal:1, master-data:2, cart:6, report:1, journal:1, stock:1
Total: 12 workers
MongoDB: --wiredTigerCacheSizeGB 1.5
```

---

## Test 22: cart:8w Verification

**Date**: 2026-04-10
**Purpose**: Evaluate the effect of increasing cart workers from 6 to 8
**Environment**: 8GB, 300 users, 15min, WT 1.5GB, cart:8w / master-data:2w / terminal:1w (12w->14w total)

### Results

| Endpoint | Requests | Errors | Avg (ms) | P50 | P95 | P99 | req/s |
|----------|----------|--------|---------|-----|-----|-----|-------|
| Create Cart | 4,500 | 0 | 207 | 130 | 550 | 2,000 | 5.00 |
| Add Item | 86,911 | 0 | 33 | 15 | 100 | 310 | 96.58 |
| Cancel Cart | 4,200 | 0 | 507 | 310 | 1,500 | 4,100 | 4.67 |
| **Aggregated** | **95,611** | **0** | **62** | **17** | **260** | **670** | **106.25** |

### cart 4w / 6w / 8w Comparison

| Metric | cart:4w (#20) | cart:6w (#21) | cart:8w (#22) |
|--------|---------------|---------------|---------------|
| Avg | 67ms | **60ms** | 62ms |
| P50 | 24ms | 19ms | **17ms** |
| P95 | 250ms | **250ms** | 260ms |
| P99 | 680ms | **650ms** | 670ms |
| req/s | 104.5 | **106.3** | 106.3 |
| Errors | 0 | 0 | 0 |
| cart memory | 623MB | 865MB | 1,055MB |
| Host usage | 71-76% | 71-76% | 75-80% |

### master-data Load

| Metric | cart:6w | cart:8w |
|--------|---------|---------|
| master-data CPU | 17% | 17-29% |
| master-data memory | ~200MB | ~205MB |

Even with cart:8w, master-data at 2w has ample headroom.

### Conclusion

1. **cart:8w only improves P50 slightly** (19->17ms); Avg/P95/P99/req/s are equivalent to cart:6w
2. **Memory cost +22%** (865->1,055MB), host free memory drops from 3.7GB to 1.6GB
3. **Low cost-effectiveness** — cart:6w is the optimal balance for 8GB
4. **master-data at cart:8w is still only 29% CPU** — Not a constraint on worker count

---

## Test 23: Buffer Size Tuning (Synchronous insert_many)

**Date**: 2026-04-10
**Purpose**: Evaluate the performance impact of varying `request_log_buffer` max_size via environment variable
**Change**: Added `REQUEST_LOG_BUFFER_SIZE` environment variable support. `get_request_log_buffer()` now reads `max_size` / `flush_interval` from environment variables
**Environment**: cart:6w, md:2, t:1 (16GB)
**Conditions**: 300 users / 10min / DB cleared each run (`down -v`)

### buffer=500

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max | req/s |
|----------|---------|-----|-----|-----|------|-------|
| Create Cart | 100 | 94 | 170 | 240 | 1,119 | 5.00 |
| Add Item | 25 | 16 | 69 | 110 | 382 | 95.60 |
| Cancel Cart | 251 | 240 | 340 | 410 | 682 | 4.50 |
| **Aggregated** | **38** | **18** | **160** | **280** | **1,119** | **105.10** |

### buffer=1000

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max | req/s |
|----------|---------|-----|-----|-----|------|-------|
| Create Cart | 95 | 88 | 160 | 220 | 610 | 5.00 |
| Add Item | 24 | 16 | 65 | 110 | 353 | 95.65 |
| Cancel Cart | 244 | 230 | 330 | 400 | 512 | 4.50 |
| **Aggregated** | **37** | **17** | **150** | **260** | **610** | **105.16** |

### buffer=50

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max | req/s |
|----------|---------|-----|-----|-----|------|-------|
| Create Cart | 91 | 82 | 150 | 190 | 284 | 5.00 |
| Add Item | 22 | 15 | 58 | 88 | 241 | 95.73 |
| Cancel Cart | 236 | 230 | 310 | 350 | 420 | 4.50 |
| **Aggregated** | **34** | **17** | **130** | **260** | **420** | **105.23** |

### Analysis

- Avg 34-38ms (+-5.5%), req/s 105.1-105.2 -- no significant difference (within baseline variance of +-15-19%)
- **Max spikes**: Larger buffers increase the number of documents per insert_many call, extending MongoDB write time and making spikes more likely
  - buffer=50: Max 420ms
  - buffer=500: Max 1,119ms (single outlier on Create Cart)
  - buffer=1000: Max 610ms
- buffer=50 produced the best results, but it ran last and may have benefited from cache warmup

### Conclusion

1. **No significant difference in Avg/req/s across buffer sizes 50-1000**
2. **Smaller buffers are better for suppressing Max spikes**
3. **buffer=100 (default) is the optimal balance** -- create_task frequency of ~2/sec resolves the ordering effect while keeping spikes under control

---

## Test 24: Async insert_many (create_task fire-and-forget)

**Date**: 2026-04-10
**Purpose**: Evaluate the impact of changing batch writes from await (synchronous) to create_task (async fire-and-forget) on response times
**Change**: DB writes in `_flush_unlocked()` changed to `asyncio.create_task(self._write_to_db(db_docs))`. Synchronous await retained only during shutdown
**Environment**: cart:6w, md:2, t:1 (16GB)
**Conditions**: 300 users / 10min / DB cleared each run (`down -v`)

### buffer=100 (async)

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max | req/s |
|----------|---------|-----|-----|-----|------|-------|
| Create Cart | 93 | 88 | 160 | 190 | 428 | 5.00 |
| Add Item | 21 | 15 | 58 | 83 | 211 | 95.76 |
| Cancel Cart | 238 | 230 | 300 | 350 | 537 | 4.50 |
| **Aggregated** | **34** | **16** | **130** | **260** | **537** | **105.27** |

### buffer=1000 (async)

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max | req/s |
|----------|---------|-----|-----|-----|------|-------|
| Create Cart | 95 | 88 | 160 | 200 | 1,130 | 5.00 |
| Add Item | 24 | 16 | 66 | 100 | 263 | 95.66 |
| Cancel Cart | 243 | 230 | 320 | 390 | 535 | 4.50 |
| **Aggregated** | **37** | **18** | **140** | **260** | **1,130** | **105.16** |

### Sync vs Async Comparison

| Method | Buffer | Avg (ms) | P50 | P95 | Max | req/s |
|--------|:------:|---------|-----|-----|------|-------|
| Sync (await) | 1000 | 37 | 17 | 150 | 610 | 105.16 |
| Async (create_task) | 1000 | 37 | 18 | 140 | 1,130 | 105.16 |

### Analysis

- **Avg/P50/req/s are equivalent between sync and async** -- Batch writes occur only ~2 times/sec, so the await cost is negligible
- **Async does not eliminate Max spikes** -- With buffer=1000, the async version still hit Max 1,130ms. Spikes are caused not by insert_many execution itself but by MongoDB-side load from processing large document batches
- **Downsides of async**: Risk of data loss during shutdown, increased code complexity (requires a dedicated sync path for shutdown)

### Conclusion

1. **No benefit from async** -- No improvement in Avg/req/s, and spikes are not suppressed
2. **Keep sync await + buffer=100** -- Simpler, safer, and performs optimally
3. The `REQUEST_LOG_BUFFER_SIZE` environment variable for tuning is useful and should be retained

---

## Test 25: 180-Minute Stability Test with Environment Variable Support

**Date**: 2026-04-10
**Purpose**: Verify long-term stability of the `REQUEST_LOG_BUFFER_SIZE` environment variable version. Check for memory leaks
**Change**: Test #23's environment variable support (sync await insert_many) applied
**Environment**: cart:6w, md:2, t:1 (8GB) / buffer=100, flush_interval=5.0
**Conditions**: 300 users / 180min / DB cleared (`down -v`)

### Performance Results

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max | req/s |
|----------|---------|-----|-----|-----|------|-------|
| Create Cart | 91 | 87 | 150 | 180 | 758 | 4.90 |
| Add Item | 21 | 15 | 55 | 81 | 664 | 97.81 |
| Cancel Cart | 231 | 220 | 290 | 340 | 1,219 | 4.88 |
| **Aggregated** | **33** | **16** | **140** | **250** | **1,219** | **107.60** |

- **Total requests**: 1,162,021
- **Errors**: 0

### Memory Progression (5-minute interval sampling)

| Elapsed | cart (MB) | MongoDB (MB) | Redis (MB) | Host free (MB) |
|---------|----------|-------------|------------|----------------|
| 0min | 491 | 376 | 31 | 3,521 |
| 10min | 782 | 1,462 | 63 | -- |
| 30min | 804 | 1,456 | 163 | -- |
| 60min | 812 | 1,469 | 291 | -- |
| 90min | 810 | 1,586 | 440 | -- |
| 120min | 822 | 1,478 | 593 | -- |
| 150min | 804 | 1,582 | 741 | -- |
| 180min | 806 | 1,485 | 868 | 960 |

### Analysis

1. **Stable performance**: Avg 33ms sustained over 180 minutes. On par with or better than Test #18 (6 hours, Avg 38ms)
2. **No cart memory leak**: Reached ~810MB by 10min, then plateaued for the remaining 180 minutes (810+-15MB)
3. **MongoDB stable**: Stable within WiredTiger cache (~1,480MB, with periodic spikes to ~1,580MB)
4. **Redis linear growth**: Cart cache accumulation causes linear growth at ~4.7MB/min. Production environments need TTL settings or periodic FLUSHALL
5. **Host free 960MB**: In an 8GB environment, 180 minutes is the safe operational limit. Redis accumulation is the primary OOM risk

### Comparison with Test #18

| Item | Test #18 (6 hours) | Test #25 (180min) |
|------|-------------------|-------------------|
| Avg | 38ms | 33ms |
| req/s | -- | 107.6 |
| Errors | 0 | 0 |
| cart memory | 979MB (plateau) | 810MB (plateau) |
| Configuration | cart:8w, md:4, t:4 | cart:6w, md:2, t:1 |

The reduced worker configuration compared to Test #18 resulted in lower memory usage (979->810MB) and improved Avg (38->33ms). This confirms that the worker rebalancing from Test #21 remains effective in long-duration tests.

---

## Test 26: Redis maxmemory 1GB + 4GB Swap Long-Duration Test

**Date**: 2026-04-10-11
**Purpose**: Evaluate long-duration operational limits in an 8GB environment. Verify Redis eviction behavior with maxmemory and OOM prevention via swap
**Change**: Redis configured with `maxmemory 1gb --maxmemory-policy allkeys-lru`. 4GB swap file added to host
**Environment**: cart:6w, md:2, t:1 (8GB) / buffer=100
**Conditions**: 300 users / 360min (target) / DB cleared (`down -v`)

### Performance Results

| Endpoint | Reqs | Fails | P50 | P95 | P99 | Max | req/s |
|----------|------|-------|-----|-----|-----|------|-------|
| Create Cart | 105,934 | 0 | 90 | 160 | 230 | 3,200 | -- |
| Add Item | 2,113,621 | 228 | 15 | 55 | 87 | 2,500 | -- |
| Cancel Cart | 105,424 | 0 | 220 | 320 | 450 | 3,300 | -- |
| **Aggregated** | **2,324,979** | **228 (0.01%)** | **16** | **150** | **260** | **3,300** | **107.6** |

- **Uptime**: 345 minutes (96% of 360-minute target)
- **Errors**: 228, concentrated around 02:25 (~345 minutes after start)

### Error Analysis

#### Error Summary

All 228 errors were **Add Item 404 errors**: `Failed to get cached cart, cart_id: xxx: cart not found (collection_name->cache_cart)`

- **evicted_keys**: 56,746 (at test end)
- **Error window**: Concentrated in just **16 seconds** from 02:25:26 to 02:25:42

#### Error Timeline

```
02:25:26  First errors (4/sec)
02:25:30  Errors accelerate (48/sec)
02:25:36  Peak burst (66/sec)
02:25:42  Last errors (2/sec)
```

#### Distribution of Failed Item Numbers

| Item # | Count | Meaning |
|:------:|:-----:|---------|
| 2 | 70 | Failed on 2nd item right after cart creation (most frequent) |
| 3 | 68 | Same -- 3rd item |
| 4-7 | 22-36 | Early in cart |
| 8-20 | 8-26 | Mid to late cart |

**Items 2-3 were most frequent** -- Carts created moments ago were evicted. Under LRU, the newest keys should be evicted last, indicating **abnormal eviction behavior**.

#### Root Cause: Abnormal Redis Eviction Under Swap

Post-test investigation revealed:

1. **Cart keys are small**: ~6KB per key (2-7KB range)
2. **288 keys x 6KB = ~1.7MB**, yet Redis `used_memory` was **636MB**
3. **`mem_fragmentation_ratio`: 0.62** -- Physical RSS (394MB) was significantly smaller than Redis-reported memory (667MB)

This indicates **Redis data had been swapped out to disk**. Redis is an in-memory database and its behavior is not guaranteed when operating on swap.

**Probable mechanism**:

```
1. Redis memory reaches 1GB as test continues
2. Eviction starts -> 981MB -> drops sharply to 135MB (mass eviction)
3. After eviction, Redis memory grows again (new carts being created)
4. At this point, host physical memory is exhausted; some Redis data resides on swap
5. LRU evaluation slows down due to latency accessing swapped-out data
6. At 345min, when eviction triggers again, swap thrashing degrades
   LRU accuracy, causing recently created carts to be evicted
```

#### Dapr State Store Key Structure

- Dapr's cartstore specifies `databaseIndex: 2`, but keys were actually stored in **DB0**
- Key format: `cart||{cart_id}` (with Dapr prefix)
- `maxmemory` applies to the entire Redis instance (all DBs combined), so DB separation provides no eviction protection

### Memory Progression (5-minute interval sampling)

| Elapsed | cart (MB) | MongoDB (MB) | Redis (MB) | Phase |
|---------|----------|-------------|------------|-------|
| 0min | 457 | 267 | 21 | Start |
| 21min | 841 | 1,463 | 111 | Stable |
| 84min | 782 | 1,428 | 411 | cart begins swapping out |
| 147min | 714 | 1,436 | 710 | |
| **211min** | **672** | **1,487** | **981** | **Redis approaching 1GB** |
| **243min** | **691** | **1,466** | **135** | **Eviction starts -> Redis drops sharply** |
| 306min | 715 | 1,458 | 427 | Eviction continues, normal operation |
| **345min** | -- | -- | -- | **In-flight carts evicted -> test failure** |

At test end: Swap usage 3,340MB / 4,095MB

### Comparison with No-Swap Run (Test #26 aborted version)

| Item | No swap | 4GB swap |
|------|---------|----------|
| Time to error | ~104min | ~345min |
| Error cause | OOM (host memory exhaustion) | Redis eviction |
| Error count | 165 | 228 |
| Lifespan extension | -- | **~3.3x** |

### Analysis

1. **Swap completely prevented OOM Killer** -- Even after exhausting 8GB of memory, all processes survived and the test ran for 345 minutes
2. **Performance degradation was minimal** -- Avg 34ms maintained even with 3.3GB of swap in use. Cart memory was swapped out (841->672MB), but hot paths remained in physical memory
3. **Redis + swap is a dangerous combination** -- Redis is designed as a pure in-memory database. LRU evaluation becomes inaccurate against swapped-out data, causing the critical issue of active carts being evicted
4. **Normal operation continued ~100 minutes after eviction** -- Most evicted carts had already been cancelled. The test failed when the second eviction cycle hit in-flight carts

### Conclusions and Recommendations

1. **Safe continuous operation time for 8GB/300users is ~180min** (no swap), ~300min (with swap, but with reliability concerns)
2. **Never allow Redis to use swap** -- LRU accuracy degrades and in-flight data gets deleted. In production, set `--memory-swappiness=0` on the Redis container or `vm.swappiness=0` at the host level
3. **Recommended Redis maxmemory-policy is `noeviction`** -- A memory limit error is easier to handle at the application level than having active carts silently evicted
4. **In production, isolate Redis on a separate host** with sufficient physical memory
5. **Swap is effective as an OOM safety net**, but should be limited to non-Redis processes (cart, MongoDB)

---

## Test 27: maxLenApprox 50000 + Redis Container Memory Limit 360min Test

**Date**: 2026-04-11
**Purpose**: Evaluate the effect of Dapr pub/sub `maxLenApprox` for Redis Stream trimming. Confirm stable 6-hour operation in an 8GB environment
**Changes**:
- Added `maxLenApprox: 50000` to 3 pub/sub components (`deleteAfterDeliver` was also added but is unsupported by Dapr Redis pub/sub and had no effect)
- Set `deploy.resources.limits.memory: 1200m` on the Redis container
- 4GB swap enabled on host
**Environment**: cart:6w, md:2, t:1 (8GB) / buffer=100
**Conditions**: 300 users / 360min / DB cleared (`down -v`)

### Performance Results

| Endpoint | Reqs | P50 | P95 | P99 | Max | req/s |
|----------|------|-----|-----|-----|------|-------|
| Create Cart | 75,187 | 95 | 160 | 220 | 830 | -- |
| Add Item | 1,500,838 | 17 | 63 | 110 | 770 | -- |
| Cancel Cart | 74,890 | 230 | 320 | 400 | 1,700 | -- |
| **Aggregated** | **1,650,915** | **18** | **160** | **270** | **1,700** | **~108** |

- **Errors**: 0
- **evicted_keys**: 0

### Memory Progression (5-minute interval sampling)

| Elapsed | cart (MB) | MongoDB (MB) | Redis (MB) | Phase |
|---------|----------|-------------|------------|-------|
| 0min | 451 | 250 | 21 | Start |
| 21min | 841 | 1,463 | 111 | Stabilizing |
| 84min | 782 | 1,428 | 411 | Redis Stream accumulating |
| 150min | 714 | 1,436 | 710 | XLEN approaching 50,000 |
| **170min** | **690** | **1,440** | **817** | **XLEN reaches 50,000 -> trimming starts** |
| 200min | 698 | 1,433 | 814 | **Memory stabilized** |
| 253min | 716 | 1,441 | 812 | Stable |
| 360min | -- | -- | 812 | Test completed |

### Effect of maxLenApprox

| Item | Test #26 (no setting) | Test #27 (maxLenApprox: 50000) |
|------|:--------------------:|:------------------------------:|
| Redis memory trend | Linear growth -> 1GB -> eviction | **Stabilized at ~813MB around 170min** |
| XLEN trend | Unbounded growth | **Fixed at 50,000** |
| evicted_keys | 56,746 | **0** |
| Errors | 228 (at 345min) | **0 (full 360min completed)** |

### Redis Memory Breakdown (at steady state)

| Component | Size | Notes |
|-----------|------|-------|
| topic-tranlog Stream (50,000 entries) | ~750MB | ~15KB per entry |
| Cart cache (~300 entries) | ~3MB | ~10KB per entry |
| Idempotency keys (~40,000 entries) | ~6MB | ~150B per entry, TTL 1h |
| Other (pub/sub topics, overhead) | ~34MB | |
| **Total** | **~793MB** | |

### Swap Usage

| Metric | Value |
|--------|-------|
| Redis used_memory | 793MB |
| Redis RSS (physical memory) | 665-712MB |
| **Redis data on swap** | **~80-130MB** |
| mem_fragmentation_ratio | 0.84-0.90 |
| Host swap total | 2,775MB / 4,095MB |

Some Redis data was swapped out to disk. Since no eviction occurred, there was no immediate impact, but this remains a structural risk.

### Findings

1. **`deleteAfterDeliver` does not exist in Dapr Redis pub/sub** -- [components-contrib#3100](https://github.com/dapr/components-contrib/issues/3100) explicitly states "Redis pub/sub is not recommended for production." There is no automatic deletion of consumed messages
2. **Redis Streams account for ~95% of Redis memory** -- Cart store (~3MB) vs Streams (~750MB). Migrating pub/sub would dramatically improve this
3. **`maxLenApprox` is an effective mitigation** -- It caps Stream entry count and stops memory growth. However, it is not a fundamental solution (which would be eliminating Streams entirely)
4. **Redis swap usage is a known constraint warned by the official documentation** -- Redis recommends `vm.swappiness=0` or disabling swap entirely. LRU accuracy degrades against swapped-out data
5. **MongoDB WiredTiger cache hit rate 99.65%** -- The 1.5GB cache size is appropriate

### Conclusions and Recommendations

1. **`maxLenApprox: 50000` achieved 6 hours with 0 errors on 8GB/300users** -- Interim production operation is feasible
2. **However, Redis pub/sub is not recommended for production** (per Dapr official) -- Migration to RabbitMQ is recommended (#99)
3. **Redis Streams consume 95% of all Redis memory** -- Migrating pub/sub is expected to reduce Redis memory from ~800MB to ~10MB
4. **Idempotency gaps should be addressed** -- Report/Journal infinite retry (#97), Stock double-deduction (#98)
5. **End-state goal**: pub/sub -> RabbitMQ, state store -> MongoDB, eliminate Redis

**Note: The final applied value is `maxLenApprox: 1000`.** Test #27 was conducted with 50,000, but the value was reduced to 1,000 (~5 minutes of buffer) to minimize duplicate risk with Cart's background republish job (5-minute interval), aligned with `processingTimeout: 180s`. Expected Redis memory reduction: ~750MB -> ~15MB.

---

## Test 28: pub/sub RabbitMQ Migration (cart:6w)

**Date**: 2026-04-11
**Purpose**: Migrate Dapr pub/sub from Redis Streams to RabbitMQ and evaluate performance impact
**Changes**: 3 pubsub YAMLs changed to `pubsub.rabbitmq`, RabbitMQ container added, Resiliency policy added
**Configuration**: cart:6w, md:2, t:1 (8GB) / RabbitMQ / Redis state store
**Conditions**: 300 users / 3min × 3 runs

### Results (3-run average)

| Metric | Run 1 | Run 2 | Run 3 | Average |
|--------|:-----:|:-----:|:-----:|:-------:|
| Avg | 41ms | 38ms | 41ms | 40ms |
| P50 | 22ms | 23ms | 24ms | 23ms |
| P95 | 140ms | 110ms | 130ms | 127ms |
| P99 | 270ms | 260ms | 270ms | 267ms |
| Max | 682ms | 518ms | 687ms | 629ms |
| req/s | 98.8 | 99.0 | 98.8 | 98.9 |

- Errors: 0 (all runs), Swap: 0

### Comparison with Test #25 (Redis pub/sub, same configuration)

| Metric | Redis pub/sub | RabbitMQ | Diff |
|--------|:------------:|:--------:|:----:|
| Avg | 33ms | 40ms | +21% |
| P50 | 16ms | 23ms | +44% |
| P95 | 130ms | 127ms | **-2% (improved)** |
| Max | 1,219ms | 629ms | **-48% (improved)** |
| req/s | 107.6 | 98.9 | -8% |
| Redis memory | ~800MB | ~5MB | **-99.8%** |

### Analysis

1. **Avg +7ms** — RabbitMQ AMQP protocol overhead (affects Cancel Cart only)
2. **P95/Max improved** — No Redis Stream trim/fragmentation, stabilized tail latency
3. **Redis memory 99.8% reduced** — Streams eliminated, only ~5MB remaining

---

## Test 29: RabbitMQ + cart:4w User Count Verification

**Date**: 2026-04-11
**Purpose**: Evaluate performance at different user counts with cart:4w on RabbitMQ. Identify optimal user count for 8GB environment
**Configuration**: cart:4w, md:2, t:1 (8GB) / RabbitMQ / Redis state store / WiredTiger 1.5GB
**Conditions**: Each user count 5min × 2 runs

### User Count Comparison Summary (Add Item)

| Metric | 150 users | 200 users | 300 users |
|--------|:---------:|:---------:|:---------:|
| Avg | 24ms | 24ms | 79ms |
| P50 | 16ms | 17ms | 37ms |
| P95 | 62ms | 60ms | 280ms |
| P99 | 86ms | 83ms | 695ms |
| Max | 150ms | 155ms | 2,450ms |
| req/s (total) | 52.5 | 69.5 | 100.5 |
| Swap | ~130MB | 641MB | ~1GB |
| Rating | Excess capacity | **Optimal** | Swap-degraded |

### 150 users (average of 2 runs)

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max |
|----------|---------|-----|-----|-----|------|
| Create Cart | 86 | 73 | 140 | 170 | 190 |
| Add Item | 24 | 16 | 62 | 86 | 150 |
| Cancel Cart | 235 | 230 | 295 | 345 | 375 |
| **Aggregated** | **35** | **17** | **110** | **250** | **375** |

### 200 users (average of 2 runs)

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max |
|----------|---------|-----|-----|-----|------|
| Create Cart | 90 | 80 | 150 | 195 | 205 |
| Add Item | 24 | 17 | 60 | 83 | 155 |
| Cancel Cart | 241 | 235 | 305 | 350 | 410 |
| **Aggregated** | **36** | **18** | **115** | **260** | **410** |

### 300 users (average of 2 runs)

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max |
|----------|---------|-----|-----|-----|------|
| Create Cart | 204 | 120 | 660 | 1,550 | 3,350 |
| Add Item | 79 | 37 | 280 | 695 | 2,450 |
| Cancel Cart | 456 | 310 | 1,200 | 2,150 | 4,250 |
| **Aggregated** | **101** | **40** | **315** | **1,055** | **3,850** |

### Conclusion

1. **200 users is optimal for 8GB/cart:4w** — Avg 36ms, Max 410ms, stable. Swap 641MB is acceptable
2. **300 users causes 2.5x Avg degradation** — Swap I/O becomes the bottleneck. cart:6w can handle 300 users but lacks memory headroom
3. **150 users has excess capacity** — Near-zero swap but throughput (52.5 req/s) underutilizes the hardware

---

## Test 30: RabbitMQ + cart:4w 180min Stability Test

**Date**: 2026-04-11
**Purpose**: Verify 3-hour stable operation with RabbitMQ pub/sub + cart:4w at 200 users
**Configuration**: cart:4w, md:2, t:1 (8GB) / RabbitMQ / Redis state store / WiredTiger 1.5GB
**Conditions**: 200 users / 180min / DB clean (`down -v`) / Swap 4GB (starting from 0)

### Performance Results

| Endpoint | Avg (ms) | P50 | P95 | P99 | Max | req/s |
|----------|---------|-----|-----|-----|------|-------|
| Create Cart | 89 | 83 | 140 | 170 | 321 | 3.28 |
| Add Item | 19 | 14 | 51 | 66 | 278 | 65.29 |
| Cancel Cart | 229 | 220 | 280 | 320 | 1,228 | 3.26 |
| **Aggregated** | **32** | **15** | **120** | **250** | **1,228** | **71.8** |

- **Total requests**: 775,665
- **Errors**: 0
- **Swap**: 0 → 1,231MB (final)

### Comparison with Test #25 (Redis pub/sub, cart:6w, 300users, 180min)

| Metric | Test #25 (Redis, 300u, 6w) | Test #30 (RabbitMQ, 200u, 4w) | Diff |
|--------|:-------------------------:|:----------------------------:|:----:|
| Avg | 33ms | 32ms | **-3%** |
| P50 | 16ms | 15ms | **-6%** |
| P95 | 140ms | 120ms | **-14% (improved)** |
| P99 | 250ms | 250ms | ±0% |
| Max | 1,219ms | 1,228ms | ±0% |
| req/s | 107.6 | 71.8 | -33% (user count ratio) |
| Redis memory | ~868MB | ~15MB | **-98%** |

### Conclusion

1. **8GB/cart:4w/RabbitMQ/200 users achieves 3-hour stable operation**
2. **Latency equivalent or better than Redis pub/sub** (P95: 120ms vs 140ms)
3. **Redis memory problem fully resolved** by RabbitMQ migration
4. Fewer workers (6→4) with right-sized users (300→200) efficiently utilizes 8GB resources

---

## Test Procedure Notes

### Standard Test Procedure (for consistent conditions)

1. Stop all services: `docker compose -f docker-compose.prod.yaml down`
2. Start all services: `docker compose -f docker-compose.prod.yaml up -d`
3. Verify health check (all 7 services healthy)
4. Setup test data: `bash run_perf_test.sh setup 310`
5. Redis FLUSHALL: `docker exec redis redis-cli FLUSHALL`
6. Run test: `bash run_perf_test.sh custom 300 3m`

### Recommended Settings for Performance Tests

```bash
# Disable request log DB writes (eliminates ordering effect)
REQUEST_LOG_TO_DB=false docker compose -f docker-compose.prod.yaml up -d
```

### Notes

- If MongoDB volumes were deleted, replica set initialization is required
  ```bash
  docker exec mongodb mongosh --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]})"
  ```
- Dapr sidecars may need restart depending on timing
- 500 users is near resource limit on this local environment (6 CPU, 16GB RAM). 300 users is recommended for stable results
