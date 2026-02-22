# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import os
from datetime import datetime, timedelta, timezone
from fastapi import status
from httpx import AsyncClient


async def cleanup_test_promotions(tenant_id: str, promotion_codes: list[str]):
    """
    Physically delete test promotions from database to ensure clean test state.
    This is necessary because soft delete doesn't free up the unique index key.
    """
    from kugel_common.database import database as db_helper

    # Reset the MongoDB client to use the current event loop
    await db_helper.reset_client_async()

    db_name = f"db_master_{tenant_id}"
    db = await db_helper.get_db_async(db_name)
    collection = db["master_promotion"]

    for code in promotion_codes:
        result = await collection.delete_many({
            "tenant_id": tenant_id,
            "promotion_code": code
        })
        if result.deleted_count > 0:
            print(f"[CLEANUP] Physically deleted promotion: {code} ({result.deleted_count} docs)")


async def get_authentication_token():
    """Get authentication token from account service."""
    tenant_id = os.environ.get("TENANT_ID")
    token_url = os.environ.get("TOKEN_URL")
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}

    async with AsyncClient() as http_auth_client:
        response = await http_auth_client.post(url=token_url, data=login_data)

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    return res.get("access_token")


async def open_terminal(tenant_id=None):
    """Open terminal for testing."""
    if tenant_id is None:
        tenant_id = os.environ.get("TENANT_ID")

    terminal_id = os.environ.get("TERMINAL_ID")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}
    base_url = os.environ.get("BASE_URL_TERMINAL")

    # Set function mode to OpenTerminal
    req_data = {"function_mode": "OpenTerminal"}
    async with AsyncClient(base_url=base_url) as client:
        await client.patch(f"/terminals/{terminal_id}/function_mode", json=req_data, headers=header)

    # Sign in
    req_data = {"staff_id": "S001"}
    async with AsyncClient(base_url=base_url) as client:
        await client.post(f"/terminals/{terminal_id}/sign-in", json=req_data, headers=header)

    # Open terminal
    req_data = {"initial_amount": 500000}
    async with AsyncClient(base_url=base_url) as client:
        await client.post(f"/terminals/{terminal_id}/open", json=req_data, headers=header)

    # Set function mode to Sales
    req_data = {"function_mode": "Sales"}
    async with AsyncClient(base_url=base_url) as client:
        await client.patch(f"/terminals/{terminal_id}/function_mode", json=req_data, headers=header)


async def create_test_promotion(token: str, tenant_id: str, store_code: str):
    """Create a test promotion in master-data service."""
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    header = {"Authorization": f"Bearer {token}"}

    # Use UTC time to ensure promotion is active (MongoDB stores/compares in UTC)
    now = datetime.now(timezone.utc)
    start_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    end_datetime = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")

    promotion_data = {
        "promotionCode": "TEST_CART_PROMO",
        "promotionType": "category_discount",
        "name": "Cart Test Promotion",
        "description": "10% off on category 001",
        "startDatetime": start_datetime,
        "endDatetime": end_datetime,
        "isActive": True,
        "detail": {
            "targetStoreCodes": [store_code],
            "targetCategoryCodes": ["001"],
            "discountRate": 10.0,
        },
    }

    async with AsyncClient(base_url=base_url) as client:
        response = await client.post(
            f"/tenants/{tenant_id}/promotions", json=promotion_data, headers=header
        )

    # Ignore if promotion already exists (409 conflict)
    if response.status_code not in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]:
        print(f"Create promotion response: {response.status_code} {response.text}")

    return "TEST_CART_PROMO"


async def delete_test_promotion(token: str, tenant_id: str, promotion_code: str):
    """Delete a test promotion from master-data service."""
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    header = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(base_url=base_url) as client:
        await client.delete(
            f"/tenants/{tenant_id}/promotions/{promotion_code}", headers=header
        )


@pytest.mark.asyncio()
async def test_category_promo_applied_to_cart(http_client):
    """
    Test that category promotions are applied to cart items.

    Steps:
    1. Create a test promotion for category "001" with 10% discount
    2. Open terminal
    3. Create a cart
    4. Add an item with category "001"
    5. Verify that the discount is applied with correct promotion_code
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}

    # Cleanup: Physically delete existing test promotions from database
    await cleanup_test_promotions(tenant_id, ["TEST_CART_PROMO"])

    # Get token and create promotion
    token = await get_authentication_token()
    promotion_code = await create_test_promotion(token, tenant_id, store_code)

    terminal_id = os.environ.get("TERMINAL_ID")

    try:
        # Open terminal
        await open_terminal(tenant_id)

        # Create cart with terminal_id in query params and required body
        cart_body = {"transaction_type": 101, "user_id": "99", "user_name": "Test User"}
        response = await http_client.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json=cart_body,
            headers=header
        )
        res = response.json()
        print(f"Create cart response: {res}")
        assert response.status_code == status.HTTP_201_CREATED
        assert res.get("success") is True
        cart_id = res.get("data").get("cartId")
        print(f"Cart ID: {cart_id}")

        # Add item with category "001" (item code "49-01" should have category "001")
        add_item_data = [{"itemCode": "49-01", "unitPrice": None, "quantity": 2}]
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=add_item_data,
            headers=header
        )
        res = response.json()
        print(f"Add item response: {res}")
        assert response.status_code == status.HTTP_200_OK
        assert res.get("success") is True

        # Check if discount was applied
        line_items = res.get("data").get("lineItems", [])
        assert len(line_items) > 0

        added_item = line_items[0]
        print(f"Added item: {added_item}")

        # Verify category matches promotion target
        assert added_item.get("categoryCode") == "001", (
            f"Expected category '001' but got '{added_item.get('categoryCode')}'"
        )

        # Verify discount was applied
        discounts = added_item.get("discounts", [])
        category_discounts = [
            d for d in discounts if d.get("promotionType") == "category_discount"
        ]
        assert len(category_discounts) > 0, "Category discount not applied!"

        discount = category_discounts[0]
        assert discount.get("promotionCode") == promotion_code
        assert discount.get("promotionType") == "category_discount"
        assert discount.get("discountType") == "DiscountPercentage"
        assert discount.get("discountValue") == 10.0
        print("Category promotion applied successfully!")

    finally:
        # Cleanup: delete test promotion
        await delete_test_promotion(token, tenant_id, promotion_code)


@pytest.mark.asyncio()
async def test_category_promo_respects_discount_restriction(http_client):
    """
    Test that category promotions respect the is_discount_restricted flag.

    This test verifies that:
    - Items with is_discount_restricted=False get discounts applied
    - Items with is_discount_restricted=True don't get category discounts

    Note: The behavior depends on the item's is_discount_restricted flag in master data.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}

    # Cleanup: Physically delete existing test promotions from database
    await cleanup_test_promotions(tenant_id, ["TEST_CART_PROMO"])

    # Get token and create promotion
    token = await get_authentication_token()
    promotion_code = await create_test_promotion(token, tenant_id, store_code)

    terminal_id = os.environ.get("TERMINAL_ID")

    try:
        # Open terminal
        await open_terminal(tenant_id)

        # Create cart with terminal_id in query params and required body
        cart_body = {"transaction_type": 101, "user_id": "99", "user_name": "Test User"}
        response = await http_client.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json=cart_body,
            headers=header
        )
        res = response.json()
        assert response.status_code == status.HTTP_201_CREATED
        cart_id = res.get("data").get("cartId")

        # Add item with category "001" (item code "49-01" should have category "001")
        add_item_data = [{"itemCode": "49-01", "unitPrice": None, "quantity": 1}]
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=add_item_data,
            headers=header
        )
        res = response.json()
        print(f"Add item response: {res}")
        assert response.status_code == status.HTTP_200_OK

        # Check the item
        line_items = res.get("data").get("lineItems", [])
        assert len(line_items) > 0

        added_item = line_items[0]
        is_restricted = added_item.get("isDiscountRestricted", False)
        discounts = added_item.get("discounts", [])
        category_code = added_item.get("categoryCode")

        print(f"category_code: {category_code}")
        print(f"is_discount_restricted: {is_restricted}")
        print(f"discounts: {discounts}")

        # Verify discount behavior based on restriction status
        category_discounts = [
            d for d in discounts if d.get("promotionType") == "category_discount"
        ]

        if is_restricted:
            # If restricted, there should be no category discounts
            assert len(category_discounts) == 0, "Discount applied to restricted item!"
            print("Correctly skipped discount for restricted item")
        else:
            # If not restricted and category matches, discount should be applied
            if category_code == "001":
                assert len(category_discounts) > 0, "Discount not applied to non-restricted item!"
                print("Correctly applied discount to non-restricted item")
            else:
                print(f"Item category {category_code} doesn't match promotion target 001")

    finally:
        # Cleanup
        await delete_test_promotion(token, tenant_id, promotion_code)


@pytest.mark.asyncio()
async def test_category_promo_all_stores(http_client):
    """
    Test that promotions with empty targetStoreCodes apply to all stores.
    """
    tenant_id = os.environ.get("TENANT_ID")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}

    # Cleanup: Physically delete existing test promotions from database
    await cleanup_test_promotions(tenant_id, ["TEST_ALL_STORES_PROMO"])

    # Get token
    token = await get_authentication_token()
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    auth_header = {"Authorization": f"Bearer {token}"}

    # Use UTC time to ensure promotion is active (MongoDB stores/compares in UTC)
    now = datetime.now(timezone.utc)
    start_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    end_datetime = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")

    # Create promotion for ALL stores (empty targetStoreCodes)
    promotion_data = {
        "promotionCode": "TEST_ALL_STORES_PROMO",
        "promotionType": "category_discount",
        "name": "All Stores Promotion",
        "startDatetime": start_datetime,
        "endDatetime": end_datetime,
        "isActive": True,
        "detail": {
            "targetStoreCodes": [],  # Empty means all stores
            "targetCategoryCodes": ["001"],
            "discountRate": 5.0,
        },
    }

    async with AsyncClient(base_url=base_url) as client:
        response = await client.post(
            f"/tenants/{tenant_id}/promotions", json=promotion_data, headers=auth_header
        )

    terminal_id = os.environ.get("TERMINAL_ID")

    try:
        # Open terminal
        await open_terminal(tenant_id)

        # Create cart with terminal_id in query params and required body
        cart_body = {"transaction_type": 101, "user_id": "99", "user_name": "Test User"}
        response = await http_client.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json=cart_body,
            headers=header
        )
        res = response.json()
        assert response.status_code == status.HTTP_201_CREATED
        cart_id = res.get("data").get("cartId")

        # Add item with category "001" (item code "49-01" should have category "001")
        add_item_data = [{"itemCode": "49-01", "unitPrice": None, "quantity": 1}]
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=add_item_data,
            headers=header
        )
        res = response.json()
        print(f"Add item response: {res}")
        assert response.status_code == status.HTTP_200_OK

        # Check if promotion was applied
        line_items = res.get("data").get("lineItems", [])
        assert len(line_items) > 0

        added_item = line_items[0]
        assert added_item.get("categoryCode") == "001", (
            f"Expected category '001' but got '{added_item.get('categoryCode')}'"
        )

        discounts = added_item.get("discounts", [])
        category_discounts = [
            d for d in discounts if d.get("promotionType") == "category_discount"
        ]
        assert len(category_discounts) > 0, "All-stores promotion not applied!"

        discount = category_discounts[0]
        assert discount.get("promotionCode") == "TEST_ALL_STORES_PROMO"
        assert discount.get("discountType") == "DiscountPercentage"
        assert discount.get("discountValue") == 5.0
        print("All-stores promotion applied successfully!")

    finally:
        # Cleanup
        await delete_test_promotion(token, tenant_id, "TEST_ALL_STORES_PROMO")


@pytest.mark.asyncio()
async def test_category_promo_best_discount_selected(http_client):
    """
    Test that when multiple promotions match, the highest discount is selected.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}

    # Cleanup: Physically delete existing test promotions from database
    await cleanup_test_promotions(tenant_id, ["TEST_PROMO_10PCT", "TEST_PROMO_15PCT"])

    token = await get_authentication_token()
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    auth_header = {"Authorization": f"Bearer {token}"}

    # Use UTC time to ensure promotion is active (MongoDB stores/compares in UTC)
    now = datetime.now(timezone.utc)
    start_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    end_datetime = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")

    # Create promotion 1: 10% discount
    promo1_data = {
        "promotionCode": "TEST_PROMO_10PCT",
        "promotionType": "category_discount",
        "name": "10% Discount",
        "startDatetime": start_datetime,
        "endDatetime": end_datetime,
        "isActive": True,
        "detail": {
            "targetStoreCodes": [store_code],
            "targetCategoryCodes": ["001"],
            "discountRate": 10.0,
        },
    }

    # Create promotion 2: 15% discount (higher)
    promo2_data = {
        "promotionCode": "TEST_PROMO_15PCT",
        "promotionType": "category_discount",
        "name": "15% Discount",
        "startDatetime": start_datetime,
        "endDatetime": end_datetime,
        "isActive": True,
        "detail": {
            "targetStoreCodes": [store_code],
            "targetCategoryCodes": ["001"],
            "discountRate": 15.0,
        },
    }

    async with AsyncClient(base_url=base_url) as client:
        await client.post(f"/tenants/{tenant_id}/promotions", json=promo1_data, headers=auth_header)
        await client.post(f"/tenants/{tenant_id}/promotions", json=promo2_data, headers=auth_header)

    terminal_id = os.environ.get("TERMINAL_ID")

    try:
        # Open terminal
        await open_terminal(tenant_id)

        # Create cart with terminal_id in query params and required body
        cart_body = {"transaction_type": 101, "user_id": "99", "user_name": "Test User"}
        response = await http_client.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json=cart_body,
            headers=header
        )
        res = response.json()
        assert response.status_code == status.HTTP_201_CREATED
        cart_id = res.get("data").get("cartId")

        # Add item with category "001" (item code "49-01" should have category "001")
        add_item_data = [{"itemCode": "49-01", "unitPrice": None, "quantity": 1}]
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=add_item_data,
            headers=header
        )
        res = response.json()
        print(f"Add item response: {res}")
        assert response.status_code == status.HTTP_200_OK

        # Check if the best discount was applied
        line_items = res.get("data").get("lineItems", [])
        assert len(line_items) > 0

        added_item = line_items[0]
        assert added_item.get("categoryCode") == "001", (
            f"Expected category '001' but got '{added_item.get('categoryCode')}'"
        )

        discounts = added_item.get("discounts", [])
        category_discounts = [
            d for d in discounts if d.get("promotionType") == "category_discount"
        ]
        assert len(category_discounts) > 0, "No category discount applied!"

        # Should have the 15% discount (best)
        discount = category_discounts[0]
        assert discount.get("discountValue") == 15.0, (
            f"Expected 15% discount but got {discount.get('discountValue')}%"
        )
        assert discount.get("promotionCode") == "TEST_PROMO_15PCT"
        print("Best discount (15%) correctly selected!")

    finally:
        # Cleanup
        await delete_test_promotion(token, tenant_id, "TEST_PROMO_10PCT")
        await delete_test_promotion(token, tenant_id, "TEST_PROMO_15PCT")


@pytest.mark.asyncio()
async def test_category_promo_not_applied_to_non_matching_category(http_client):
    """
    Test that category promotions are NOT applied when item category does not match.

    Creates a promotion targeting category "999" (non-existent),
    then adds item "49-01" (category "001") and verifies no discount is applied.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}

    promo_code = "TEST_NON_MATCH_PROMO"
    await cleanup_test_promotions(tenant_id, [promo_code])

    token = await get_authentication_token()
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    auth_header = {"Authorization": f"Bearer {token}"}

    now = datetime.now(timezone.utc)
    promotion_data = {
        "promotionCode": promo_code,
        "promotionType": "category_discount",
        "name": "Non-matching Category Promotion",
        "startDatetime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "endDatetime": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
        "isActive": True,
        "detail": {
            "targetStoreCodes": [store_code],
            "targetCategoryCodes": ["999"],  # No items have this category
            "discountRate": 20.0,
        },
    }

    async with AsyncClient(base_url=base_url) as client:
        response = await client.post(
            f"/tenants/{tenant_id}/promotions", json=promotion_data, headers=auth_header
        )
    assert response.status_code == status.HTTP_201_CREATED

    terminal_id = os.environ.get("TERMINAL_ID")

    try:
        await open_terminal(tenant_id)

        cart_body = {"transaction_type": 101, "user_id": "99", "user_name": "Test User"}
        response = await http_client.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json=cart_body,
            headers=header
        )
        res = response.json()
        assert response.status_code == status.HTTP_201_CREATED
        cart_id = res.get("data").get("cartId")

        # Add item with category "001" - does NOT match promotion target "999"
        add_item_data = [{"itemCode": "49-01", "unitPrice": None, "quantity": 1}]
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=add_item_data,
            headers=header
        )
        res = response.json()
        print(f"Add item response: {res}")
        assert response.status_code == status.HTTP_200_OK

        line_items = res.get("data").get("lineItems", [])
        assert len(line_items) > 0

        added_item = line_items[0]
        assert added_item.get("categoryCode") == "001"

        category_discounts = [
            d for d in added_item.get("discounts", [])
            if d.get("promotionType") == "category_discount"
        ]
        assert len(category_discounts) == 0, (
            "Discount should NOT be applied when category does not match!"
        )
        print("Correctly skipped discount for non-matching category")

    finally:
        await delete_test_promotion(token, tenant_id, promo_code)


@pytest.mark.asyncio()
async def test_category_promo_inactive_not_applied(http_client):
    """
    Test that inactive promotions (isActive=false) are NOT applied.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}

    promo_code = "TEST_INACTIVE_PROMO"
    await cleanup_test_promotions(tenant_id, [promo_code])

    token = await get_authentication_token()
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    auth_header = {"Authorization": f"Bearer {token}"}

    now = datetime.now(timezone.utc)
    promotion_data = {
        "promotionCode": promo_code,
        "promotionType": "category_discount",
        "name": "Inactive Promotion",
        "startDatetime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "endDatetime": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
        "isActive": False,  # Inactive
        "detail": {
            "targetStoreCodes": [store_code],
            "targetCategoryCodes": ["001"],
            "discountRate": 10.0,
        },
    }

    async with AsyncClient(base_url=base_url) as client:
        response = await client.post(
            f"/tenants/{tenant_id}/promotions", json=promotion_data, headers=auth_header
        )
    assert response.status_code == status.HTTP_201_CREATED

    terminal_id = os.environ.get("TERMINAL_ID")

    try:
        await open_terminal(tenant_id)

        cart_body = {"transaction_type": 101, "user_id": "99", "user_name": "Test User"}
        response = await http_client.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json=cart_body,
            headers=header
        )
        res = response.json()
        assert response.status_code == status.HTTP_201_CREATED
        cart_id = res.get("data").get("cartId")

        add_item_data = [{"itemCode": "49-01", "unitPrice": None, "quantity": 1}]
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=add_item_data,
            headers=header
        )
        res = response.json()
        print(f"Add item response: {res}")
        assert response.status_code == status.HTTP_200_OK

        line_items = res.get("data").get("lineItems", [])
        assert len(line_items) > 0

        added_item = line_items[0]
        category_discounts = [
            d for d in added_item.get("discounts", [])
            if d.get("promotionCode") == promo_code
        ]
        assert len(category_discounts) == 0, (
            "Inactive promotion should NOT be applied!"
        )
        print("Correctly skipped inactive promotion")

    finally:
        await delete_test_promotion(token, tenant_id, promo_code)


@pytest.mark.asyncio()
async def test_category_promo_expired_not_applied(http_client):
    """
    Test that expired promotions (endDatetime in the past) are NOT applied.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}

    promo_code = "TEST_EXPIRED_PROMO"
    await cleanup_test_promotions(tenant_id, [promo_code])

    token = await get_authentication_token()
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    auth_header = {"Authorization": f"Bearer {token}"}

    # Create promotion that already expired (ended 1 hour ago)
    now = datetime.now(timezone.utc)
    promotion_data = {
        "promotionCode": promo_code,
        "promotionType": "category_discount",
        "name": "Expired Promotion",
        "startDatetime": (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
        "endDatetime": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"),
        "isActive": True,
        "detail": {
            "targetStoreCodes": [store_code],
            "targetCategoryCodes": ["001"],
            "discountRate": 10.0,
        },
    }

    async with AsyncClient(base_url=base_url) as client:
        response = await client.post(
            f"/tenants/{tenant_id}/promotions", json=promotion_data, headers=auth_header
        )
    assert response.status_code == status.HTTP_201_CREATED

    terminal_id = os.environ.get("TERMINAL_ID")

    try:
        await open_terminal(tenant_id)

        cart_body = {"transaction_type": 101, "user_id": "99", "user_name": "Test User"}
        response = await http_client.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json=cart_body,
            headers=header
        )
        res = response.json()
        assert response.status_code == status.HTTP_201_CREATED
        cart_id = res.get("data").get("cartId")

        add_item_data = [{"itemCode": "49-01", "unitPrice": None, "quantity": 1}]
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=add_item_data,
            headers=header
        )
        res = response.json()
        print(f"Add item response: {res}")
        assert response.status_code == status.HTTP_200_OK

        line_items = res.get("data").get("lineItems", [])
        assert len(line_items) > 0

        added_item = line_items[0]
        category_discounts = [
            d for d in added_item.get("discounts", [])
            if d.get("promotionCode") == promo_code
        ]
        assert len(category_discounts) == 0, (
            "Expired promotion should NOT be applied!"
        )
        print("Correctly skipped expired promotion")

    finally:
        await delete_test_promotion(token, tenant_id, promo_code)


@pytest.mark.asyncio()
async def test_category_promo_discount_amount_calculation(http_client):
    """
    Test that discount amount is calculated correctly.

    Item "49-01" has unit_price=100, quantity=2 → base_amount=200
    Promotion: 10% discount → discount_amount should be 20
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    api_key = os.environ.get("API_KEY")
    header = {"X-API-KEY": api_key}

    await cleanup_test_promotions(tenant_id, ["TEST_CART_PROMO"])

    token = await get_authentication_token()
    promotion_code = await create_test_promotion(token, tenant_id, store_code)

    terminal_id = os.environ.get("TERMINAL_ID")

    try:
        await open_terminal(tenant_id)

        cart_body = {"transaction_type": 101, "user_id": "99", "user_name": "Test User"}
        response = await http_client.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json=cart_body,
            headers=header
        )
        res = response.json()
        assert response.status_code == status.HTTP_201_CREATED
        cart_id = res.get("data").get("cartId")

        # Add item with quantity=2 to verify amount calculation
        add_item_data = [{"itemCode": "49-01", "unitPrice": None, "quantity": 2}]
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=add_item_data,
            headers=header
        )
        res = response.json()
        print(f"Add item response: {res}")
        assert response.status_code == status.HTTP_200_OK

        line_items = res.get("data").get("lineItems", [])
        assert len(line_items) > 0

        added_item = line_items[0]
        unit_price = added_item.get("unitPrice")
        quantity = added_item.get("quantity")
        print(f"unit_price: {unit_price}, quantity: {quantity}")

        category_discounts = [
            d for d in added_item.get("discounts", [])
            if d.get("promotionType") == "category_discount"
        ]
        assert len(category_discounts) > 0, "Category discount not applied!"

        discount = category_discounts[0]
        assert discount.get("discountValue") == 10.0

        # Verify discount amount: unit_price * quantity * rate / 100
        expected_amount = round(unit_price * quantity * 10.0 / 100, 0)
        actual_amount = discount.get("discountAmount")
        print(f"expected_amount: {expected_amount}, actual_amount: {actual_amount}")
        assert actual_amount == expected_amount, (
            f"Expected discount amount {expected_amount} but got {actual_amount}"
        )
        print(f"Discount amount correctly calculated: {actual_amount}")

    finally:
        await delete_test_promotion(token, tenant_id, promotion_code)
