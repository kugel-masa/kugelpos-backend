# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.dapr_client_helper.

Mocks the Dapr sidecar HTTP API via respx.
"""
from datetime import datetime, timedelta

import httpx
import pytest
import respx

from kugel_common.utils.dapr_client_helper import (
    CircuitState,
    DaprClientHelper,
    DaprComponent,
    get_dapr_client,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_dapr_component_values(self):
        assert DaprComponent.PUBSUB.value == "pubsub"
        assert DaprComponent.STATE_STORE.value == "statestore"

    def test_circuit_state_values(self):
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


# ---------------------------------------------------------------------------
# Initialization & circuit breaker state
# ---------------------------------------------------------------------------

class TestDaprClientHelperInit:
    @pytest.mark.asyncio
    async def test_default_port_3500(self):
        client = DaprClientHelper()
        assert client.dapr_http_port == 3500
        assert "localhost:3500" in client.base_url
        await client.close()

    @pytest.mark.asyncio
    async def test_custom_port(self):
        client = DaprClientHelper(dapr_http_port=3501)
        assert client.dapr_http_port == 3501
        assert "localhost:3501" in client.base_url
        await client.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_starts_closed(self):
        client = DaprClientHelper()
        assert client._circuit_state == CircuitState.CLOSED
        assert client._failure_count == 0
        await client.close()


class TestCircuitBreakerLogic:
    @pytest.mark.asyncio
    async def test_record_failure_opens_after_threshold(self):
        client = DaprClientHelper(circuit_breaker_threshold=3)
        assert client._check_circuit_breaker() is True

        for _ in range(3):
            client._record_failure()

        assert client._circuit_state == CircuitState.OPEN
        assert client._check_circuit_breaker() is False
        await client.close()

    @pytest.mark.asyncio
    async def test_circuit_moves_to_half_open_after_timeout(self):
        client = DaprClientHelper(
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=1,
        )
        client._record_failure()
        client._record_failure()
        assert client._circuit_state == CircuitState.OPEN

        # Backdate the failure to before the timeout window
        client._last_failure_time = datetime.now() - timedelta(seconds=10)

        # Next check moves to HALF_OPEN
        assert client._check_circuit_breaker() is True
        assert client._circuit_state == CircuitState.HALF_OPEN
        await client.close()

    @pytest.mark.asyncio
    async def test_record_success_in_half_open_closes_circuit(self):
        client = DaprClientHelper(circuit_breaker_threshold=1)
        client._record_failure()
        client._circuit_state = CircuitState.HALF_OPEN

        client._record_success()
        assert client._circuit_state == CircuitState.CLOSED
        assert client._failure_count == 0
        await client.close()


# ---------------------------------------------------------------------------
# publish_event
# ---------------------------------------------------------------------------

class TestPublishEvent:
    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_publish(self):
        respx.post("http://localhost:3500/v1.0/publish/pubsub/topic").mock(
            return_value=httpx.Response(200, json={})
        )
        client = DaprClientHelper()
        try:
            ok = await client.publish_event("pubsub", "topic", {"key": "value"})
            assert ok is True
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_failure_returns_false_and_records(self):
        respx.post("http://localhost:3500/v1.0/publish/pubsub/topic").mock(
            return_value=httpx.Response(500, json={"error": "x"})
        )
        client = DaprClientHelper(circuit_breaker_threshold=10, max_retries=1)
        try:
            ok = await client.publish_event("pubsub", "topic", {"data": 1})
            assert ok is False
            assert client._failure_count == 1
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_metadata_appended_as_query_string(self):
        route = respx.post(
            url__regex=r"http://localhost:3500/v1\.0/publish/pubsub/topic\?.*"
        ).mock(return_value=httpx.Response(200, json={}))
        client = DaprClientHelper()
        try:
            await client.publish_event(
                "pubsub", "topic", {"x": 1}, metadata={"ttl": "60"}
            )
        finally:
            await client.close()
        assert route.called
        assert "ttl=60" in str(route.calls[0].request.url)

    @pytest.mark.asyncio
    async def test_circuit_open_short_circuits(self):
        client = DaprClientHelper(circuit_breaker_threshold=1)
        client._record_failure()  # opens the circuit
        # No respx routes registered — if it tried to hit the network it would fail
        ok = await client.publish_event("pubsub", "topic", {})
        assert ok is False
        await client.close()


# ---------------------------------------------------------------------------
# get_state / save_state / delete_state
# ---------------------------------------------------------------------------

class TestStateStore:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_state_returns_value(self):
        respx.get("http://localhost:3500/v1.0/state/store/key1").mock(
            return_value=httpx.Response(200, json={"foo": "bar"})
        )
        client = DaprClientHelper()
        try:
            value = await client.get_state("store", "key1")
            assert value == {"foo": "bar"}
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_state_204_returns_none(self):
        respx.get("http://localhost:3500/v1.0/state/store/missing").mock(
            return_value=httpx.Response(204, content=b"")
        )
        client = DaprClientHelper()
        try:
            value = await client.get_state("store", "missing")
            assert value is None
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_state_404_returns_none(self):
        respx.get("http://localhost:3500/v1.0/state/store/notfound").mock(
            return_value=httpx.Response(404, json={"detail": "not found"})
        )
        client = DaprClientHelper(max_retries=1)
        try:
            value = await client.get_state("store", "notfound")
            assert value is None
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_save_state_success(self):
        route = respx.post("http://localhost:3500/v1.0/state/store").mock(
            return_value=httpx.Response(204)
        )
        client = DaprClientHelper()
        try:
            ok = await client.save_state("store", "k", {"v": 1})
            assert ok is True
        finally:
            await client.close()
        assert route.called
        # Inspect payload
        import json
        body = json.loads(route.calls[0].request.content.decode())
        assert body[0]["key"] == "k"
        assert body[0]["value"] == {"v": 1}

    @pytest.mark.asyncio
    @respx.mock
    async def test_save_state_with_etag(self):
        route = respx.post("http://localhost:3500/v1.0/state/store").mock(
            return_value=httpx.Response(204)
        )
        client = DaprClientHelper()
        try:
            await client.save_state("store", "k", "v", etag="etag-1")
        finally:
            await client.close()
        import json
        body = json.loads(route.calls[0].request.content.decode())
        assert body[0]["etag"] == "etag-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_save_state_failure_returns_false(self):
        respx.post("http://localhost:3500/v1.0/state/store").mock(
            return_value=httpx.Response(500)
        )
        client = DaprClientHelper(max_retries=1)
        try:
            ok = await client.save_state("store", "k", "v")
            assert ok is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_state_success(self):
        respx.delete("http://localhost:3500/v1.0/state/store/k").mock(
            return_value=httpx.Response(204)
        )
        client = DaprClientHelper()
        try:
            ok = await client.delete_state("store", "k")
            assert ok is True
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_state_failure_returns_false(self):
        respx.delete("http://localhost:3500/v1.0/state/store/k").mock(
            return_value=httpx.Response(500)
        )
        client = DaprClientHelper(max_retries=1)
        try:
            ok = await client.delete_state("store", "k")
            assert ok is False
        finally:
            await client.close()


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------

class TestBulkState:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_bulk_state_returns_dict(self):
        respx.post("http://localhost:3500/v1.0/state/store/bulk").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"key": "a", "data": "av"},
                    {"key": "b", "data": "bv"},
                ],
            )
        )
        client = DaprClientHelper()
        try:
            result = await client.get_bulk_state("store", ["a", "b"])
            assert result == {"a": "av", "b": "bv"}
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_get_bulk_state_short_circuits_when_open(self):
        client = DaprClientHelper(circuit_breaker_threshold=1)
        client._record_failure()  # opens circuit
        result = await client.get_bulk_state("store", ["a", "b"])
        assert result == {}
        await client.close()


# ---------------------------------------------------------------------------
# get_dapr_client context manager
# ---------------------------------------------------------------------------

class TestGetDaprClientContext:
    @pytest.mark.asyncio
    async def test_context_manager_yields_and_closes(self):
        async with get_dapr_client() as client:
            assert isinstance(client, DaprClientHelper)
        # Client closed after context exit (no easy way to assert internal,
        # but no exception is the contract)
