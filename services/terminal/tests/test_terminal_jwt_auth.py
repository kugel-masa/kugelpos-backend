"""
Integration tests for terminal JWT authentication.

Tests the complete JWT auth flow:
- POST /auth/token (API key -> JWT)
- X-New-Token header on lifecycle operations
- JWT-based authentication on terminal endpoints
- Backward compatibility with API key auth
- Invalid credentials handling
"""
import pytest
import os
from fastapi import status
from httpx import AsyncClient
from jose import jwt


def decode_jwt_claims(token: str) -> dict:
    """Decode JWT claims without verification (for test assertions)."""
    return jwt.get_unverified_claims(token)


@pytest.mark.asyncio()
async def test_terminal_jwt_auth_flow(http_client):
    """
    End-to-end test for terminal JWT authentication lifecycle.

    Flow:
    1. Create terminal (via admin token)
    2. POST /auth/token with API key -> get JWT
    3. Verify JWT claims
    4. Use JWT to access terminal endpoint
    5. Sign-in -> verify X-New-Token has staff claims
    6. Open -> verify X-New-Token has business state
    7. Sign-out -> verify X-New-Token has no staff claims
    8. Close -> verify X-New-Token has status=Closed
    9. Backward compatibility: API key auth still works
    10. Invalid API key -> 401
    """
    tenant_id = os.environ.get("TENANT_ID")

    # --- Setup: Get admin token and create terminal ---
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}
    async with AsyncClient() as auth_client:
        url = os.environ.get("TOKEN_URL")
        response = await auth_client.post(url=url, data=login_data)
    assert response.status_code == status.HTTP_200_OK
    admin_token = response.json().get("access_token")
    admin_header = {"Authorization": f"Bearer {admin_token}"}

    # Create tenant (ignore if exists)
    await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": tenant_id, "tenant_name": "JWT Test Tenant", "stores": [], "tags": ["JWT-Test"]},
        headers=admin_header,
    )
    # Create store (ignore if exists)
    await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores",
        json={"store_code": "JWT1", "store_name": "JWT Test Store", "tags": ["JWT-Test"]},
        headers=admin_header,
    )
    # Create terminal
    create_resp = await http_client.post(
        "/api/v1/terminals",
        json={"store_code": "JWT1", "terminal_no": 77, "description": "JWT Auth Test Terminal"},
        headers=admin_header,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    create_data = create_resp.json().get("data")
    terminal_id = create_data.get("terminalId")
    api_key = create_data.get("apiKey")
    print(f"Created terminal: {terminal_id}, API key: {api_key[:10]}...")

    # =============================================
    # Test 1: POST /auth/token - Valid API key
    # =============================================
    response = await http_client.post("/api/v1/auth/token", headers={"X-API-KEY": api_key})
    assert response.status_code == status.HTTP_200_OK
    token_data = response.json()
    assert token_data.get("success") is True
    jwt_data = token_data.get("data")
    assert jwt_data.get("token_type") == "bearer"
    assert jwt_data.get("expires_in") == 86400
    terminal_jwt = jwt_data.get("access_token")
    assert terminal_jwt is not None
    print(f"JWT token obtained: {terminal_jwt[:40]}...")

    # =============================================
    # Test 2: Verify JWT claims
    # =============================================
    claims = decode_jwt_claims(terminal_jwt)
    assert claims.get("sub") == f"terminal:{terminal_id}"
    assert claims.get("tenant_id") == tenant_id
    assert claims.get("store_code") == "JWT1"
    assert claims.get("terminal_id") == terminal_id
    assert claims.get("token_type") == "terminal"
    assert claims.get("iss") == "terminal-service"
    assert claims.get("status") == "Idle"
    assert "staff_id" not in claims  # Not signed in
    assert "exp" in claims
    print(f"JWT claims verified: sub={claims['sub']}, status={claims['status']}")

    # =============================================
    # Test 3: Use JWT to access terminal endpoint
    # =============================================
    jwt_header = {"Authorization": f"Bearer {terminal_jwt}"}
    response = await http_client.get(f"/api/v1/terminals/{terminal_id}", headers=jwt_header)
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("terminalId") == terminal_id
    print("JWT-based terminal access: OK")

    # =============================================
    # Test 4: Sign-in -> X-New-Token with staff claims
    # =============================================
    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/sign-in",
        json={"staff_id": "S001"},
        headers=jwt_header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("staff").get("staffId") == "S001"

    signin_jwt = response.headers.get("x-new-token")
    assert signin_jwt is not None, "X-New-Token header missing after sign-in"
    signin_claims = decode_jwt_claims(signin_jwt)
    assert signin_claims.get("staff_id") == "S001"
    assert signin_claims.get("staff_name") is not None
    assert signin_claims.get("status") == "Idle"
    print(f"Sign-in X-New-Token: staff_id={signin_claims['staff_id']}")

    # =============================================
    # Test 5: Open -> X-New-Token with business state
    # =============================================
    jwt_header_updated = {"Authorization": f"Bearer {signin_jwt}"}
    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/open",
        json={"initial_amount": 50000},
        headers=jwt_header_updated,
    )
    assert response.status_code == status.HTTP_200_OK

    open_jwt = response.headers.get("x-new-token")
    assert open_jwt is not None, "X-New-Token header missing after open"
    open_claims = decode_jwt_claims(open_jwt)
    assert open_claims.get("status") == "Opened"
    assert open_claims.get("business_date") is not None
    assert open_claims.get("open_counter") >= 1
    assert open_claims.get("business_counter") >= 1
    assert open_claims.get("staff_id") == "S001"  # Staff still present
    print(f"Open X-New-Token: status={open_claims['status']}, business_date={open_claims['business_date']}")

    # =============================================
    # Test 6: Sign-out -> X-New-Token without staff claims
    # =============================================
    jwt_header_opened = {"Authorization": f"Bearer {open_jwt}"}
    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/sign-out",
        headers=jwt_header_opened,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("staff") is None

    signout_jwt = response.headers.get("x-new-token")
    assert signout_jwt is not None, "X-New-Token header missing after sign-out"
    signout_claims = decode_jwt_claims(signout_jwt)
    assert "staff_id" not in signout_claims
    assert "staff_name" not in signout_claims
    assert signout_claims.get("status") == "Opened"  # Still opened
    print("Sign-out X-New-Token: staff claims removed")

    # =============================================
    # Test 7: Close -> X-New-Token with status=Closed
    # =============================================
    jwt_header_signedout = {"Authorization": f"Bearer {signout_jwt}"}
    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/close",
        json={"physical_amount": 50000},
        headers=jwt_header_signedout,
    )
    assert response.status_code == status.HTTP_200_OK

    close_jwt = response.headers.get("x-new-token")
    assert close_jwt is not None, "X-New-Token header missing after close"
    close_claims = decode_jwt_claims(close_jwt)
    assert close_claims.get("status") == "Closed"
    print(f"Close X-New-Token: status={close_claims['status']}")

    # =============================================
    # Test 8: Backward compatibility - API key auth
    # =============================================
    api_key_header = {"X-API-KEY": api_key}
    response = await http_client.get(f"/api/v1/terminals/{terminal_id}", headers=api_key_header)
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("terminalId") == terminal_id
    print("Backward compatibility (API key): OK")

    # =============================================
    # Test 9: Invalid API key -> 401
    # =============================================
    response = await http_client.post(
        "/api/v1/auth/token",
        headers={"X-API-KEY": "invalid-api-key-12345"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    print("Invalid API key: 401 OK")

    # =============================================
    # Test 10: Missing API key -> 401
    # =============================================
    response = await http_client.post("/api/v1/auth/token")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    print("Missing API key: 401 OK")

    # =============================================
    # Cleanup: Delete the test terminal
    # =============================================
    response = await http_client.delete(f"/api/v1/terminals/{terminal_id}", headers=admin_header)
    assert response.status_code == status.HTTP_200_OK
    print(f"Cleanup: terminal {terminal_id} deleted")

    print("All terminal JWT auth tests passed!")
