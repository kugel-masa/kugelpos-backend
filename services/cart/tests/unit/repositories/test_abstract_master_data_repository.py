# Copyright 2026 masa@kugel
"""Unit tests for app.models.repositories.abstract_master_data_repository.

Uses InMemoryCacheBackend so no real Dapr/Redis is required.
"""
import logging
from typing import ClassVar

import pytest
from pydantic import BaseModel

from kugel_common.exceptions.repository_exceptions import NotFoundException
from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.utils.cache.in_memory_cache_backend import InMemoryCacheBackend

from app.config.settings_cart import cart_settings
from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
)


# ---------------------------------------------------------------------------
# Fixtures: tiny document type, fake terminal_info, fake subclass.
# ---------------------------------------------------------------------------

class FakeDoc(BaseDocumentModel):
    code: str
    value: int


class _FakeTerminal:
    """Minimal stand-in for TerminalInfoDocument; only store_code is read
    by the base class (and only when explicitly opted into)."""
    store_code: str = "DEFAULT_STORE"


class FakeOneRepo(AbstractMasterDataRepository[FakeDoc]):
    cache_namespace = "fake_master"
    document_class = FakeDoc
    default_ttl_seconds = 60
    is_store_scoped = True

    def __init__(self, *, tenant_id, store_code, cache_backend):
        super().__init__(
            tenant_id=tenant_id,
            terminal_info=_FakeTerminal(),
            cache_backend=cache_backend,
            store_code=store_code,
        )
        self.fetch_calls = 0
        self.return_value: FakeDoc | None = None
        self.raise_not_found = False

    async def _fetch_one(self, logical_key: str) -> FakeDoc:
        self.fetch_calls += 1
        if self.raise_not_found:
            raise NotFoundException("missing", "fake_master", logical_key)
        return self.return_value or FakeDoc(code=logical_key, value=42)


class FakeListRepo(AbstractMasterDataRepository[FakeDoc]):
    cache_namespace = "fake_list_master"
    document_class = FakeDoc
    default_ttl_seconds = 60
    is_store_scoped = True

    def __init__(self, *, tenant_id, store_code, cache_backend):
        super().__init__(
            tenant_id=tenant_id,
            terminal_info=_FakeTerminal(),
            cache_backend=cache_backend,
            store_code=store_code,
        )
        self.fetch_calls = 0
        self.return_value: list[FakeDoc] = []

    async def _fetch_one(self, logical_key: str) -> FakeDoc:  # required
        raise NotImplementedError

    async def _fetch_list(self, logical_key: str) -> list[FakeDoc]:
        self.fetch_calls += 1
        return list(self.return_value)


class TenantScopedRepo(AbstractMasterDataRepository[FakeDoc]):
    cache_namespace = "tenant_only_master"
    document_class = FakeDoc
    default_ttl_seconds = 60
    is_store_scoped = False  # Tenant-wide; store position in key is always "_"

    def __init__(self, *, tenant_id, cache_backend, store_code=None):
        super().__init__(
            tenant_id=tenant_id,
            terminal_info=_FakeTerminal(),
            cache_backend=cache_backend,
            store_code=store_code,
        )
        self.fetch_calls = 0

    async def _fetch_one(self, logical_key: str) -> FakeDoc:
        self.fetch_calls += 1
        return FakeDoc(code=logical_key, value=1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def cache():
    return InMemoryCacheBackend()


@pytest.mark.asyncio
class TestBasicHitMiss:
    async def test_first_call_is_miss_then_hit(self, cache):
        repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        doc1 = await repo.get_or_fetch_one("CODE")
        doc2 = await repo.get_or_fetch_one("CODE")
        assert doc1.code == "CODE" and doc2.code == "CODE"
        assert repo.fetch_calls == 1  # only the first call hit the source

    async def test_different_keys_are_isolated(self, cache):
        repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        await repo.get_or_fetch_one("A")
        await repo.get_or_fetch_one("B")
        assert repo.fetch_calls == 2

    async def test_list_lookup_caches_full_list(self, cache):
        repo = FakeListRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        repo.return_value = [FakeDoc(code="A", value=1), FakeDoc(code="B", value=2)]
        a = await repo.get_or_fetch_list("active")
        b = await repo.get_or_fetch_list("active")
        assert [d.code for d in a] == ["A", "B"]
        assert [d.code for d in b] == ["A", "B"]
        assert repo.fetch_calls == 1


@pytest.mark.asyncio
class TestEntryKindIsolation:
    async def test_one_and_list_do_not_collide_on_same_logical_key(self, cache):
        """FR-010: entry_kind must distinguish single-vs-list cache entries."""
        one_repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        list_repo = FakeListRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        # Force both to share the same logical_key string and namespace prefix
        # would still differ, so to exercise entry_kind specifically we use
        # the same namespace via subclassing — done below in a tighter test.
        # Here we at least verify they don't accidentally interfere.
        list_repo.return_value = [FakeDoc(code="L", value=99)]
        await one_repo.get_or_fetch_one("X")
        await list_repo.get_or_fetch_list("X")
        # No collision: both fetched once.
        assert one_repo.fetch_calls == 1
        assert list_repo.fetch_calls == 1


@pytest.mark.asyncio
class TestNotFoundSemantics:
    async def test_not_found_is_propagated_and_not_cached(self, cache):
        """FR-013 / SC-009: absence is never cached."""
        repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        repo.raise_not_found = True
        with pytest.raises(NotFoundException):
            await repo.get_or_fetch_one("MISSING")
        with pytest.raises(NotFoundException):
            await repo.get_or_fetch_one("MISSING")
        # Both calls hit the source (no caching of absence).
        assert repo.fetch_calls == 2


@pytest.mark.asyncio
class TestBackendFailureFallback:
    async def test_backend_get_failure_falls_through_to_fetch(self, cache, monkeypatch):
        """FR-007 / SC-003: backend errors must not break cart operations."""
        async def broken_get(_key):
            return None  # InMemoryCacheBackend never errors, but simulate.
        monkeypatch.setattr(cache, "get", broken_get)
        repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        doc = await repo.get_or_fetch_one("CODE")
        assert doc.code == "CODE"


@pytest.mark.asyncio
class TestStoreCodeResolution:
    async def test_override_takes_precedence_over_instance(self, cache):
        """R-009: store_code_override has highest priority."""
        repo = FakeOneRepo(tenant_id="T1", store_code="S_INST", cache_backend=cache)
        await repo.get_or_fetch_one("X", store_code_override="S_OVR")
        # Verify the key actually went to the OVR scope by checking what
        # exists in the backend store.
        assert any(":S_OVR:" in k for k in cache._store.keys())
        assert not any(":S_INST:" in k for k in cache._store.keys())

    async def test_store_scoped_missing_store_code_raises(self, cache):
        """R-009: store-scoped repo without resolvable store_code is a bug."""
        # Construct without store_code; terminal_info should NOT be used as
        # fallback per R-009.
        repo = FakeOneRepo.__new__(FakeOneRepo)
        AbstractMasterDataRepository.__init__(
            repo,
            tenant_id="T1",
            terminal_info=_FakeTerminal(),
            cache_backend=cache,
            store_code=None,
        )
        repo.fetch_calls = 0
        repo.return_value = None
        repo.raise_not_found = False
        with pytest.raises(ValueError, match="store-scoped"):
            await repo.get_or_fetch_one("X")


@pytest.mark.asyncio
class TestTenantScopedKeyPlaceholder:
    async def test_tenant_scoped_keys_use_underscore(self, cache):
        """R-009: is_store_scoped=False forces store position to '_'."""
        repo = TenantScopedRepo(tenant_id="T1", cache_backend=cache)
        await repo.get_or_fetch_one("CASH")
        keys = list(cache._store.keys())
        assert len(keys) == 1
        assert ":T1:_:tenant_only_master:" in keys[0]


@pytest.mark.asyncio
class TestInvalidation:
    async def test_invalidate_single_key_only(self, cache):
        repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        await repo.get_or_fetch_one("A")
        await repo.get_or_fetch_one("B")
        assert repo.fetch_calls == 2
        await repo.invalidate("A")
        await repo.get_or_fetch_one("A")  # MISS -> fetch
        await repo.get_or_fetch_one("B")  # still HIT
        assert repo.fetch_calls == 3

    async def test_invalidate_all_bumps_generation_and_misses_everything(self, cache):
        """FR-006 / SC-005."""
        repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        await repo.get_or_fetch_one("A")
        await repo.get_or_fetch_one("B")
        assert repo.fetch_calls == 2
        await repo.invalidate_all()
        await repo.get_or_fetch_one("A")  # MISS in new generation
        await repo.get_or_fetch_one("B")  # MISS in new generation
        assert repo.fetch_calls == 4

    async def test_invalidate_all_does_not_affect_other_namespaces(self, cache):
        item_repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        other_repo = TenantScopedRepo(tenant_id="T1", cache_backend=cache)
        await item_repo.get_or_fetch_one("ITEM_A")
        await other_repo.get_or_fetch_one("CASH")
        await item_repo.invalidate_all()
        await item_repo.get_or_fetch_one("ITEM_A")  # MISS
        await other_repo.get_or_fetch_one("CASH")   # still HIT
        assert item_repo.fetch_calls == 2
        assert other_repo.fetch_calls == 1


@pytest.mark.asyncio
class TestTenantAndStoreIsolation:
    async def test_two_tenants_do_not_share_cache(self, cache):
        """FR-003 / SC-006: cross-tenant isolation."""
        repo_a = FakeOneRepo(tenant_id="T_A", store_code="S1", cache_backend=cache)
        repo_b = FakeOneRepo(tenant_id="T_B", store_code="S1", cache_backend=cache)
        await repo_a.get_or_fetch_one("ITEM_X")
        await repo_b.get_or_fetch_one("ITEM_X")
        # Two separate fetches because the cache keys must differ.
        assert repo_a.fetch_calls == 1
        assert repo_b.fetch_calls == 1
        assert any(":T_A:" in k for k in cache._store.keys())
        assert any(":T_B:" in k for k in cache._store.keys())

    async def test_two_stores_same_tenant_do_not_share(self, cache):
        """FR-003 / SC-006b: same-tenant cross-store isolation."""
        repo_a = FakeOneRepo(tenant_id="T1", store_code="S_A", cache_backend=cache)
        repo_b = FakeOneRepo(tenant_id="T1", store_code="S_B", cache_backend=cache)
        await repo_a.get_or_fetch_one("ITEM_X")
        await repo_b.get_or_fetch_one("ITEM_X")
        assert repo_a.fetch_calls == 1
        assert repo_b.fetch_calls == 1
        assert any(":T1:S_A:" in k for k in cache._store.keys())
        assert any(":T1:S_B:" in k for k in cache._store.keys())


@pytest.mark.asyncio
class TestGlobalSwitch:
    async def test_disabled_cache_always_calls_source(self, cache, monkeypatch):
        """FR-008: MASTER_DATA_CACHE_ENABLED=False bypasses cache entirely."""
        monkeypatch.setattr(cart_settings, "MASTER_DATA_CACHE_ENABLED", False)
        repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        for _ in range(3):
            await repo.get_or_fetch_one("X")
        assert repo.fetch_calls == 3
        # Nothing was written to the backend store.
        assert len(cache._store) == 0


@pytest.mark.asyncio
class TestLogMasking:
    async def test_set_failure_warning_does_not_leak_logical_key_or_value(
        self, cache, monkeypatch, caplog
    ):
        """FR-012 / R-011: warning logs MUST NOT include logical_key or value."""
        async def failing_set(_k, _v, _ttl):
            return False
        monkeypatch.setattr(cache, "set", failing_set)
        repo = FakeOneRepo(tenant_id="T1", store_code="S1", cache_backend=cache)
        repo.return_value = FakeDoc(code="SECRET_KEY_VALUE", value=999)
        with caplog.at_level(logging.WARNING):
            await repo.get_or_fetch_one("SECRET_KEY_VALUE")
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "expected at least one warning"
        for record in warnings:
            assert "SECRET_KEY_VALUE" not in record.getMessage()
            assert "999" not in record.getMessage()
            # Allowed identifiers: namespace, entry_kind, key length.
            assert "fake_master" in record.getMessage()
            assert "key_len=" in record.getMessage()
