# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""
Dapr state-store backed cache.

Wraps DaprClientHelper to provide a shared cache across cart-service workers
via Redis. All backend errors are swallowed (returning None / False) so the
calling repository can fall back to direct fetch, preserving cart operation
availability even when the cache layer is unreachable.

Generation-counter increment is implemented as read-then-write (no CAS),
because the underlying DaprClientHelper wrapper does not expose the ETag
returned by the Dapr state-store GET. Lost updates are acceptable for the
invalidate-all semantics: any successful bump renders all prior-generation
cache entries unreachable.
"""
import logging
from typing import Optional

from kugel_common.utils.cache.cache_backend import AbstractCacheBackend
from kugel_common.utils.dapr_client_helper import DaprClientHelper

logger = logging.getLogger(__name__)

# Effectively "no expiry" for the generation counter. The counter must outlive
# cache entries so that "gen{N}" never silently resets and revives old data.
_COUNTER_TTL_SECONDS = 365 * 24 * 60 * 60

# Counters are wrapped in a single-key dict so that the unified get() contract
# (Optional[dict]) covers both cached entries and counters with one API.
_COUNTER_WRAPPER_KEY = "_counter"


class DaprStateCacheBackend(AbstractCacheBackend):
    def __init__(
        self,
        store_name: str,
        dapr_client: Optional[DaprClientHelper] = None,
    ) -> None:
        self.store_name = store_name
        # Permit injection of a pre-built client for testing; otherwise create
        # one and own its lifecycle via close().
        self._owns_client = dapr_client is None
        self._client = dapr_client or DaprClientHelper()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def get(self, key: str) -> Optional[dict]:
        try:
            value = await self._client.get_state(self.store_name, key)
        except Exception as exc:
            # DaprClientHelper already handles its own errors and returns None,
            # but guard against unexpected wrapper bugs surfacing here.
            logger.warning(
                "cache get unexpected error: store=%s key_len=%d error=%s",
                self.store_name, len(key), type(exc).__name__,
            )
            return None
        # Dapr returns None on miss OR on handled errors. Both map to MISS
        # from the caller's perspective.
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        # Unexpected shape (e.g., backend stored a non-dict). Treat as miss to
        # force a re-fetch and overwrite with the correct shape.
        logger.warning(
            "cache get unexpected value type: store=%s key_len=%d type=%s",
            self.store_name, len(key), type(value).__name__,
        )
        return None

    async def set(self, key: str, value: dict, ttl_seconds: int) -> bool:
        metadata = {"ttlInSeconds": str(ttl_seconds)} if ttl_seconds > 0 else None
        try:
            return await self._client.save_state(
                store_name=self.store_name,
                key=key,
                value=value,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(
                "cache set unexpected error: store=%s key_len=%d error=%s",
                self.store_name, len(key), type(exc).__name__,
            )
            return False

    async def delete(self, key: str) -> bool:
        try:
            return await self._client.delete_state(self.store_name, key)
        except Exception as exc:
            logger.warning(
                "cache delete unexpected error: store=%s key_len=%d error=%s",
                self.store_name, len(key), type(exc).__name__,
            )
            return False

    async def increment(self, key: str) -> Optional[int]:
        try:
            current = await self._client.get_state(self.store_name, key)
        except Exception as exc:
            logger.warning(
                "cache increment read error: store=%s key_len=%d error=%s",
                self.store_name, len(key), type(exc).__name__,
            )
            return None

        current_int = 0
        if isinstance(current, dict):
            try:
                current_int = int(current.get(_COUNTER_WRAPPER_KEY, 0))
            except (TypeError, ValueError):
                logger.warning(
                    "cache increment non-integer counter: store=%s key_len=%d",
                    self.store_name, len(key),
                )
                current_int = 0
        elif current is not None:
            # Legacy bare-int counter (shouldn't happen after first bump under
            # the wrapper convention); coerce defensively.
            try:
                current_int = int(current)
            except (TypeError, ValueError):
                current_int = 0

        new_value = current_int + 1
        saved = await self._client.save_state(
            store_name=self.store_name,
            key=key,
            value={_COUNTER_WRAPPER_KEY: new_value},
            metadata={"ttlInSeconds": str(_COUNTER_TTL_SECONDS)},
        )
        if not saved:
            return None
        return new_value
