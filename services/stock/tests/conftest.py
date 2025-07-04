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
        os.environ["BASE_URL_STOCK"] = "http://localhost:8006"
        os.environ["BASE_URL_MASTER_DATA"] = "http://localhost:8002/api/v1"
        os.environ["BASE_URL_TERMINAL"] = "http://localhost:8001/api/v1"
        os.environ["TOKEN_URL"] = "http://localhost:8000/api/v1/accounts/token"
    else:
        print("Setting up remote environment variables")
        print("is_local: ", is_local)
        os.environ["BASE_URL_STOCK"] = f"https://stock.{remote_server}"
        os.environ["BASE_URL_MASTER_DATA"] = f"https://master-data.{remote_server}/api/v1"
        os.environ["BASE_URL_TERMINAL"] = f"https://terminal.{remote_server}/api/v1"
        os.environ["TOKEN_URL"] = f"https://account.{remote_server}/api/v1/accounts/token"

    print(f"BASE_URL_STOCK: {os.environ.get('BASE_URL_STOCK')}")

    os.environ["DB_NAME_PREFIX"] = "db_stock"
    os.environ["STORE_CODE"] = "5678"
    os.environ["TERMINAL_NO"] = "5555"
    os.environ["TERMINAL_ID"] = f"{tenant_id}-5678-5555"
    os.environ["BUSINESS_DATE"] = datetime.now().strftime("%Y%m%d")

    # Set alert cooldown to 0 for testing
    os.environ["ALERT_COOLDOWN_SECONDS"] = "0"

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
    del os.environ["BASE_URL_STOCK"]
    del os.environ["BASE_URL_MASTER_DATA"]
    del os.environ["BASE_URL_TERMINAL"]
    del os.environ["STORE_CODE"]
    del os.environ["TERMINAL_NO"]
    del os.environ["TERMINAL_ID"]
    del os.environ["BUSINESS_DATE"]
    del os.environ["ALERT_COOLDOWN_SECONDS"]


@pytest.fixture(scope="session")
def websocket_base_url(set_env_vars):
    """Get WebSocket URL based on environment configuration"""
    base_url = os.environ.get("BASE_URL_STOCK")
    if base_url.startswith("https://"):
        # Convert HTTPS to WSS for secure WebSocket
        ws_url = base_url.replace("https://", "wss://")
    elif base_url.startswith("http://"):
        # Convert HTTP to WS for insecure WebSocket
        ws_url = base_url.replace("http://", "ws://")
    else:
        ws_url = base_url
    return ws_url


@pytest_asyncio.fixture(scope="function")
async def http_client(set_env_vars):
    from httpx import AsyncClient

    print("Setting up http client")
    base_url = os.environ.get("BASE_URL_STOCK")
    async with AsyncClient(base_url=base_url) as client:
        yield client
    print("Closing http client")


@pytest.fixture
def test_tenant_id():
    """Test tenant ID from environment"""
    return os.getenv("TENANT_ID", "test_tenant")


@pytest_asyncio.fixture()
async def setup_db(set_env_vars):
    from kugel_common.database import database as db_helper
    from app.database import database_setup

    """
    setup database
    create database and collections
    """
    print("Setting up database")
    tenant_id = os.environ.get("TENANT_ID")
    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        print("WARNING: MONGODB_URI not found in environment variables. Using default.")
        mongodb_uri = "mongodb://localhost:27017/"
    print(f"MONGODB_URI: {mongodb_uri}")
    db_helper.MONGODB_URI = mongodb_uri

    await database_setup.execute(tenant_id=tenant_id)
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}")

    yield db
    print("Database setup completed")

    print("Shutdown database")
    await db_helper.close_client_async()


@pytest.fixture
def test_store_code():
    """Test store code from environment"""
    return os.getenv("STORE_CODE", "5678")


@pytest_asyncio.fixture
async def test_auth_headers(set_env_vars):
    """Test authentication headers"""
    # Get real token from auth service
    tenant_id = os.getenv("TENANT_ID", "test_tenant")
    login_data = {
        "username": "admin",
        "password": "admin",
        "client_id": tenant_id,
    }

    async with AsyncClient() as http_auth_client:
        url_token = os.environ.get("TOKEN_URL")
        response = await http_auth_client.post(url=url_token, data=login_data)

    if response.status_code == 200:
        res = response.json()
        token = res.get("access_token")
        return {"Authorization": f"Bearer {token}", "X-User-ID": "admin", "X-Tenant-ID": tenant_id}
    else:
        # If auth fails, return minimal headers
        print(f"Authentication failed: {response.status_code}")
        return {"X-Tenant-ID": tenant_id}


@pytest.fixture
def test_item_data():
    """Test item data"""
    return {"itemCode": "ITEM001", "currentQuantity": 100.0, "minimumQuantity": 10.0}


# Fixture for using app directly without HTTP
@pytest_asyncio.fixture
async def async_client(set_env_vars):
    """Create an async test client for direct app testing"""
    import sys
    from pathlib import Path

    # Add the parent directory to the Python path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from app.main import app
    from httpx import AsyncClient

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# Motor client fixture for direct database access
@pytest_asyncio.fixture
async def db_client(set_env_vars):
    """Create a test database client"""
    from motor.motor_asyncio import AsyncIOMotorClient

    # Use the MongoDB URI directly from environment variable
    mongodb_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
    client = AsyncIOMotorClient(mongodb_uri)
    yield client
    client.close()


# Export test constants for use in other test files  # Load .env.test to get values
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
dotenv_path = os.path.join(ROOT_DIR, ".env.test")
load_dotenv(dotenv_path=dotenv_path, override=True)

# Test constants
tenant_id = os.getenv("TENANT_ID", "J5578")
test_store_code = "5678"  # Hardcoded as per convention in all services


# Add back the test_store_code fixture that was previously defined
@pytest.fixture
def test_store_code():
    """Test store code from environment"""
    return "5678"
