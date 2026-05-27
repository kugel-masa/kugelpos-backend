"""
Contract: AbstractMasterDataRepository[TDoc]

Base class for master-data repositories in the cart service. Provides a
transparent caching layer over the underlying fetch implementation
(`_fetch_one` / `_fetch_list`) and standard invalidation APIs.

Subclasses declare:
- cache_namespace        (e.g. "item_master")
- document_class         (Pydantic BaseDocumentModel subclass)
- default_ttl_seconds    (per-namespace TTL)
- is_store_scoped        (bool: True if the master is per-store, False if tenant-wide)
                         May be overridden as a @property for repositories whose
                         scoping depends on instance state (e.g. SettingsMaster).
- _fetch_one(logical_key)         (required)
- _fetch_list(logical_key)        (override only when list lookups are used)

Cache key format:
    mdcache:{tenant_id}:{store_code or '_'}:{namespace}:gen{N}:{entry_kind}:{logical_key}

Behavior:
- Per-entry TTL via the backend's `set(..., ttl_seconds)`.
- NotFound responses MUST NOT be cached (FR-013). The exception is propagated
  to the caller and the next call re-fetches.
- Backend failures are non-fatal: lookups fall back to direct fetch and log a
  warning, never abort cart operations.
- `invalidate_all` uses a per-namespace/tenant/store generation counter that
  is atomically incremented, making all prior-generation cache entries
  logically unreachable without requiring a backend-side bulk delete.
"""
from abc import ABC, abstractmethod
from typing import (
    Awaitable,
    Callable,
    ClassVar,
    Generic,
    Optional,
    TypeVar,
)

from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.cache_backend import AbstractCacheBackend


TDoc = TypeVar("TDoc", bound=BaseDocumentModel)


class AbstractMasterDataRepository(Generic[TDoc], ABC):
    # Required class-level declarations from subclass.
    cache_namespace: ClassVar[str]
    document_class: ClassVar[type[BaseDocumentModel]]
    default_ttl_seconds: ClassVar[int] = 300
    # Whether this master is per-store (True) or tenant-wide (False).
    # When False, the store_code position in the cache key is forced to "_"
    # regardless of self.store_code or any override, preventing tenant-scoped
    # masters from fragmenting across stores. Subclasses with dynamic scoping
    # (e.g. SettingsMaster: tenant settings vs. store settings on the same
    # class) may override this as an @property.
    is_store_scoped: ClassVar[bool] = True

    def __init__(
        self,
        tenant_id: str,
        terminal_info: TerminalInfoDocument,
        cache_backend: AbstractCacheBackend,
        store_code: Optional[str] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.terminal_info = terminal_info
        self.cache_backend = cache_backend
        self.store_code = store_code

    # ------------------------------------------------------------------ public

    async def get_or_fetch_one(
        self,
        logical_key: str,
        *,
        store_code_override: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        fetcher: Optional[Callable[[], Awaitable[TDoc]]] = None,
    ) -> TDoc:
        """
        Returns the single document for `logical_key`.

        Cache MISS path:
            calls fetcher() if provided, else self._fetch_one(logical_key).
            On NotFound: propagates the exception WITHOUT caching anything.
            On other errors: propagates without caching.

        store_code_override:
            When provided, replaces self.store_code for THIS call's key
            construction. Used by repositories that accept store_code as a
            method argument (e.g. PromotionMasterWebRepository).
        """
        ...

    async def get_or_fetch_list(
        self,
        logical_key: str,
        *,
        store_code_override: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        fetcher: Optional[Callable[[], Awaitable[list[TDoc]]]] = None,
    ) -> list[TDoc]:
        """List-valued counterpart of get_or_fetch_one."""
        ...

    async def invalidate(
        self,
        logical_key: str,
        *,
        store_code_override: Optional[str] = None,
        entry_kind: str = "one",
    ) -> None:
        """
        Remove a single cache entry. Safe under backend failure (logs warning,
        does not raise). The next lookup will re-fetch from source.
        """
        ...

    async def invalidate_all(self) -> None:
        """
        Invalidate every cache entry in this (tenant, store, namespace) scope
        by atomically bumping the generation counter. Other namespaces and
        other tenants/stores are NOT affected.
        """
        ...

    # ---------------------------------------------------------------- abstract

    @abstractmethod
    async def _fetch_one(self, logical_key: str) -> TDoc:
        """Implement the actual source fetch (HTTP / gRPC / DB) for one entry."""
        ...

    async def _fetch_list(self, logical_key: str) -> list[TDoc]:
        """
        Override only when list lookups are supported for this namespace.
        Default implementation raises NotImplementedError.
        """
        raise NotImplementedError

    # -------------------------------------------------------- internal helpers

    def _resolve_store_code(self, override: Optional[str]) -> Optional[str]:
        """
        Resolves the store_code segment for cache-key construction.

        Algorithm:
        - If `is_store_scoped` is False, returns None (key segment becomes "_"),
          regardless of any override or instance value. This prevents
          tenant-wide masters (Payment, Tax) from being fragmented across
          stores even when called from a store-attached terminal.
        - If `is_store_scoped` is True:
            1. explicit `override` (method argument) takes precedence
            2. else `self.store_code` (constructor argument)
            3. otherwise raise ValueError (programming error: a store-scoped
               repository was constructed without a usable store_code)
        - This intentionally does NOT fall back to `self.terminal_info.store_code`.
          Business logic that needs "use the terminal's store when omitted"
          must build that at the subclass method level and pass it explicitly
          via `store_code_override`.
        """
        ...

    def _build_key(
        self,
        store_code: Optional[str],
        generation: int,
        entry_kind: str,
        logical_key: str,
    ) -> str:
        """
        Returns the full cache key in the format:
            mdcache:{tenant_id}:{store_code or '_'}:{namespace}:gen{N}:{entry_kind}:{logical_key}
        """
        ...

    async def _get_generation(self, store_code: Optional[str]) -> int:
        """Read the current generation counter (0 if absent or on backend error)."""
        ...

    async def _bump_generation(self, store_code: Optional[str]) -> Optional[int]:
        """Atomically increment the generation counter. Returns new value or None on failure."""
        ...
