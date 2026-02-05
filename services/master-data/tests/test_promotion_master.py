# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import os
from datetime import datetime, timedelta
from fastapi import status
from httpx import AsyncClient


async def cleanup_test_promotions(tenant_id: str, promotion_codes: list[str]):
    """
    Physically delete test promotions from database to ensure clean test state.
    This is necessary because soft delete doesn't free up the unique index key.
    """
    from kugel_common.database import database as db_helper

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


@pytest.mark.asyncio()
async def test_promotion_master(http_client):
    """
    Test promotion master CRUD operations.

    Tests include:
    - Create promotion
    - Get all promotions
    - Get promotion by code
    - Get active promotions
    - Update promotion
    - Delete promotion
    - Validation errors
    """
    # Set tenant_id & store_code
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")

    # Get token from auth service
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    token = res.get("access_token")
    header = {"Authorization": f"Bearer {token}"}

    # Define test data
    promotion_code = "TEST_PROMO_001"
    promotion_code_all_stores = "TEST_PROMO_ALL_STORES"
    now = datetime.now()
    start_datetime = now.strftime("%Y-%m-%dT%H:%M:%S")
    end_datetime = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")

    #
    # Cleanup: Physically delete existing test promotions from database
    # This is necessary because soft delete doesn't free up the unique index key
    #
    await cleanup_test_promotions(tenant_id, [promotion_code, promotion_code_all_stores])

    #
    # Test 1: Create a new promotion
    #
    promotion_data = {
        "promotionCode": promotion_code,
        "promotionType": "category_discount",
        "name": "Test Summer Sale",
        "description": "10% off on beverages",
        "startDatetime": start_datetime,
        "endDatetime": end_datetime,
        "isActive": True,
        "categoryPromoDetail": {
            "targetStoreCodes": [store_code],
            "targetCategoryCodes": ["BEV001", "BEV002"],
            "discountRate": 10.0,
        },
    }

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/promotions", json=promotion_data, headers=header
    )
    res = response.json()
    print(f"Create promotion response: {res}")
    assert response.status_code == status.HTTP_201_CREATED
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("promotionCode") == promotion_code
    assert res.get("data").get("promotionType") == "category_discount"
    assert res.get("data").get("name") == "Test Summer Sale"
    assert res.get("data").get("isActive") is True
    assert res.get("data").get("categoryPromoDetail").get("discountRate") == 10.0

    #
    # Test 2: Create duplicate promotion (should fail)
    #
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/promotions", json=promotion_data, headers=header
    )
    res = response.json()
    print(f"Duplicate promotion response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_400_BAD_REQUEST

    #
    # Test 3: Get promotion by code
    #
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/promotions/{promotion_code}", headers=header
    )
    res = response.json()
    print(f"Get promotion response: {res}")
    assert response.status_code == status.HTTP_200_OK
    assert res.get("success") is True
    assert res.get("data").get("promotionCode") == promotion_code

    #
    # Test 4: Get all promotions with pagination
    #
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/promotions", headers=header
    )
    res = response.json()
    print(f"Get all promotions response: {res}")
    assert response.status_code == status.HTTP_200_OK
    assert res.get("success") is True
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 1

    #
    # Test 5: Get promotions filtered by type
    #
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/promotions?promotionType=category_discount",
        headers=header,
    )
    res = response.json()
    print(f"Get promotions by type response: {res}")
    assert response.status_code == status.HTTP_200_OK
    assert res.get("success") is True
    # All returned promotions should be category_discount type
    for promo in res.get("data"):
        assert promo.get("promotionType") == "category_discount"

    #
    # Test 6: Get active promotions
    #
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/promotions/active", headers=header
    )
    res = response.json()
    print(f"Get active promotions response: {res}")
    assert response.status_code == status.HTTP_200_OK
    assert res.get("success") is True
    # All returned promotions should be active
    for promo in res.get("data"):
        assert promo.get("isActive") is True

    #
    # Test 7: Get active promotions by store
    #
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/promotions/active?storeCode={store_code}",
        headers=header,
    )
    res = response.json()
    print(f"Get active promotions by store response: {res}")
    assert response.status_code == status.HTTP_200_OK
    assert res.get("success") is True

    #
    # Test 8: Update promotion
    #
    update_data = {
        "name": "Test Summer Sale Extended",
        "description": "15% off on beverages - Extended!",
        "categoryPromoDetail": {
            "targetStoreCodes": [store_code],
            "targetCategoryCodes": ["BEV001", "BEV002", "BEV003"],
            "discountRate": 15.0,
        },
    }
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/promotions/{promotion_code}",
        json=update_data,
        headers=header,
    )
    res = response.json()
    print(f"Update promotion response: {res}")
    assert response.status_code == status.HTTP_200_OK
    assert res.get("success") is True
    assert res.get("data").get("name") == "Test Summer Sale Extended"
    assert res.get("data").get("categoryPromoDetail").get("discountRate") == 15.0

    #
    # Test 9: Update non-existent promotion (should fail)
    #
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/promotions/NONEXISTENT",
        json=update_data,
        headers=header,
    )
    res = response.json()
    print(f"Update non-existent promotion response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_404_NOT_FOUND

    #
    # Test 10: Get non-existent promotion (should fail)
    #
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/promotions/NONEXISTENT", headers=header
    )
    res = response.json()
    print(f"Get non-existent promotion response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_404_NOT_FOUND

    #
    # Test 11: Create promotion for all stores (empty target_store_codes)
    #
    promotion_data_all_stores = {
        "promotionCode": promotion_code_all_stores,
        "promotionType": "category_discount",
        "name": "All Stores Promotion",
        "startDatetime": start_datetime,
        "endDatetime": end_datetime,
        "isActive": True,
        "categoryPromoDetail": {
            "targetStoreCodes": [],  # Empty means all stores
            "targetCategoryCodes": ["FOOD001"],
            "discountRate": 5.0,
        },
    }
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/promotions",
        json=promotion_data_all_stores,
        headers=header,
    )
    res = response.json()
    print(f"Create all-stores promotion response: {res}")
    assert response.status_code == status.HTTP_201_CREATED
    assert res.get("success") is True
    assert res.get("data").get("categoryPromoDetail").get("targetStoreCodes") == []

    #
    # Test 12: Delete promotion
    #
    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/promotions/{promotion_code}", headers=header
    )
    res = response.json()
    print(f"Delete promotion response: {res}")
    assert response.status_code == status.HTTP_200_OK
    assert res.get("success") is True
    assert res.get("data").get("promotionCode") == promotion_code

    #
    # Test 13: Delete non-existent promotion (should fail)
    #
    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/promotions/NONEXISTENT", headers=header
    )
    res = response.json()
    print(f"Delete non-existent promotion response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_404_NOT_FOUND

    #
    # Test 14: Verify deleted promotion is not found
    #
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/promotions/{promotion_code}", headers=header
    )
    res = response.json()
    print(f"Get deleted promotion response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_404_NOT_FOUND

    #
    # Cleanup: Delete all-stores promotion
    #
    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/promotions/{promotion_code_all_stores}",
        headers=header,
    )
    res = response.json()
    print(f"Cleanup all-stores promotion response: {res}")
    assert res.get("success") is True


@pytest.mark.asyncio()
async def test_promotion_validation(http_client):
    """
    Test promotion validation rules.

    Tests include:
    - Invalid date range (end before start)
    - Invalid discount rate
    - Missing required fields
    """
    # Set tenant_id
    tenant_id = os.environ.get("TENANT_ID")

    # Get token from auth service
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    token = res.get("access_token")
    header = {"Authorization": f"Bearer {token}"}

    now = datetime.now()

    #
    # Test 1: Invalid date range (end before start)
    #
    invalid_date_promotion = {
        "promotionCode": "INVALID_DATE_PROMO",
        "promotionType": "category_discount",
        "name": "Invalid Date Promotion",
        "startDatetime": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
        "endDatetime": now.strftime("%Y-%m-%dT%H:%M:%S"),  # End before start
        "isActive": True,
        "categoryPromoDetail": {
            "targetStoreCodes": [],
            "targetCategoryCodes": ["CAT001"],
            "discountRate": 10.0,
        },
    }
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/promotions",
        json=invalid_date_promotion,
        headers=header,
    )
    res = response.json()
    print(f"Invalid date promotion response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_422_UNPROCESSABLE_ENTITY

    #
    # Test 2: Invalid discount rate (over 100)
    #
    invalid_rate_promotion = {
        "promotionCode": "INVALID_RATE_PROMO",
        "promotionType": "category_discount",
        "name": "Invalid Rate Promotion",
        "startDatetime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "endDatetime": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
        "isActive": True,
        "categoryPromoDetail": {
            "targetStoreCodes": [],
            "targetCategoryCodes": ["CAT001"],
            "discountRate": 150.0,  # Over 100%
        },
    }
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/promotions",
        json=invalid_rate_promotion,
        headers=header,
    )
    res = response.json()
    print(f"Invalid rate promotion response: {res}")
    assert res.get("success") is False

    #
    # Test 3: Category discount without category_promo_detail
    #
    missing_detail_promotion = {
        "promotionCode": "MISSING_DETAIL_PROMO",
        "promotionType": "category_discount",
        "name": "Missing Detail Promotion",
        "startDatetime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "endDatetime": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
        "isActive": True,
        # categoryPromoDetail is missing
    }
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/promotions",
        json=missing_detail_promotion,
        headers=header,
    )
    res = response.json()
    print(f"Missing detail promotion response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_422_UNPROCESSABLE_ENTITY

    #
    # Test 4: Empty target_category_codes
    #
    empty_categories_promotion = {
        "promotionCode": "EMPTY_CATEGORIES_PROMO",
        "promotionType": "category_discount",
        "name": "Empty Categories Promotion",
        "startDatetime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "endDatetime": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
        "isActive": True,
        "categoryPromoDetail": {
            "targetStoreCodes": [],
            "targetCategoryCodes": [],  # Empty
            "discountRate": 10.0,
        },
    }
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/promotions",
        json=empty_categories_promotion,
        headers=header,
    )
    res = response.json()
    print(f"Empty categories promotion response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_422_UNPROCESSABLE_ENTITY
