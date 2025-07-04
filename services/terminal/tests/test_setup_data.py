# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Test Database Setup Module

This module contains tests and fixtures for initializing the test database.
It ensures that necessary collections and indexes are created before
running functional tests that depend on the database structure.
"""

import pytest
import pytest_asyncio
import os
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config.settings import settings


@pytest_asyncio.fixture()
async def setup_db(set_env_vars):
    """
    Function-scoped fixture to set up the test database

    This fixture:
    1. Uses the database_setup utility to create necessary collections and indexes
    2. Returns the database connection for use in tests
    3. Closes the connection after tests complete

    Args:
        set_env_vars: Session-scoped fixture that ensures environment variables are set

    Yields:
        AsyncIOMotorDatabase: MongoDB database connection for the tenant-specific test database
    """
    from kugel_common.database import database as db_helper
    from app.database import database_setup

    # Reset the database connection to ensure clean state
    await db_helper.close_client_async()

    # Initialize the tenant-specific database
    tenant_id = os.environ.get("TENANT_ID")
    await database_setup.execute(tenant_id)
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}")

    yield db
    print("Database setup completed")

    print("Shutting down database")
    await db_helper.close_client_async()


@pytest.mark.asyncio
async def test_setup_data(setup_db: AsyncIOMotorDatabase):
    """
    Test that verifies the database setup was successful

    This test checks that the database connection is valid and reports
    the name of the initialized database.

    Args:
        setup_db: Module-scoped fixture that sets up the database
    """
    assert setup_db is not None
    print("database name: ", setup_db.name)
