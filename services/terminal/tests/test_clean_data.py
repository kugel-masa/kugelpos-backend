# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Test Database Cleanup Module

This module contains tests and fixtures for cleaning up test databases.
It ensures that test data doesn't persist between test runs, maintaining
test isolation and preventing interference between test suites.
"""

import pytest, os
import pytest_asyncio
import asyncio


@pytest_asyncio.fixture(scope="function")
async def clean_db(set_env_vars):
    """
    Module-scoped fixture to clean up test databases

    This fixture:
    1. Connects to the MongoDB server
    2. Drops the tenant-specific test database to remove all test data
    3. Closes the database connection

    Args:
        set_env_vars: Session-scoped fixture that ensures environment variables are set

    Yields:
        None: The result of closing the database client
    """
    from kugel_common.database import database as db_helper

    db_client = await db_helper.get_client_async()

    # The following code can be uncommented to drop all test databases
    # instead of just the tenant-specific one
    # databases = await db_client.list_database_names()
    # for db_name in databases:
    #    if db_name.startswith(os.environ.get("DB_NAME_PREFIX")):
    #        print(f"Dropping database: {db_name}")
    #        await db_client.drop_database(db_name)

    # Drop only the tenant-specific test database
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"Dropping database: {target_db_name}")
    await db_client.drop_database(target_db_name)

    print("Closing database connection")
    yield await db_helper.close_client_async()

    print("Database cleaned up")


@pytest.mark.asyncio
async def test_clean_data(clean_db):
    """
    Test that verifies the database cleanup was successful

    This test simply ensures that the clean_db fixture runs without errors.
    The actual cleanup is performed by the fixture itself.

    Args:
        clean_db: Module-scoped fixture that cleans the database
    """
    assert clean_db is None
