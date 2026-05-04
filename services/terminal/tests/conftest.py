# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""
Top-level conftest for terminal service tests.

Provides only environment-variable plumbing shared by integration and e2e
tiers. The HTTP client lives in tests/e2e/conftest.py. Unit tests override
`set_env_vars` to a no-op (see tests/unit/conftest.py) so they can run
with no external services or environment file.
"""
import logging
import logging.config
import os

# Module-level env bootstrap: must run BEFORE any test file imports the
# terminal app so app.config.settings sees the correct DB_NAME_PREFIX
# / SECRET_KEY etc. on first load. Otherwise pytest's auto-discovery
# of tests/unit/ caches the defaults before set_env_vars fixture fires,
# leading to integration-tier flakes (in-process app reads from a
# different DB / wrong secret than the test fixtures expect).
from dotenv import load_dotenv as _load_dotenv

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_load_dotenv(os.path.join(_ROOT_DIR, ".env.test"), override=True)
os.environ.setdefault("DB_NAME_PREFIX", "db_terminal")
os.environ.setdefault("STORE_CODE", "5678")
os.environ.setdefault(
    "TERMINAL_ID", f"{os.environ.get('TENANT_ID', 'T9999')}-5678-9"
)

logging.config.fileConfig("app/logging.conf")

import pytest
from dotenv import load_dotenv
from fastapi import status


def ensure_admin_user_exists(tenant_id: str, account_base_url: str):
    """Register the test admin user with the account service if missing.

    Required for e2e tests that fetch a JWT from the account service.
    Safe to call repeatedly: returns early if the user already exists.
    """
    from httpx import Client

    with Client() as client:
        token_url = f"{account_base_url}/api/v1/accounts/token"
        login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}
        response = client.post(url=token_url, data=login_data)

        if response.status_code == status.HTTP_200_OK:
            print(f"Admin user already exists for tenant: {tenant_id}")
            return

        print(f"Registering admin user for tenant: {tenant_id}")
        register_url = f"{account_base_url}/api/v1/accounts/register"
        register_data = {"username": "admin", "password": "admin", "tenant_id": tenant_id}
        response = client.post(url=register_url, json=register_data)

        if response.status_code == status.HTTP_201_CREATED:
            print(f"Admin user registered successfully for tenant: {tenant_id}")
        else:
            print(f"Admin user registration response: {response.json()}")


@pytest.fixture(scope="session")
def set_env_vars():
    """Load .env.test, set service URLs, ensure admin user exists, configure DB.

    Used by integration and e2e tests. Unit tests override this to a no-op.
    """
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dotenv_path = os.path.join(ROOT_DIR, ".env.test")
    if os.path.exists(dotenv_path):
        print(f".env.test file found at: {dotenv_path}")
        load_dotenv(dotenv_path=dotenv_path, override=True)
    else:
        print(f"WARNING: .env.test file not found at: {dotenv_path}")
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
        os.environ["BASE_URL_TERMINAL"] = "http://localhost:8001"
        os.environ["BASE_URL_MASTER_DATA"] = "http://localhost:8002/api/v1"
        os.environ["BASE_URL_CART"] = "http://localhost:8003/api/v1"
        os.environ["BASE_URL_REPORT"] = "http://localhost:8004/api/v1"
        os.environ["BASE_URL_JOURNAL"] = "http://localhost:8005/api/v1"
        os.environ["BASE_URL_ACCOUNT"] = "http://localhost:8000"
        os.environ["TOKEN_URL"] = "http://localhost:8000/api/v1/accounts/token"
    else:
        os.environ["BASE_URL_TERMINAL"] = f"https://terminal.{remote_server}"
        os.environ["BASE_URL_MASTER_DATA"] = f"https://master-data.{remote_server}/api/v1"
        os.environ["BASE_URL_CART"] = f"https://cart.{remote_server}/api/v1"
        os.environ["BASE_URL_REPORT"] = f"https://report.{remote_server}/api/v1"
        os.environ["BASE_URL_JOURNAL"] = f"https://journal.{remote_server}/api/v1"
        os.environ["BASE_URL_ACCOUNT"] = f"https://account.{remote_server}"
        os.environ["TOKEN_URL"] = f"https://account.{remote_server}/api/v1/accounts/token"

    # Required for e2e tests; integration tests using respx + ASGITransport
    # would skip this in their own integration/conftest.py.
    account_base_url = os.environ.get("BASE_URL_ACCOUNT")
    ensure_admin_user_exists(tenant_id, account_base_url)

    os.environ["DB_NAME_PREFIX"] = "db_terminal"

    from kugel_common.database import database as db_helper

    is_docker = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER", False)
    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        if is_docker:
            mongodb_uri = "mongodb://mongodb:27017/"
        else:
            mongodb_uri = "mongodb://localhost:27017/"
        print(f"Using default MongoDB URI: {mongodb_uri}")
    else:
        print(f"Using MONGODB_URI from environment: {mongodb_uri}")

    db_helper.MONGODB_URI = mongodb_uri

    yield

    del os.environ["DB_NAME_PREFIX"]
    del os.environ["TOKEN_URL"]
    del os.environ["BASE_URL_TERMINAL"]
    del os.environ["BASE_URL_MASTER_DATA"]
    del os.environ["BASE_URL_CART"]
    del os.environ["BASE_URL_REPORT"]
    del os.environ["BASE_URL_JOURNAL"]
    del os.environ["BASE_URL_ACCOUNT"]
