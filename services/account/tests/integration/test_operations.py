# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pytest
import os
from fastapi import status
from kugel_common.database import database as db_helper


@pytest.mark.asyncio()
async def test_operations(http_client):

    print("Running Account test_operations...")
    tenant_id = os.environ.get("TENANT_ID")

    # superuser registration
    response = await http_client.post(
        "/api/v1/accounts/register", json={"username": "admin", "password": "admin", "tenant_id": tenant_id}
    )
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["success"] is True
    assert response_data["code"] == status.HTTP_201_CREATED
    assert response_data["message"] == "User registration successful"
    assert response_data["data"]["username"] == "admin"
    assert response_data["data"]["isSuperuser"] is True
    assert response_data["data"]["isActive"] is True
    assert response_data["data"]["tenantId"] is not None
    assert response_data["data"]["createdAt"] is not None
    assert response_data["data"]["updatedAt"] is None
    assert response_data["data"]["lastLogin"] is None
    assert response_data["data"]["tenantId"] == tenant_id

    # superuser registration with existing tenant_id should succeed generating new tenant_id
    response = await http_client.post(
        "/api/v1/accounts/register", json={"username": "admin", "password": "admin", "tenant_id": tenant_id}
    )
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["success"] is True
    assert response_data["code"] == status.HTTP_201_CREATED
    new_tenant_id = response_data["data"]["tenantId"]
    assert new_tenant_id != tenant_id

    # drop database for new tenant_id
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{new_tenant_id}"
    print(f"Dropping database: {target_db_name}")
    try:
        drop_result = await db_helper.drop_db_async(target_db_name)
    except Exception as e:
        print(f"Failed to drop database: {target_db_name}")
        print(e)
    assert drop_result is True

    # superuser registration without tenant_id should succeed generating new tenant_id
    response = await http_client.post("/api/v1/accounts/register", json={"username": "admin", "password": "admin"})
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["success"] is True
    assert response_data["code"] == status.HTTP_201_CREATED
    new_tenant_id = response_data["data"]["tenantId"]
    assert new_tenant_id is not None

    # drop database for new tenant_id
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{new_tenant_id}"
    print(f"Dropping database: {target_db_name}")
    try:
        drop_result = await db_helper.drop_db_async(target_db_name)
    except Exception as e:
        print(f"Failed to drop database: {target_db_name}")
        print(e)
    assert drop_result is True

    # superuser login
    response = await http_client.post(
        "/api/v1/accounts/token",
        # form data
        data={"username": "admin", "password": "admin", "client_id": tenant_id},
    )
    response = await http_client.post(
        "/api/v1/accounts/token",
        # form data
        data={"username": "admin", "password": "admin", "client_id": tenant_id},
    )
    print(f"response: {response}")
    response.status_code == status.HTTP_200_OK
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["access_token"] is not None
    assert response_data["token_type"] == "bearer"
    access_token = response_data["access_token"]

    # user registration by superuser
    response = await http_client.post(
        f"/api/v1/accounts/register/user?tenant_id={tenant_id}",
        json={"username": "user", "password": "user"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["success"] is True
    assert response_data["code"] == status.HTTP_201_CREATED
    assert response_data["message"] == "User registration successful"
    assert response_data["data"]["username"] == "user"
    assert response_data["data"]["isSuperuser"] is False
    assert response_data["data"]["isActive"] is True
    assert response_data["data"]["tenantId"] is not None
