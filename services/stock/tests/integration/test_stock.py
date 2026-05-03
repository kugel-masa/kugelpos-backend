# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Stock service tests
"""
import pytest
from httpx import AsyncClient

from app.enums.update_type import UpdateType


@pytest.mark.asyncio
async def test_health_check(http_client: AsyncClient):
    """Test health check endpoint"""
    response = await http_client.get("/health")
    assert response.status_code in [200, 503]  # May be unhealthy if dependencies not running
    data = response.json()
    assert data["service"] == "stock"
    assert "status" in data
    assert "checks" in data


@pytest.mark.asyncio
async def test_get_stock(http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict):
    """Test getting stock information"""
    item_code = "ITEM001"

    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/{item_code}", headers=test_auth_headers
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert data["itemCode"] == item_code
    assert data["tenantId"] == test_tenant_id
    assert data["storeCode"] == test_store_code
    assert "currentQuantity" in data
    assert "minimumQuantity" in data


@pytest.mark.asyncio
async def test_update_stock(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test updating stock quantity"""
    item_code = "ITEM001"

    # Update stock with a purchase
    update_data = {
        "quantityChange": 50.0,
        "updateType": UpdateType.PURCHASE.value,
        "referenceId": "PO001",
        "note": "Test purchase",
    }

    response = await http_client.put(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/{item_code}/update",
        json=update_data,
        headers=test_auth_headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert data["itemCode"] == item_code
    assert data["quantityChange"] == 50.0
    assert data["updateType"] == UpdateType.PURCHASE.value
    # Don't assume initial quantity - just verify the change is correct
    assert data["afterQuantity"] == data["beforeQuantity"] + 50.0


@pytest.mark.asyncio
async def test_stock_history(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test getting stock update history"""
    item_code = "ITEM001"

    # First, make some updates
    updates = [
        {"quantityChange": 100.0, "updateType": UpdateType.INITIAL.value},
        {"quantityChange": -20.0, "updateType": UpdateType.SALE.value},
        {"quantityChange": 30.0, "updateType": UpdateType.PURCHASE.value},
    ]

    for update in updates:
        response = await http_client.put(
            f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/{item_code}/update",
            json=update,
            headers=test_auth_headers,
        )
        assert response.status_code == 200

    # Get history
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/{item_code}/history",
        headers=test_auth_headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert "data" in data
    assert "metadata" in data
    assert len(data["data"]) >= len(updates)
    assert data["metadata"]["total"] >= len(updates)
    assert data["metadata"]["page"] == 1
    assert data["metadata"]["limit"] == 100


@pytest.mark.asyncio
async def test_negative_stock_allowed(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test that negative stock is allowed (backorders)"""
    item_code = "ITEM002"

    # Try to sell more than available
    update_data = {
        "quantityChange": -1000.0,  # Large negative quantity
        "updateType": UpdateType.SALE.value,
        "referenceId": "SALE001",
    }

    response = await http_client.put(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/{item_code}/update",
        json=update_data,
        headers=test_auth_headers,
    )

    # Should succeed with 200 since we allow negative stock
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert data["afterQuantity"] < 0  # Stock should be negative


@pytest.mark.asyncio
async def test_get_store_stocks(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test getting all stocks for a store"""
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock", headers=test_auth_headers
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert "data" in data
    assert "metadata" in data
    assert len(data["data"]) > 0
    assert data["metadata"]["total"] > 0
    assert data["metadata"]["page"] == 1
    assert data["metadata"]["limit"] == 100


@pytest.mark.asyncio
async def test_create_snapshot(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test creating a stock snapshot"""
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
    assert "totalItems" in data
    assert "stocks" in data


@pytest.mark.asyncio
async def test_get_snapshots(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test getting stock snapshots"""
    # First create a snapshot
    await http_client.post(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshot",
        json={"createdBy": "test_user"},
        headers=test_auth_headers,
    )

    # Get snapshots using the new endpoint
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock/snapshots", headers=test_auth_headers
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert "data" in data
    assert "metadata" in data
    assert len(data["data"]) > 0
    assert data["metadata"]["total"] > 0
    assert data["metadata"]["page"] == 1
    assert data["metadata"]["limit"] == 100  # Default limit for new endpoint


@pytest.mark.asyncio
async def test_pagination_parameters(
    http_client: AsyncClient, test_tenant_id: str, test_store_code: str, test_auth_headers: dict
):
    """Test pagination with page and limit parameters"""
    # Test with page 2 and limit 5
    response = await http_client.get(
        f"/api/v1/tenants/{test_tenant_id}/stores/{test_store_code}/stock?page=2&limit=5", headers=test_auth_headers
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert "data" in data
    assert "metadata" in data
    assert data["metadata"]["page"] == 2
    assert data["metadata"]["limit"] == 5
    assert len(data["data"]) <= 5


@pytest.mark.asyncio
async def test_dapr_subscribe(http_client: AsyncClient):
    """Test Dapr subscription endpoint"""
    response = await http_client.get("/dapr/subscribe")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["topic"] == "topic-tranlog"
    assert data[0]["route"] == "/api/v1/tranlog"
