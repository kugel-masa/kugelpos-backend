"""
Full cart business logic tests using JWT authentication.

This is the JWT equivalent of test_cart.py - it exercises the same business
logic but authenticates via terminal JWT instead of API key. This ensures
that TerminalInfoDocument constructed from JWT claims (with missing fields
like api_key, description, tags) works correctly throughout the entire
cart transaction lifecycle.

Covers:
- Cart CRUD operations
- Line item operations (add, quantity change, unit price change, cancel)
- Discount operations (line item discount, subtotal discount)
- Payment process (partial payment, full payment, bill)
- Transaction operations (return, void)
- Multiple payment methods
- Unregistered item error handling
"""
import pytest
import os
from fastapi import status
from httpx import AsyncClient
from app.enums.cart_status import CartStatus


async def get_jwt_header() -> dict:
    """Get JWT auth header for the test terminal."""
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")

    async with AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8001/api/v1/auth/token",
            headers={"X-API-KEY": api_key},
        )
    assert resp.status_code == status.HTTP_200_OK, f"Failed to get JWT: {resp.text}"
    jwt_token = resp.json().get("data").get("access_token")
    return {"Authorization": f"Bearer {jwt_token}"}


async def ensure_terminal_ready():
    """Ensure terminal is opened and signed in via API key."""
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    base_url = os.environ.get("BASE_URL_TERMINAL")
    header = {"X-API-KEY": api_key}

    async with AsyncClient(base_url=base_url) as client:
        resp = await client.get(f"/terminals/{terminal_id}", headers=header)
        data = resp.json().get("data", {})
        if data.get("status") != "Opened" or data.get("staff") is None:
            await client.post(f"/terminals/{terminal_id}/sign-in", json={"staff_id": "S001"}, headers=header)
            if data.get("status") != "Opened":
                await client.post(f"/terminals/{terminal_id}/open", json={"initial_amount": 500000}, headers=header)


@pytest.mark.asyncio
async def test_jwt_cart_operations(http_client):
    """Cart CRUD with JWT: create, get, cancel."""
    await ensure_terminal_ready()
    header = await get_jwt_header()
    tenant_id = os.environ.get("TENANT_ID")

    # Create cart
    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "JWT99", "user_name": "JWT Test"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    assert res.get("success") is True
    cart_id = res.get("data").get("cartId")

    # Get cart
    response = await http_client.get(f"/api/v1/carts/{cart_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    cart = response.json().get("data")
    assert cart.get("cartId") == cart_id
    assert cart.get("cartStatus") == CartStatus.Idle.value
    assert cart.get("tenantId") == tenant_id

    # Cancel cart
    response = await http_client.post(f"/api/v1/carts/{cart_id}/cancel", headers=header)
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("cartStatus") == CartStatus.Cancelled.value
    print("JWT cart operations: PASS")


@pytest.mark.asyncio
async def test_jwt_line_item_operations(http_client):
    """Line item operations with JWT: add, quantity change, unit price change, cancel."""
    await ensure_terminal_ready()
    header = await get_jwt_header()

    # Create cart
    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "JWT99", "user_name": "JWT Test"},
        headers=header,
    )
    cart_id = response.json().get("data").get("cartId")

    # Add item
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("data").get("cartStatus") == CartStatus.EnteringItem.value
    assert res.get("data").get("lineItems")[0].get("isCancelled") is False

    # Change quantity
    response = await http_client.patch(
        f"/api/v1/carts/{cart_id}/lineItems/1/quantity",
        json={"quantity": 3},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("lineItems")[0].get("quantity") == 3

    # Add item with specific unit price
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems",
        json=[{"itemCode": "49-01", "quantity": 1, "unitPrice": 88}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("lineItems")[1].get("unitPrice") == 88

    # Change unit price
    response = await http_client.patch(
        f"/api/v1/carts/{cart_id}/lineItems/2/unitPrice",
        json={"unitPrice": 95},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("data").get("lineItems")[1].get("unitPrice") == 95
    assert res.get("data").get("lineItems")[1].get("isUnitPriceChanged") is True

    # Cancel line item
    response = await http_client.post(f"/api/v1/carts/{cart_id}/lineItems/2/cancel", headers=header)
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("lineItems")[1].get("isCancelled") is True

    # Cleanup
    await http_client.post(f"/api/v1/carts/{cart_id}/cancel", headers=header)
    print("JWT line item operations: PASS")


@pytest.mark.asyncio
async def test_jwt_discount_operations(http_client):
    """Discount operations with JWT: line discount, subtotal discount."""
    await ensure_terminal_ready()
    header = await get_jwt_header()

    # Create cart + add items
    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "JWT99", "user_name": "JWT Test"},
        headers=header,
    )
    cart_id = response.json().get("data").get("cartId")

    await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )

    # Line item amount discount
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems/1/discounts",
        json=[{"discountType": "DiscountAmount", "discountValue": 10}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("lineItems")[0].get("discounts")[0].get("discountAmount") == 10

    # Add another item + percentage discount
    await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems",
        json=[{"itemCode": "49-02", "quantity": 3}],
        headers=header,
    )
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems/2/discounts",
        json=[{"discountType": "DiscountPercentage", "discountValue": 10}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Subtotal
    response = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal", headers=header)
    assert response.status_code == status.HTTP_200_OK

    # Subtotal discount
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/discounts",
        json=[{"discountType": "DiscountAmount", "discountValue": 50}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("subtotalDiscounts")[0].get("discountValue") == 50

    # Cleanup
    await http_client.post(f"/api/v1/carts/{cart_id}/cancel", headers=header)
    print("JWT discount operations: PASS")


@pytest.mark.asyncio
async def test_jwt_payment_process(http_client):
    """Full payment process with JWT: add items, subtotal, partial payment, bill."""
    await ensure_terminal_ready()
    header = await get_jwt_header()

    # Create cart + add item
    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "JWT99", "user_name": "JWT Test"},
        headers=header,
    )
    cart_id = response.json().get("data").get("cartId")

    await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )

    # Subtotal
    response = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal", headers=header)
    assert response.status_code == status.HTTP_200_OK
    total_amount = response.json().get("data").get("totalAmountWithTax")

    # Partial payment (insufficient)
    await http_client.post(
        f"/api/v1/carts/{cart_id}/payments",
        json=[{"paymentCode": "01", "amount": 100, "detail": "Cash payment"}],
        headers=header,
    )

    # Bill with insufficient balance
    response = await http_client.post(f"/api/v1/carts/{cart_id}/bill", headers=header)
    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE

    # Full payment
    await http_client.post(
        f"/api/v1/carts/{cart_id}/payments",
        json=[{"paymentCode": "01", "amount": 1000, "detail": "Cash payment"}],
        headers=header,
    )

    # Bill (success)
    response = await http_client.post(f"/api/v1/carts/{cart_id}/bill", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("data").get("cartStatus") == CartStatus.Completed.value
    assert res.get("data").get("changeAmount") > 0
    print(f"JWT payment process: PASS (total={total_amount}, change={res.get('data').get('changeAmount')})")


@pytest.mark.asyncio
async def test_jwt_transaction_operations(http_client):
    """Transaction operations with JWT: complete sale, return, void."""
    await ensure_terminal_ready()
    header = await get_jwt_header()
    tenant_id = os.environ.get("TENANT_ID")
    terminal_id = os.environ.get("TERMINAL_ID")
    parts = terminal_id.split("-")
    store_code = parts[1]
    terminal_no = parts[2]

    # Create cart + add items + subtotal + pay + bill
    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "JWT99", "user_name": "JWT Test"},
        headers=header,
    )
    cart_id = response.json().get("data").get("cartId")

    await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    await http_client.post(f"/api/v1/carts/{cart_id}/subtotal", headers=header)
    await http_client.post(
        f"/api/v1/carts/{cart_id}/payments",
        json=[{"paymentCode": "01", "amount": 1000, "detail": "Cash"}],
        headers=header,
    )
    response = await http_client.post(f"/api/v1/carts/{cart_id}/bill", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    transaction_no = res.get("data").get("transactionNo")
    journal_text = res.get("data").get("journalText")
    assert journal_text is not None and len(journal_text) > 0
    print(f"JWT sale completed: transaction_no={transaction_no}")

    # Get transaction list
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json().get("data")) > 0

    # Get transaction detail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json().get("data").get("transactionNo") == transaction_no

    # Return
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return",
        json=[{"paymentCode": "01", "amount": 220, "detail": "Cash"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    return_no = response.json().get("data").get("transactionNo")
    print(f"JWT return completed: return_no={return_no}")

    # Void the return
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{return_no}/void",
        json=[{"paymentCode": "01", "amount": 220, "detail": "Cash"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    void_no = response.json().get("data").get("transactionNo")
    print(f"JWT void completed: void_no={void_no}")


@pytest.mark.asyncio
async def test_jwt_multiple_payment_methods(http_client):
    """Multiple payment methods with JWT: cash + cashless + others."""
    await ensure_terminal_ready()
    header = await get_jwt_header()

    # Create cart + add items
    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "JWT99", "user_name": "JWT Test"},
        headers=header,
    )
    cart_id = response.json().get("data").get("cartId")

    await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems",
        json=[{"itemCode": "49-01", "quantity": 10}],
        headers=header,
    )

    # Subtotal
    response = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal", headers=header)
    total_amount = response.json().get("data").get("totalAmountWithTax")

    # Others payment (voucher)
    others_amount = 300
    await http_client.post(
        f"/api/v1/carts/{cart_id}/payments",
        json=[{"paymentCode": "12", "amount": others_amount, "detail": "{ paymentMethod: 'voucher' }"}],
        headers=header,
    )

    # Cashless
    cashless_amount = 400
    await http_client.post(
        f"/api/v1/carts/{cart_id}/payments",
        json=[{"paymentCode": "11", "amount": cashless_amount, "detail": "{'card':'1234'}"}],
        headers=header,
    )

    # Cash (remainder + change)
    cash_amount = 2000
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments",
        json=[{"paymentCode": "01", "amount": cash_amount, "detail": "Cash"}],
        headers=header,
    )
    assert len(response.json().get("data").get("payments")) == 3

    # Bill
    response = await http_client.post(f"/api/v1/carts/{cart_id}/bill", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("data").get("cartStatus") == CartStatus.Completed.value

    expected_change = cash_amount - (total_amount - others_amount - cashless_amount)
    assert res.get("data").get("changeAmount") == expected_change
    print(f"JWT multiple payments: PASS (change={expected_change})")


@pytest.mark.asyncio
async def test_jwt_unregistered_item_error(http_client):
    """Unregistered item code error with JWT."""
    await ensure_terminal_ready()
    header = await get_jwt_header()

    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "JWT99", "user_name": "JWT Test"},
        headers=header,
    )
    cart_id = response.json().get("data").get("cartId")

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems",
        json=[{"itemCode": "NONEXISTENT", "quantity": 1}],
        headers=header,
    )
    assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY]

    await http_client.post(f"/api/v1/carts/{cart_id}/cancel", headers=header)
    print("JWT unregistered item error: PASS")
