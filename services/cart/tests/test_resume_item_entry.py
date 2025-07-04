# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Test cases for resume item entry functionality.

This module tests the ability to transition a cart from Paying state
back to EnteringItem state, clearing payment information.
"""

import pytest
import pytest_asyncio
import os
from decimal import Decimal
from httpx import AsyncClient
from fastapi import status

from app.enums.cart_status import CartStatus
from kugel_common.exceptions import EventBadSequenceException


@pytest_asyncio.fixture
async def async_client(set_env_vars):
    """Create async HTTP client for testing."""
    base_url = os.environ.get("BASE_URL_CART")
    async with AsyncClient(base_url=base_url) as client:
        yield client


@pytest.fixture
def terminal_api_key(set_env_vars):
    """Get terminal API key."""
    return os.environ.get("API_KEY")


@pytest.fixture
def create_cart_data():
    """Cart creation data."""
    return {"storeCode": os.environ.get("STORE_CODE"), "terminalNo": 9, "staffCode": "2001", "customerCode": "0001"}


@pytest.fixture
def add_item_data():
    """Item addition data."""
    return {"itemCode": "4901780723102", "quantity": 1}


@pytest.fixture
def add_payment_data():
    """Payment addition data."""
    return {"paymentCode": "cash", "amount": 100.0, "detail": {}}


@pytest.mark.asyncio
async def test_resume_item_entry_from_paying_state(
    async_client: AsyncClient,
    terminal_api_key: str,
    create_cart_data: dict,
    add_item_data: dict,
    add_payment_data: dict,
):
    """Test resuming item entry from paying state."""
    headers = {"x-api-key": terminal_api_key}

    # Create cart
    response = await async_client.post("/api/v1/carts", json=create_cart_data, headers=headers)
    assert response.status_code == 201
    cart_id = response.json()["data"]["cartId"]

    # Add an item
    response = await async_client.post(f"/api/v1/carts/{cart_id}/lineItems", json=add_item_data, headers=headers)
    assert response.status_code == 200

    # Execute subtotal to move to Paying state
    response = await async_client.post(f"/api/v1/carts/{cart_id}/subtotal", headers=headers)
    assert response.status_code == 200
    cart_data = response.json()["data"]
    assert cart_data["status"] == CartStatus.Paying.value

    # Add a payment
    payment_amount = cart_data["balanceAmount"] / 2  # Pay half
    payment_data = {"paymentCode": add_payment_data["paymentCode"], "amount": payment_amount, "detail": {}}
    response = await async_client.post(f"/api/v1/carts/{cart_id}/payments", json=[payment_data], headers=headers)
    assert response.status_code == 200
    cart_data = response.json()["data"]
    assert len(cart_data["payments"]) == 1
    assert cart_data["payments"][0]["amount"] == payment_amount

    # Resume item entry
    response = await async_client.post(f"/api/v1/carts/{cart_id}/resume-item-entry", headers=headers)
    assert response.status_code == 200
    cart_data = response.json()["data"]

    # Verify state transition and payment clearing
    assert cart_data["status"] == CartStatus.EnteringItem.value
    assert len(cart_data["payments"]) == 0
    assert cart_data["balanceAmount"] == cart_data["totalAmount"]

    # Verify we can add items again
    response = await async_client.post(f"/api/v1/carts/{cart_id}/lineItems", json=add_item_data, headers=headers)
    assert response.status_code == 200
    assert len(response.json()["data"]["lineItems"]) == 2


@pytest.mark.asyncio
async def test_resume_item_entry_from_invalid_states(
    async_client: AsyncClient, terminal_api_key: str, create_cart_data: dict, add_item_data: dict
):
    """Test that resume item entry fails from invalid states."""
    headers = {"x-api-key": terminal_api_key}

    # Test from Idle state
    response = await async_client.post("/api/v1/carts", json=create_cart_data, headers=headers)
    assert response.status_code == 201
    cart_id_idle = response.json()["data"]["cartId"]

    response = await async_client.post(f"/api/v1/carts/{cart_id_idle}/resume-item-entry", headers=headers)
    assert response.status_code == 400
    assert "Invalid event" in response.json()["message"]

    # Test from EnteringItem state
    response = await async_client.post("/api/v1/carts", json=create_cart_data, headers=headers)
    assert response.status_code == 201
    cart_id_entering = response.json()["data"]["cartId"]

    response = await async_client.post(
        f"/api/v1/carts/{cart_id_entering}/lineItems", json=add_item_data, headers=headers
    )
    assert response.status_code == 200

    response = await async_client.post(f"/api/v1/carts/{cart_id_entering}/resume-item-entry", headers=headers)
    assert response.status_code == 400
    assert "Invalid event" in response.json()["message"]


@pytest.mark.asyncio
async def test_resume_item_entry_preserves_line_items(
    async_client: AsyncClient, terminal_api_key: str, create_cart_data: dict, add_item_data: dict
):
    """Test that resume item entry preserves existing line items."""
    headers = {"x-api-key": terminal_api_key}

    # Create cart and add multiple items
    response = await async_client.post("/api/v1/carts", json=create_cart_data, headers=headers)
    assert response.status_code == 201
    cart_id = response.json()["data"]["cartId"]

    # Add items with different quantities
    for i in range(3):
        item_data = add_item_data.copy()
        item_data["quantity"] = i + 1
        response = await async_client.post(f"/api/v1/carts/{cart_id}/lineItems", json=item_data, headers=headers)
        assert response.status_code == 200

    # Execute subtotal
    response = await async_client.post(f"/api/v1/carts/{cart_id}/subtotal", headers=headers)
    assert response.status_code == 200
    original_cart = response.json()["data"]
    original_line_items = original_cart["lineItems"]
    original_total = original_cart["totalAmount"]

    # Resume item entry
    response = await async_client.post(f"/api/v1/carts/{cart_id}/resume-item-entry", headers=headers)
    assert response.status_code == 200
    resumed_cart = response.json()["data"]

    # Verify line items are preserved
    assert len(resumed_cart["lineItems"]) == len(original_line_items)
    for i, line_item in enumerate(resumed_cart["lineItems"]):
        assert line_item["itemCode"] == original_line_items[i]["itemCode"]
        assert line_item["quantity"] == original_line_items[i]["quantity"]
        assert line_item["unitPrice"] == original_line_items[i]["unitPrice"]
        assert line_item["amount"] == original_line_items[i]["amount"]

    # Verify totals are preserved
    assert resumed_cart["totalAmount"] == original_total
    assert resumed_cart["balanceAmount"] == original_total


@pytest.mark.asyncio
async def test_resume_item_entry_clears_all_payments(
    async_client: AsyncClient,
    terminal_api_key: str,
    create_cart_data: dict,
    add_item_data: dict,
    add_payment_data: dict,
):
    """Test that resume item entry clears all payment records."""
    headers = {"x-api-key": terminal_api_key}

    # Create cart and prepare for payment
    response = await async_client.post("/api/v1/carts", json=create_cart_data, headers=headers)
    assert response.status_code == 201
    cart_id = response.json()["data"]["cartId"]

    response = await async_client.post(f"/api/v1/carts/{cart_id}/lineItems", json=add_item_data, headers=headers)
    assert response.status_code == 200

    response = await async_client.post(f"/api/v1/carts/{cart_id}/subtotal", headers=headers)
    assert response.status_code == 200
    total_amount = response.json()["data"]["totalAmount"]

    # Add multiple payments
    payment1 = {
        "paymentCode": add_payment_data["paymentCode"],
        "amount": total_amount * 0.3,
        "detail": {"note": "First payment"},
    }
    payment2 = {
        "paymentCode": add_payment_data["paymentCode"],
        "amount": total_amount * 0.5,
        "detail": {"note": "Second payment"},
    }

    response = await async_client.post(f"/api/v1/carts/{cart_id}/payments", json=[payment1, payment2], headers=headers)
    assert response.status_code == 200
    cart_data = response.json()["data"]
    assert len(cart_data["payments"]) == 2

    # Resume item entry
    response = await async_client.post(f"/api/v1/carts/{cart_id}/resume-item-entry", headers=headers)
    assert response.status_code == 200
    cart_data = response.json()["data"]

    # Verify all payments are cleared
    assert len(cart_data["payments"]) == 0
    assert cart_data["balanceAmount"] == cart_data["totalAmount"]
