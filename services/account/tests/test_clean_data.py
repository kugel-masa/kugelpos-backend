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
import os


@pytest_asyncio.fixture(scope="function")
async def clean_db(set_env_vars):
    from kugel_common.database import database as db_helper

    db_client = await db_helper.get_client_async()
    #    databases = await db_client.list_database_names()
    #    for db_name in databases:
    #        if db_name.startswith(os.environ.get("DB_NAME_PREFIX")):
    #            print(f"Dropping database: {db_name}")
    #            await db_client.drop_database(db_name)
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"Dropping database: {target_db_name}")
    await db_client.drop_database(target_db_name)

    print("Closing database connection")
    await db_helper.close_client_async()

    yield None

    print("Database cleaned up")


@pytest.mark.asyncio
async def test_clean_data(clean_db):

    assert clean_db is None
