# Phase 2 Implementation Plan: gRPC Channel Pooling

**GitHub Issue:** [#12 - Performance: Implement connection pooling](https://github.com/kugel-masa/kugelpos-backend/issues/12)
**Priority:** High
**Estimated Effort:** 0.5-1 day
**Created:** 2025-10-19

---

## Executive Summary

This document outlines the implementation plan for Phase 2 performance optimization: **gRPC Channel Pooling** for the ItemMasterGrpcRepository. This addresses the second critical bottleneck identified in the root cause analysis.

### Problem Statement

Currently, each item lookup via gRPC creates a new channel and stub:

```python
# Current implementation (lines 104-105)
channel = await self.grpc_helper.get_channel()
stub = item_service_pb2_grpc.ItemServiceStub(channel)
```

**Impact:**
- Each Add Item request creates **1 new gRPC channel** (100-300ms overhead)
- 15 users × 1884 requests = **~3768 channel creations**
- Cumulative overhead: **94-282 seconds** per 10-minute test

### Expected Improvement

| Metric | After Phase 1 | After Phase 2 | Additional Improvement |
|--------|---------------|---------------|------------------------|
| **99%ile Latency** | 1500-1800ms | **600-900ms** | **45-55% reduction** |
| **Throughput** | 4.5-5.0 req/s | **6.5-8.0 req/s** | **33% improvement** |
| **Channel Creation** | ~3768/test | **1-3/test** | **99.9% reduction** |

---

## Current Implementation Analysis

### File: `app/models/repositories/item_master_grpc_repository.py`

**Lines 104-117: Channel created per request**

```python
async def get_item_by_code_async(self, item_code: str) -> ItemMasterDocument:
    """Get an item by its code from cache or via gRPC."""

    # ... cache check logic ...

    # 🔴 PROBLEM: New channel created for EVERY item lookup
    channel = await self.grpc_helper.get_channel()
    stub = item_service_pb2_grpc.ItemServiceStub(channel)

    request = item_service_pb2.ItemDetailRequest(
        tenant_id=self.tenant_id,
        store_code=self.store_code,
        item_code=item_code,
        terminal_id=self.terminal_info.terminal_id
    )

    response = await stub.GetItemDetail(
        request,
        timeout=cart_settings.GRPC_TIMEOUT  # Currently 30s
    )
    # ... rest of implementation
```

**Performance Issues:**
1. **Channel creation overhead:** 100-300ms per request
2. **No connection reuse:** Each request pays full connection establishment cost
3. **Resource waste:** Channels not properly closed (potential memory leak)
4. **No timeout on channel creation:** Could hang indefinitely

---

## Proposed Solution

### Architecture: Instance-Level gRPC Channel Pooling

Similar to Phase 1's session pooling approach, but at the instance level rather than module level (since each repository instance has different tenant/store context).

**Key Design Decisions:**

1. **Instance-level pooling:** Each `ItemMasterGrpcRepository` instance maintains its own channel/stub
2. **Lazy initialization:** Channel created on first use
3. **Automatic reconnection:** Handle channel failures gracefully
4. **Proper cleanup:** Close channel on repository destruction

---

## Implementation Steps

### Step 1: Update `__init__()` Method

Add channel and stub instance variables:

```python
def __init__(
    self,
    tenant_id: str,
    store_code: str,
    terminal_info: TerminalInfoDocument,
    item_master_documents: list[ItemMasterDocument] = None,
):
    """Initialize the repository with tenant, store and terminal information."""
    self.tenant_id = tenant_id
    self.store_code = store_code
    self.terminal_info = terminal_info
    self.item_master_documents = item_master_documents
    self.grpc_helper = GrpcClientHelper(
        target=cart_settings.MASTER_DATA_GRPC_URL,
        options=[
            ('grpc.max_send_message_length', 10 * 1024 * 1024),
            ('grpc.max_receive_message_length', 10 * 1024 * 1024),
        ]
    )

    # 🟢 NEW: Instance-level channel and stub for connection pooling
    self._channel: Optional[grpc.aio.Channel] = None
    self._stub: Optional[item_service_pb2_grpc.ItemServiceStub] = None
```

**Changes:**
- Add `_channel` instance variable (Optional[grpc.aio.Channel])
- Add `_stub` instance variable (Optional[ItemServiceStub])
- Initialize both to None (lazy initialization)

---

### Step 2: Create `_get_stub()` Helper Method

Add a new method to get or create the shared stub:

```python
async def _get_stub(self) -> item_service_pb2_grpc.ItemServiceStub:
    """
    Get or create a shared gRPC stub with channel pooling.

    Creates a persistent channel on first use and reuses it for all subsequent requests.
    This eliminates the 100-300ms channel creation overhead per request.

    Returns:
        ItemServiceStub: A gRPC stub for ItemService

    Raises:
        RepositoryException: If channel creation fails
    """
    if self._channel is None or self._stub is None:
        try:
            # Create channel via helper (this uses connection pooling internally)
            self._channel = await self.grpc_helper.get_channel()

            # Create stub (reused for all requests)
            self._stub = item_service_pb2_grpc.ItemServiceStub(self._channel)

            logger.info(
                f"Created new gRPC channel for master-data service "
                f"(tenant={self.tenant_id}, store={self.store_code})"
            )
        except Exception as e:
            message = "Failed to create gRPC channel for master-data service"
            raise RepositoryException(
                message=message,
                collection_name="item grpc",
                logger=logger,
                original_exception=e,
            )

    return self._stub
```

**Features:**
- Lazy initialization on first use
- Logs channel creation for monitoring
- Proper error handling
- Thread-safe (Python async is single-threaded)

---

### Step 3: Update `get_item_by_code_async()` Method

Replace inline channel creation with shared stub:

**BEFORE:**
```python
async def get_item_by_code_async(self, item_code: str) -> ItemMasterDocument:
    # ... cache check ...

    try:
        # 🔴 Creates new channel every time
        channel = await self.grpc_helper.get_channel()
        stub = item_service_pb2_grpc.ItemServiceStub(channel)

        request = item_service_pb2.ItemDetailRequest(...)
        response = await stub.GetItemDetail(request, timeout=cart_settings.GRPC_TIMEOUT)
        # ... rest of logic
```

**AFTER:**
```python
async def get_item_by_code_async(self, item_code: str) -> ItemMasterDocument:
    # ... cache check ...

    try:
        # 🟢 Reuses shared stub (eliminates 100-300ms overhead)
        stub = await self._get_stub()

        request = item_service_pb2.ItemDetailRequest(
            tenant_id=self.tenant_id,
            store_code=self.store_code,
            item_code=item_code,
            terminal_id=self.terminal_info.terminal_id
        )

        response = await stub.GetItemDetail(
            request,
            timeout=cart_settings.GRPC_TIMEOUT
        )
        # ... rest of logic unchanged
```

**Changes:**
- Replace `channel = await self.grpc_helper.get_channel()` with `stub = await self._get_stub()`
- Remove `stub = item_service_pb2_grpc.ItemServiceStub(channel)`
- No other changes to business logic

---

### Step 4: Add `close()` Method

Add cleanup method for proper resource management:

```python
async def close(self) -> None:
    """
    Close the gRPC channel and release resources.

    Should be called when the repository is no longer needed,
    typically during application shutdown.
    """
    if self._channel is not None:
        try:
            await self._channel.close()
            logger.info(
                f"Closed gRPC channel for master-data service "
                f"(tenant={self.tenant_id}, store={self.store_code})"
            )
        except Exception as e:
            logger.warning(
                f"Error closing gRPC channel: {e}",
                exc_info=True
            )
        finally:
            self._channel = None
            self._stub = None
```

**Features:**
- Gracefully closes channel
- Logs closure for monitoring
- Handles errors during closure
- Resets state (allows recreation if needed)

---

### Step 5: Update Application Shutdown Handler

Ensure channels are closed when the application shuts down.

**File:** `app/main.py`

**Current shutdown handler (after Phase 1):**

```python
async def close_event():
    """Shutdown event handler"""
    logger.info("Shutting down application...")

    # Close Dapr state store session
    logger.info("Closing Dapr state store session")
    from app.utils.dapr_statestore_session_helper import close_dapr_statestore_session
    await close_dapr_statestore_session()

    # Close MongoDB connections
    logger.info("Closing MongoDB connections")
    from app.models.database import close_database
    await close_database()

    logger.info("Application shutdown complete")
```

**Updated shutdown handler (after Phase 2):**

```python
async def close_event():
    """Shutdown event handler"""
    logger.info("Shutting down application...")

    # Close Dapr state store session
    logger.info("Closing Dapr state store session")
    from app.utils.dapr_statestore_session_helper import close_dapr_statestore_session
    await close_dapr_statestore_session()

    # 🟢 NEW: Close gRPC channels
    # Note: ItemMasterGrpcRepository instances are created per request,
    # so we don't maintain a global reference. The channels will be
    # automatically closed when the repository instances are garbage collected.
    # However, we should ensure proper cleanup in the CartRepository.
    logger.info("gRPC channels will be closed during garbage collection")

    # Close MongoDB connections
    logger.info("Closing MongoDB connections")
    from app.models.database import close_database
    await close_database()

    logger.info("Application shutdown complete")
```

**Note:** Since `ItemMasterGrpcRepository` instances are created per request (via `CartRepository`), we don't have a single global instance to close. The channels will be automatically closed during garbage collection. If we want explicit cleanup, we would need to track instances or add a `close()` method to `CartRepository`.

**Alternative approach (more explicit):**

If we want to ensure channels are always closed, we can:

1. Add `__aenter__` and `__aexit__` to make the repository an async context manager
2. Use it with `async with` in the cart operations

```python
class ItemMasterGrpcRepository:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
```

Then use it as:

```python
async with ItemMasterGrpcRepository(...) as repo:
    item = await repo.get_item_by_code_async(item_code)
```

**Decision:** For this phase, we'll rely on garbage collection but add a TODO comment for future enhancement.

---

## Testing Strategy

### Unit Tests

**File:** `tests/repositories/test_item_master_grpc_repository.py` (new)

Create comprehensive tests:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.repositories.item_master_grpc_repository import ItemMasterGrpcRepository
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument


@pytest.fixture
def terminal_info():
    """Create a test terminal info document"""
    return TerminalInfoDocument(
        terminal_id="TEST001",
        store_code="STORE01",
        terminal_name="Test Terminal"
    )


@pytest.fixture
def repository(terminal_info):
    """Create a test repository instance"""
    return ItemMasterGrpcRepository(
        tenant_id="test_tenant",
        store_code="STORE01",
        terminal_info=terminal_info
    )


@pytest.mark.asyncio
async def test_get_stub_creates_channel_on_first_call(repository):
    """Test that _get_stub creates channel on first call"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel = MagicMock()
        mock_get_channel.return_value = mock_channel

        # First call should create channel
        stub = await repository._get_stub()

        assert repository._channel == mock_channel
        assert repository._stub is not None
        mock_get_channel.assert_called_once()


@pytest.mark.asyncio
async def test_get_stub_reuses_existing_channel(repository):
    """Test that _get_stub reuses existing channel (CORE FUNCTIONALITY)"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel = MagicMock()
        mock_get_channel.return_value = mock_channel

        # First call
        stub1 = await repository._get_stub()

        # Second call should reuse channel
        stub2 = await repository._get_stub()

        assert stub1 is stub2  # Same stub instance
        assert repository._channel == mock_channel
        mock_get_channel.assert_called_once()  # Only called once


@pytest.mark.asyncio
async def test_close_closes_channel(repository):
    """Test that close() properly closes the channel"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock()
        mock_get_channel.return_value = mock_channel

        # Create channel
        await repository._get_stub()

        # Close
        await repository.close()

        mock_channel.close.assert_called_once()
        assert repository._channel is None
        assert repository._stub is None


@pytest.mark.asyncio
async def test_get_stub_after_close_creates_new_channel(repository):
    """Test that _get_stub creates new channel after close"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel1 = MagicMock()
        mock_channel2 = MagicMock()
        mock_get_channel.side_effect = [mock_channel1, mock_channel2]

        # Create and close
        await repository._get_stub()
        await repository.close()

        # Create again
        await repository._get_stub()

        assert repository._channel == mock_channel2
        assert mock_get_channel.call_count == 2


@pytest.mark.asyncio
async def test_get_item_by_code_uses_shared_stub(repository):
    """Test that get_item_by_code_async uses shared stub"""
    with patch.object(repository, '_get_stub', new_callable=AsyncMock) as mock_get_stub:
        mock_stub = MagicMock()
        mock_response = MagicMock()
        mock_response.item_code = "ITEM001"
        mock_response.item_name = "Test Item"
        mock_response.price = 100.0
        mock_response.tax_code = "T1"
        mock_response.category_code = "CAT1"
        mock_response.is_active = True

        mock_stub.GetItemDetail = AsyncMock(return_value=mock_response)
        mock_get_stub.return_value = mock_stub

        # Call twice
        item1 = await repository.get_item_by_code_async("ITEM001")
        item2 = await repository.get_item_by_code_async("ITEM002")

        # Should use shared stub
        assert mock_get_stub.call_count == 2
        assert item1.item_code == "ITEM001"


@pytest.mark.asyncio
async def test_close_handles_errors_gracefully(repository):
    """Test that close() handles errors gracefully"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock(side_effect=Exception("Close failed"))
        mock_get_channel.return_value = mock_channel

        # Create channel
        await repository._get_stub()

        # Close should not raise exception
        await repository.close()

        # Should still reset state
        assert repository._channel is None
        assert repository._stub is None
```

**Test Coverage Goals:**
- ✅ Channel creation on first use
- ✅ Channel reuse on subsequent calls (CORE FUNCTIONALITY)
- ✅ Proper cleanup on close
- ✅ New channel creation after close
- ✅ Integration with get_item_by_code_async
- ✅ Error handling during close

---

### Integration Tests

**Verification steps:**

1. **Channel reuse verification:**
   - Monitor logs for "Created new gRPC channel" messages
   - Should see only 1 message per CartRepository instance
   - Compare against number of item lookups

2. **Performance measurement:**
   - Measure time for first item lookup vs subsequent lookups
   - First lookup: ~100-300ms (channel creation + RPC)
   - Subsequent lookups: ~10-50ms (RPC only)

3. **Load testing:**
   - Run 15-user performance test
   - Monitor gRPC channel creation logs
   - Verify 99%ile latency improvement

---

## Performance Verification

### Log Analysis

Add logging to track channel creation:

```python
async def _get_stub(self) -> item_service_pb2_grpc.ItemServiceStub:
    if self._channel is None or self._stub is None:
        # ... channel creation ...
        logger.info(
            f"Created new gRPC channel for master-data service "
            f"(tenant={self.tenant_id}, store={self.store_code})"
        )
    return self._stub
```

**Expected results:**

**Before (no pooling):**
```
15 users × ~126 requests/user = ~1890 channel creations
Log entries: ~1890 times
```

**After (with pooling):**
```
15 users × 1 channel/user = ~15 channel creations
Log entries: ~15 times (one per user session)
```

**Improvement:** 99.2% reduction in channel creation

### Performance Test Execution

Run the same 10-minute tests as Phase 1:

```bash
cd services/cart/performance_tests

# Run tests for all user counts
./run_multiple_tests.sh
```

**Expected improvements (compared to Phase 1 results):**

| Users | Phase 1 99%ile | Phase 2 99%ile | Improvement |
|-------|----------------|----------------|-------------|
| 1     | ~1300-1400ms   | **~400-500ms** | ~65% |
| 3     | ~1100-1200ms   | **~500-600ms** | ~50% |
| 5     | ~1500-1800ms   | **~600-700ms** | ~60% |
| 10    | ~2500-3000ms   | **~700-800ms** | ~70% |
| 15    | ~3500-4200ms   | **~800-900ms** | ~78% |

---

## Implementation Checklist

### Code Changes

- [ ] Update `ItemMasterGrpcRepository.__init__()` to add `_channel` and `_stub` variables
- [ ] Create `_get_stub()` method for channel pooling
- [ ] Update `get_item_by_code_async()` to use `_get_stub()`
- [ ] Add `close()` method for cleanup
- [ ] Update `main.py` shutdown handler (add comment about garbage collection)
- [ ] Add import statement: `from typing import Optional`

### Testing

- [ ] Create `tests/repositories/test_item_master_grpc_repository.py`
- [ ] Implement 7 unit tests (listed above)
- [ ] Run tests: `pipenv run pytest tests/repositories/test_item_master_grpc_repository.py -v`
- [ ] Verify all tests pass
- [ ] Check test coverage: `pipenv run pytest --cov=app.models.repositories.item_master_grpc_repository tests/repositories/test_item_master_grpc_repository.py`

### Performance Verification

- [ ] Run performance tests (1/3/5/10/15 users)
- [ ] Analyze Docker logs for channel creation frequency
- [ ] Calculate channel reuse rate
- [ ] Compare 99%ile latency with Phase 1 results
- [ ] Measure throughput improvement

### Documentation

- [ ] Create performance improvement report (Phase 2)
- [ ] Update GitHub Issue #12 with Phase 2 results
- [ ] Document any unexpected findings or issues
- [ ] Update baseline performance metrics

---

## Risk Assessment

### Low Risk

- ✅ **Similar pattern to Phase 1:** We successfully implemented session pooling in Phase 1
- ✅ **Instance-level pooling:** Each repository instance has its own channel (no shared state issues)
- ✅ **Backward compatible:** No API changes, only internal optimization

### Medium Risk

- ⚠️ **Channel lifecycle management:** Need to ensure channels are properly closed
  - **Mitigation:** Implement comprehensive unit tests for close() method
  - **Mitigation:** Add garbage collection fallback

- ⚠️ **gRPC channel reconnection:** Channel might fail and need reconnection
  - **Mitigation:** Check `_channel` state before reuse
  - **Mitigation:** Add error handling in `_get_stub()`

### Monitoring

Add metrics to track:
- Channel creation frequency (via logs)
- Channel close events (via logs)
- gRPC call success/failure rate
- Average gRPC call duration

---

## Success Criteria

### Functional Requirements

- ✅ All existing tests continue to pass
- ✅ New unit tests pass (7/7)
- ✅ No errors in application logs
- ✅ gRPC communication continues to work correctly

### Performance Requirements

- ✅ 99%ile latency reduced by **45-55%** compared to Phase 1
- ✅ Throughput improved by **30-33%** compared to Phase 1
- ✅ Channel creation reduced by **99%+** (verified via logs)
- ✅ No regression in median latency

### Quality Requirements

- ✅ Code coverage for new code: **>90%**
- ✅ No new linting errors
- ✅ Clear, documented code with docstrings
- ✅ Proper error handling

---

## Rollback Plan

If Phase 2 causes issues:

1. **Identify the issue:**
   - Check application logs for errors
   - Check performance test results
   - Check unit test failures

2. **Quick rollback:**
   ```bash
   git revert HEAD
   ```

3. **Gradual rollback (if needed):**
   - Revert `get_item_by_code_async()` changes first
   - Keep logging/monitoring improvements
   - Investigate root cause

4. **Alternative approaches:**
   - Use module-level pooling (like Phase 1)
   - Implement connection pool size limits
   - Add circuit breaker for gRPC calls

---

## Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Implementation** | 2-3 hours | Code changes, unit tests |
| **Testing** | 1-2 hours | Run tests, verify results |
| **Performance Testing** | 1-2 hours | Run load tests (5 patterns × 10 min) |
| **Documentation** | 1 hour | Reports, GitHub issue update |
| **Total** | **5-8 hours** | **0.5-1 day** |

---

## Next Steps After Phase 2

Once Phase 2 is complete and verified:

1. **Monitor production performance** (if deployed)
2. **Consider additional optimizations:**
   - Database query optimization
   - Caching improvements
   - gRPC request batching
3. **Update performance baseline** for future comparisons
4. **Share learnings** with team

---

**Document Status:** Ready for Implementation
**Last Updated:** 2025-10-19
**Author:** Claude Code (AI-assisted development)
