# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Terminal Service Test Configuration Module

This module contains pytest fixtures and configuration for testing the Terminal service.
It sets up the test environment, configures logging, and provides HTTP client fixtures
for making API requests during tests.
"""

# setup logging
import logging, logging.config

logging.config.fileConfig("app/logging.conf")

import os
import pytest
import pytest_asyncio
from dotenv import load_dotenv


@pytest.fixture(scope="session")
def set_env_vars():
    """
    Session-scoped fixture to set up environment variables for testing

    This fixture:
    1. Loads environment variables from .env.test file
    2. Sets service URLs based on whether tests are running locally or against remote servers
    3. Configures the database connection
    4. Cleans up environment variables after tests complete

    Yields:
        None: The fixture yields control back to the test after setup
    """
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dotenv_path = os.path.join(ROOT_DIR, ".env.test")
    if os.path.exists(dotenv_path):
        print(f".env.test file found at: {dotenv_path}")
        load_dotenv(dotenv_path=dotenv_path, override=True)
    else:
        print(f"WARNING: .env.test file not found at: {dotenv_path}")
        # Try loading from terminal service .env file
        terminal_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(terminal_env_path):
            print(f"Loading from terminal service .env file: {terminal_env_path}")
            load_dotenv(dotenv_path=terminal_env_path, override=False)

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
        # Configure URLs for local test environment
        os.environ["BASE_URL_TERMINAL"] = "http://localhost:8001"
        os.environ["BASE_URL_MASTER_DATA"] = "http://localhost:8002/api/v1"
        os.environ["BASE_URL_CART"] = "http://localhost:8003/api/v1"
        os.environ["BASE_URL_REPORT"] = "http://localhost:8004/api/v1"
        os.environ["BASE_URL_JOURNAL"] = "http://localhost:8005/api/v1"
        os.environ["TOKEN_URL"] = "http://localhost:8000/api/v1/accounts/token"
    else:
        # Configure URLs for remote test environment
        os.environ["BASE_URL_TERMINAL"] = f"https://terminal.{remote_server}"
        os.environ["BASE_URL_MASTER_DATA"] = f"https://master-data.{remote_server}/api/v1"
        os.environ["BASE_URL_CART"] = f"https://cart.{remote_server}/api/v1"
        os.environ["BASE_URL_REPORT"] = f"https://report.{remote_server}/api/v1"
        os.environ["BASE_URL_JOURNAL"] = f"https://journal.{remote_server}/api/v1"
        os.environ["TOKEN_URL"] = f"https://account.{remote_server}/api/v1/accounts/token"

    # Set database name prefix for test database
    os.environ["DB_NAME_PREFIX"] = "db_terminal"

    # Configure MongoDB connection
    from kugel_common.database import database as db_helper

    # Check if running in Docker container
    is_docker = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER", False)

    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        if is_docker:
            # Default for Docker environment
            mongodb_uri = "mongodb://mongodb:27017/"
            print(f"Running in Docker. Using Docker MongoDB URI: {mongodb_uri}")
        else:
            # Default for local environment
            mongodb_uri = "mongodb://localhost:27017/"
            print(f"Running locally. Using local MongoDB URI: {mongodb_uri}")
    else:
        print(f"Using MONGODB_URI from environment: {mongodb_uri}")

    db_helper.MONGODB_URI = mongodb_uri

    yield

    # Clean up environment variables after tests
    del os.environ["DB_NAME_PREFIX"]
    del os.environ["TOKEN_URL"]
    del os.environ["BASE_URL_TERMINAL"]
    del os.environ["BASE_URL_MASTER_DATA"]
    del os.environ["BASE_URL_CART"]
    del os.environ["BASE_URL_REPORT"]
    del os.environ["BASE_URL_JOURNAL"]


@pytest_asyncio.fixture(scope="function")
async def http_client(set_env_vars):
    """
    Function-scoped fixture that provides an HTTP client for API testing

    This fixture creates an asynchronous HTTP client configured with the appropriate
    base URL for the Terminal service and an infinite timeout. The client is automatically
    closed after each test function completes.

    Args:
        set_env_vars: Session-scoped fixture that ensures environment variables are set

    Yields:
        AsyncClient: Configured HTTP client for making API requests
    """
    from httpx import AsyncClient, Timeout

    print("Setting up http client")
    base_url = os.environ.get("BASE_URL_TERMINAL")
    timeout = Timeout(timeout=None)  # Use infinite timeout for tests
    async with AsyncClient(base_url=base_url, timeout=timeout) as client:
        yield client
    print("Closing http client")
