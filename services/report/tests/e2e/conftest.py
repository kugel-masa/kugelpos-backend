# Copyright 2026 masa@kugel
"""E2E test conftest for report service.

Auto-marks tests with `e2e`, ensures test_setup_data runs first, and
drops the report test database once at session start (replacing the
legacy test_clean_data.py boot file). Otherwise inherits set_env_vars,
http_client, clean_test_data, and the autouse cleanup_database_connection
from the parent conftest.
"""
import os

import pytest
import pytest_asyncio


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _setup_report_db(set_env_vars):
    """Drop the report test database once before any e2e test runs.

    Without this, residual data from earlier perf-test or feature-test
    runs accumulates across sessions and report aggregations no longer
    match expected fixture totals (cash_in, payment, etc.).

    The parent conftest's autouse `cleanup_database_connection` already
    resets the singleton client between tests, so we only need to close
    the session-loop client after the drop here — no per-test reset
    fixture is needed in this directory.
    """
    from kugel_common.database import database as db_helper

    db_client = await db_helper.get_client_async()
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"[e2e setup] Dropping database: {target_db_name}")
    await db_client.drop_database(target_db_name)
    await db_helper.close_client_async()

    yield


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
