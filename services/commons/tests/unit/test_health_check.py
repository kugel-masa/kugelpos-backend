# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.health_check.HealthChecker."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from kugel_common.schemas.health import ComponentHealth, HealthStatus
from kugel_common.utils.health_check import HealthChecker


class TestCheckMongoDB:
    @pytest.mark.asyncio
    async def test_healthy_when_ping_succeeds(self):
        client = MagicMock()
        client.admin.command = AsyncMock(return_value={"ok": 1.0})
        result = await HealthChecker.check_mongodb(client)
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms is not None
        assert result.response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_unhealthy_on_timeout(self):
        client = MagicMock()

        async def slow_ping(*a, **kw):
            await asyncio.sleep(10)

        client.admin.command = slow_ping
        result = await HealthChecker.check_mongodb(client, timeout=0.05)
        assert result.status == HealthStatus.UNHEALTHY
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_unhealthy_on_other_error(self):
        client = MagicMock()
        client.admin.command = AsyncMock(side_effect=RuntimeError("connection refused"))
        result = await HealthChecker.check_mongodb(client)
        assert result.status == HealthStatus.UNHEALTHY
        assert "MongoDB error" in result.error
        assert "connection refused" in result.error


class TestCheckDaprSidecar:
    @pytest.mark.asyncio
    @respx.mock
    async def test_healthy_when_204(self):
        respx.get("http://localhost:3500/v1.0/healthz").mock(
            return_value=httpx.Response(204)
        )
        result = await HealthChecker.check_dapr_sidecar()
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    @respx.mock
    async def test_unhealthy_when_non_204(self):
        respx.get("http://localhost:3500/v1.0/healthz").mock(
            return_value=httpx.Response(503)
        )
        result = await HealthChecker.check_dapr_sidecar()
        assert result.status == HealthStatus.UNHEALTHY
        assert "503" in result.error

    @pytest.mark.asyncio
    @respx.mock
    async def test_unhealthy_on_timeout(self):
        respx.get("http://localhost:3500/v1.0/healthz").mock(
            side_effect=httpx.TimeoutException("slow")
        )
        result = await HealthChecker.check_dapr_sidecar()
        assert result.status == HealthStatus.UNHEALTHY
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_custom_port(self):
        respx.get("http://localhost:9999/v1.0/healthz").mock(
            return_value=httpx.Response(204)
        )
        result = await HealthChecker.check_dapr_sidecar(dapr_port=9999)
        assert result.status == HealthStatus.HEALTHY


class TestCheckDaprPubsub:
    @pytest.mark.asyncio
    @respx.mock
    async def test_healthy_on_200(self):
        respx.post("http://localhost:3500/v1.0/publish/pubsub/health-check").mock(
            return_value=httpx.Response(200)
        )
        result = await HealthChecker.check_dapr_pubsub()
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "pubsub"

    @pytest.mark.asyncio
    @respx.mock
    async def test_healthy_on_204(self):
        respx.post("http://localhost:3500/v1.0/publish/pubsub/health-check").mock(
            return_value=httpx.Response(204)
        )
        result = await HealthChecker.check_dapr_pubsub()
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    @respx.mock
    async def test_unhealthy_on_500(self):
        respx.post("http://localhost:3500/v1.0/publish/pubsub/health-check").mock(
            return_value=httpx.Response(500)
        )
        result = await HealthChecker.check_dapr_pubsub()
        assert result.status == HealthStatus.UNHEALTHY


class TestCheckDaprStateStore:
    @pytest.mark.asyncio
    @respx.mock
    async def test_healthy_on_write_then_read(self):
        respx.post("http://localhost:3500/v1.0/state/statestore").mock(
            return_value=httpx.Response(204)
        )
        respx.get(
            "http://localhost:3500/v1.0/state/statestore/health-check-key"
        ).mock(return_value=httpx.Response(200, json={"test": "x"}))
        # The cleanup delete is fire-and-forget; mock it too
        respx.delete(
            "http://localhost:3500/v1.0/state/statestore/health-check-key"
        ).mock(return_value=httpx.Response(204))
        result = await HealthChecker.check_dapr_state_store()
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    @respx.mock
    async def test_unhealthy_when_write_fails(self):
        respx.post("http://localhost:3500/v1.0/state/statestore").mock(
            return_value=httpx.Response(500)
        )
        result = await HealthChecker.check_dapr_state_store()
        assert result.status == HealthStatus.UNHEALTHY
        assert "write failed" in result.error

    @pytest.mark.asyncio
    @respx.mock
    async def test_unhealthy_when_read_fails(self):
        respx.post("http://localhost:3500/v1.0/state/statestore").mock(
            return_value=httpx.Response(204)
        )
        respx.get(
            "http://localhost:3500/v1.0/state/statestore/health-check-key"
        ).mock(return_value=httpx.Response(500))
        result = await HealthChecker.check_dapr_state_store()
        assert result.status == HealthStatus.UNHEALTHY


class TestDetermineOverallStatus:
    def test_all_healthy_yields_healthy(self):
        checks = {
            "a": ComponentHealth(status=HealthStatus.HEALTHY),
            "b": ComponentHealth(status=HealthStatus.HEALTHY),
        }
        assert HealthChecker.determine_overall_status(checks) == HealthStatus.HEALTHY

    def test_one_unhealthy_yields_unhealthy(self):
        checks = {
            "a": ComponentHealth(status=HealthStatus.HEALTHY),
            "b": ComponentHealth(status=HealthStatus.UNHEALTHY, error="x"),
        }
        assert HealthChecker.determine_overall_status(checks) == HealthStatus.UNHEALTHY

    def test_empty_yields_healthy(self):
        # No checks → vacuously healthy
        assert HealthChecker.determine_overall_status({}) == HealthStatus.HEALTHY
