import pytest
from datetime import datetime

from app.models.documents.snapshot_schedule_document import SnapshotScheduleDocument

# These are integration tests that hit the actual API endpoints


@pytest.mark.asyncio
async def test_get_snapshot_schedule_default(http_client, test_tenant_id, test_auth_headers):
    """Test getting snapshot schedule returns defaults when none exists."""
    # First, delete any existing schedule to ensure clean state
    await http_client.delete(f"/api/v1/tenants/{test_tenant_id}/stock/snapshot-schedule", headers=test_auth_headers)

    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stock/snapshot-schedule", headers=test_auth_headers
    )

    # Print response details for debugging
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["tenant_id"] == test_tenant_id
    assert data["data"]["enabled"] is True
    assert data["data"]["schedule_interval"] == "daily"
    assert data["data"]["schedule_hour"] == 2
    assert data["data"]["retention_days"] == 30


@pytest.mark.asyncio
async def test_update_snapshot_schedule_success(http_client, test_tenant_id, test_auth_headers):
    """Test updating snapshot schedule successfully."""
    update_data = {
        "enabled": True,
        "schedule_interval": "monthly",
        "schedule_hour": 4,
        "schedule_minute": 15,
        "retention_days": 90,
        "schedule_day_of_month": 1,
        "target_stores": ["store1", "store2"],
    }

    response = await http_client.put(
        f"/api/v1/tenants/{test_tenant_id}/stock/snapshot-schedule", headers=test_auth_headers, json=update_data
    )

    # Print response details for debugging if error
    if response.status_code != 200:
        print(f"Update Response status: {response.status_code}")
        print(f"Update Response body: {response.text}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Snapshot schedule updated successfully"
    assert data["data"]["schedule_interval"] == "monthly"
    assert data["data"]["retention_days"] == 90


@pytest.mark.asyncio
async def test_get_snapshot_schedule_after_update(http_client, test_tenant_id, test_auth_headers):
    """Test getting snapshot schedule after updating it."""
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stock/snapshot-schedule", headers=test_auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Should return the previously updated values
    assert data["data"]["schedule_interval"] == "monthly"
    assert data["data"]["retention_days"] == 90


@pytest.mark.asyncio
async def test_update_snapshot_schedule_validation_error(http_client, test_tenant_id, test_auth_headers):
    """Test updating snapshot schedule with validation errors."""
    # Invalid data - missing required day_of_week for weekly
    update_data = {"enabled": True, "schedule_interval": "weekly", "schedule_hour": 2, "retention_days": 30}

    response = await http_client.put(
        f"/api/v1/tenants/{test_tenant_id}/stock/snapshot-schedule", headers=test_auth_headers, json=update_data
    )

    assert response.status_code == 500  # Validation error should be caught


@pytest.mark.asyncio
async def test_update_snapshot_schedule_retention_validation(http_client, test_tenant_id, test_auth_headers):
    """Test retention days validation."""
    # Retention days too high
    update_data = {
        "enabled": True,
        "schedule_interval": "daily",
        "schedule_hour": 2,
        "retention_days": 400,  # Exceeds max of 365
    }

    response = await http_client.put(
        f"/api/v1/tenants/{test_tenant_id}/stock/snapshot-schedule", headers=test_auth_headers, json=update_data
    )

    assert response.status_code == 500  # Should fail validation


@pytest.mark.asyncio
async def test_delete_snapshot_schedule(http_client, test_tenant_id, test_auth_headers):
    """Test deleting snapshot schedule."""
    response = await http_client.delete(
        f"/api/v1/tenants/{test_tenant_id}/stock/snapshot-schedule", headers=test_auth_headers
    )

    # Print response details for debugging if error
    if response.status_code != 200:
        print(f"Delete Response status: {response.status_code}")
        print(f"Delete Response body: {response.text}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Snapshot schedule deleted successfully"
    assert data["data"]["deleted"] is True


@pytest.mark.asyncio
async def test_get_snapshot_schedule_after_delete(http_client, test_tenant_id, test_auth_headers):
    """Test getting snapshot schedule after deletion returns defaults."""
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stock/snapshot-schedule", headers=test_auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Should be back to defaults after deletion
    assert data["data"]["tenant_id"] == test_tenant_id
    assert data["data"]["enabled"] is True
    assert data["data"]["schedule_interval"] == "daily"
    assert data["data"]["schedule_hour"] == 2
    assert data["data"]["retention_days"] == 30
