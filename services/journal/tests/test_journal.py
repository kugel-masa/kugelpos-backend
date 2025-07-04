# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import asyncio
import os
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio()
async def test_report_operations(http_client):

    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")
    terminal_no = os.environ.get("TERMINAL_NO")

    # get token from auth service
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as http_auth_client:
        url = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url, data=login_data)

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    token = res.get("access_token")
    print(f"Token: {token}")
    header = {"Authorization": f"Bearer {token}"}

    # get journals
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals",
        headers=header,
        params={
            "terminals": [terminal_no],
            "transaction_types": [101],
            "business_date_from": "20231001",
            "business_date_to": "21251001",
            "generate_date_time_from": "2023-10-01T12:34:56",
            "generate_date_time_to": "2125-10-01T12:34:56",
            "receipt_no_from": 700,
            "receipt_no_to": 800,
            "keywords": ["example"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    journals = res.get("data")
    print(f"Journals: {journals}")
    assert len(journals) > 0
    # Check metadata for paginated response
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 0
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # get journal with api key
    store_code = os.environ.get("STORE_CODE")
    terminal_no = os.environ.get("TERMINAL_NO")
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"

    terminal_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals/{terminal_id}"
    async with AsyncClient() as http_terminal_client:
        response = await http_terminal_client.get(url=terminal_url, headers=header)
    res = response.json()
    print(f"get terminal response: {res}")
    api_key = res.get("data").get("apiKey")
    print(f"terminal_id: {terminal_id}, api_key: {api_key}")

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals",
        headers={"X-API-Key": api_key},
        params={
            "terminal_id": terminal_id,
            "terminals": [terminal_no],
            "transaction_types": [101],
            "business_date_from": "20231001",
            "business_date_to": "21251001",
            "generate_date_time_from": "2023-10-01T12:34:56",
            "generate_date_time_to": "2125-10-01T12:34:56",
            "receipt_no_from": 700,
            "receipt_no_to": 800,
            "keywords": ["example"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response: {res}")
    # Check metadata for paginated response with API key
    assert res.get("metadata") is not None
    assert res.get("metadata").get("total") >= 0
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") > 0

    # Test pagination parameters
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals",
        headers=header,
        params={
            "terminals": [terminal_no],
            "transaction_types": [101],
            "business_date_from": "20231001",
            "business_date_to": "21251001",
            "page": 1,
            "limit": 5,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    res = response.json()
    print(f"Response with pagination: {res}")
    # Check metadata for paginated response with specific parameters
    assert res.get("metadata") is not None
    assert res.get("metadata").get("page") == 1
    assert res.get("metadata").get("limit") == 5
