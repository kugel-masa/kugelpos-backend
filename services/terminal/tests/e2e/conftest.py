# Copyright 2026 masa@kugel
"""E2E test conftest for terminal service.

Holds the lifecycle tests (sign-in / open / close / cash-in/out / void)
that require the full docker-compose stack — master-data for staff
lookup, Dapr sidecar for cashlog/opencloselog publish, and the rest of
the services for tenant fan-out.

Auto-marks tests with `e2e`. Inherits set_env_vars and the live
http_client from the parent conftest.
"""
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, Timeout


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _setup_terminal_db(set_env_vars):
    """Drop the terminal test DB once per session for e2e isolation."""
    from kugel_common.database import database as db_helper

    db_client = await db_helper.get_client_async()
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"[e2e setup] Dropping database: {target_db_name}")
    await db_client.drop_database(target_db_name)
    await db_helper.close_client_async()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_db_client_per_test(_setup_terminal_db):
    yield
    from kugel_common.database import database as db_helper
    try:
        await db_helper.reset_client_async()
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def http_client(_reset_db_client_per_test):
    """AsyncClient pointed at the running terminal service."""
    base_url = os.environ.get("BASE_URL_TERMINAL")
    timeout = Timeout(timeout=None)
    async with AsyncClient(base_url=base_url, timeout=timeout) as client:
        yield client


def pytest_collection_modifyitems(config, items):
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.e2e)
