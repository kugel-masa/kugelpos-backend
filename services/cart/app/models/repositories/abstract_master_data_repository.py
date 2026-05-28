# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""
Abstract base class for master-data repositories in the cart service.

Subclasses declare:
- cache_namespace      : str   (ClassVar, e.g. "item_master")
- document_class       : type  (ClassVar, a Pydantic BaseDocumentModel subclass)
- default_ttl_seconds  : int   (ClassVar, per-namespace TTL)
- is_store_scoped      : bool  (ClassVar, True = per-store, False = tenant-wide)
                         May be overridden as @property when scoping depends
                         on instance state (e.g., SettingsMasterWebRepository).
- _fetch_one(logical_key) -> TDoc    (REQUIRED)
- _fetch_list(logical_key) -> list   (override only when list lookups are used)

Cache key format:
    mdcache:{tenant_id}:{store_code or '_'}:{namespace}:gen{N}:{entry_kind}:{logical_key}

Behavior summary:
- Per-entry TTL via the backend.
- "Not found" responses MUST NOT be cached (FR-013); the exception is
  propagated so the next call re-fetches and observes any newly added master.
- Backend failures are non-fatal: lookups fall back to the source fetch with
  a warning log, never breaking cart operations (FR-007).
- `invalidate_all` bumps a per-(tenant, store, namespace) generation counter
  to render prior-generation entries unreachable without needing a backend
  bulk-delete API.
"""
import logging
from abc import ABC, abstractmethod
from typing import (
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Generic,
    Optional,
    TypeVar,
)

from kugel_common.exceptions.base_exceptions import RepositoryException
from kugel_common.exceptions.repository_exceptions import NotFoundException
from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.cache_backend import AbstractCacheBackend

from app.config.settings_cart import cart_settings

logger = logging.getLogger(__name__)

TDoc = TypeVar("TDoc", bound=BaseDocumentModel)

_KEY_PREFIX = "mdcache"
_ENTRY_ONE = "one"
_ENTRY_LIST = "list"
_TENANT_SCOPE_PLACEHOLDER = "_"


class AbstractMasterDataRepository(Generic[TDoc], ABC):
    # ---- Required class-level declarations ------------------------------- #
    cache_namespace: ClassVar[str]
    document_class: ClassVar[type[BaseDocumentModel]]
    default_ttl_seconds: ClassVar[int] = 300
    # See _resolve_store_code for the contract; subclasses with dynamic
    # scoping may override this as an @property.
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
        # Per-instance (i.e. per-request) memo of the generation counter, keyed
        # by store segment. Repositories are constructed per request, so the
        # generation is effectively stable for the instance's lifetime; caching
        # it avoids a second Redis round-trip on every lookup. A concurrent
        # invalidate_all() from another worker mid-request is not observed until
        # the next request, which is within the spec's staleness tolerance.
        self._generation_memo: dict[str, int] = {}

    # ===================================================================== #
    # Public API
    # ===================================================================== #

    async def get_or_fetch_one(
        self,
        logical_key: str,
        *,
        store_code_override: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        fetcher: Optional[Callable[[], Awaitable[TDoc]]] = None,
    ) -> TDoc:
        """Look up a single document, fetching on miss."""
        return await self._get_or_fetch(
            logical_key=logical_key,
            entry_kind=_ENTRY_ONE,
            store_code_override=store_code_override,
            ttl_seconds=ttl_seconds,
            fetcher=fetcher,
            list_mode=False,
        )

    async def get_or_fetch_list(
        self,
        logical_key: str,
        *,
        store_code_override: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        fetcher: Optional[Callable[[], Awaitable[list[TDoc]]]] = None,
    ) -> list[TDoc]:
        """Look up a list of documents, fetching on miss."""
        return await self._get_or_fetch(
            logical_key=logical_key,
            entry_kind=_ENTRY_LIST,
            store_code_override=store_code_override,
            ttl_seconds=ttl_seconds,
            fetcher=fetcher,
            list_mode=True,
        )

    async def invalidate(
        self,
        logical_key: str,
        *,
        store_code_override: Optional[str] = None,
        entry_kind: str = _ENTRY_ONE,
    ) -> None:
        """Remove a single cache entry. Safe under backend failure."""
        if not cart_settings.MASTER_DATA_CACHE_ENABLED:
            return
        effective_store = self._resolve_store_code(store_code_override)
        generation = await self._get_generation(effective_store)
        key = self._build_key(effective_store, generation, entry_kind, logical_key)
        ok = await self.cache_backend.delete(key)
        if not ok:
            logger.warning(
                "master cache invalidate failed: namespace=%s entry_kind=%s key_len=%d",
                self.cache_namespace, entry_kind, len(key),
            )

    async def invalidate_all(self) -> None:
        """
        Invalidate every cache entry in this (tenant, store, namespace) scope
        by atomically bumping the generation counter.
        """
        if not cart_settings.MASTER_DATA_CACHE_ENABLED:
            return
        effective_store = self._resolve_store_code(store_code_override=None)
        new_gen = await self._bump_generation(effective_store)
        if new_gen is None:
            logger.warning(
                "master cache invalidate_all bump failed: namespace=%s",
                self.cache_namespace,
            )

    # ===================================================================== #
    # Abstract / overridable fetch hooks
    # ===================================================================== #

    @abstractmethod
    async def _fetch_one(self, logical_key: str) -> TDoc:
        """Implement the actual source fetch for a single entry."""

    async def _fetch_list(self, logical_key: str) -> list[TDoc]:
        """Override only when list lookups are supported."""
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _fetch_list."
        )

    # ===================================================================== #
    # Internal helpers
    # ===================================================================== #

    def _resolve_store_code(self, store_code_override: Optional[str]) -> Optional[str]:
        """
        Tenant-scoped masters (is_store_scoped == False) always key with "_".
        Store-scoped masters require a resolvable store_code; missing values
        are treated as a programming error.
        """
        if not self.is_store_scoped:
            return None
        if store_code_override is not None:
            return store_code_override
        if self.store_code is not None:
            return self.store_code
        raise ValueError(
            f"{type(self).__name__} is store-scoped but no store_code was "
            "provided (neither via constructor nor via store_code_override)."
        )

    def _build_key(
        self,
        store_code: Optional[str],
        generation: int,
        entry_kind: str,
        logical_key: str,
    ) -> str:
        store_segment = store_code if store_code else _TENANT_SCOPE_PLACEHOLDER
        return (
            f"{_KEY_PREFIX}:{self.tenant_id}:{store_segment}"
            f":{self.cache_namespace}:gen{generation}:{entry_kind}:{logical_key}"
        )

    def _build_generation_key(self, store_code: Optional[str]) -> str:
        return self.build_generation_key(self.tenant_id, store_code, self.cache_namespace)

    @staticmethod
    def build_generation_key(
        tenant_id: str, store_code: Optional[str], namespace: str
    ) -> str:
        """Build the per-(tenant, store, namespace) generation-counter key.

        Exposed statically so operational tooling (e.g. the cache-invalidation
        HTTP endpoint) can bump a namespace's generation without constructing a
        full repository instance.
        """
        store_segment = store_code if store_code else _TENANT_SCOPE_PLACEHOLDER
        return f"{_KEY_PREFIX}:{tenant_id}:{store_segment}:{namespace}:generation"

    async def _get_generation(self, store_code: Optional[str]) -> int:
        memo_key = store_code if store_code else _TENANT_SCOPE_PLACEHOLDER
        if memo_key in self._generation_memo:
            return self._generation_memo[memo_key]
        gen_key = self._build_generation_key(store_code)
        raw = await self.cache_backend.get(gen_key)
        if raw is None:
            self._generation_memo[memo_key] = 0
            return 0
        # Counters are stored as {"_counter": N} by the backend's increment().
        # Be defensive in case a legacy bare value is encountered.
        if isinstance(raw, dict):
            value: Any = raw.get("_counter", raw.get("value", 0))
        else:
            value = raw
        try:
            resolved = int(value)
        except (TypeError, ValueError):
            logger.warning(
                "master cache generation non-integer: namespace=%s",
                self.cache_namespace,
            )
            resolved = 0
        self._generation_memo[memo_key] = resolved
        return resolved

    async def _bump_generation(self, store_code: Optional[str]) -> Optional[int]:
        gen_key = self._build_generation_key(store_code)
        new_value = await self.cache_backend.increment(gen_key)
        if new_value is not None:
            # Keep this instance's memo consistent with the bump it just made,
            # so a subsequent lookup on the same instance uses the new generation.
            memo_key = store_code if store_code else _TENANT_SCOPE_PLACEHOLDER
            self._generation_memo[memo_key] = new_value
        return new_value

    async def _get_or_fetch(
        self,
        *,
        logical_key: str,
        entry_kind: str,
        store_code_override: Optional[str],
        ttl_seconds: Optional[int],
        fetcher: Optional[Callable[[], Awaitable[Any]]],
        list_mode: bool,
    ) -> Any:
        # Global cache disable: bypass entirely and call the source.
        if not cart_settings.MASTER_DATA_CACHE_ENABLED:
            return await self._invoke_fetch(logical_key, fetcher, list_mode)

        effective_store = self._resolve_store_code(store_code_override)
        generation = await self._get_generation(effective_store)
        key = self._build_key(effective_store, generation, entry_kind, logical_key)

        cached = await self.cache_backend.get(key)
        if cached is not None:
            return self._deserialize(cached, list_mode)

        # MISS (or backend failure) -> fetch from source.
        result = await self._invoke_fetch(logical_key, fetcher, list_mode)

        # NotFound is handled by _invoke_fetch raising; if we get here, the
        # source returned a real result. Persist for next time. set() failure
        # is non-fatal.
        serialized = self._serialize(result, list_mode)
        effective_ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        saved = await self.cache_backend.set(key, serialized, effective_ttl)
        if not saved:
            logger.warning(
                "master cache set failed: namespace=%s entry_kind=%s key_len=%d",
                self.cache_namespace, entry_kind, len(key),
            )
        return result

    async def _invoke_fetch(
        self,
        logical_key: str,
        fetcher: Optional[Callable[[], Awaitable[Any]]],
        list_mode: bool,
    ) -> Any:
        """
        Delegate to the explicit fetcher closure if provided, otherwise to
        the subclass _fetch_one / _fetch_list. NotFoundException and any
        other RepositoryException propagate unchanged.
        """
        try:
            if fetcher is not None:
                return await fetcher()
            if list_mode:
                return await self._fetch_list(logical_key)
            return await self._fetch_one(logical_key)
        except NotFoundException:
            # Per FR-013, do NOT cache absence. Re-raise for the caller to
            # decide (some subclasses convert to None at their API surface).
            raise
        except RepositoryException:
            raise

    # ---- (de)serialization ----------------------------------------------- #

    def _serialize(self, result: Any, list_mode: bool) -> dict:
        """Convert domain object(s) into a JSON-safe dict for the backend."""
        if list_mode:
            items = [self._doc_to_dict(doc) for doc in result]
            return {"items": items}
        return self._doc_to_dict(result)

    def _deserialize(self, cached: dict, list_mode: bool) -> Any:
        """Convert the cached dict back into domain object(s)."""
        if list_mode:
            items = cached.get("items", []) if isinstance(cached, dict) else []
            return [self.document_class.model_validate(item) for item in items]
        return self.document_class.model_validate(cached)

    @staticmethod
    def _doc_to_dict(doc: BaseDocumentModel) -> dict:
        # mode="json" yields a fully JSON-serializable dict (datetime, Decimal, etc).
        return doc.model_dump(mode="json")
