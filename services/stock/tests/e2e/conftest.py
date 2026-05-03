# Copyright 2026 masa@kugel
"""E2E test conftest for stock service.

E2E tests require the full docker-compose stack. Provides a session
autouse fixture that drops the stock test database and an http_client
pointing at BASE_URL_STOCK. test_setup_data runs first via collection
ordering hook.
"""
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, Timeout


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_stock_db(set_env_vars):
    from kugel_common.database import database as db_helper

    db_client = await db_helper.get_client_async()
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"[e2e setup] Dropping database: {target_db_name}")
    await db_client.drop_database(target_db_name)

    yield

    print("[e2e teardown] Closing database connection")
    await db_helper.close_client_async()


@pytest_asyncio.fixture(scope="function")
async def http_client(_setup_stock_db):
    base_url = os.environ.get("BASE_URL_STOCK")
    timeout = Timeout(timeout=None)
    async with AsyncClient(base_url=base_url, timeout=timeout) as client:
        yield client


def pytest_collection_modifyitems(config, items):
    setup_items = [i for i in items if "test_setup_data" in i.nodeid]
    other_items = [i for i in items if "test_setup_data" not in i.nodeid]
    items[:] = setup_items + other_items
    for item in items:
        item.add_marker(pytest.mark.e2e)
