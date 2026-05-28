# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.cache.dapr_state_cache_backend.

The underlying DaprClientHelper is mocked so these tests stay in the unit
tier (no real Dapr sidecar).
"""
import logging
from unittest.mock import AsyncMock

import pytest

from kugel_common.utils.cache.dapr_state_cache_backend import (
    DaprStateCacheBackend,
    _COUNTER_TTL_SECONDS,
)


def _make_backend(client_mock: AsyncMock) -> DaprStateCacheBackend:
    """Build a backend with the provided client mock injected."""
    return DaprStateCacheBackend(store_name="masterstore", dapr_client=client_mock)


@pytest.mark.asyncio
class TestGet:
    async def test_returns_dict_on_hit(self):
        client = AsyncMock()
        client.get_state.return_value = {"item_code": "ITEM_A"}
        backend = _make_backend(client)
        assert await backend.get("some_key") == {"item_code": "ITEM_A"}
        client.get_state.assert_awaited_once_with("masterstore", "some_key")

    async def test_returns_none_on_miss(self):
        client = AsyncMock()
        client.get_state.return_value = None
        backend = _make_backend(client)
        assert await backend.get("k") is None

    async def test_returns_none_on_backend_exception_with_warning(self, caplog):
        client = AsyncMock()
        client.get_state.side_effect = RuntimeError("boom")
        backend = _make_backend(client)
        with caplog.at_level(logging.WARNING):
            assert await backend.get("k") is None
        assert any("cache get unexpected error" in r.message for r in caplog.records)

    async def test_returns_none_for_non_dict_value(self, caplog):
        client = AsyncMock()
        client.get_state.return_value = "not a dict"
        backend = _make_backend(client)
        with caplog.at_level(logging.WARNING):
            assert await backend.get("k") is None


@pytest.mark.asyncio
class TestSet:
    async def test_set_passes_ttl_metadata(self):
        client = AsyncMock()
        client.save_state.return_value = True
        backend = _make_backend(client)
        assert await backend.set("k", {"v": 1}, ttl_seconds=300) is True
        client.save_state.assert_awaited_once_with(
            store_name="masterstore",
            key="k",
            value={"v": 1},
            metadata={"ttlInSeconds": "300"},
        )

    async def test_set_omits_metadata_when_ttl_zero(self):
        client = AsyncMock()
        client.save_state.return_value = True
        backend = _make_backend(client)
        assert await backend.set("k", {"v": 1}, ttl_seconds=0) is True
        client.save_state.assert_awaited_once_with(
            store_name="masterstore",
            key="k",
            value={"v": 1},
            metadata=None,
        )

    async def test_set_returns_false_on_backend_failure(self):
        client = AsyncMock()
        client.save_state.return_value = False
        backend = _make_backend(client)
        assert await backend.set("k", {"v": 1}, ttl_seconds=300) is False

    async def test_set_returns_false_on_backend_exception(self, caplog):
        client = AsyncMock()
        client.save_state.side_effect = RuntimeError("boom")
        backend = _make_backend(client)
        with caplog.at_level(logging.WARNING):
            assert await backend.set("k", {"v": 1}, ttl_seconds=300) is False


@pytest.mark.asyncio
class TestDelete:
    async def test_delete_returns_true_on_success(self):
        client = AsyncMock()
        client.delete_state.return_value = True
        backend = _make_backend(client)
        assert await backend.delete("k") is True

    async def test_delete_returns_false_on_backend_failure(self):
        client = AsyncMock()
        client.delete_state.return_value = False
        backend = _make_backend(client)
        assert await backend.delete("k") is False

    async def test_delete_returns_false_on_backend_exception(self, caplog):
        client = AsyncMock()
        client.delete_state.side_effect = RuntimeError("boom")
        backend = _make_backend(client)
        with caplog.at_level(logging.WARNING):
            assert await backend.delete("k") is False


@pytest.mark.asyncio
class TestIncrement:
    async def test_first_increment_starts_at_one(self):
        client = AsyncMock()
        client.get_state.return_value = None
        client.save_state.return_value = True
        backend = _make_backend(client)
        assert await backend.increment("gen") == 1
        client.save_state.assert_awaited_once_with(
            store_name="masterstore",
            key="gen",
            value={"_counter": 1},
            metadata={"ttlInSeconds": str(_COUNTER_TTL_SECONDS)},
        )

    async def test_increment_advances_existing_wrapped_counter(self):
        client = AsyncMock()
        client.get_state.return_value = {"_counter": 5}
        client.save_state.return_value = True
        backend = _make_backend(client)
        assert await backend.increment("gen") == 6
        client.save_state.assert_awaited_once_with(
            store_name="masterstore",
            key="gen",
            value={"_counter": 6},
            metadata={"ttlInSeconds": str(_COUNTER_TTL_SECONDS)},
        )

    async def test_increment_handles_legacy_bare_int(self):
        client = AsyncMock()
        # Pre-wrapper counter format (defensive coercion path).
        client.get_state.return_value = 7
        client.save_state.return_value = True
        backend = _make_backend(client)
        assert await backend.increment("gen") == 8

    async def test_increment_returns_none_on_read_error(self, caplog):
        client = AsyncMock()
        client.get_state.side_effect = RuntimeError("boom")
        backend = _make_backend(client)
        with caplog.at_level(logging.WARNING):
            assert await backend.increment("gen") is None
        # Save must NOT be attempted when read failed.
        client.save_state.assert_not_awaited()

    async def test_increment_returns_none_on_write_failure(self):
        client = AsyncMock()
        client.get_state.return_value = 3
        client.save_state.return_value = False
        backend = _make_backend(client)
        assert await backend.increment("gen") is None

    async def test_increment_recovers_from_non_integer_counter(self, caplog):
        client = AsyncMock()
        client.get_state.return_value = "garbage"
        client.save_state.return_value = True
        backend = _make_backend(client)
        with caplog.at_level(logging.WARNING):
            # Treat non-integer as 0, write 1.
            assert await backend.increment("gen") == 1


@pytest.mark.asyncio
class TestClose:
    async def test_close_closes_owned_client(self):
        client = AsyncMock()
        # Backend constructs its own client when dapr_client=None, but for the
        # close-ownership test we inject and toggle _owns_client manually.
        backend = DaprStateCacheBackend(store_name="masterstore", dapr_client=client)
        backend._owns_client = True
        await backend.close()
        client.close.assert_awaited_once()

    async def test_close_does_not_close_borrowed_client(self):
        client = AsyncMock()
        backend = _make_backend(client)
        assert backend._owns_client is False
        await backend.close()
        client.close.assert_not_awaited()
