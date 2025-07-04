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
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase


@pytest_asyncio.fixture(scope="function")
async def setup_db(set_env_vars):
    from kugel_common.database import database as db_helper

    """
    setup database
    create database and collections
    """
    # Reset the database connection to ensure clean state
    await db_helper.close_client_async()

    # below add more setup tasks here
    yield

    # Cleanup
    await db_helper.close_client_async()


@pytest.mark.asyncio
async def test_setup_data(setup_db: AsyncIOMotorDatabase):

    print("Setting up database - do nothing")
