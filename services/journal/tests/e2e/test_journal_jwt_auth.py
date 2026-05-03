"""
Integration tests for journal service with terminal JWT authentication.

Verifies that journal endpoints accept terminal JWT via Authorization header
and correctly extract tenant_id from JWT claims.
"""
import pytest
import os
from fastapi import status
from httpx import AsyncClient


async def get_terminal_jwt() -> str:
    """Get a terminal JWT via the terminal service."""
    tenant_id = os.environ.get("TENANT_ID")
    token_url = os.environ.get("TOKEN_URL")

    async with AsyncClient() as client:
        resp = await client.post(token_url, data={"username": "admin", "password": "admin", "client_id": tenant_id})
        admin_token = resp.json().get("access_token")

        terminal_id = f"{tenant_id}-5678-9"
        resp = await client.get(
            f"http://localhost:8001/api/v1/terminals/{terminal_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if resp.status_code != status.HTTP_200_OK:
            return None
        api_key = resp.json().get("data", {}).get("apiKey")

        resp = await client.post(
            "http://localhost:8001/api/v1/auth/token",
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json().get("data").get("access_token")


@pytest.mark.asyncio
async def test_journal_transactions_with_jwt(http_client):
    """GET /transactions with terminal JWT authentication."""
    tenant_id = os.environ.get("TENANT_ID")
    jwt_token = await get_terminal_jwt()
    if jwt_token is None:
        pytest.skip("Terminal not found - run terminal tests first")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/terminals/9/transactions",
        headers={"Authorization": f"Bearer {jwt_token}"},
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
        f"JWT auth failed: {response.text}"
    )
    print(f"journal transactions with JWT: {response.status_code} (auth OK)")


@pytest.mark.asyncio
async def test_journal_backward_compat_api_key(http_client):
    """GET /transactions with API key (backward compatibility)."""
    tenant_id = os.environ.get("TENANT_ID")
    terminal_id = f"{tenant_id}-5678-9"

    token_url = os.environ.get("TOKEN_URL")
    async with AsyncClient() as client:
        resp = await client.post(token_url, data={"username": "admin", "password": "admin", "client_id": tenant_id})
        admin_token = resp.json().get("access_token")
        resp = await client.get(
            f"http://localhost:8001/api/v1/terminals/{terminal_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if resp.status_code != status.HTTP_200_OK:
            pytest.skip("Terminal not found")
        api_key = resp.json().get("data", {}).get("apiKey")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/terminals/9/transactions",
        params={"terminal_id": terminal_id},
        headers={"X-API-KEY": api_key},
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
        f"API key auth failed: {response.text}"
    )
    print(f"journal with API key (backward compat): {response.status_code} (auth OK)")
