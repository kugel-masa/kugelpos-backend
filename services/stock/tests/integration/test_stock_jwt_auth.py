# Copyright 2026 masa@kugel
"""Integration tests for stock endpoints under terminal-JWT auth.

Uses locally-generated JWTs (terminal_jwt / api_key fixtures) so no
calls to account / terminal services are required.
"""
import os

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_stock_with_terminal_jwt(http_client, terminal_jwt):
    """GET /stock with a terminal JWT — verified locally."""
    tenant_id = os.environ.get("TENANT_ID")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/stock",
        headers={"Authorization": f"Bearer {terminal_jwt}"},
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
        f"terminal-JWT auth failed: {response.text}"
    )


@pytest.mark.asyncio
async def test_stock_backward_compat_api_key(http_client, api_key):
    """GET /stock with X-API-KEY (backward compat).

    The terminal-service lookup happens through kugel_common.security
    and is mocked by the conftest's mock_dapr_sidecar fixture (which
    also routes the terminals/ endpoint).
    """
    tenant_id = os.environ.get("TENANT_ID")
    terminal_id = f"{tenant_id}-5678-9"

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/stock",
        params={"terminal_id": terminal_id},
        headers={"X-API-KEY": api_key},
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
        f"API-key auth failed: {response.text}"
    )
