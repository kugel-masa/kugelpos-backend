# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for report endpoints not exercised by the existing
sales-report regression tests:

  POST   /tenants
  POST   /tenants/{tid}/stores/{sc}/terminals/{tn}/transactions
  POST   /tranlog            (Dapr pubsub topic — health-check path covered here)
  POST   /cashlog            (same)
  POST   /opencloselog       (same)
  GET    /tenants/{tid}/stores/{sc}/reports
  GET    /tenants/{tid}/stores/{sc}/terminals/{tn}/reports
"""
import os
from datetime import datetime

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_post_tenants(http_client, admin_header):
    """POST /tenants initialises the per-tenant report DB. Idempotent."""
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
    """POST /tranlog accepts the Dapr pubsub health-check message shape."""
    response = await http_client.post(
        "/api/v1/tranlog",
        json={"data": {"test": "health-check"}},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    assert body.get("status") == "SUCCESS"


@pytest.mark.asyncio
async def test_cashlog_health_check(http_client):
    """POST /cashlog accepts the Dapr pubsub health-check message shape."""
    response = await http_client.post(
        "/api/v1/cashlog",
        json={"data": {"test": "health-check"}},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    assert body.get("status") == "SUCCESS"


@pytest.mark.asyncio
async def test_opencloselog_health_check(http_client):
    """POST /opencloselog accepts the Dapr pubsub health-check message shape."""
    response = await http_client.post(
        "/api/v1/opencloselog",
        json={"data": {"test": "health-check"}},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    assert body.get("status") == "SUCCESS"


@pytest.mark.asyncio
async def test_post_transactions_invalid_body(http_client, admin_header):
    """POST .../transactions must reject an empty body with a *validation*
    error (400 or 422), not crash with a 500. A 500 here would mean the
    handler is missing input validation."""
    tenant_id = os.environ.get("TENANT_ID")

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/5678/terminals/9/transactions",
        json={},
        headers=admin_header,
    )
    assert response.status_code in (
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    ), response.text


@pytest.mark.asyncio
async def test_get_store_reports_empty(http_client, admin_header):
    """GET /reports returns successfully (empty/zero data) for a fresh store
    with no transactions."""
    tenant_id = os.environ.get("TENANT_ID")
    business_date = datetime.now().strftime("%Y%m%d")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/reports",
        params={
            "report_scope": "flash",
            "report_type": "sales",
            "business_date": business_date,
        },
        headers=admin_header,
    )
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND), response.text


@pytest.mark.asyncio
async def test_get_terminal_reports_empty(http_client, admin_header):
    """GET .../terminals/{tn}/reports — same as above but at terminal scope."""
    tenant_id = os.environ.get("TENANT_ID")
    business_date = datetime.now().strftime("%Y%m%d")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/terminals/9/reports",
        params={
            "report_scope": "flash",
            "report_type": "sales",
            "business_date": business_date,
        },
        headers=admin_header,
    )
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND), response.text
