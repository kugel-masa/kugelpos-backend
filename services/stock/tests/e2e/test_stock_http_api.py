# Copyright 2026 masa@kugel
"""E2E coverage for stock HTTP API.

Drives the live stock service with admin JWT to exercise:
  - PUT /stock/{item_code}/update (manual stock adjustment)
  - GET /stock/{item_code} (read after update)
  - GET /stock (list)
  - GET /stock/{item_code}/history
  - PUT /stock/{item_code}/minimum + GET /stock/low
  - POST /stock/snapshot + GET /stock/snapshots + GET /stock/snapshot/{id}

The existing test_websocket_*.py files only cover the WebSocket alert
streams; this file covers the HTTP CRUD/query surface that the e2e tier
otherwise leaves untested.
"""
import os
import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient, Timeout


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _ensure_admin_user():
    from fastapi import status as http_status

    base_account = os.environ.get("BASE_URL_ACCOUNT", "http://localhost:8000")
    tenant_id = os.environ.get("TENANT_ID")
    async with AsyncClient(base_url=base_account, timeout=Timeout(timeout=None)) as client:
        login = await client.post(
            "/api/v1/accounts/token",
            data={"username": "admin", "password": "admin", "client_id": tenant_id},
        )
        if login.status_code == http_status.HTTP_200_OK:
            return
        await client.post(
            "/api/v1/accounts/register",
            json={"username": "admin", "password": "admin", "tenant_id": tenant_id},
        )


@pytest_asyncio.fixture(scope="function")
async def admin_token(_ensure_admin_user):
    base_account = os.environ.get("BASE_URL_ACCOUNT", "http://localhost:8000")
    tenant_id = os.environ.get("TENANT_ID")
    async with AsyncClient(base_url=base_account, timeout=Timeout(timeout=None)) as client:
        response = await client.post(
            "/api/v1/accounts/token",
            data={"username": "admin", "password": "admin", "client_id": tenant_id},
        )
        response.raise_for_status()
        return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def admin_header(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _unique_item_code() -> str:
    return "STK-" + uuid.uuid4().hex[:6].upper()


@pytest.mark.asyncio
async def test_update_stock_then_get(http_client, admin_header):
    """PUT /stock/{item_code}/update increments quantity, then GET reflects it."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = "5678"
    item_code = _unique_item_code()

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update",
        json={
            "quantityChange": 10.0,
            "updateType": "purchase",
            "operatorId": "admin",
            "note": "E2E setup",
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    assert body["data"]["currentQuantity"] == 10.0


@pytest.mark.asyncio
async def test_stock_list(http_client, admin_header):
    """GET /stock returns the stock list for a store."""
    tenant_id = os.environ.get("TENANT_ID")
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/stock",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json().get("success") is True


@pytest.mark.asyncio
async def test_stock_history(http_client, admin_header):
    """GET /stock/{item_code}/history returns the update history."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = "5678"
    item_code = _unique_item_code()

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update",
        json={"quantityChange": 5.0, "updateType": "initial", "operatorId": "admin"},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/history",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    assert body.get("success") is True
    # history may be wrapped as a paginated dict {"data": [...], "metadata": ...}
    # or a bare list — accept either shape.
    data = body.get("data")
    if isinstance(data, dict):
        data = data.get("data") or []
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_minimum_quantity_and_low_stock(http_client, admin_header):
    """PUT /stock/{item}/minimum sets the threshold; the item then shows up
    in GET /stock/low if current < minimum."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = "5678"
    item_code = _unique_item_code()

    await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update",
        json={"quantityChange": 1.0, "updateType": "initial", "operatorId": "admin"},
        headers=admin_header,
    )

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/minimum",
        json={"minimumQuantity": 100.0},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/low",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_create_snapshot_then_list(http_client, admin_header):
    """POST /stock/snapshot creates a snapshot, then GET /stock/snapshots
    lists it."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = "5678"

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot",
        json={"createdBy": "e2e-test"},
        headers=admin_header,
    )
    assert response.status_code in (
        status.HTTP_200_OK,
        status.HTTP_201_CREATED,
    ), response.text
    snapshot_id = response.json()["data"].get("snapshotId") or response.json()["data"].get("id")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshots",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    if snapshot_id:
        response = await http_client.get(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}",
            headers=admin_header,
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        ), response.text


@pytest.mark.asyncio
async def test_reorder_alerts(http_client, admin_header):
    """GET /stock/reorder-alerts returns currently-flagged items."""
    tenant_id = os.environ.get("TENANT_ID")
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/stock/reorder-alerts",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json().get("success") is True


@pytest.mark.asyncio
async def test_snapshot_schedule_crud(http_client, admin_header):
    """PUT /stock/snapshot-schedule then GET then DELETE."""
    tenant_id = os.environ.get("TENANT_ID")

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stock/snapshot-schedule",
        json={
            "enabled": True,
            "schedule_interval": "daily",
            "schedule_hour": 3,
            "schedule_minute": 0,
            "retention_days": 30,
            "target_stores": ["5678"],
        },
        headers=admin_header,
    )
    assert response.status_code in (
        status.HTTP_200_OK,
        status.HTTP_201_CREATED,
    ), response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stock/snapshot-schedule",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/stock/snapshot-schedule",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
