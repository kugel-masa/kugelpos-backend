# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest, os
from fastapi import status
from httpx import AsyncClient

email_address = "someone@kugel.cloud"


@pytest.mark.asyncio()
async def test_operations(http_client):

    # set tenant_id & store_code
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")

    # get token from auth service
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    assert response.status_code == status.HTTP_200_OK

    res = response.json()
    print(f"Response: {res}")
    token = res.get("access_token")
    print(f"Token: {token}")
    header = {"Authorization": f"Bearer {token}"}

    # create a new tenant with invalid tenant_id
    tenant_data = {"tenantId": "ZZZZ"}
    response = await http_client.post("/api/v1/tenants", json=tenant_data, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_400_BAD_REQUEST

    # create a new tenant
    tenant_data = {"tenantId": tenant_id}
    response = await http_client.post("/api/v1/tenants", json=tenant_data, headers=header)
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("tenantId") == tenant_id

    # create a new staff_master
    staff_master = {"id": "1234", "name": "yushi", "pin": "9999", "roles": ["staff"]}
    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/staff", json=staff_master, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("id") == "1234"
    assert res.get("data").get("name") == "yushi"

    # get staff_master
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/staff/1234", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("id") == "1234"
    assert res.get("data").get("name") == "yushi"

    # get all staff_master without token
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/staff")
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_401_UNAUTHORIZED

    # get all staff_master
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/staff", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 1
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # update staff_master
    staff_master = {"name": "ushi", "pin": "8888", "roles": ["staff"]}
    response = await http_client.put(f"/api/v1/tenants/{tenant_id}/staff/1234", json=staff_master, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("id") == "1234"
    assert res.get("data").get("name") == "ushi"
    assert res.get("data").get("pin") == "8888"

    # update staff_master with invalid data
    staff_master = {
        "name": "ushi",
    }
    response = await http_client.put(f"/api/v1/tenants/{tenant_id}/staff/1234", json=staff_master, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_422_UNPROCESSABLE_ENTITY

    # update staff_master with invalid id (staff not found)
    staff_master = {"name": "ushi", "pin": "8888", "roles": ["staff"]}
    response = await http_client.put(f"/api/v1/tenants/{tenant_id}/staff/5678", json=staff_master, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_404_NOT_FOUND

    # delete staff_master with invalid id (staff not found)
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/staff/5678", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_404_NOT_FOUND

    # delete staff_master
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/staff/1234", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("staffId") == "1234"

    #
    # category_master
    #

    # create a new category
    category_code = "999"
    category_master = {
        "categoryCode": category_code,
        "description": "Electronics",
        "descriptionShort": "Elec",
        "taxCode": "01",
    }

    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/categories", json=category_master, headers=header)
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("categoryCode") == category_code

    # get all categories
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/categories", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"*** get all categories response: {res}")
    assert res.get("success") is True
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 1
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # get category by ID
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/categories/{category_code}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("categoryCode") == category_code
    assert res.get("data").get("description") == "Electronics"

    # update category
    updated_category_master = {
        "categoryCode": category_code,  # this id should not be changed
        "description": "Updated Electronics",
        "descriptionShort": "Updated Elec",
        "taxCode": "01",  # no change
    }

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/categories/{category_code}", json=updated_category_master, headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("data").get("description") == "Updated Electronics"

    # delete category
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/categories/{category_code}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True

    #
    # item_common_master
    #

    # create new instance of Item with test data
    item_master = {
        "itemCode": "1234",
        "description": "item 1234",
        "unitPrice": 100,
        "unitCost": 50,
        "itemDetails": ["detail1", "detail2"],
        "imageUrls": ["url1", "url2"],
        "categoryCode": "001",
        "taxCode": "01",
    }

    # create item_master
    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/items", json=item_master, headers=header)
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("itemCode") == "1234"

    # create itme_master with invalid tenant_id
    response = await http_client.post("/api/v1/tenants/ZZZZ/items", json=item_master, headers=header)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_400_BAD_REQUEST

    # get item_master
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/items/1234", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("itemCode") == "1234"

    # get all item_master
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/items", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 1
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # update item_master
    update_data = {
        "itemCode": "1234",  # this id should not be changed
        "description": "item 1234 updated",
        "unitPrice": 200,
        "unitCost": 100,
        "itemDetails": ["detail1", "detail2", "detail3"],
        "imageUrls": ["url1", "url2", "url3"],
        "categoryCode": "001",
        "taxCode": "01",
    }
    response = await http_client.put(f"/api/v1/tenants/{tenant_id}/items/1234", json=update_data, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("unitPrice") == 200
    assert res.get("data").get("unitCost") == 100

    # delete item_master logically
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/items/1234?is_logical=True", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("itemCode") == "1234"
    assert res.get("data").get("isLogical") is True

    # get item_master logically deleted
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/items/1234?is_logical_deleted=True", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("itemCode") == "1234"

    # get all items
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/items", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 0  # After deletion, could be 0
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # delete item_master physically
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/items/1234", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("itemCode") == "1234"
    assert res.get("data").get("isLogical") is False

    #
    # ItemStoreMaster
    #

    # First, try to delete item 49-99 if it exists from previous test runs
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/items/49-99", headers=header)
    # We don't assert here because it might not exist

    # create a new ItemCommonMaster for ItemStoreMaster
    item_master = {
        "itemCode": "49-99",
        "description": "item 49-99",
        "unitPrice": 100,
        "unitCost": 50,
        "itemDetails": ["detail1", "detail2"],
        "imageUrls": ["url1", "url2"],
        "categoryCode": "001",
        "taxCode": "01",
    }
    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/items", json=item_master, headers=header)
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()

    # create a new ItemStoreMaster
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items",
        json={"itemCode": "49-99", "storePrice": 90.0},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("itemCode") == "49-99"
    assert res.get("data").get("storePrice") == 90.0

    # create a new item_store_master with invalid store_code
    # TODO: implement this case

    # create a new item_store_master with invalid item_code (no item common found)
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items",
        json={"itemCode": "ZZZZ", "storePrice": 90.0},
        headers=header,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_404_NOT_FOUND

    # get item_store_master
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items/49-99", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("itemCode") == "49-99"
    assert res.get("data").get("storePrice") == 90.0

    # get all item_store_master
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert len(res.get("data")) == 2
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") == 2
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # update item_store_master
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items/49-99",
        json={"itemCode": "49-99", "storePrice": 80.0},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("storePrice") == 80.0

    # update item_store_master with invalid item_code (no item common found)
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items/ZZZZ",
        json={"itemCode": "ZZZZ", "storePrice": 80.0},
        headers=header,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_404_NOT_FOUND

    # delete item_store_master with invalid item_code (no item common found)
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items/ZZZZ", headers=header)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_404_NOT_FOUND

    # delete item_store_master
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items/49-99", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("itemCode") == "49-99"

    # get item_store_detail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items/49-01/details", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("itemCode") == "49-01"
    assert res.get("data").get("storePrice") == 100.0

    # create a new payment_master
    payment_code = "99"
    payment_master = {
        "paymentCode": payment_code,
        "description": "E-Wallet",
        "limitAmount": 100000.0,
        "canRefund": True,
        "canDepositOver": False,
        "canChange": False,
        "isActive": True,
    }

    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/payments", json=payment_master, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("paymentCode") == payment_code

    # get payment_master
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/payments/{payment_code}", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("paymentCode") == payment_code

    # get all payment_master
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/payments", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 1
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # update payment_master
    update_data = {
        "paymentCode": payment_code,
        "description": "E-Money",
        "limitAmount": 200000.0,
        "canRefund": False,
        "canDepositOver": False,
        "canChange": False,
        "isActive": True,
    }
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/payments/{payment_code}", json=update_data, headers=header
    )
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("description") == "E-Money"
    assert res.get("data").get("limitAmount") == 200000.0
    assert res.get("data").get("canRefund") is False

    # delete payment_master
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/payments/{payment_code}", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("paymentCode") == payment_code

    # create a new settings_master
    settings_name = "my_setting"
    terminal_no = 9
    settings_master = {
        "name": settings_name,
        "defaultValue": "default name",
        "values": [
            {"storeCode": "5678", "terminalNo": terminal_no, "value": "this value is for terminal 9"},
            {"storeCode": "5678", "value": "this value is for store 5678"},
        ],
    }

    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/settings", json=settings_master, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("name") == settings_name

    # veriy values in data
    assert res.get("data").get("values")[0].get("storeCode") == store_code
    assert res.get("data").get("values")[0].get("terminalNo") == terminal_no
    assert res.get("data").get("values")[0].get("value") == "this value is for terminal 9"

    # create a new settings_master with the same name
    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/settings", json=settings_master, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_400_BAD_REQUEST

    # get settings_master all
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/settings", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert len(res.get("data")) >= 2
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 2
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # get settings_master by name
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/settings/{settings_name}", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("name") == settings_name

    # get settings_master value by name
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/settings/{settings_name}/value?store_code={store_code}&terminal_no={terminal_no}",
        headers=header,
    )
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("value") == "this value is for terminal 9"

    # update settings_master
    update_data = {
        "name": settings_name,
        "defaultValue": "default name updated",
        "values": [{"storeCode": "5678", "value": "this value is for store 5678 updated"}],
    }

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/settings/{settings_name}", json=update_data, headers=header
    )
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("name") == settings_name
    assert res.get("data").get("defaultValue") == "default name updated"
    assert res.get("data").get("values")[0].get("value") == "this value is for store 5678 updated"

    # get settings_master value by name
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/settings/{settings_name}/value?store_code={store_code}&terminal_no={terminal_no}",
        headers=header,
    )
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("value") == "this value is for store 5678 updated"

    # delete settings_master
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/settings/{settings_name}", headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("name") == settings_name

    # create a new item_book_master
    item_book = {"title": "grand menu", "categories": []}

    response = await http_client.post(f"/api/v1/tenants/{tenant_id}/item_books", json=item_book, headers=header)
    res = response.json()
    print(f"Response: {res}")
    assert response.status_code == status.HTTP_201_CREATED
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("itemBookId") is not None
    item_book_id = res.get("data").get("itemBookId")
    assert res.get("data").get("title") == "grand menu"

    # add category to item_book
    category_number = 22
    item_book_category = {"categoryNumber": category_number, "title": "food", "color": "0xF0FFFF", "tabs": []}  # azure

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories", json=item_book_category, headers=header
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("categories")[0].get("categoryNumber") == category_number

    # add tab to category in item_book
    tab_number = 1
    item_book_tab = {"tabNumber": tab_number, "title": "lunch", "color": "0xF0FFFF", "buttons": []}  # azure
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs",
        json=item_book_tab,
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("categories")[0].get("tabs")[0].get("tabNumber") == tab_number

    # add button to tab in category in item_book
    item_book_button = {
        "pos_x": 1,
        "pos_y": 1,
        "size": "Single",
        "imageUrl": "url1",
        "colorText": "0xF0FFFF",  # azure
        "itemCode": "49-01",
    }
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons",
        json=item_book_button,
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("categories")[0].get("tabs")[0].get("buttons")[0].get("itemCode") == "49-01"

    item_book_button = {
        "pos_x": 1,
        "pos_y": 2,
        "size": "Single",
        "imageUrl": "url2",
        "colorText": "0xF0FFFF",  # azure
        "itemCode": "49-02",
    }
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons",
        json=item_book_button,
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    assert res.get("data").get("categories")[0].get("tabs")[0].get("buttons")[1].get("itemCode") == "49-02"

    # get item_book_master list
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/item_books", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"*** get item_book_master list Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 1
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # get item_book_master by id
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"*** get item_book_master by id Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("itemBookId") == item_book_id

    # get item_book_master_detail by id with store price
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/detail?store_code={store_code}", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"*** get item_book_master_detail by id Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("itemBookId") == item_book_id

    # get tax_master by tax_code
    tax_code = "01"
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/taxes/{tax_code}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert res.get("data").get("taxCode") == tax_code

    # get all tax_master
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/taxes", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    assert res.get("success") is True
    assert len(res.get("data")) > 0
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") > 0
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    #
    # Test pagination parameters
    #

    # Test pagination with specific page and limit for items
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/items?page=1&limit=10", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"*** Paginated items response: {res}")
    assert res.get("success") is True
    assert res.get("metadata") is not None
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") == 10

    # Test pagination with sorting for staff
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/staff?page=1&limit=20&sort=name:1", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"*** Sorted staff response: {res}")
    assert res.get("success") is True
    assert res.get("metadata") is not None
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") == 20
    # Note: sort format in metadata might be different from input
