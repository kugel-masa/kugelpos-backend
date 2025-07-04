# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Clean test data before running tests
"""
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from app.config.settings import settings


@pytest.mark.asyncio
async def test_clean_stock_database(db_client, test_tenant_id: str):
    """Drop the entire stock database for test tenant"""
    db_name = f"{settings.DB_NAME_PREFIX}_{test_tenant_id}"

    print(f"Dropping database: {db_name}")

    try:
        # Drop the entire database
        await db_client.drop_database(db_name)
        print(f"Successfully dropped database: {db_name}")
    except Exception as e:
        print(f"Error dropping database {db_name}: {e}")
        # Even if there's an error, we continue since the database might not exist

    # Verify database is dropped by checking if it exists in the list
    database_names = await db_client.list_database_names()
    assert db_name not in database_names, f"Database {db_name} still exists"

    print(f"Successfully cleaned database for tenant {test_tenant_id}")
