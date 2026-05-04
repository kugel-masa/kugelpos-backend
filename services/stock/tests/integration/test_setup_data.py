# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Setup test data after cleaning
"""
import pytest
import os
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase


@pytest.mark.asyncio
async def test_setup_data(setup_db: AsyncIOMotorDatabase, http_client: AsyncClient):
    """Setup database and initial stock data for testing"""
    assert setup_db is not None
    print(f"Database: {setup_db.name}")

    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE")

    # Get token from auth service for API authentication
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }
    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    # For stock service, we may need to handle authentication differently
    # If the service doesn't require authentication for these operations,
    # we can skip the token part
    header = {}
    if response.status_code == 200:
        res = response.json()
        token = res.get("access_token")
        header = {"Authorization": f"Bearer {token}"}
    else:
        print(f"Authentication failed, proceeding without token. Status: {response.status_code}")

    # Create some initial stock items
    test_items = [
        {"itemCode": "ITEM001", "minimumQuantity": 10.0},
        {"itemCode": "ITEM002", "minimumQuantity": 20.0},
        {"itemCode": "ITEM003", "minimumQuantity": 5.0},
    ]

    for item in test_items:
        # Set minimum quantity (this will create the stock record)
        response = await http_client.put(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item['itemCode']}/minimum",
            json={"minimumQuantity": item["minimumQuantity"]},
            headers=header,
        )
        if response.status_code != 200:
            print(
                f"Failed to create stock for {item['itemCode']}. Status: {response.status_code}, Response: {response.text}"
            )
        assert response.status_code == 200
        print(f"Created stock record for {item['itemCode']} with minimum quantity {item['minimumQuantity']}")

    print("Successfully setup initial stock data")
