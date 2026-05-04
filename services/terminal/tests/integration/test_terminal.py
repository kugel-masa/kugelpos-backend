# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest, os
import asyncio
from fastapi import status
from httpx import AsyncClient
from app.config.settings import settings


@pytest.mark.asyncio()
async def test_terminal_operations(http_client, admin_header, mock_outbound_services):
    """Full terminal CRUD against the in-process FastAPI app.

    Outbound HTTP from POST /tenants (master-data / cart / report /
    journal / stock) is mocked via the mock_outbound_services fixture,
    and the admin JWT is generated locally via the admin_header fixture
    instead of fetched from the account service.
    """
    print("Testing terminal operations started")

    tenant_id = os.environ.get("TENANT_ID")
    header = admin_header

    # Test create Tenant Info
    response = await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": tenant_id, "tenant_name": "Test Tenant", "stores": [], "tags": ["Test"]},
        headers=header,
    )

    res = response.json()
    if response.status_code != status.HTTP_201_CREATED:
        print(f"Create tenant failed with status {response.status_code}: {res}")
    assert response.status_code == status.HTTP_201_CREATED
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED

    # Test add Store to Tenant
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores",
        json={"store_code": "5678", "store_name": "テスト店舗", "tags": ["Test"]},
        headers=header,
    )

    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    print(f"add store Response: {res} ")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED

    # Test add store to Tenant with existing store
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores",
        json={"store_code": "5678", "store_name": "テスト店舗", "tags": ["Test"]},
        headers=header,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Test add another store to Tenant
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores",
        json={"store_code": "1234", "store_name": "テスト店舗2", "tags": ["Test"]},
        headers=header,
    )

    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    print(f"add store Response: {res} ")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED

    # Test get Stores with token
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/stores", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"get stores Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert len(res.get("data")) > 0
    # Check metadata for paginated response if implemented
    metadata = res.get("metadata")
    if metadata is not None:
        assert metadata.get("total") >= 2  # We added 2 stores
        assert metadata.get("page") == 1
        assert metadata.get("limit") > 0
    else:
        print("WARNING: Metadata not implemented for get stores endpoint")

    # Test get Store with token and sort query parameter
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores?sort=store_code:-1&limit=10&page=1", headers=header
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"get stores Response sort 'store_code:-1': {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert len(res.get("data")) > 0
    # Check metadata for paginated response with parameters if implemented
    metadata = res.get("metadata")
    if metadata is not None:
        assert metadata.get("total") >= 2
        assert metadata.get("page") == 1
        assert metadata.get("limit") == 10
        # Note: sort format in metadata might be different from input
    else:
        print("WARNING: Metadata not implemented for get stores endpoint with pagination")

    # Test get Store by store code with token
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}/stores/5678", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("storeCode") == "5678"

    store_name = res.get("data").get("storeName")
    store_status = res.get("data").get("status")
    business_date = res.get("data").get("businessDate")

    # Test update Store with token
    store_name_upd = store_name + "UPD"
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/5678",
        json={
            "store_name": store_name_upd,
            "status": store_status,
            "business_date": business_date,
            "tags": ["Updated", "Test"],
        },
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("storeCode") == "5678"
    assert res.get("data").get("storeName") == store_name_upd

    # Test delete Store with token
    response = await http_client.delete(f"/api/v1/tenants/{tenant_id}/stores/1234", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("storeCode") == "1234"

    # Test get Tenants with token
    # response = await http_client.get(
    #     "/api/v1/tenants",
    #     headers=header
    # )
    # assert response.status_code == status.HTTP_200_OK
    # res = response.json()
    # print(f"get tenants Response: {res}")
    # assert res.get("success") is True
    # assert res.get("code") == status.HTTP_200_OK
    # assert len(res.get("data")) > 0

    # Test get Tenant with token
    response = await http_client.get(f"/api/v1/tenants/{tenant_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("tenantId") == tenant_id

    # Test update Tenant with token
    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}",
        json={"tenant_name": "Test Tenant Updated", "tags": ["Updated", "Test"]},
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("tenantId") == tenant_id
    assert res.get("data").get("tenantName") == "Test Tenant Updated"

    # Test create Tenant with token Bad Request
    response = await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": "Z9999", "tenant_name": "Test Tenant Z", "stores": [], "tags": ["Test", "Z"]},
        headers=header,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res = response.json()
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_400_BAD_REQUEST

    # Test delete Tenant with token
    response = await http_client.delete("/api/v1/tenants/Z9999", headers=header)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res = response.json()
    assert res.get("success") is False
    assert res.get("code") == status.HTTP_400_BAD_REQUEST

    # Test create Terminal with token
    response = await http_client.post(
        "/api/v1/terminals",
        json={"store_code": "5678", "terminal_no": 9, "description": "Test Terminal"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    terminalId = res.get("data").get("terminalId")
    apiKey = res.get("data").get("apiKey")
    print(f"TerminalId: {terminalId}")
    print(f"ApiKey: {apiKey}")

    # Test create Terminal with token Bad Request
    response = await http_client.post("/api/v1/terminals", json={}, headers=header)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test create Terminal with existing terminal
    response = await http_client.post(
        "/api/v1/terminals",
        json={"store_code": "5678", "terminal_no": 9, "description": "Test Terminal"},
        headers=header,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Test create Terminal again
    response = await http_client.post(
        "/api/v1/terminals",
        json={"store_code": "5678", "terminal_no": 99, "description": "Test Terminal"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_201_CREATED
    terminalId_99 = res.get("data").get("terminalId")
    apiKey_99 = res.get("data").get("apiKey")
    print(f"TerminalId: {terminalId_99}", f"API Key: {apiKey_99}")

    # test get Terminals with token
    response = await http_client.get("/api/v1/terminals", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"get terminals Response: {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert len(res.get("data")) > 0
    # Check metadata for paginated response if implemented
    metadata = res.get("metadata")
    if metadata is not None:
        assert metadata.get("total") >= 2  # We created 2 terminals
        assert metadata.get("page") == 1
        assert metadata.get("limit") > 0
    else:
        print("WARNING: Metadata not implemented for get terminals endpoint")

    # Test get Terminals with token and sort query parameter
    response = await http_client.get("/api/v1/terminals?sort=terminal_id:-1&limit=10&page=1", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"get terminals Response sort 'terminal_id:-1': {res}")
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert len(res.get("data")) > 0
    # Check metadata for paginated response with parameters if implemented
    metadata = res.get("metadata")
    if metadata is not None:
        assert metadata.get("total") >= 2
        assert metadata.get("page") == 1
        assert metadata.get("limit") == 10
        # Note: sort format in metadata might be different from input
    else:
        print("WARNING: Metadata not implemented for get terminals endpoint with pagination")

    # Test delete Terminal with token
    response = await http_client.delete(f"/api/v1/terminals/{terminalId_99}", headers=header)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("terminalId") == terminalId_99

    # Test get Terminal with API Key
    headers = {"X-API-KEY": apiKey}

    print(f"*** headers: {headers}")
    response = await http_client.get(f"/api/v1/terminals/{terminalId}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("terminalId") == terminalId

    # Test Terminal Update Function Mode with API key Bad Request
    response = await http_client.patch(f"/api/v1/terminals/{terminalId}/function_mode", json={}, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    res = response.json()

    # Test Terminal Update Function Mode with API key Bad Request
    response = await http_client.patch(
        f"/api/v1/terminals/{terminalId}/function_mode", json={"function_mode": "Sales"}, headers=headers
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    res = response.json()

    # Test Terminal Update Function Mode with API key
    response = await http_client.patch(
        f"/api/v1/terminals/{terminalId}/function_mode", json={"function_mode": "OpenTerminal"}, headers=headers
    )
    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    assert res.get("success") is True
    assert res.get("code") == status.HTTP_200_OK
    assert res.get("data").get("terminalId") == terminalId
    assert res.get("data").get("functionMode") == "OpenTerminal"

    # NOTE: Lifecycle tests (sign-in/open/close/sign-out, cash-in/out)
    # have been left in tests/e2e/test_terminal_jwt_auth.py since they
    # depend on master-data staff lookups and Dapr publish, which are
    # awkward to mock in-process. The integration tier focuses on CRUD
    # of tenants, stores, terminals, and basic API-key behaviour.
    print("Testing terminal CRUD operations completed")
