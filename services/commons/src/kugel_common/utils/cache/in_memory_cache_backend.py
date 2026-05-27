# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""
In-memory cache backend.

Process-local, asyncio-safe cache with per-key TTL. Intended for tests and
single-process fallback usage; for cross-worker sharing, use the Dapr backend.
"""
import asyncio
import time
from typing import Optional

from kugel_common.utils.cache.cache_backend import AbstractCacheBackend


# Well-known wrapper key for counter values so a single get()/set() namespace
# can hold both cached dicts and atomically-updated integer counters.
_COUNTER_WRAPPER_KEY = "_counter"


class InMemoryCacheBackend(AbstractCacheBackend):
    def __init__(self) -> None:
        # key -> (value, expires_at_epoch_seconds). expires_at == 0 means no expiry.
        # value is always a dict (cache entries) or a counter-wrapper dict.
        self._store: dict[str, tuple[dict, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[dict]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at and expires_at <= time.time():
                # Expired; evict eagerly.
                self._store.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: dict, ttl_seconds: int) -> bool:
        async with self._lock:
            expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else 0.0
            self._store[key] = (value, expires_at)
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            self._store.pop(key, None)
            return True

    async def increment(self, key: str) -> Optional[int]:
        async with self._lock:
            current = 0
            entry = self._store.get(key)
            if entry is not None:
                value, _ = entry
                if isinstance(value, dict) and _COUNTER_WRAPPER_KEY in value:
                    try:
                        current = int(value[_COUNTER_WRAPPER_KEY])
                    except (TypeError, ValueError):
                        current = 0
            new_value = current + 1
            # Counters never expire (matches DaprStateCacheBackend behavior).
            self._store[key] = ({_COUNTER_WRAPPER_KEY: new_value}, 0.0)
            return new_value

    async def clear_all(self) -> None:
        """Test helper: drop all entries."""
        async with self._lock:
            self._store.clear()
