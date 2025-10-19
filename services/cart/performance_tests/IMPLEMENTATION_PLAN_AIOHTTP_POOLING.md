# Implementation Plan: aiohttp Session Pooling for CartRepository

**Issue:** [#12](https://github.com/kugel-masa/kugelpos-backend/issues/12) - Phase 1: Critical Priority
**Target:** Reduce Add Item 99%ile latency from 4200ms to 1500-1800ms (30-45% improvement)
**Estimated Effort:** 2 days (0.5 day implementation + 0.5 day testing + 1 day performance validation)

---

## 1. Problem Analysis Summary

### Current Implementation Issues

**File:** `services/cart/app/models/repositories/cart_repository.py`

Three methods create new `aiohttp.ClientSession` for EVERY request:

1. **`__cache_cart_async` (line 245)** - POST to Dapr state store
2. **`__get_cached_cart_async` (line 269)** - GET from Dapr state store
3. **`__delete_cached_cart_async` (line 290)** - DELETE from Dapr state store

**Impact per Add Item request:**
- 2 session creations (get cart + cache cart)
- 50-100ms overhead per session
- **Total overhead: 100-200ms per Add Item**

**Performance Test Results (15 users, 10 minutes):**
- Add Item requests: 1,884
- Unnecessary session creations: **3,768**
- Cumulative overhead: **188-376 seconds**
- 99%ile latency: **4200ms**

---

## 2. Architecture Design

### Option A: Module-Level Session Manager (RECOMMENDED)

**Pros:**
- Simple implementation
- Works with existing DI pattern (CartRepository created per request)
- Centralized lifecycle management
- Follows existing pattern (see `kugel_common.utils.http_client_helper`)

**Cons:**
- Module-level state (acceptable for connection pooling)

### Option B: Application-Level Singleton Repository

**Pros:**
- More "proper" OOP design

**Cons:**
- Requires significant refactoring of DI system
- Higher risk of breaking existing functionality
- More complex implementation

**Decision:** Use **Option A** - Module-Level Session Manager

---

## 3. Detailed Implementation Plan

### Step 1: Create Dapr State Store Session Helper

**New File:** `services/cart/app/utils/dapr_statestore_session_helper.py`

```python
"""
Session helper for Dapr state store HTTP operations with connection pooling.
"""
from typing import Optional
import aiohttp
from logging import getLogger
from app.config.settings import settings

logger = getLogger(__name__)

# Module-level session instance
_session: Optional[aiohttp.ClientSession] = None


async def get_dapr_statestore_session() -> aiohttp.ClientSession:
    """
    Get or create a shared aiohttp session for Dapr state store operations.

    Returns:
        aiohttp.ClientSession: Shared session with connection pooling
    """
    global _session

    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(
            total=10.0,      # Total timeout: 10 seconds
            connect=3.0,     # Connection timeout: 3 seconds
            sock_read=5.0    # Socket read timeout: 5 seconds
        )

        connector = aiohttp.TCPConnector(
            limit=100,           # Max total concurrent connections
            limit_per_host=50,   # Max connections per host
            ttl_dns_cache=300    # DNS cache TTL: 5 minutes
        )

        _session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        )

        logger.info(
            "Created new aiohttp session for Dapr state store "
            f"(limit=100, limit_per_host=50, timeout=10s)"
        )

    return _session


async def close_dapr_statestore_session() -> None:
    """
    Close the shared aiohttp session.
    Should be called during application shutdown.
    """
    global _session

    if _session and not _session.closed:
        await _session.close()
        logger.info("Closed aiohttp session for Dapr state store")
        _session = None
```

**Key Configuration Decisions:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `limit` | 100 | Support up to 100 concurrent cart operations |
| `limit_per_host` | 50 | Dapr sidecar can handle 50 concurrent connections |
| `total timeout` | 10s | Dapr state store operations should complete within 10s |
| `connect timeout` | 3s | Connection to localhost:3500 should be immediate |
| `sock_read timeout` | 5s | Read operations (cache get) should complete within 5s |
| `ttl_dns_cache` | 300s | Localhost doesn't need frequent DNS refresh |

---

### Step 2: Update CartRepository Methods

**File:** `services/cart/app/models/repositories/cart_repository.py`

#### 2.1 Add Import

```python
# Add to imports section (around line 4-20)
from app.utils.dapr_statestore_session_helper import get_dapr_statestore_session
```

#### 2.2 Update `__cache_cart_async` (line 234-256)

**Before:**
```python
async def __cache_cart_async(self, cart: CartDocument, isNew: bool = False) -> None:
    cart_data = cart.model_dump()
    state_post_data = [{"key": cart.cart_id, "value": cart_data}]
    logger.debug(f"State post data: {state_post_data}")
    async with aiohttp.ClientSession() as session:  # 🔴 REMOVE
        async with session.post(self.base_url_cartstore, json=state_post_data) as response:
            # ... existing logic
```

**After:**
```python
async def __cache_cart_async(self, cart: CartDocument, isNew: bool = False) -> None:
    """
    Cache the cart to Dapr state store.
    Uses shared aiohttp session with connection pooling for performance.

    args:
        cart: CartDocument to cache
        isNew: Whether this is a new cart (for logging purposes)
    return:
        None
    exceptions:
        UpdateNotWorkException if caching fails
    """
    cart_data = cart.model_dump()
    state_post_data = [{"key": cart.cart_id, "value": cart_data}]
    logger.debug(f"State post data: {state_post_data}")

    # 🟢 Use shared session with connection pooling
    session = await get_dapr_statestore_session()
    async with session.post(self.base_url_cartstore, json=state_post_data) as response:
        logger.debug(f"Response status: {response.status}")
        logger.debug(f"Response text: {await response.text()}")
        if response.status != 204:
            if response.status == 400:
                error_message = await response.json()
                if error_message.get("errorCode") == "ERR_STATE_STORE_NOT_FOUND":
                    logger.error(f"State store not found: {error_message.get('message')}")
            message = "Failed to cache cart"
            raise UpdateNotWorkException(message, self.collection_name, cart.cart_id, logger)
        logger.debug(f"Cart cached: {cart}")
```

#### 2.3 Update `__get_cached_cart_async` (line 258-278)

**Before:**
```python
async def __get_cached_cart_async(self, cart_id: str) -> CartDocument:
    async with aiohttp.ClientSession() as session:  # 🔴 REMOVE
        async with session.get(f"{self.base_url_cartstore}/{cart_id}") as response:
            # ... existing logic
```

**After:**
```python
async def __get_cached_cart_async(self, cart_id: str) -> CartDocument:
    """
    Get the cart from Dapr state store cache.
    Uses shared aiohttp session with connection pooling for performance.

    args:
        cart_id: str - Cart ID to retrieve
    return:
        CartDocument if found
    exceptions:
        NotFoundException if cart not found in cache
    """
    # 🟢 Use shared session with connection pooling
    session = await get_dapr_statestore_session()
    async with session.get(f"{self.base_url_cartstore}/{cart_id}") as response:
        if response.status != 200:
            message = "cart not found"
            raise NotFoundException(message, self.collection_name, cart_id, logger)
        cart_data = await response.json()
        logger.debug(f"Cart data: {cart_data}")
        cart_doc = CartDocument(**cart_data)
        cart_doc.staff = CartDocument.Staff(
            id=self.terminal_info.staff.id,
            name=self.terminal_info.staff.name
        )
        return cart_doc
```

#### 2.4 Update `__delete_cached_cart_async` (line 280-295)

**Before:**
```python
async def __delete_cached_cart_async(self, cart_id: str) -> None:
    async with aiohttp.ClientSession() as session:  # 🔴 REMOVE
        async with session.delete(f"{self.base_url_cartstore}/{cart_id}") as response:
            # ... existing logic
```

**After:**
```python
async def __delete_cached_cart_async(self, cart_id: str) -> None:
    """
    Delete the cart from Dapr state store cache.
    Uses shared aiohttp session with connection pooling for performance.

    args:
        cart_id: str - Cart ID to delete
    return:
        None
    exceptions:
        CannotDeleteException if deletion fails
    """
    # 🟢 Use shared session with connection pooling
    session = await get_dapr_statestore_session()
    async with session.delete(f"{self.base_url_cartstore}/{cart_id}") as response:
        if response.status != 204:
            message = f"cart not found. cart_id->{cart_id}"
            raise CannotDeleteException(message, self.collection_name, cart_id, logger)
        return None
```

---

### Step 3: Integrate with Application Shutdown

**File:** `services/cart/app/main.py`

**Update `close_event()` function (line 163-185):**

```python
async def close_event():
    """
    Application shutdown event handler that properly closes connections.

    This function runs when the FastAPI app is shutting down and ensures
    that all connections are closed properly to prevent resource leaks.
    """
    logger.info("closing the application")

    logger.info("Closing the database connection")
    await db_helper.close_client_async()

    logger.info("Stopping the scheduler for republishing undelivered tranlog messages")
    await shutdown_republish_undelivered_tranlog_job()

    # Close all HTTP client pools to prevent resource leaks
    logger.info("Closing all HTTP client pools")
    from kugel_common.utils.http_client_helper import close_all_clients
    await close_all_clients()

    # 🟢 ADD: Close Dapr state store session
    logger.info("Closing Dapr state store session")
    from app.utils.dapr_statestore_session_helper import close_dapr_statestore_session
    await close_dapr_statestore_session()

    # add shutdown tasks here
    logger.info("Application closed")
```

---

## 4. Testing Strategy

### 4.1 Unit Tests

**New File:** `services/cart/tests/utils/test_dapr_statestore_session_helper.py`

```python
import pytest
import aiohttp
from app.utils.dapr_statestore_session_helper import (
    get_dapr_statestore_session,
    close_dapr_statestore_session,
)


@pytest.mark.asyncio
async def test_get_session_creates_new_session():
    """Test that get_session creates a session on first call"""
    session = await get_dapr_statestore_session()

    assert session is not None
    assert isinstance(session, aiohttp.ClientSession)
    assert not session.closed

    await close_dapr_statestore_session()


@pytest.mark.asyncio
async def test_get_session_reuses_existing_session():
    """Test that get_session reuses the same session instance"""
    session1 = await get_dapr_statestore_session()
    session2 = await get_dapr_statestore_session()

    assert session1 is session2

    await close_dapr_statestore_session()


@pytest.mark.asyncio
async def test_close_session():
    """Test that close_session properly closes the session"""
    session = await get_dapr_statestore_session()
    assert not session.closed

    await close_dapr_statestore_session()
    assert session.closed


@pytest.mark.asyncio
async def test_get_session_after_close_creates_new_session():
    """Test that get_session creates a new session after close"""
    session1 = await get_dapr_statestore_session()
    await close_dapr_statestore_session()

    session2 = await get_dapr_statestore_session()
    assert session1 is not session2
    assert not session2.closed

    await close_dapr_statestore_session()


@pytest.mark.asyncio
async def test_session_timeout_configuration():
    """Test that session has correct timeout configuration"""
    session = await get_dapr_statestore_session()

    assert session.timeout.total == 10.0
    assert session.timeout.connect == 3.0
    assert session.timeout.sock_read == 5.0

    await close_dapr_statestore_session()


@pytest.mark.asyncio
async def test_session_connector_configuration():
    """Test that session has correct connector configuration"""
    session = await get_dapr_statestore_session()

    assert session.connector.limit == 100
    assert session.connector.limit_per_host == 50

    await close_dapr_statestore_session()
```

### 4.2 Integration Tests

**Update:** `services/cart/tests/test_cart.py`

Add test to verify session reuse:

```python
@pytest.mark.asyncio
async def test_add_item_uses_shared_session():
    """Test that multiple add_item calls use the same aiohttp session"""
    from app.utils.dapr_statestore_session_helper import get_dapr_statestore_session

    # Get session before operations
    session_before = await get_dapr_statestore_session()
    session_id_before = id(session_before)

    # Perform multiple add_item operations
    # ... existing test code ...

    # Get session after operations
    session_after = await get_dapr_statestore_session()
    session_id_after = id(session_after)

    # Verify same session was used
    assert session_id_before == session_id_after
    assert not session_after.closed
```

### 4.3 Performance Tests

**File:** `services/cart/performance_tests/locustfile.py` (no changes needed)

**Test Execution:**

```bash
cd services/cart/performance_tests

# Run performance test for 1 user (baseline)
./run_perf_test.sh 1users 10m

# Run performance test for 15 users (stress test)
./run_perf_test.sh 15users 10m

# Generate comparison report
python generate_comparison_report.py
```

**Expected Results:**

| Metric | Before | After Phase 1 | Improvement |
|--------|--------|---------------|-------------|
| **99%ile (15 users)** | 4200ms | 1500-1800ms | **30-45% reduction** |
| **Median (15 users)** | 67ms | 60-65ms | **3-10% reduction** |
| **Throughput (15 users)** | 3.45 req/s | 4.5-5.0 req/s | **30% improvement** |

---

## 5. Implementation Checklist

### Phase 1: Core Implementation (Day 1, Morning)

- [ ] Create `app/utils/dapr_statestore_session_helper.py`
  - [ ] Implement `get_dapr_statestore_session()`
  - [ ] Implement `close_dapr_statestore_session()`
  - [ ] Add proper logging
  - [ ] Add type hints

- [ ] Update `app/models/repositories/cart_repository.py`
  - [ ] Add import for session helper
  - [ ] Update `__cache_cart_async()` to use shared session
  - [ ] Update `__get_cached_cart_async()` to use shared session
  - [ ] Update `__delete_cached_cart_async()` to use shared session
  - [ ] Update docstrings

- [ ] Update `app/main.py`
  - [ ] Add session close to `close_event()`
  - [ ] Add logging for session lifecycle

### Phase 2: Testing (Day 1, Afternoon)

- [ ] Create unit tests
  - [ ] `test_get_session_creates_new_session`
  - [ ] `test_get_session_reuses_existing_session`
  - [ ] `test_close_session`
  - [ ] `test_get_session_after_close_creates_new_session`
  - [ ] `test_session_timeout_configuration`
  - [ ] `test_session_connector_configuration`

- [ ] Run unit tests
  ```bash
  cd services/cart
  pipenv run pytest tests/utils/test_dapr_statestore_session_helper.py -v
  ```

- [ ] Run integration tests
  ```bash
  pipenv run pytest tests/test_cart.py -v
  ```

- [ ] Verify no regressions
  ```bash
  pipenv run pytest tests/ -v
  ```

### Phase 3: Performance Validation (Day 2)

- [ ] Run baseline performance test (current implementation)
  ```bash
  cd performance_tests
  git stash  # Save changes temporarily
  ./run_perf_test.sh 15users 10m
  cp -r results results_baseline
  git stash pop
  ```

- [ ] Run performance test with implementation
  ```bash
  ./run_perf_test.sh 1users 10m
  ./run_perf_test.sh 3users 10m
  ./run_perf_test.sh 5users 10m
  ./run_perf_test.sh 10users 10m
  ./run_perf_test.sh 15users 10m
  ```

- [ ] Generate comparison report
  ```bash
  python generate_comparison_report.py
  ```

- [ ] Verify improvement targets
  - [ ] 99%ile latency reduced by 30-45%
  - [ ] Median latency stable or improved
  - [ ] Throughput increased by ~30%
  - [ ] No errors or failures

- [ ] Document results
  - [ ] Update GitHub issue #12 with results
  - [ ] Create performance comparison report
  - [ ] Add graphs showing before/after

---

## 6. Rollback Plan

If issues are encountered:

1. **Immediate rollback:**
   ```bash
   git checkout -- services/cart/app/models/repositories/cart_repository.py
   git checkout -- services/cart/app/main.py
   rm services/cart/app/utils/dapr_statestore_session_helper.py
   ```

2. **Restore previous performance:**
   - Restart cart service
   - Verify health check endpoint
   - Run smoke tests

3. **Investigate issues:**
   - Check application logs
   - Check Dapr sidecar logs
   - Review error messages

---

## 7. Success Criteria

### Must Have (P0)
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] No regression in existing functionality
- [ ] 99%ile latency reduced by at least 25%
- [ ] No new errors or exceptions in logs

### Should Have (P1)
- [ ] 99%ile latency reduced by 30-45%
- [ ] Throughput increased by 25-35%
- [ ] Connection count reduced by 95%+

### Nice to Have (P2)
- [ ] Documentation updated in CLAUDE.md
- [ ] Performance graphs generated
- [ ] Blog post / tech note written

---

## 8. Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|------------|
| Session leaks memory | High | Low | Proper close() in shutdown + monitoring |
| Connection pool exhausted | Medium | Low | Conservative limits (50/host) + testing |
| Timeout too aggressive | Low | Low | Conservative 10s total timeout |
| Breaking existing tests | Medium | Low | Comprehensive test suite before merge |
| Performance regression | High | Very Low | Extensive performance testing |

---

## 9. Next Steps After Phase 1

After successful Phase 1 completion:

1. **Monitor Production (1 week)**
   - Track 99%ile latency metrics
   - Monitor connection pool utilization
   - Watch for any memory leaks

2. **Proceed to Phase 2 (gRPC Channel Pooling)**
   - Similar implementation for `item_master_grpc_repository.py`
   - Expected additional 30-40% latency reduction
   - Target: 99%ile 1500ms → 600-900ms

3. **Consider Phase 3 (DaprClientHelper gRPC)**
   - System-wide change affecting all 5 services
   - Additional 10-15% improvement
   - Larger scope, higher risk

---

## 10. References

- **GitHub Issue:** [#12 - Performance: Implement connection pooling](https://github.com/kugel-masa/kugelpos-backend/issues/12)
- **Performance Report:** `services/cart/performance_tests/results_backup/20251019_033512/comparison_report_ja.md`
- **aiohttp Documentation:** https://docs.aiohttp.org/en/stable/client_advanced.html#connectors
- **Existing Pattern:** `commons/src/kugel_common/utils/http_client_helper.py`

---

**Created:** 2025-10-19
**Author:** Claude Code
**Status:** Ready for Implementation
