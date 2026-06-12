# Copyright 2026 masa@kugel
"""E2E coverage for journal service.

Sequence:
  1. POST /tenants — initialise the tenant DB.
  2. POST /tenants/.../journals — write a sample journal entry.
  3. GET  /tenants/.../journals — read it back.
"""
import os
from datetime import datetime
from kugel_common.utils.misc import get_app_time

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_setup_data(http_client, admin_header):
    """POST /tenants on journal initialises the per-tenant DB."""
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
async def test_post_and_get_journals(http_client, admin_header):
    """Write a journal entry, then read it back via GET /journals."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = "5678"
    terminal_no = 9
    business_date = get_app_time().strftime("%Y%m%d")
    transaction_no = int(get_app_time().strftime("%H%M%S"))

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/journals",
        json={
            "tenantId": tenant_id,
            "storeCode": store_code,
            "terminalNo": terminal_no,
            "transactionNo": transaction_no,
            "transactionType": 101,
            "businessDate": business_date,
            "openCounter": 1,
            "businessCounter": 1,
            "generateDateTime": datetime.now().isoformat(),
            "receiptNo": 1,
            "amount": 110.0,
            "quantity": 1,
            "staffId": "S001",
            "userId": "admin",
            "journalText": "E2E journal entry",
            "receiptText": "E2E receipt text",
        },
        headers=admin_header,
    )
    assert response.status_code in (
        status.HTTP_200_OK,
        status.HTTP_201_CREATED,
    ), response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals"
        f"?business_date_from={business_date}&business_date_to={business_date}",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    assert body.get("success") is True
    journals = body.get("data") or []
    assert any(j.get("transactionNo") == transaction_no for j in journals), (
        f"Just-written journal not visible in GET: {journals}"
    )


@pytest.mark.asyncio
async def test_get_journals_with_filters(http_client, admin_header):
    """GET /journals with various filter params returns successfully."""
    tenant_id = os.environ.get("TENANT_ID")
    business_date = get_app_time().strftime("%Y%m%d")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/journals"
        f"?business_date_from={business_date}&business_date_to={business_date}"
        f"&transaction_types=101&terminals=9&limit=50&page=1",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json().get("success") is True
