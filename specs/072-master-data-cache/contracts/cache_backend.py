"""
Contract: AbstractCacheBackend

Generic key/value cache abstraction with TTL semantics, used by
AbstractMasterDataRepository for transparent cache layering.

Implementations: InMemoryCacheBackend, DaprStateCacheBackend.

Invariants:
- All methods MUST NOT raise exceptions from backend connectivity / serialization
  failures. They return None / False to indicate failure. The caller is
  responsible for deciding fallback behavior (typically: log warning and fetch
  directly from source).
- value type is a JSON-serializable dict. Callers serialize their domain
  objects (e.g. Pydantic models via `model_dump(mode="json")`) before set,
  and deserialize after get.
- TTL is per-key. A backend MAY also enforce a component-level fallback TTL.
"""
from abc import ABC, abstractmethod
from typing import Optional


class AbstractCacheBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[dict]:
        """
        Returns the cached value (as dict) or None.

        None semantics covers BOTH cache miss AND backend error. Callers
        treat None uniformly as "must fetch from source".
        """
        ...

    @abstractmethod
    async def set(self, key: str, value: dict, ttl_seconds: int) -> bool:
        """
        Persist `value` under `key` with the given TTL.

        Returns True on success, False on backend error. False is recoverable
        (caller has already obtained the value from source and can return it
        to the user; the next caller will simply miss and re-fetch).
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Remove the entry at `key`.

        Returns True if the key was removed or already absent.
        Returns False only on backend error.
        """
        ...

    @abstractmethod
    async def increment(self, key: str) -> Optional[int]:
        """
        Atomically increment an integer counter at `key`.

        - If absent, treat current value as 0 and write 1.
        - Implementations MUST use CAS / ETag semantics to be safe under
          concurrent invalidation calls.
        - Returns the new value, or None on backend error / give-up.
        """
        ...
