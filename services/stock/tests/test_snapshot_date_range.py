# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Stock snapshot date range functionality tests
"""
import pytest
import asyncio
from httpx import AsyncClient
from datetime import datetime, timedelta
from kugel_common.utils.misc import get_app_time_str


@pytest.mark.asyncio
async def test_create_snapshot_with_generate_date_time(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test creating a stock snapshot with generate_date_time"""
    response = await http_client.post(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshot",
        json={"createdBy": "test_user"},
        headers=test_auth_headers,
    )

    assert response.status_code == 201
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert data["tenantId"] == test_tenant_id
    assert data["storeCode"] == test_store_code
    assert "generateDateTime" in data
    assert data["generateDateTime"] is not None


@pytest.mark.asyncio
async def test_get_snapshots_by_date_range(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test getting stock snapshots by date range"""
    # Create multiple snapshots with small delays
    for i in range(3):
        await http_client.post(
            f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshot",
            json={"createdBy": f"test_user_{i}"},
            headers=test_auth_headers,
        )
        if i < 2:
            await asyncio.sleep(0.1)  # Small delay between snapshots

    # Get current time for date range
    current_time = get_app_time_str()
    start_time = get_app_time_str(datetime.now() - timedelta(minutes=5))

    # Get snapshots by date range
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshots",
        params={"start_date": start_time, "end_date": current_time, "page": 1, "limit": 10},
        headers=test_auth_headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert "data" in data
    assert "metadata" in data

    # Check metadata
    metadata = data["metadata"]
    assert metadata["page"] == 1
    assert metadata["limit"] == 10
    assert metadata["sort"] == "generate_date_time:-1"
    assert "filter" in metadata
    assert metadata["filter"]["start_date"] == start_time
    assert metadata["filter"]["end_date"] == current_time

    # Check snapshots
    snapshots = data["data"]
    assert len(snapshots) >= 3  # Should have at least the 3 we created
    for snapshot in snapshots:
        assert "generateDateTime" in snapshot
        assert snapshot["generateDateTime"] is not None
        assert snapshot["generateDateTime"] >= start_time
        assert snapshot["generateDateTime"] <= current_time


@pytest.mark.asyncio
async def test_get_snapshots_without_date_range(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test getting all snapshots without date range filter"""
    # Create a new snapshot to ensure we have one with generate_date_time
    await http_client.post(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshot",
        json={"createdBy": "test_no_range"},
        headers=test_auth_headers,
    )

    # Get snapshots without date range
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshots",
        params={"page": 1, "limit": 100},
        headers=test_auth_headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]

    # Check that filter is None when no date range is provided
    metadata = data["metadata"]
    assert metadata["filter"] is None or metadata["filter"] == {}

    # All returned snapshots should have generate_date_time
    for snapshot in data["data"]:
        assert "generateDateTime" in snapshot
        assert snapshot["generateDateTime"] is not None


@pytest.mark.asyncio
async def test_get_snapshots_with_start_date_only(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test getting snapshots with only start date"""
    start_time = get_app_time_str(datetime.now() - timedelta(hours=1))

    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshots",
        params={"start_date": start_time, "page": 1, "limit": 10},
        headers=test_auth_headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]

    # Check filter contains only start_date
    metadata = data["metadata"]
    assert "filter" in metadata
    assert metadata["filter"]["start_date"] == start_time
    assert "end_date" not in metadata["filter"]


@pytest.mark.asyncio
async def test_get_snapshots_with_end_date_only(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test getting snapshots with only end date"""
    end_time = get_app_time_str()

    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshots",
        params={"end_date": end_time, "page": 1, "limit": 10},
        headers=test_auth_headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]

    # Check filter contains only end_date
    metadata = data["metadata"]
    assert "filter" in metadata
    assert metadata["filter"]["end_date"] == end_time
    assert "start_date" not in metadata["filter"]


@pytest.mark.asyncio
async def test_get_snapshots_pagination(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test pagination for snapshot date range API"""
    # Create multiple snapshots
    for i in range(5):
        await http_client.post(
            f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshot",
            json={"createdBy": f"pagination_test_{i}"},
            headers=test_auth_headers,
        )
        await asyncio.sleep(0.05)

    # Get first page
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshots",
        params={"page": 1, "limit": 2},
        headers=test_auth_headers,
    )

    assert response.status_code == 200
    result = response.json()
    data = result["data"]

    # Check pagination
    assert len(data["data"]) <= 2
    metadata = data["metadata"]
    assert metadata["page"] == 1
    assert metadata["limit"] == 2
    assert metadata["total"] >= 5  # Should have at least the 5 we created

    # Get second page
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshots",
        params={"page": 2, "limit": 2},
        headers=test_auth_headers,
    )

    assert response.status_code == 200
    result = response.json()
    data = result["data"]

    # Check second page
    assert len(data["data"]) <= 2
    metadata = data["metadata"]
    assert metadata["page"] == 2
    assert metadata["limit"] == 2
