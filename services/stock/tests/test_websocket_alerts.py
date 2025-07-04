# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import asyncio
import json
from httpx import AsyncClient
from fastapi import status
import websockets
from datetime import datetime

# Import test constants from conftest
from tests.conftest import tenant_id  # Use the hardcoded test_store_code to avoid confusion with fixture

test_store_code = "5678"

# Test item codes will be generated uniquely for each test


@pytest.mark.asyncio
async def test_websocket_connection(test_auth_headers: dict, websocket_base_url: str):
    """Test WebSocket connection establishment"""
    # Extract token from auth headers
    token = test_auth_headers["Authorization"].replace("Bearer ", "")

    # Connect to WebSocket
    uri = f"{websocket_base_url}/api/v1/ws/{tenant_id}/{test_store_code}?token={token}"

    async with websockets.connect(uri) as websocket:
        # Receive initial connection message
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "connection"
        assert data["status"] == "connected"

        # Send a ping to verify connection
        await websocket.ping()

        # Wait a bit to ensure connection is stable
        await asyncio.sleep(0.1)

        # Close connection
        await websocket.close()


@pytest.mark.asyncio
async def test_websocket_reorder_alert(http_client: AsyncClient, test_auth_headers: dict, websocket_base_url: str):
    """Test WebSocket alerts for reorder point"""
    import uuid

    # Generate unique item code for this test
    test_item_code = f"WS_REORDER_{uuid.uuid4().hex[:8].upper()}"

    # Extract token from auth headers
    token = test_auth_headers["Authorization"].replace("Bearer ", "")

    # First, create a stock item with initial quantity
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
        headers=test_auth_headers,
        json={
            "updateType": "adjustment",
            "quantityChange": 100.0,
            "referenceId": "INIT_WS_001",
            "operatorId": "test_user",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    # Set reorder parameters
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/reorder",
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

        # Skip any initial alerts that were sent on connection
        while True:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                # Continue reading until we get a timeout (no more initial messages)
            except asyncio.TimeoutError:
                break

        # Update stock to trigger reorder alert
        response = await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
            headers=test_auth_headers,
            json={
                "updateType": "sale",
                "quantityChange": -60.0,  # Reduce from 100 to 40 (below reorder point 50)
                "referenceId": "TEST_WS_001",
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
            assert alert_data["item_code"] == test_item_code
            assert alert_data["current_quantity"] == 40.0
            assert alert_data["reorder_point"] == 50.0
            assert "timestamp" in alert_data

        except asyncio.TimeoutError:
            pytest.fail("WebSocket message not received within timeout")

    # Cleanup - use a separate HTTP request to avoid event loop issues
    try:
        # Clean up by setting quantity to 0 (effectively marking as deleted)
        await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
            headers=test_auth_headers,
            json={
                "updateType": "adjustment",
                "quantityChange": -100.0,  # Remove all stock
                "referenceId": "CLEANUP",
                "operatorId": "test_user",
            },
        )
    except Exception:
        pass  # Ignore cleanup errors


@pytest.mark.asyncio
async def test_websocket_minimum_stock_alert(
    http_client: AsyncClient, test_auth_headers: dict, websocket_base_url: str
):
    """Test WebSocket alerts for minimum stock"""
    import uuid

    # Generate unique item code for this test
    test_item_code = f"WS_MINIMUM_{uuid.uuid4().hex[:8].upper()}"

    # Extract token from auth headers
    token = test_auth_headers["Authorization"].replace("Bearer ", "")

    # Create stock item with minimum quantity
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
        headers=test_auth_headers,
        json={
            "updateType": "adjustment",
            "quantityChange": 50.0,  # Start above minimum
            "referenceId": "INIT_MIN_001",
            "operatorId": "test_user",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    # Set minimum quantity
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/minimum",
        headers=test_auth_headers,
        json={"minimum_quantity": 10.0},
    )
    assert response.status_code == status.HTTP_200_OK

    # Connect to WebSocket
    uri = f"{websocket_base_url}/api/v1/ws/{tenant_id}/{test_store_code}?token={token}"

    async with websockets.connect(uri) as websocket:
        # Skip initial messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                break

        # Update stock to trigger minimum stock alert
        response = await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
            headers=test_auth_headers,
            json={
                "updateType": "sale",
                "quantityChange": -45.0,  # Reduce from 50 to 5 (below minimum 10)
                "referenceId": "TEST_WS_002",
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
            assert alert_data["alert_type"] == "minimum_stock"
            assert alert_data["tenant_id"] == tenant_id
            assert alert_data["store_code"] == test_store_code
            assert alert_data["item_code"] == test_item_code
            assert alert_data["current_quantity"] == 5.0
            assert alert_data["minimum_quantity"] == 10.0
            assert "timestamp" in alert_data

        except asyncio.TimeoutError:
            pytest.fail("WebSocket message not received within timeout")

    # Cleanup - use a separate HTTP request to avoid event loop issues
    try:
        # Clean up by setting quantity to 0 (effectively marking as deleted)
        await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
            headers=test_auth_headers,
            json={
                "updateType": "adjustment",
                "quantityChange": -100.0,  # Remove all stock
                "referenceId": "CLEANUP",
                "operatorId": "test_user",
            },
        )
    except Exception:
        pass  # Ignore cleanup errors


@pytest.mark.asyncio
async def test_websocket_no_alert_when_above_thresholds(
    http_client: AsyncClient, test_auth_headers: dict, websocket_base_url: str
):
    """Test that no alert is sent when stock is above thresholds"""
    import uuid

    # Generate unique item code for this test
    test_item_code = f"WS_NOALERT_{uuid.uuid4().hex[:8].upper()}"

    # Extract token from auth headers
    token = test_auth_headers["Authorization"].replace("Bearer ", "")

    # Create stock with high quantity and set reorder point
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
        headers=test_auth_headers,
        json={
            "updateType": "purchase",
            "quantityChange": 100.0,  # Start with 100
            "referenceId": "TEST_WS_003",
            "operatorId": "test_user",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    # Set reorder point
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/reorder",
        headers=test_auth_headers,
        json={"reorder_point": 50.0, "reorder_quantity": 100.0},
    )
    assert response.status_code == status.HTTP_200_OK

    # Connect to WebSocket
    uri = f"{websocket_base_url}/api/v1/ws/{tenant_id}/{test_store_code}?token={token}"

    async with websockets.connect(uri) as websocket:
        # Skip initial messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                break

        # Update stock but stay above thresholds
        response = await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
            headers=test_auth_headers,
            json={
                "updateType": "sale",
                "quantityChange": -20.0,  # Reduce to 80 (still above reorder point 50)
                "referenceId": "TEST_WS_004",
                "operatorId": "test_user",
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Wait for a short time - no message should be received
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
            pytest.fail(f"Unexpected WebSocket message received: {message}")
        except asyncio.TimeoutError:
            # This is expected - no alert should be sent
            pass

    # Cleanup - use a separate HTTP request to avoid event loop issues
    try:
        # Clean up by setting quantity to 0 (effectively marking as deleted)
        await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
            headers=test_auth_headers,
            json={
                "updateType": "adjustment",
                "quantityChange": -100.0,  # Remove all stock
                "referenceId": "CLEANUP",
                "operatorId": "test_user",
            },
        )
    except Exception:
        pass  # Ignore cleanup errors


@pytest.mark.asyncio
async def test_websocket_multiple_clients(http_client: AsyncClient, test_auth_headers: dict, websocket_base_url: str):
    """Test that alerts are sent to multiple connected clients"""
    import uuid

    # Generate unique item code for this test
    test_item_code = f"WS_MULTI_{uuid.uuid4().hex[:8].upper()}"

    # Extract token from auth headers
    token = test_auth_headers["Authorization"].replace("Bearer ", "")

    # Create stock with reorder point
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
        headers=test_auth_headers,
        json={
            "updateType": "adjustment",
            "quantityChange": 100.0,
            "referenceId": "INIT_MULTI_001",
            "operatorId": "test_user",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    # Set reorder point
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/reorder",
        headers=test_auth_headers,
        json={"reorder_point": 50.0, "reorder_quantity": 100.0},
    )
    assert response.status_code == status.HTTP_200_OK

    # Connect two WebSocket clients
    uri = f"{websocket_base_url}/api/v1/ws/{tenant_id}/{test_store_code}?token={token}"

    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
        # Skip initial messages for both connections
        for ws in [ws1, ws2]:
            while True:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    break

        # Update stock to trigger alert
        response = await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
            headers=test_auth_headers,
            json={
                "updateType": "sale",
                "quantityChange": -60.0,  # Reduce to 40 (below reorder point 50)
                "referenceId": "TEST_WS_005",
                "operatorId": "test_user",
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Both clients should receive the alert
        try:
            message1 = await asyncio.wait_for(ws1.recv(), timeout=5.0)
            message2 = await asyncio.wait_for(ws2.recv(), timeout=5.0)

            alert1 = json.loads(message1)
            alert2 = json.loads(message2)

            # Both should receive the same alert
            assert alert1["type"] == "stock_alert"
            assert alert2["type"] == "stock_alert"
            assert alert1["item_code"] == test_item_code
            assert alert2["item_code"] == test_item_code
            assert alert1["current_quantity"] == 40.0
            assert alert2["current_quantity"] == 40.0

        except asyncio.TimeoutError:
            pytest.fail("WebSocket messages not received within timeout")

    # Cleanup - use a separate HTTP request to avoid event loop issues
    try:
        # Clean up by setting quantity to 0 (effectively marking as deleted)
        await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{test_store_code}/stock/{test_item_code}/update",
            headers=test_auth_headers,
            json={
                "updateType": "adjustment",
                "quantityChange": -100.0,  # Remove all stock
                "referenceId": "CLEANUP",
                "operatorId": "test_user",
            },
        )
    except Exception:
        pass  # Ignore cleanup errors


@pytest.mark.asyncio
async def test_websocket_unauthorized_connection(websocket_base_url: str):
    """Test that WebSocket connection fails without valid token"""
    # Try to connect without token
    uri = f"{websocket_base_url}/api/v1/ws/{tenant_id}/{test_store_code}"

    try:
        async with websockets.connect(uri) as websocket:
            # Connection should be closed by server with policy violation
            pass
    except websockets.exceptions.ConnectionClosedError as e:
        # Expected: connection closed with code 1008 (policy violation)
        assert e.code == 1008
        assert "No token provided" in e.reason
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")

    # Try to connect with invalid token
    uri = f"{websocket_base_url}/api/v1/ws/{tenant_id}/{test_store_code}?token=invalid_token"

    try:
        async with websockets.connect(uri) as websocket:
            # Connection should be closed by server with policy violation
            pass
    except websockets.exceptions.ConnectionClosedError as e:
        # Expected: connection closed with code 1008 (policy violation)
        assert e.code == 1008
        assert "Authentication failed" in e.reason
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")


# Cleanup is now done in each individual test
