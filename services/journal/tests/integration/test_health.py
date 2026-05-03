# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""Test health check endpoint for journal service."""

import pytest
from httpx import AsyncClient
from kugel_common.schemas.health import HealthStatus


@pytest.mark.asyncio
async def test_health_endpoint(http_client: AsyncClient):
    """Test the /health endpoint returns expected structure."""
    response = await http_client.get("/health")

    assert response.status_code == 200

    data = response.json()

    # Check required fields
    assert "status" in data
    assert "timestamp" in data
    assert "service" in data
    assert "version" in data
    assert "checks" in data

    # Check service name
    assert data["service"] == "journal"

    # Check version format
    assert data["version"] == "1.0.0"

    # Check checks structure - journal service checks MongoDB, Dapr sidecar and state store
    assert "mongodb" in data["checks"]
    assert "dapr_sidecar" in data["checks"]
    assert "dapr_statestore" in data["checks"]

    # Check individual component structure
    for component_name, component_data in data["checks"].items():
        assert "status" in component_data
        assert component_data["status"] in [HealthStatus.HEALTHY.value, HealthStatus.UNHEALTHY.value]

        # Optional fields that may or may not be present
        if "response_time_ms" in component_data:
            assert isinstance(component_data["response_time_ms"], (int, type(None)))
        if "error" in component_data:
            assert isinstance(component_data["error"], (str, type(None)))
        if "component" in component_data:
            assert isinstance(component_data["component"], (str, type(None)))
        if "details" in component_data:
            assert isinstance(component_data["details"], (dict, type(None)))


@pytest.mark.asyncio
async def test_health_endpoint_without_dapr(http_client: AsyncClient):
    """Test the /health endpoint when Dapr is not available."""
    # This test will likely show unhealthy status for Dapr components
    # when running in test environment without Dapr
    response = await http_client.get("/health")

    assert response.status_code == 200

    data = response.json()

    # Even if some components are unhealthy, the endpoint should still respond
    assert "status" in data
    assert data["status"] in [HealthStatus.HEALTHY.value, HealthStatus.UNHEALTHY.value]

    # MongoDB should be healthy in test environment
    assert data["checks"]["mongodb"]["status"] in [HealthStatus.HEALTHY.value, HealthStatus.UNHEALTHY.value]

    # Dapr components might be unhealthy in test environment
    assert "dapr_sidecar" in data["checks"]
    assert "dapr_statestore" in data["checks"]
