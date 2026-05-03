# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""
Integration test conftest for account service.

Integration tests run against a real MongoDB but use httpx ASGITransport
to drive the FastAPI app in-process — there is no need to start a uvicorn
process or docker-compose stack.

Provides:
  - http_client: AsyncClient bound to the in-process FastAPI app
  - _clean_account_db: session-scoped autouse, drops the test DB once at
    session start, replacing the legacy test_clean_data.py / test_setup_data.py
    pattern.

Tests under this directory are auto-marked with `integration`.
"""
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _clean_account_db(set_env_vars):
    """Drop the account test database once before any integration test runs."""
    from kugel_common.database import database as db_helper

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    db_client = await db_helper.get_client_async()
    target_db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"[integration setup] Dropping database: {target_db_name}")
    await db_client.drop_database(target_db_name)

    yield

    print("[integration teardown] Closing database connection")
    await db_helper.close_client_async()


@pytest_asyncio.fixture(scope="function")
async def http_client(_clean_account_db):
    """In-process HTTP client driving the FastAPI app via ASGITransport.

    Replaces the previous out-of-process pattern (AsyncClient pointed at
    http://localhost:8000), so integration tests no longer require a running
    uvicorn or docker-compose stack — only MongoDB.
    """
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def pytest_collection_modifyitems(config, items):
    """Mark only items located under THIS conftest's directory.

    pytest invokes the hook with the full `items` list collected from the
    whole session — without the path filter, the marker would apply to
    every test in the project, not just this tier.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.integration)
