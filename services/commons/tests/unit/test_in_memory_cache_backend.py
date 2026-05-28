# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.cache.in_memory_cache_backend."""
import asyncio

import pytest

from kugel_common.utils.cache.in_memory_cache_backend import InMemoryCacheBackend


@pytest.mark.asyncio
class TestRoundTrip:
    async def test_set_then_get_returns_value(self):
        backend = InMemoryCacheBackend()
        await backend.set("k1", {"a": 1}, ttl_seconds=60)
        assert await backend.get("k1") == {"a": 1}

    async def test_missing_key_returns_none(self):
        backend = InMemoryCacheBackend()
        assert await backend.get("absent") is None

    async def test_overwrite_replaces_value(self):
        backend = InMemoryCacheBackend()
        await backend.set("k", {"v": 1}, ttl_seconds=60)
        await backend.set("k", {"v": 2}, ttl_seconds=60)
        assert await backend.get("k") == {"v": 2}


@pytest.mark.asyncio
class TestTTL:
    async def test_zero_ttl_means_no_expiry(self):
        backend = InMemoryCacheBackend()
        await backend.set("k", {"v": 1}, ttl_seconds=0)
        assert await backend.get("k") == {"v": 1}

    async def test_expired_entry_returns_none_and_is_evicted(self, monkeypatch):
        backend = InMemoryCacheBackend()
        # Capture the real clock BEFORE patching so the patched lambda does
        # not recurse into itself.
        from kugel_common.utils.cache import in_memory_cache_backend as module
        real_now = module.time.time()
        await backend.set("k", {"v": 1}, ttl_seconds=1)
        monkeypatch.setattr(module.time, "time", lambda: real_now + 5)
        assert await backend.get("k") is None
        # Internal store should not retain the expired entry.
        assert "k" not in backend._store


@pytest.mark.asyncio
class TestDelete:
    async def test_delete_removes_entry(self):
        backend = InMemoryCacheBackend()
        await backend.set("k", {"v": 1}, ttl_seconds=60)
        assert await backend.delete("k") is True
        assert await backend.get("k") is None

    async def test_delete_absent_key_returns_true(self):
        backend = InMemoryCacheBackend()
        # The contract: delete returns True for "removed or already absent".
        assert await backend.delete("never_set") is True


@pytest.mark.asyncio
class TestIncrement:
    async def test_first_increment_returns_one(self):
        backend = InMemoryCacheBackend()
        assert await backend.increment("gen") == 1

    async def test_sequential_increments(self):
        backend = InMemoryCacheBackend()
        await backend.increment("gen")
        await backend.increment("gen")
        assert await backend.increment("gen") == 3

    async def test_concurrent_increments_serialize_correctly(self):
        backend = InMemoryCacheBackend()

        async def bump():
            await backend.increment("gen")

        await asyncio.gather(*(bump() for _ in range(50)))
        # All 50 must land thanks to the internal lock.
        final = await backend.get("gen")
        assert final == {"_counter": 50}


@pytest.mark.asyncio
class TestClearAll:
    async def test_clear_all_drops_everything(self):
        backend = InMemoryCacheBackend()
        await backend.set("k", {"v": 1}, ttl_seconds=60)
        await backend.increment("gen")
        await backend.clear_all()
        assert await backend.get("k") is None
        assert await backend.get("gen") is None
