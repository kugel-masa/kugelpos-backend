# Copyright 2026 masa@kugel
"""Integration tests for master-data endpoints under terminal-JWT auth.

The original e2e variant fetched a terminal JWT by hitting the account
and terminal services. Here we generate the JWTs locally and verify
that master-data accepts terminal JWTs without calling out, plus that
the X-API-KEY backward-compat path still works (with the terminal
lookup mocked via respx).
"""
import os

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_master_data_payments_with_terminal_jwt(http_client, terminal_jwt):
    """GET /payments with a terminal JWT — verified locally."""
    tenant_id = os.environ.get("TENANT_ID")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/payments",
        headers={"Authorization": f"Bearer {terminal_jwt}"},
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
        f"terminal-JWT auth failed: {response.text}"
    )


@pytest.mark.asyncio
async def test_master_data_items_with_terminal_jwt(http_client, terminal_jwt):
    """GET /items with a terminal JWT — verified locally."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = "5678"

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items",
        headers={"Authorization": f"Bearer {terminal_jwt}"},
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
        f"terminal-JWT auth failed: {response.text}"
    )


@pytest.mark.asyncio
async def test_master_data_backward_compat_api_key(http_client, api_key, mock_terminal_service):
    """GET /payments with X-API-KEY (backward compat).

    master-data routes go through kugel_common.security's API-key path,
    which calls the terminal service to verify the key — mocked here.
    """
    tenant_id = os.environ.get("TENANT_ID")
    terminal_id = f"{tenant_id}-5678-9"

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/payments",
        params={"terminal_id": terminal_id},
        headers={"X-API-KEY": api_key},
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
        f"API-key auth failed: {response.text}"
    )
