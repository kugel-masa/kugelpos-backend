# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.  # setup logging
import logging, logging.config

logging.config.fileConfig("app/logging.conf")

import os, pytest
import pytest_asyncio
from httpx import AsyncClient
from datetime import datetime
from dotenv import load_dotenv


@pytest.fixture(scope="session")
def set_env_vars():

    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dotenv_path = os.path.join(ROOT_DIR, ".env.test")
    load_dotenv(dotenv_path=dotenv_path, override=True)

    is_local = os.getenv("LOCAL_TEST") == "True"
    remote_server = os.getenv("REMOTE_URL")
    tenant_id = os.getenv("TENANT_ID")

    print("")
    print("---------------------------")
    print(f"ROOT_DIR: {ROOT_DIR}")
    print(f"dotenv_path: {dotenv_path}")
    print(f"LOCAL_TEST: {is_local}")
    print(f"REMOTE_URL: {remote_server}")
    print(f"TENANT_ID: {tenant_id}")
    print("---------------------------")

    if is_local:
        print("Setting up local environment variables")
        print("is_local: ", is_local)
        os.environ["BASE_URL_REPORT"] = "http://localhost:8004"
        os.environ["BASE_URL_MASTER_DATA"] = "http://localhost:8002/api/v1"
        os.environ["BASE_URL_TERMINAL"] = "http://localhost:8001/api/v1"
        os.environ["TOKEN_URL"] = "http://localhost:8000/api/v1/accounts/token"
    else:
        print("Setting up remote environment variables")
        print("is_local: ", is_local)
        os.environ["BASE_URL_REPORT"] = f"https://report.{remote_server}"
        os.environ["BASE_URL_MASTER_DATA"] = f"https://master-data.{remote_server}/api/v1"
        os.environ["BASE_URL_TERMINAL"] = f"https://terminal.{remote_server}/api/v1"
        os.environ["TOKEN_URL"] = f"https://account.{remote_server}/api/v1/accounts/token"

    print(f"BASE_URL_REPORT: {os.environ.get('BASE_URL_REPORT')}")

    os.environ["DB_NAME_PREFIX"] = "db_report"
    os.environ["STORE_CODE"] = "5678"
    os.environ["TERMINAL_NO"] = "5555"
    os.environ["TERMINAL_ID"] = f"{tenant_id}-5678-5555"
    os.environ["BUSINESS_DATE"] = datetime.now().strftime("%Y%m%d")

    from kugel_common.database import database as db_helper

    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        print("WARNING: MONGODB_URI not found in environment variables. Using default.")
        mongodb_uri = "mongodb://localhost:27017/"
    print(f"MONGODB_URI: {mongodb_uri}")
    db_helper.MONGODB_URI = mongodb_uri

    yield

    del os.environ["DB_NAME_PREFIX"]
    del os.environ["TOKEN_URL"]
    del os.environ["BASE_URL_REPORT"]
    del os.environ["BASE_URL_MASTER_DATA"]
    del os.environ["BASE_URL_TERMINAL"]
    del os.environ["STORE_CODE"]
    del os.environ["TERMINAL_NO"]
    del os.environ["TERMINAL_ID"]
    del os.environ["BUSINESS_DATE"]


@pytest_asyncio.fixture(scope="function")
async def http_client(set_env_vars):
    from httpx import AsyncClient

    print("Setting up http client")
    base_url = os.environ.get("BASE_URL_REPORT")
    async with AsyncClient(base_url=base_url) as client:
        yield client
    print("Closing http client")


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_database_connection(set_env_vars):
    """
    Automatically cleanup database connection after each test.

    This fixture solves the "Event loop is closed" error that occurs when
    running multiple async tests. The issue happens because:

    1. kugel_common.database.database uses a global singleton MongoDB client
    2. The client is tied to the event loop that created it
    3. When pytest creates a new event loop for the next test, the old client
       is still referenced in the global variable
    4. Attempting to use the old client with the new event loop causes
       "RuntimeError: Event loop is closed"

    This fixture ensures that after each test:
    - The database client is properly closed
    - The global client variable is reset to None
    - The next test will create a fresh client with the new event loop

    The 'autouse=True' parameter means this fixture runs automatically for
    every test function, even if not explicitly requested.
    """
    # Setup: runs before test
    yield

    # Teardown: runs after test
    try:
        from kugel_common.database import database as db_helper
        await db_helper.reset_client_async()
        print("Database connection cleaned up successfully")
    except Exception as e:
        print(f"Warning: Failed to cleanup database connection: {e}")
