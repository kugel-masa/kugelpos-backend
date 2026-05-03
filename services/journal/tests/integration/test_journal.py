# Copyright 2026 masa@kugel
"""Integration tests for the journal service's GET /journals endpoint.

These tests drive the journal FastAPI app in-process via ASGITransport.
The admin JWT is generated locally by a fixture (no call to account),
and the API-key auth path is exercised by mocking the terminal service
lookup via respx.
"""
import os

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_get_journals_with_bearer_token(http_client, admin_token):
    """GET /journals authenticated via Bearer token (verified locally)."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    terminal_no = os.environ.get("TERMINAL_NO")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={
            "terminals": [terminal_no],
            "transaction_types": [101],
            "business_date_from": "20231001",
            "business_date_to": "21251001",
            "generate_date_time_from": "2023-10-01T12:34:56",
            "generate_date_time_to": "2125-10-01T12:34:56",
            "receipt_no_from": 700,
            "receipt_no_to": 800,
            "keywords": ["example"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    journals = res.get("data")
    # The journal entries seeded by test_setup_data.py match the filter.
    assert len(journals) > 0
    metadata = res.get("metadata")
    assert metadata is not None
    assert metadata.get("total") >= 0
    assert metadata.get("page") == 1
    assert metadata.get("limit") > 0


@pytest.mark.asyncio
async def test_get_journals_with_api_key(http_client, api_key, mock_terminal_service):
    """GET /journals authenticated via X-API-KEY (journal service verifies
    the key by calling terminal service — mocked here)."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    terminal_no = os.environ.get("TERMINAL_NO")
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals",
        headers={"X-API-KEY": api_key},
        params={
            "terminal_id": terminal_id,
            "terminals": [terminal_no],
            "transaction_types": [101],
            "business_date_from": "20231001",
            "business_date_to": "21251001",
            "generate_date_time_from": "2023-10-01T12:34:56",
            "generate_date_time_to": "2125-10-01T12:34:56",
            "receipt_no_from": 700,
            "receipt_no_to": 800,
            "keywords": ["example"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    metadata = res.get("metadata")
    assert metadata is not None
    assert metadata.get("total") >= 0


@pytest.mark.asyncio
async def test_get_journals_pagination(http_client, admin_token):
    """Verify limit / page metadata round-trip."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    terminal_no = os.environ.get("TERMINAL_NO")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={
            "terminals": [terminal_no],
            "transaction_types": [101],
            "business_date_from": "20231001",
            "business_date_to": "21251001",
            "page": 1,
            "limit": 5,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    metadata = res.get("metadata")
    assert metadata is not None
    assert metadata.get("page") == 1
    assert metadata.get("limit") == 5
