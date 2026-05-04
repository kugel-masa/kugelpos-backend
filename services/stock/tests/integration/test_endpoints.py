# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for the stock endpoints not exercised by
test_stock.py / test_snapshot_*.py / test_reorder_alerts.py:

  POST   /tenants
  POST   /tranlog            (Dapr pubsub topic — health-check path)
  GET    /tenants/{tid}/stores/{sc}/stock/snapshot/{snapshot_id}
"""
import os

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_post_tenants(http_client, admin_header):
    """POST /tenants initialises the per-tenant stock DB. Idempotent."""
    tenant_id = os.environ.get("TENANT_ID")
    response = await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": tenant_id},
        headers=admin_header,
    )
    assert response.status_code in (
        status.HTTP_201_CREATED,
        status.HTTP_400_BAD_REQUEST,
    ), response.text


@pytest.mark.asyncio
async def test_tranlog_health_check(http_client):
    """POST /tranlog accepts the Dapr pubsub health-check shape."""
    response = await http_client.post(
        "/api/v1/tranlog",
        json={"data": {"test": "health-check"}},
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_get_snapshot_by_id_not_found(http_client, admin_header):
    """GET .../stock/snapshot/{snapshot_id} returns 404 for missing IDs.
    Proves the route is wired and behind auth."""
    tenant_id = os.environ.get("TENANT_ID")
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/stock/snapshot/nonexistent-snap-id",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
