"""Test WebSocket alerts for new items without existing alerts"""

import pytest
import websockets
import asyncio
import json
from httpx import AsyncClient
from fastapi import status
from datetime import datetime
import uuid

# Import test constants from conftest
from tests.conftest import tenant_id  # Use the hardcoded test_store_code to avoid confusion with fixture

test_store_code = "5678"


@pytest.mark.asyncio
async def test_websocket_reorder_alert_new_item(
    test_auth_headers: dict, http_client: AsyncClient, websocket_base_url: str
):
    """Test WebSocket reorder alert for a new item"""
    # Use a unique item code to avoid cooldown issues
    unique_item_code = f"ITEM_WS_{uuid.uuid4().hex[:8].upper()}"

    # Extract token for WebSocket
    token = test_auth_headers["Authorization"].replace("Bearer ", "")

    # First create the item with stock ABOVE reorder point (no alert should trigger)
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{unique_item_code}/update",
        headers=test_auth_headers,
        json={
            "updateType": "adjustment",
            "quantityChange": 100.0,  # Start with 100 units
            "referenceId": "INIT_001",
            "operatorId": "test_user",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    # Set reorder parameters (reorder at 50, order 100)
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{unique_item_code}/reorder",
        headers=test_auth_headers,
        json={"reorder_point": 50.0, "reorder_quantity": 100.0},
    )
    assert response.status_code == status.HTTP_200_OK

    # Connect to WebSocket
    uri = f"{websocket_base_url}/api/v1/ws/{tenant_id}/{test_store_code}?token={token}"

    async with websockets.connect(uri) as websocket:
        # Skip initial connection message
        initial_msg = await websocket.recv()
        connection_data = json.loads(initial_msg)
        assert connection_data["type"] == "connection"

        # Skip any initial alerts (there shouldn't be one for our new item)
        while True:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                data = json.loads(msg)
                # Make sure we're not getting an alert for our new item
                if data.get("item_code") == unique_item_code:
                    pytest.fail(f"Unexpected initial alert for {unique_item_code}")
            except asyncio.TimeoutError:
                break

        # Now update stock to trigger reorder alert (reduce from 100 to 40)
        response = await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{unique_item_code}/update",
            headers=test_auth_headers,
            json={
                "updateType": "sale",
                "quantityChange": -60.0,  # Reduce to 40 (below reorder point 50)
                "referenceId": "SALE_001",
                "operatorId": "test_user",
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Wait for WebSocket message
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            alert_data = json.loads(message)

            # Verify alert structure
            assert alert_data["type"] == "stock_alert"
            assert alert_data["alert_type"] == "reorder_point"
            assert alert_data["tenant_id"] == tenant_id
            assert alert_data["store_code"] == test_store_code
            assert alert_data["item_code"] == unique_item_code
            assert alert_data["current_quantity"] == 40.0
            assert alert_data["reorder_point"] == 50.0
            assert alert_data["reorder_quantity"] == 100.0
            assert "timestamp" in alert_data

        except asyncio.TimeoutError:
            pytest.fail("WebSocket message not received within timeout")
