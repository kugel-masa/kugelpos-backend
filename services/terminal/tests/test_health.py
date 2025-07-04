# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""Test health check endpoint for terminal service."""

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
    assert data["service"] == "terminal"

    # Check version format
    assert data["version"] == "1.0.0"

    # Check checks structure - terminal service checks MongoDB, Dapr pub/sub for cash and open/close logs, and background jobs
    assert "mongodb" in data["checks"]
    assert "dapr_sidecar" in data["checks"]
    assert "dapr_pubsub_cashlog" in data["checks"]
    assert "dapr_pubsub_opencloselog" in data["checks"]
    assert "background_jobs" in data["checks"]

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
async def test_health_endpoint_background_jobs_details(http_client: AsyncClient):
    """Test the /health endpoint properly reports background job details."""
    response = await http_client.get("/health")

    assert response.status_code == 200

    data = response.json()

    # Check background jobs component exists
    assert "background_jobs" in data["checks"]
    bg_jobs = data["checks"]["background_jobs"]

    # Check status
    assert "status" in bg_jobs
    assert bg_jobs["status"] in [HealthStatus.HEALTHY.value, HealthStatus.UNHEALTHY.value]

    # If healthy, check for job details
    if bg_jobs["status"] == HealthStatus.HEALTHY.value and "details" in bg_jobs and bg_jobs["details"]:
        assert "scheduler_running" in bg_jobs["details"]
        assert "job_count" in bg_jobs["details"]
        assert "job_names" in bg_jobs["details"]
        assert isinstance(bg_jobs["details"]["job_names"], list)
