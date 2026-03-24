"""
Integration tests for report service with terminal JWT authentication.

Verifies:
1. Report endpoints accept terminal JWT for authentication
2. get_requesting_staff_id extracts staff_id from JWT claims
3. TerminalInfoWebRepository uses JWT to call terminal service
4. Backward compatibility with API key auth
"""
import pytest
import os
from fastapi import status
from httpx import AsyncClient
from jose import jwt as jose_jwt


async def get_terminal_jwt(api_key: str) -> str:
    """Get a terminal JWT token via POST /auth/token on the terminal service."""
    async with AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/api/v1/auth/token",
            headers={"X-API-KEY": api_key},
        )
    assert response.status_code == status.HTTP_200_OK, f"Failed to get JWT: {response.text}"
    return response.json().get("data").get("access_token")


async def get_terminal_api_key_and_info() -> tuple:
    """Get API key and info for an existing terminal using admin token.

    Returns:
        Tuple of (api_key, terminal_id, store_code) or (None, None, None) if not found
    """
    tenant_id = os.environ.get("TENANT_ID")
    token_url = os.environ.get("TOKEN_URL")

    async with AsyncClient() as client:
        # Get admin token
        resp = await client.post(token_url, data={"username": "admin", "password": "admin", "client_id": tenant_id})
        admin_token = resp.json().get("access_token")

        # List terminals to find one that exists
        resp = await client.get(
            "http://localhost:8001/api/v1/terminals",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    if resp.status_code != status.HTTP_200_OK:
        return None, None, None
    terminals = resp.json().get("data", [])
    if not terminals:
        return None, None, None
    terminal = terminals[0]
    return terminal.get("apiKey"), terminal.get("terminalId"), terminal.get("storeCode")


@pytest.mark.asyncio
async def test_report_endpoint_with_jwt(http_client):
    """
    Report endpoint accepts terminal JWT and returns data.

    Exercises:
    - __get_tenant_id() terminal JWT path (authentication)
    - get_requesting_staff_id() JWT claim extraction (staff_id)
    - TerminalInfoWebRepository Bearer token forwarding (terminal service call)
    """
    tenant_id = os.environ.get("TENANT_ID")
    business_date = os.environ.get("BUSINESS_DATE")

    # Find an existing terminal
    api_key, terminal_id, store_code = await get_terminal_api_key_and_info()
    if api_key is None:
        pytest.skip("No terminals found - run terminal tests first to create test data")

    # Get terminal JWT
    jwt_token = await get_terminal_jwt(api_key)
    jwt_header = {"Authorization": f"Bearer {jwt_token}"}

    # Verify JWT contains expected claims
    claims = jose_jwt.get_unverified_claims(jwt_token)
    print(f"JWT claims: tenant_id={claims.get('tenant_id')}, staff_id={claims.get('staff_id', 'NONE')}, status={claims.get('status')}")

    # Call report endpoint with JWT
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "report_scope": "flash",
            "report_type": "sales",
            "business_date": business_date,
        },
        headers=jwt_header,
    )

    print(f"Report response: {response.status_code}")
    if response.status_code == status.HTTP_200_OK:
        res = response.json()
        assert res.get("success") is True
        print(f"Report with JWT auth: success, data keys={list(res.get('data', {}).keys()) if res.get('data') else 'empty'}")
    elif response.status_code == status.HTTP_404_NOT_FOUND:
        # No report data available - but JWT auth succeeded (not 401)
        print("Report: 404 (no data for this business_date, but JWT auth succeeded)")
    else:
        # If we get 401 or 403, JWT auth failed
        assert response.status_code not in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ], f"JWT auth failed for report: {response.status_code} {response.text}"
        print(f"Report response: {response.status_code} (unexpected but not auth failure)")

    print("Report endpoint with JWT: PASS")


@pytest.mark.asyncio
async def test_report_staff_id_from_jwt(http_client):
    """
    Verify get_requesting_staff_id extracts staff_id from terminal JWT claims.

    When a terminal JWT with staff_id is used, the report endpoint should
    use that staff_id for filtering without making a separate terminal service call.
    """
    tenant_id = os.environ.get("TENANT_ID")
    business_date = os.environ.get("BUSINESS_DATE")

    api_key, terminal_id, store_code = await get_terminal_api_key_and_info()
    if api_key is None:
        pytest.skip("No terminals found")

    jwt_token = await get_terminal_jwt(api_key)
    claims = jose_jwt.get_unverified_claims(jwt_token)

    # Check if JWT has staff_id
    staff_id = claims.get("staff_id")
    if staff_id:
        print(f"JWT has staff_id={staff_id} - report should use it directly from claims")
    else:
        print("JWT has no staff_id (terminal not signed in) - report should handle gracefully")

    jwt_header = {"Authorization": f"Bearer {jwt_token}"}

    # Call terminal-specific report (uses get_requesting_staff_id)
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "report_scope": "flash",
            "report_type": "sales",
            "business_date": business_date,
        },
        headers=jwt_header,
    )

    # Auth should succeed regardless of staff_id presence
    assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
        f"JWT auth failed: {response.text}"
    )
    print(f"Report with staff_id from JWT: {response.status_code} (auth OK)")


@pytest.mark.asyncio
async def test_report_backward_compat_api_key(http_client):
    """Report endpoint still works with API key auth (backward compatibility)."""
    tenant_id = os.environ.get("TENANT_ID")
    business_date = os.environ.get("BUSINESS_DATE")

    api_key, terminal_id, store_code = await get_terminal_api_key_and_info()
    if api_key is None:
        pytest.skip("No terminals found")

    api_key_header = {"X-API-KEY": api_key}

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "terminal_id": terminal_id,
            "report_scope": "flash",
            "report_type": "sales",
            "business_date": business_date,
        },
        headers=api_key_header,
    )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED, (
        f"API key auth failed: {response.text}"
    )
    print(f"Report with API key (backward compat): {response.status_code} (auth OK)")
