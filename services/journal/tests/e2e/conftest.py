# Copyright 2026 masa@kugel
"""E2E test conftest for journal service.

Drives the live journal service. Auto-marks tests with `e2e`.
"""
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, Timeout


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _setup_journal_db(set_env_vars):
    """Drop the journal test DB once per session for e2e isolation."""
    from kugel_common.database import database as db_helper

    db_client = await db_helper.get_client_async()
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"[e2e setup] Dropping database: {target_db_name}")
    await db_client.drop_database(target_db_name)
    await db_helper.close_client_async()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_db_client_per_test(_setup_journal_db):
    yield
    from kugel_common.database import database as db_helper
    try:
        await db_helper.reset_client_async()
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def http_client(_reset_db_client_per_test):
    """AsyncClient pointed at the running journal service."""
    base_url = os.environ.get("BASE_URL_JOURNAL", "http://localhost:8005")
    async with AsyncClient(base_url=base_url, timeout=Timeout(timeout=None)) as client:
        yield client


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _ensure_admin_user():
    """Register admin user on the live account service if not present."""
    from fastapi import status as http_status

    base_account = os.environ.get("BASE_URL_ACCOUNT", "http://localhost:8000")
    tenant_id = os.environ.get("TENANT_ID")
    async with AsyncClient(base_url=base_account, timeout=Timeout(timeout=None)) as client:
        login = await client.post(
            "/api/v1/accounts/token",
            data={"username": "admin", "password": "admin", "client_id": tenant_id},
        )
        if login.status_code == http_status.HTTP_200_OK:
            return
        await client.post(
            "/api/v1/accounts/register",
            json={"username": "admin", "password": "admin", "tenant_id": tenant_id},
        )


@pytest_asyncio.fixture(scope="function")
async def admin_token(_ensure_admin_user):
    base_account = os.environ.get("BASE_URL_ACCOUNT", "http://localhost:8000")
    tenant_id = os.environ.get("TENANT_ID")
    async with AsyncClient(base_url=base_account, timeout=Timeout(timeout=None)) as client:
        response = await client.post(
            "/api/v1/accounts/token",
            data={"username": "admin", "password": "admin", "client_id": tenant_id},
        )
        response.raise_for_status()
        return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def admin_header(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def pytest_collection_modifyitems(config, items):
    this_dir = os.path.dirname(os.path.abspath(__file__))
    own = []
    other = []
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.e2e)
            own.append(item)
        else:
            other.append(item)
    setups = [i for i in own if "test_setup_data" in i.nodeid]
    rest = [i for i in own if "test_setup_data" not in i.nodeid]
    items[:] = other + setups + rest
