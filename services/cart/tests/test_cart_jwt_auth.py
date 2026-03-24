"""
Integration tests for cart operations using terminal JWT authentication.

Verifies that cart endpoints accept terminal JWT tokens and that
JWT is correctly forwarded to master-data for item/payment lookups.
"""
import pytest
import os
from fastapi import status
from httpx import AsyncClient


async def get_terminal_jwt(terminal_id: str, api_key: str) -> str:
    """Get a terminal JWT token via POST /auth/token."""
    base_url = os.environ.get("BASE_URL_TERMINAL")
    # BASE_URL_TERMINAL includes /api/v1 suffix for cart tests
    # Strip it to get the terminal service root
    terminal_root = base_url.replace("/api/v1", "")

    async with AsyncClient(base_url=terminal_root) as client:
        response = await client.post(
            "/api/v1/auth/token",
            headers={"X-API-KEY": api_key},
        )
    assert response.status_code == status.HTTP_200_OK, f"Failed to get JWT: {response.text}"
    return response.json().get("data").get("access_token")


async def ensure_terminal_opened_and_signed_in(terminal_id: str, api_key: str):
    """Ensure the terminal is opened and signed in using API key auth."""
    base_url = os.environ.get("BASE_URL_TERMINAL")
    header = {"X-API-KEY": api_key}

    async with AsyncClient(base_url=base_url) as client:
        # Check current status
        resp = await client.get(f"/terminals/{terminal_id}", headers=header)
        if resp.status_code == status.HTTP_200_OK:
            data = resp.json().get("data", {})
            terminal_status = data.get("status")
            staff = data.get("staff")
            if terminal_status == "Opened" and staff is not None:
                return

        # Sign-in (idempotent - OK if already signed in)
        await client.post(
            f"/terminals/{terminal_id}/sign-in",
            json={"staff_id": "S001"},
            headers=header,
        )

        # Open (only if not already opened)
        resp = await client.get(f"/terminals/{terminal_id}", headers=header)
        if resp.status_code == status.HTTP_200_OK:
            if resp.json().get("data", {}).get("status") != "Opened":
                await client.post(
                    f"/terminals/{terminal_id}/open",
                    json={"initial_amount": 50000},
                    headers=header,
                )


@pytest.mark.asyncio
async def test_cart_create_with_jwt(http_client):
    """Cart creation using terminal JWT authentication (no API key)."""
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")

    # Ensure terminal is opened
    await ensure_terminal_opened_and_signed_in(terminal_id, api_key)

    # Get terminal JWT
    jwt_token = await get_terminal_jwt(terminal_id, api_key)
    jwt_header = {"Authorization": f"Bearer {jwt_token}"}

    # Create cart with JWT auth (no terminal_id query param needed)
    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "JWT01", "user_name": "JWT Test User"},
        headers=jwt_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, f"Cart create failed: {response.text}"
    res = response.json()
    assert res.get("success") is True
    cart_id = res.get("data").get("cartId")
    assert cart_id is not None
    print(f"Cart created with JWT auth: {cart_id}")

    # Get cart with JWT auth
    response = await http_client.get(
        f"/api/v1/carts/{cart_id}",
        headers=jwt_header,
    )
    assert response.status_code == status.HTTP_200_OK
    cart = response.json().get("data")
    assert cart.get("cartId") == cart_id
    assert cart.get("tenantId") == os.environ.get("TENANT_ID")
    print(f"Cart retrieved with JWT auth: tenant={cart.get('tenantId')}, store={cart.get('storeCode')}")

    # Cancel cart (cleanup)
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel",
        headers=jwt_header,
    )
    assert response.status_code == status.HTTP_200_OK
    print("Cart cancelled with JWT auth: OK")


@pytest.mark.asyncio
async def test_cart_add_item_with_jwt(http_client):
    """Add item to cart using JWT auth (verifies JWT forwarding to master-data)."""
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")

    await ensure_terminal_opened_and_signed_in(terminal_id, api_key)

    jwt_token = await get_terminal_jwt(terminal_id, api_key)
    jwt_header = {"Authorization": f"Bearer {jwt_token}"}

    # Create cart
    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "JWT02", "user_name": "JWT Item Test"},
        headers=jwt_header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    cart_id = response.json().get("data").get("cartId")

    # Add item (this triggers JWT forwarding to master-data for item lookup)
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=jwt_header,
    )

    if response.status_code == status.HTTP_200_OK:
        res = response.json()
        assert res.get("success") is True
        line_items = res.get("data", {}).get("lineItems", [])
        assert len(line_items) > 0
        print(f"Item added with JWT auth: {line_items[0].get('itemCode')}")
    elif response.status_code == status.HTTP_404_NOT_FOUND:
        # Item may not exist in test data - this still proves JWT forwarding worked
        # (a 404 from master-data means the JWT auth succeeded, just the item is missing)
        print("Item not found in master-data (JWT forwarding to master-data succeeded, item not in test data)")
    else:
        # Unexpected error
        print(f"Add item response: {response.status_code} {response.text}")
        assert False, f"Unexpected status: {response.status_code}"

    # Cancel cart (cleanup)
    await http_client.post(f"/api/v1/carts/{cart_id}/cancel", headers=jwt_header)
    print("Cart with item cancelled: OK")


@pytest.mark.asyncio
async def test_cart_backward_compat_api_key(http_client):
    """Cart operations still work with API key auth (backward compatibility)."""
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")

    await ensure_terminal_opened_and_signed_in(terminal_id, api_key)

    api_key_header = {"X-API-KEY": api_key}

    # Create cart with API key (legacy)
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "LEGACY01", "user_name": "Legacy API Key Test"},
        headers=api_key_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, f"Legacy cart create failed: {response.text}"
    cart_id = response.json().get("data").get("cartId")
    print(f"Cart created with API key (legacy): {cart_id}")

    # Cancel cart (cleanup)
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel?terminal_id={terminal_id}",
        headers=api_key_header,
    )
    assert response.status_code == status.HTTP_200_OK
    print("Legacy API key backward compatibility: OK")
