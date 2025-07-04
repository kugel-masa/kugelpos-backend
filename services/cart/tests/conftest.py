# Copyright 2025 masa@kugel
# kugelpos-oppe  # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.  # setup logging
import logging, logging.config

logging.config.fileConfig("app/logging.conf")

import os
import pytest
import pytest_asyncio
from dotenv import load_dotenv


@pytest.fixture(scope="session")
def set_env_vars():

    # Load cart's .env file first to get MONGODB_URI
    CART_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cart_env_path = os.path.join(CART_DIR, ".env")
    load_dotenv(dotenv_path=cart_env_path, override=False)

    # Then load .env.test from root directory
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dotenv_path = os.path.join(ROOT_DIR, ".env.test")
    load_dotenv(dotenv_path=dotenv_path, override=True)

    is_local = os.getenv("LOCAL_TEST") == "True"
    remote_server = os.getenv("REMOTE_URL")
    tenant_id = os.getenv("TENANT_ID")

    print("")
    print("---------------------------")
    print(f"CART_DIR: {CART_DIR}")
    print(f"cart_env_path: {cart_env_path}")
    print(f"ROOT_DIR: {ROOT_DIR}")
    print(f"dotenv_path: {dotenv_path}")
    print(f"LOCAL_TEST: {is_local}")
    print(f"REMOTE_URL: {remote_server}")
    print(f"TENANT_ID: {tenant_id}")
    print(f"MONGODB_URI: {os.environ.get('MONGODB_URI')}")
    print("---------------------------")

    if is_local:
        os.environ["BASE_URL_CART"] = "http://localhost:8003"
        os.environ["BASE_URL_MASTER_DATA"] = "http://localhost:8002/api/v1"
        os.environ["BASE_URL_TERMINAL"] = "http://localhost:8001/api/v1"
        os.environ["TOKEN_URL"] = "http://localhost:8000/api/v1/accounts/token"
    else:
        os.environ["BASE_URL_CART"] = f"https://cart.{remote_server}"
        os.environ["BASE_URL_MASTER_DATA"] = f"https://master-data.{remote_server}/api/v1"
        os.environ["BASE_URL_TERMINAL"] = f"https://terminal.{remote_server}/api/v1"
        os.environ["TOKEN_URL"] = f"https://account.{remote_server}/api/v1/accounts/token"

    os.environ["DB_NAME_PREFIX"] = "db_cart"
    os.environ["STORE_CODE"] = "5678"
    os.environ["TERMINAL_ID"] = f"{tenant_id}-5678-9"

    # get token from account service
    from httpx import Client

    token_url = os.environ.get("TOKEN_URL")
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}
    with Client() as http_auth_client:
        response = http_auth_client.post(url=token_url, data=login_data)
    res = response.json()
    print(f"auth response: {res}")
    token = res.get("access_token")

    # get api key from terminal service
    terminal_id = os.environ.get("TERMINAL_ID")
    header = {"Authorization": f"Bearer {token}"}
    terminal_url = f"{os.environ.get('BASE_URL_TERMINAL')}/terminals/{terminal_id}"
    with Client() as http_terminal_client:
        response = http_terminal_client.get(url=terminal_url, headers=header)
    res = response.json()
    print(f"terminal response: {res}")
    api_key = res.get("data").get("apiKey")
    print(f"api_key: {api_key}")

    # replace API_KEY
    os.environ["API_KEY"] = api_key

    from kugel_common.database import database as db_helper

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")

    yield

    del os.environ["BASE_URL_CART"]
    del os.environ["DB_NAME_PREFIX"]
    del os.environ["TOKEN_URL"]
    del os.environ["BASE_URL_MASTER_DATA"]
    del os.environ["BASE_URL_TERMINAL"]
    del os.environ["STORE_CODE"]
    del os.environ["TERMINAL_ID"]
    del os.environ["API_KEY"]


@pytest_asyncio.fixture(scope="function")
async def http_client(set_env_vars):
    from httpx import AsyncClient, Timeout

    print("Setting up http client")
    base_url = os.environ.get("BASE_URL_CART")
    timeout = Timeout(timeout=None)  # Corrected the timeout parameter
    async with AsyncClient(base_url=base_url, timeout=timeout) as client:
        yield client
    print("Closing http client")
