# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
import os
import pytest
from fastapi import status
from app.enums.cart_status import CartStatus
from httpx import AsyncClient


# Helper - obtain admin auth token
async def get_authentication_token():
    tenant_id = os.environ.get("TENANT_ID")
    token_url = os.environ.get("TOKEN_URL")
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}

    async with AsyncClient() as http_auth_client:
        response = await http_auth_client.post(url=token_url, data=login_data)

    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json().get("access_token")


# Helper - create tenant (idempotent: 409 means it already exists in this session)
async def create_tenant(http_client, token):
    tenant_id = os.environ.get("TENANT_ID")
    header = {"Authorization": f"Bearer {token}"}

    response = await http_client.post(
        "/api/v1/tenants", json={"tenant_id": tenant_id}, headers=header,
    )
    if response.status_code == status.HTTP_201_CREATED:
        res = response.json()
        assert res.get("success") is True
        assert res.get("data").get("tenantId") == tenant_id
        return tenant_id
    if response.status_code == status.HTTP_409_CONFLICT:
        # Tenant already created in an earlier test in this session.
        return tenant_id
    raise AssertionError(
        f"Failed to create tenant: {response.status_code} {response.text}"
    )


# Helper - fetch terminal info via X-API-KEY
async def get_terminal_info(tenant_id=None):
    if tenant_id is None:
        tenant_id = os.environ.get("TENANT_ID")
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    base_url = os.environ.get("BASE_URL_TERMINAL")

    async with AsyncClient(base_url=base_url) as http_terminal_client:
        response = await http_terminal_client.get(
            f"/terminals/{terminal_id}", headers={"X-API-KEY": api_key},
        )

    assert response.status_code == status.HTTP_200_OK, response.text
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("terminalId") == terminal_id
    return res.get("data")


# Helper - open the terminal (function_mode -> sign-in -> open -> Sales mode)
async def open_terminal(tenant_id=None):
    if tenant_id is None:
        tenant_id = os.environ.get("TENANT_ID")
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}
    base_url = os.environ.get("BASE_URL_TERMINAL")

    async with AsyncClient(base_url=base_url) as http_terminal_client:
        # function_mode -> OpenTerminal
        r = await http_terminal_client.patch(
            f"/terminals/{terminal_id}/function_mode",
            json={"function_mode": "OpenTerminal"}, headers=header,
        )
        assert r.status_code == status.HTTP_200_OK, r.text

        # sign in
        r = await http_terminal_client.post(
            f"/terminals/{terminal_id}/sign-in",
            json={"staff_id": "S001"}, headers=header,
        )
        assert r.status_code == status.HTTP_200_OK, r.text

        # open
        r = await http_terminal_client.post(
            f"/terminals/{terminal_id}/open",
            json={"initial_amount": 500000}, headers=header,
        )
        assert r.status_code == status.HTTP_200_OK, r.text

        # function_mode -> Sales
        r = await http_terminal_client.patch(
            f"/terminals/{terminal_id}/function_mode",
            json={"function_mode": "Sales"}, headers=header,
        )
        assert r.status_code == status.HTTP_200_OK, r.text

    return terminal_id


# Helper - close + sign-out
async def close_terminal(tenant_id=None):
    if tenant_id is None:
        tenant_id = os.environ.get("TENANT_ID")
    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}
    base_url = os.environ.get("BASE_URL_TERMINAL")

    async with AsyncClient(base_url=base_url) as http_terminal_client:
        r = await http_terminal_client.post(
            f"/terminals/{terminal_id}/close", headers=header,
        )
        assert r.status_code == status.HTTP_200_OK, r.text

        r = await http_terminal_client.post(
            f"/terminals/{terminal_id}/sign-out", headers=header,
        )
        assert r.status_code == status.HTTP_200_OK, r.text

    return terminal_id


# Main test - basic cart operations
@pytest.mark.asyncio
async def test_cart_operations(http_client):
    """Basic cart operations test"""

    # Get auth token
    token = await get_authentication_token()

    # Create tenant
    tenant_id = await create_tenant(http_client, token)

    # Clear terminal cache
    header = {"Authorization": f"Bearer {token}"}
    await http_client.delete("/api/v1/cache/terminal", headers=header)

    # Fetch terminal info
    terminal_info = await get_terminal_info(tenant_id)
    store_code = terminal_info["storeCode"]
    terminal_no = terminal_info["terminalNo"]
    terminal_id = terminal_info["terminalId"]

    # Only run the open process if the terminal is not already Opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)
    else:
        print(f"Terminal is already opened with status: {current_status}")

    # Set API key on the request header
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Create cart
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    assert res.get("success") is True
    cartId = res.get("data").get("cartId")
    assert cartId is not None

    # Get cart
    response = await http_client.get(f"/api/v1/carts/{cartId}?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    cart = res.get("data")
    assert cart.get("cartId") == cartId
    assert cart.get("cartStatus") == CartStatus.Idle.value
    assert cart.get("tenantId") == tenant_id
    assert cart.get("storeCode") == store_code
    assert cart.get("terminalNo") == terminal_no

    # Cancel cart
    response = await http_client.post(f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("cartId") == cartId
    assert res.get("data").get("cartStatus") == CartStatus.Cancelled.value



# Test - line item operations
@pytest.mark.asyncio
async def test_line_item_operations(http_client):
    """Line item operations test (add, change quantity, cancel)"""
    # Auth + tenant + terminal setup
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info["terminalId"]
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Make sure the terminal is opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)

    # Create a fresh cart
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    cartId = res.get("data").get("cartId")

    # Add items
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("cartStatus") == CartStatus.EnteringItem.value
    assert res.get("data").get("lineItems")[0].get("isCancelled") is False

    # Change item quantity
    lineNo = 1
    response = await http_client.patch(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/quantity?terminal_id={terminal_id}",
        json={"quantity": 3},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("lineItems")[0].get("quantity") == 3

    # Add item with override unit price
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1, "unitPrice": 88}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("lineItems")[1].get("unitPrice") == 88

    # Change item unit price
    lineNo = 2
    response = await http_client.patch(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/unitPrice?terminal_id={terminal_id}",
        json={"unitPrice": 95},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("lineItems")[1].get("unitPrice") == 95
    assert res.get("data").get("lineItems")[1].get("isUnitPriceChanged") is True

    # Cancel item
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/cancel?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("lineItems")[1].get("isCancelled") is True

    # Cancel cart to clean up
    await http_client.post(f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header)



# Test - discount operations
@pytest.mark.asyncio
async def test_discount_operations(http_client):
    """Discount operations test (line discount, subtotal discount)"""
    # Auth + tenant + terminal setup
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info["terminalId"]
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Make sure the terminal is opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)

    # Create cart
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")

    # Add items
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Add a flat-amount discount on the line item (detail carries the reason)
    lineNo = 1
    line_discount_detail = "{ discountReason : 'ポイント値引き' }"
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 10, "discountDetail": line_discount_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("lineItems")[0].get("discounts")[0].get("discountType") == "DiscountAmount"
    assert res.get("data").get("lineItems")[0].get("discounts")[0].get("discountValue") == 10
    assert res.get("data").get("lineItems")[0].get("discounts")[0].get("discountAmount") == 10
    # Verify the detail field
    assert res.get("data").get("lineItems")[0].get("discounts")[0].get("discountDetail") == line_discount_detail

    # Add another item
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-02", "quantity": 3}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Add a percentage discount on the line item
    lineNo = 2
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems/{lineNo}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountPercentage", "discountValue": 10}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("lineItems")[1].get("discounts")[0].get("discountType") == "DiscountPercentage"

    # Run subtotal
    response = await http_client.post(f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK

    # Add a flat-amount discount on the subtotal (detail carries point-redemption info)
    discount_detail = "{ discountReason : 'ポイント値引き' }"
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 50, "discountDetail": discount_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("subtotalDiscounts")[0].get("discountType") == "DiscountAmount"
    assert res.get("data").get("subtotalDiscounts")[0].get("discountValue") == 50
    assert res.get("data").get("subtotalDiscounts")[0].get("discountDetail") == discount_detail

    # Overwrite the subtotal discount
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 100, "discountDetail": discount_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("subtotalDiscounts")[0].get("discountValue") == 100
    assert res.get("data").get("subtotalDiscounts")[0].get("discountDetail") == discount_detail

    # Cancel cart to clean up
    await http_client.post(f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header)



# Test - payment + bill flow
@pytest.mark.asyncio
async def test_payment_process(http_client):
    """Payment and bill test"""
    # Auth + tenant + terminal setup
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info["terminalId"]
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Make sure the terminal is opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)

    # Create cart
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")

    # Add items
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Subtotal
    response = await http_client.post(f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    total_amount = res.get("data").get("totalAmountWithTax")

    # Partial payment (balance still owed)
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 100, "detail": "Cash payment"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Bill while balance is still owed (must reject)
    response = await http_client.post(f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE

    # Additional payment (cashless)
    detail_data = str({"card_no": "1234567890"})
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "11", "amount": 50, "detail": detail_data}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Add yet another payment (exceeds remaining balance)
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 1000, "detail": "Cash payment"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Bill (success)
    response = await http_client.post(f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("cartStatus") == CartStatus.Completed.value

    # Verify change amount
    assert res.get("data").get("totalAmountWithTax") < res.get("data").get("depositAmount")
    assert res.get("data").get("changeAmount") > 0



# Test - bill rejected when balance is unpaid
@pytest.mark.asyncio
async def test_bill_with_insufficient_balance(http_client):
    """Bill must be rejected if there is still an unpaid balance"""
    # Auth + tenant + terminal setup
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info["terminalId"]
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Make sure the terminal is opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)

    # Create cart
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")

    # Add items
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 3}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Subtotal
    response = await http_client.post(f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK

    # Partial payment (balance still owed)
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 50, "detail": "Cash payment"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Bill while balance is still owed (must reject)
    response = await http_client.post(f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE

    # Cancel cart to clean up
    await http_client.post(f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header)



# Test - stamp duty
@pytest.mark.asyncio
async def test_stamp_duty(http_client):
    # Verify stamp duty applies when a transaction is >= 50,000 yen

    # Auth + tenant + terminal setup
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info["terminalId"]
    store_code = terminal_info["storeCode"]
    terminal_no = terminal_info["terminalNo"]
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Make sure the terminal is opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)

    # Create cart and complete the transaction
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")

    # Add items
    await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 500}],
        headers=header,
    )

    # Subtotal
    await http_client.post(f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header)

    # Payment
    await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 60000, "detail": "Cash payment"}],
        headers=header,
    )

    # Bill
    response = await http_client.post(f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True

    # Verify stamp duty is applied
    assert res.get("data").get("stampDutyAmount") == 200


# Test - transaction operations (return, void, etc.)
@pytest.mark.asyncio
async def test_transaction_operations(http_client):
    """Transaction operations test (return, void, etc.)"""
    # Auth + tenant + terminal setup
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info["terminalId"]
    store_code = terminal_info["storeCode"]
    terminal_no = terminal_info["terminalNo"]
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Make sure the terminal is opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)

    # Create cart and complete the transaction
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    res = response.json()
    cartId = res.get("data").get("cartId")

    # Add items
    await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )

    # Add items
    await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=header,
    )

    # Subtotal
    await http_client.post(f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header)

    # Payment
    await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 1000, "detail": "Cash payment"}],
        headers=header,
    )

    # Bill
    response = await http_client.post(f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    transaction_no = response.json().get("data").get("transactionNo")
    res = response.json()
    assert res.get("success") is True
    journal_data = res.get("data").get("journalText")
    assert journal_data is not None
    assert len(journal_data) > 0

    # Get transactions list
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert len(res.get("data")) > 0
    for tran in res.get("data"):
        journal_data = tran.get("journalText")
        assert journal_data is not None
        assert len(journal_data) > 0

    # Get transactions list with query params
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions",
        params={
            "terminal_id": terminal_id,
            "limit": 10,
            "page": 1,
            "sort": "business_date:-1,transaction_no:1",
            "transaction_type": [101],
        },
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True

    # Get transaction detail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("transactionNo") == transaction_no
    journal_data = res.get("data").get("journalText")
    assert journal_data is not None
    assert len(journal_data) > 0

    # Return the transaction
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return?terminal_id={terminal_id}",
        headers=header,
        json=[{"paymentCode": "01", "amount": 330, "detail": "Cash payment"}],
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    return_transaction_no = res.get("data").get("transactionNo")

    # Get the returned transaction's detail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{return_transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    journal_data = res.get("data").get("journalText")
    assert journal_data is not None
    assert len(journal_data) > 0

    # Void the return transaction
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{return_transaction_no}/void?terminal_id={terminal_id}",
        headers=header,
        json=[
            {"paymentCode": "01", "amount": 330, "detail": "Cash payment"},
        ],
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    void_transaction_no = res.get("data").get("transactionNo")

    # Get the voided transaction's detail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{void_transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    journal_data = res.get("data").get("journalText")
    assert journal_data is not None
    assert len(journal_data) > 0



# Test - "Others" payment method
@pytest.mark.asyncio
async def test_payment_by_others(http_client):
    """Test for the 'Others' payment method"""

    # Auth + tenant + terminal setup
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info["terminalId"]
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Make sure the terminal is opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)

    # Create cart
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    cartId = res.get("data").get("cartId")

    # Add items
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Subtotal
    response = await http_client.post(f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    total_amount = res.get("data").get("totalAmountWithTax")

    # "Others" payment (code 12)
    others_detail = "{ paymentMethod: '商品券', voucherNumber: 'ABC123' }"
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "12", "amount": total_amount, "detail": others_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()

    # Verify the payment was added correctly
    assert res.get("success") is True
    payments = res.get("data").get("payments")
    assert len(payments) > 0

    # Verify the "Others" payment
    others_payment = next((p for p in payments if p.get("paymentCode") == "12"), None)
    assert others_payment is not None
    assert others_payment.get("paymentAmount") == total_amount
    assert others_payment.get("paymentDetail") == others_detail

    # Bill
    response = await http_client.post(f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("cartStatus") == CartStatus.Completed.value

    # Fetch transaction detail and verify
    transaction_no = res.get("data").get("transactionNo")
    store_code = terminal_info["storeCode"]
    terminal_no = terminal_info["terminalNo"]

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True

    # Verify the "Others" payment is recorded on the transaction
    payments = res.get("data").get("payments")
    others_payment = next((p for p in payments if p.get("paymentCode") == "12"), None)
    assert others_payment is not None
    assert others_payment.get("paymentAmount") == total_amount
    assert others_payment.get("paymentDetail") == others_detail



# Test - multiple payment methods combined
@pytest.mark.asyncio
async def test_multiple_payment_methods(http_client):
    """Test combining multiple payment methods (cash, cashless, others)"""

    # Auth + tenant + terminal setup
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info["terminalId"]
    store_code = terminal_info["storeCode"]
    terminal_no = terminal_info["terminalNo"]
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Make sure the terminal is opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)

    # Create cart
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    cartId = res.get("data").get("cartId")

    # Add items (multiple of a higher-priced item)
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 10}],  # 100 yen x 10 = 1,000 yen
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Subtotal
    response = await http_client.post(f"/api/v1/carts/{cartId}/subtotal?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    total_amount = res.get("data").get("totalAmountWithTax")
    assert total_amount > 0

    # 1. Partial payment with "Others" (gift voucher)
    others_detail = "{ paymentMethod: '商品券', voucherNumber: 'ABC123' }"
    others_amount = 300  # 300 yen worth of gift voucher
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "12", "amount": others_amount, "detail": others_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # 2. Partial payment with cashless
    cashless_detail = str({"card_no": "9876543210", "auth_code": "XYZ789"})
    cashless_amount = 400  # 400 yen via cashless payment
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "11", "amount": cashless_amount, "detail": cashless_detail}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # 3. Pay the remainder in cash (over-deposit so change is given)
    cash_amount = 2000  # 2000 yen cash (triggers change)
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": cash_amount, "detail": "Cash payment"}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK

    # Verify payment state
    res = response.json()
    payments = res.get("data").get("payments")
    assert len(payments) == 3  # three distinct payment methods

    # Bill
    response = await http_client.post(f"/api/v1/carts/{cartId}/bill?terminal_id={terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("cartStatus") == CartStatus.Completed.value

    # Verify change amount
    expected_change = cash_amount - (total_amount - others_amount - cashless_amount)
    assert res.get("data").get("changeAmount") == expected_change

    # Verify the receipt mentions all payment methods
    journal_text = res.get("data").get("journalText")
    assert "商品券" in journal_text or "Others" in journal_text
    assert "Cashless" in journal_text
    assert "Cash" in journal_text
    assert f"お釣り                  \\{int(expected_change):,}" in journal_text

    # Check the transaction detail
    transaction_no = res.get("data").get("transactionNo")
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}?terminal_id={terminal_id}",
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()

    # Verify all payments are recorded
    payments = res.get("data").get("payments")
    assert len(payments) == 3

    # Verify "Others" payment
    others_payment = next((p for p in payments if p.get("paymentCode") == "12"), None)
    assert others_payment is not None
    assert others_payment.get("paymentAmount") == others_amount

    # Verify cashless payment
    cashless_payment = next((p for p in payments if p.get("paymentCode") == "11"), None)
    assert cashless_payment is not None
    assert cashless_payment.get("paymentAmount") == cashless_amount

    # Verify cash payment
    cash_payment = next((p for p in payments if p.get("paymentCode") == "01"), None)
    assert cash_payment is not None
    # For cash payments, the recorded amount should equal deposit minus change
    assert cash_payment.get("paymentAmount") == total_amount - others_amount - cashless_amount



# Test - unregistered item error
@pytest.mark.asyncio
async def test_unregistered_item_error(http_client):
    """Test error handling when using an unregistered item code"""

    # Auth + tenant + terminal setup
    token = await get_authentication_token()
    tenant_id = await create_tenant(http_client, token)
    terminal_info = await get_terminal_info(tenant_id)
    terminal_id = terminal_info["terminalId"]
    api_key = terminal_info.get("apiKey")
    header = {"X-API-KEY": api_key}

    # Make sure the terminal is opened
    current_status = terminal_info.get("status", "")
    if current_status != "Opened":
        await open_terminal(tenant_id)

    # Create cart
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    cartId = res.get("data").get("cartId")

    # Try adding an item using an unregistered item code
    response = await http_client.post(
        f"/api/v1/carts/{cartId}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "NONEXISTENT", "quantity": 1}],
        headers=header,
    )

    # Unregistered items must return 404 Not Found or 422 Unprocessable Entity
    assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY]
    res = response.json()

    # Cancel cart to clean up
    await http_client.post(f"/api/v1/carts/{cartId}/cancel?terminal_id={terminal_id}", headers=header)

