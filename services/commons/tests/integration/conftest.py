# Copyright 2026 masa@kugel
"""Integration test conftest for kugel_common.

These tests run the database helpers and AbstractRepository against a real
MongoDB (a replica set, for transactions). Nothing else is needed.

Every test gets a database of its own, named once when the fixture creates it
and dropped by that name alone at teardown. The name is never recomputed at
teardown: a name rebuilt from settings after a test has changed them can point
at a real database (#335).

The shared client is bound to the event loop that created it. Each test closes
it at its own end, on its own loop, so no client outlives the loop it belongs to.

Tests under this directory are auto-marked with `integration`.
"""
import os
import uuid

import pytest
import pytest_asyncio

# The tests run on the published development keys (issue #132).
os.environ.setdefault("ALLOW_INSECURE_DEV_SECRETS", "true")

TEST_DB_PREFIX = "commons_it_"
DEFAULT_MONGODB_URI = "mongodb://localhost:27017/?replicaSet=rs0&directConnection=true"


def pytest_collection_modifyitems(config, items):
    """Mark only items located under THIS conftest's directory."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def mongodb_uri() -> str:
    return os.environ.get("MONGODB_URI", DEFAULT_MONGODB_URI)


@pytest_asyncio.fixture
async def db_helper(mongodb_uri, monkeypatch):
    """The database module, pointed at the test MongoDB, closed on this test's loop."""
    from kugel_common.database import database

    monkeypatch.setattr(database, "MONGODB_URI", mongodb_uri)
    assert database.client is None, "a client leaked from an earlier test"
    yield database
    await database.close_client_async()


@pytest_asyncio.fixture
async def test_db(db_helper):
    """A database of this test's own, dropped by the name it was created with."""
    name = f"{TEST_DB_PREFIX}{uuid.uuid4().hex[:12]}"
    assert name.startswith(TEST_DB_PREFIX)
    client = await db_helper.get_client_async()
    db = client[name]
    yield db
    assert name.startswith(TEST_DB_PREFIX)
    await client.drop_database(name)
