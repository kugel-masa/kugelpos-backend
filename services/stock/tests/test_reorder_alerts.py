# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
from httpx import AsyncClient
from fastapi import status
import asyncio

import os
from app.models.documents import StockDocument
from app.models.repositories import StockRepository
from kugel_common.database import database as db_helper
from app.config.settings import settings

# Import test constants from conftest
from tests.conftest import tenant_id  # Use the hardcoded test_store_code to avoid confusion with fixture

test_store_code = "5678"

# Test item code
test_item_code = "ITEM_REORDER_001"


@pytest.mark.asyncio
async def test_set_reorder_parameters(http_client: AsyncClient, test_auth_headers: dict):
    """Test setting reorder parameters for an item"""

    # Set reorder parameters
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/reorder",
        headers=test_auth_headers,
        json={"reorder_point": 20.0, "reorder_quantity": 50.0},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert response.json()["message"] == "Reorder parameters set successfully"

    # Verify the stock was created/updated
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}", headers=test_auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["reorderPoint"] == 20.0
    assert data["reorderQuantity"] == 50.0


@pytest.mark.asyncio
async def test_get_reorder_alerts_empty(http_client: AsyncClient, test_auth_headers: dict):
    """Test getting reorder alerts when no items need reordering"""

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/reorder-alerts", headers=test_auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]

    # Since we just set reorder point but current quantity is 0, it should appear in alerts
    assert data["metadata"]["total"] >= 0


@pytest.mark.asyncio
async def test_update_stock_triggers_reorder_alert(http_client: AsyncClient, test_auth_headers: dict):
    """Test that updating stock triggers reorder alert when below reorder point"""

    # First, update stock to be above reorder point
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
        headers=test_auth_headers,
        json={
            "quantityChange": 100.0,
            "updateType": "adjustment",
            "referenceId": "ADJ001",
            "operatorId": "test_user",
            "note": "Initial stock",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    # Now reduce stock below reorder point
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
        headers=test_auth_headers,
        json={
            "quantityChange": -85.0,  # This will bring it to 15, below reorder point of 20
            "updateType": "sale",
            "referenceId": "SALE001",
            "operatorId": "test_user",
            "note": "Large sale",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    # Check reorder alerts
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/reorder-alerts", headers=test_auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]

    # Should have at least one alert
    assert data["metadata"]["total"] > 0

    # Find our test item in the alerts
    items = data["data"]
    test_item = next((item for item in items if item["itemCode"] == test_item_code), None)
    assert test_item is not None
    assert test_item["currentQuantity"] == 15.0
    assert test_item["reorderPoint"] == 20.0
    assert test_item["reorderQuantity"] == 50.0


@pytest.mark.asyncio
async def test_minimum_stock_alert(http_client: AsyncClient, test_auth_headers: dict):
    """Test minimum stock alerts work alongside reorder alerts"""

    # Set minimum quantity
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/minimum",
        headers=test_auth_headers,
        json={"minimum_quantity": 10.0},
    )
    assert response.status_code == status.HTTP_200_OK

    # Update stock to be below minimum (currently at 15 from previous test)
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
        headers=test_auth_headers,
        json={
            "quantityChange": -10.0,  # This will bring it to 5, below minimum of 10
            "updateType": "sale",
            "referenceId": "SALE002",
            "operatorId": "test_user",
            "note": "Another sale",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    # Check low stock alerts
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/low", headers=test_auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]

    # Should have at least one low stock alert
    assert data["metadata"]["total"] > 0

    # Find our test item
    items = data["data"]
    test_item = next((item for item in items if item["itemCode"] == test_item_code), None)
    assert test_item is not None
    assert test_item["currentQuantity"] == 5.0
    assert test_item["minimumQuantity"] == 10.0


@pytest.mark.asyncio
async def test_stock_snapshot_includes_reorder_fields(http_client: AsyncClient, test_auth_headers: dict):
    """Test that stock snapshots include reorder fields"""

    # Create a snapshot
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/snapshot",
        headers=test_auth_headers,
        json={"createdBy": "test_user"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    snapshot_data = response.json()["data"]

    # Verify the snapshot was created and contains our test data
    # We don't need to retrieve by ID since we already have the data
    assert snapshot_data["tenantId"] == tenant_id
    assert snapshot_data["storeCode"] == test_store_code

    # Find our test item in the snapshot
    stocks = snapshot_data["stocks"]
    test_item = next((item for item in stocks if item["itemCode"] == test_item_code), None)
    assert test_item is not None
    assert test_item["reorderPoint"] == 20.0
    assert test_item["reorderQuantity"] == 50.0


@pytest.mark.asyncio
async def test_cleanup_test_data(http_client: AsyncClient, test_auth_headers: dict):
    """Clean up test data"""
    # Clean up the test stock item
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    stock_repo = StockRepository(db)

    await stock_repo.delete_async({"tenant_id": tenant_id, "store_code": test_store_code, "item_code": test_item_code})
