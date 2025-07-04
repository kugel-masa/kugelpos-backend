# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.  # setup logging
import logging, logging.config

logging.config.fileConfig("app/logging.conf")

import os
import pytest
import pytest_asyncio
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
        os.environ["BASE_URL_MASTER_DATA"] = "http://localhost:8002"
        os.environ["BASE_URL_TERMINAL"] = "http://localhost:8001/api/v1"
        os.environ["TOKEN_URL"] = "http://localhost:8000/api/v1/accounts/token"
    else:
        os.environ["BASE_URL_MASTER_DATA"] = f"https://master-data.{remote_server}"
        os.environ["BASE_URL_TERMINAL"] = f"https://terminal.{remote_server}/api/v1"
        os.environ["TOKEN_URL"] = f"https://account.{remote_server}/api/v1/accounts/token"

    os.environ["DB_NAME_PREFIX"] = "db_master"
    os.environ["STORE_CODE"] = "5678"
    os.environ["MANAGEMENT"] = "admin"

    from kugel_common.database import database as db_helper

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")

    yield

    del os.environ["DB_NAME_PREFIX"]
    del os.environ["TOKEN_URL"]
    del os.environ["BASE_URL_MASTER_DATA"]
    del os.environ["BASE_URL_TERMINAL"]
    del os.environ["STORE_CODE"]
    del os.environ["MANAGEMENT"]


@pytest_asyncio.fixture(scope="function")
async def http_client(set_env_vars):
    from httpx import AsyncClient

    print("Setting up http client for external API")
    base_url = os.environ.get("BASE_URL_MASTER_DATA")
    async with AsyncClient(base_url=base_url) as client:
        yield client
    print("Closing http client for external API")
