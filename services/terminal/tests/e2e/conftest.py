# Copyright 2026 masa@kugel
"""E2E test conftest for terminal service.

E2E tests require the full docker-compose stack to be running:
  - account (8000), terminal (8001), master-data (8002), cart (8003),
    report (8004), journal (8005), stock (8006)
  - MongoDB, Redis, RabbitMQ, Dapr sidecars

This conftest provides:
  - http_client: AsyncClient pointed at BASE_URL_TERMINAL (the running service)
  - _setup_terminal_db: session-scoped autouse fixture that drops and
    re-initializes the terminal test database, replacing the legacy
    test_clean_data.py / test_setup_data.py boot files.

Tests under this directory are auto-marked with `e2e`.
"""
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, Timeout


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _setup_terminal_db(set_env_vars):
    """Drop and re-initialize the terminal test database once per session.

    Replaces the previous test_clean_data.py + test_setup_data.py pattern,
    which relied on test-file ordering to bootstrap the database.
    """
    from kugel_common.database import database as db_helper
    from app.database import database_setup

    db_client = await db_helper.get_client_async()
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"[e2e setup] Dropping database: {target_db_name}")
    await db_client.drop_database(target_db_name)

    # Recreate collections / indexes
    await db_helper.close_client_async()
    tenant_id = os.environ.get("TENANT_ID")
    await database_setup.execute(tenant_id)

    yield

    print("[e2e teardown] Closing database connection")
    await db_helper.close_client_async()


@pytest_asyncio.fixture(scope="function")
async def http_client(_setup_terminal_db):
    """AsyncClient pointed at the running terminal service (BASE_URL_TERMINAL)."""
    base_url = os.environ.get("BASE_URL_TERMINAL")
    timeout = Timeout(timeout=None)
    async with AsyncClient(base_url=base_url, timeout=timeout) as client:
        yield client


def pytest_collection_modifyitems(config, items):
    """Mark only items located under THIS conftest's directory and ensure
    test_setup_data runs first within this tier.

    pytest invokes the hook with the full `items` list collected from the
    whole session — without the path filter, the marker would apply to
    every test in the project, not just this tier.
    """
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
