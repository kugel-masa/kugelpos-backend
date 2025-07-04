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


# =============================================================================
# Superuser Registration Tests
# =============================================================================

@pytest.mark.asyncio()
async def test_superuser_registration_with_tenant_id(init_test_database, http_client):
    """Test superuser registration with a specific tenant_id"""
    print("Running test_superuser_registration_with_tenant_id...")
    tenant_id = os.environ.get("TENANT_ID")

    response = await http_client.post(
        "/api/v1/accounts/register",
        json={
            "username": "admin",
            "password": "admin",
            "tenant_id": tenant_id
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["success"] == True
    assert response_data["code"] == status.HTTP_201_CREATED
    assert response_data["message"] == "User registration successful"
    assert response_data["data"]["username"] == "admin"
    assert response_data["data"]["isSuperuser"] == True
    assert response_data["data"]["isActive"] == True
    assert response_data["data"]["tenantId"] is not None
    assert response_data["data"]["createdAt"] is not None
    assert response_data["data"]["updatedAt"] is None
    assert response_data["data"]["lastLogin"] is None
    assert response_data["data"]["tenantId"] == tenant_id


@pytest.mark.asyncio()
async def test_superuser_registration_with_existing_tenant_id(init_test_database, http_client, cleanup_test_databases):
    """Test superuser registration with existing tenant_id generates new tenant_id"""
    print("Running test_superuser_registration_with_existing_tenant_id...")
    tenant_id = os.environ.get("TENANT_ID")

    # First registration
    await http_client.post(
        "/api/v1/accounts/register",
        json={
            "username": "admin",
            "password": "admin",
            "tenant_id": tenant_id
        }
    )

    # Second registration with same tenant_id should generate new tenant_id
    response = await http_client.post(
        "/api/v1/accounts/register",
        json={
            "username": "admin",
            "password": "admin",
            "tenant_id": tenant_id
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["success"] == True
    assert response_data["code"] == status.HTTP_201_CREATED
    new_tenant_id = response_data["data"]["tenantId"]
    assert new_tenant_id != tenant_id

    # Register database for cleanup
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{new_tenant_id}"
    cleanup_test_databases(target_db_name)


@pytest.mark.asyncio()
async def test_superuser_registration_without_tenant_id(init_test_database, http_client, cleanup_test_databases):
    """Test superuser registration without tenant_id generates new tenant_id"""
    print("Running test_superuser_registration_without_tenant_id...")

    response = await http_client.post(
        "/api/v1/accounts/register",
        json={
            "username": "admin",
            "password": "admin"
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["success"] == True
    assert response_data["code"] == status.HTTP_201_CREATED
    new_tenant_id = response_data["data"]["tenantId"]
    assert new_tenant_id is not None

    # Register database for cleanup
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{new_tenant_id}"
    cleanup_test_databases(target_db_name)


# =============================================================================
# Authentication Tests
# =============================================================================

@pytest.mark.asyncio()
async def test_superuser_login(init_test_database, http_client):
    """Test superuser login and token generation"""
    print("Running test_superuser_login...")
    tenant_id = os.environ.get("TENANT_ID")

    # Register superuser first
    await http_client.post(
        "/api/v1/accounts/register",
        json={
            "username": "admin",
            "password": "admin",
            "tenant_id": tenant_id
        }
    )

    # Login
    response = await http_client.post(
        f"/api/v1/accounts/token",
        data={
            "username": "admin",
            "password": "admin",
            "client_id": tenant_id 
        }
    )
    print(f"response: {response}")
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["access_token"] is not None
    assert response_data["token_type"] == "bearer"


# =============================================================================
# User Management Tests
# =============================================================================

@pytest.mark.asyncio()
async def test_user_registration_by_superuser(init_test_database, http_client):
    """Test user registration by superuser"""
    print("Running test_user_registration_by_superuser...")
    tenant_id = os.environ.get("TENANT_ID")

    # Register superuser first
    await http_client.post(
        "/api/v1/accounts/register",
        json={
            "username": "admin",
            "password": "admin",
            "tenant_id": tenant_id
        }
    )

    # Login to get access token
    login_response = await http_client.post(
        f"/api/v1/accounts/token",
        data={
            "username": "admin",
            "password": "admin",
            "client_id": tenant_id 
        }
    )
    access_token = login_response.json()["access_token"]

    # Register user by superuser
    response = await http_client.post(
        f"/api/v1/accounts/register/user?tenant_id={tenant_id}",
        json={
            "username": "user",
            "password": "user"
        },
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    print(f"response_data: {response_data}")
    assert response_data["success"] == True
    assert response_data["code"] == status.HTTP_201_CREATED
    assert response_data["message"] == "User registration successful"
    assert response_data["data"]["username"] == "user"
    assert response_data["data"]["isSuperuser"] == False
    assert response_data["data"]["isActive"] == True
    assert response_data["data"]["tenantId"] is not None

