# Copyright 2026 masa@kugel
"""E2E test conftest for cart service.

Holds the cart flows that exercise full cross-service contracts
(promotion CRUD on master-data, tranlog publish round-trips, payment
state machines, etc.) and therefore need the full docker-compose stack.

Auto-marks tests with `e2e`. Inherits set_env_vars from the parent
conftest (which fetches admin token + API key from running services).
"""
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, Timeout


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _setup_cart_db_e2e(set_env_vars):
    """Drop db_cart_<tenant> once per session for e2e isolation."""
    from kugel_common.database import database as db_helper

    db_client = await db_helper.get_client_async()
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"[e2e setup] Dropping database: {target_db_name}")
    await db_client.drop_database(target_db_name)
    await db_helper.close_client_async()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_db_client_per_test_e2e(_setup_cart_db_e2e):
    yield
    from kugel_common.database import database as db_helper
    try:
        await db_helper.reset_client_async()
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def http_client(_reset_db_client_per_test_e2e):
    """AsyncClient pointed at the running cart service."""
    base_url = os.environ.get("BASE_URL_CART")
    timeout = Timeout(timeout=None)
    async with AsyncClient(base_url=base_url, timeout=timeout) as client:
        yield client


def pytest_collection_modifyitems(config, items):
    """Auto-mark e2e and ensure test_setup_data runs first if present."""
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
