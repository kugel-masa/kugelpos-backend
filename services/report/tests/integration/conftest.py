# Copyright 2026 masa@kugel
"""Integration test conftest for report service.

These tests exercise repository / aggregation logic against a real
MongoDB instance, but do NOT need the account, terminal, master-data,
cart, or journal services running. The override of `set_env_vars` skips
the cross-service admin-user setup parent does.

Tests under this directory are auto-marked with `integration`. Parent's
autouse fixtures `cleanup_database_connection` and `mock_locale` continue
to apply.
"""
import os
from datetime import datetime

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session")
def set_env_vars():
    """Lighter set_env_vars: load .env.test and configure MongoDB only."""
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    dotenv_path = os.path.join(ROOT_DIR, ".env.test")
    load_dotenv(dotenv_path=dotenv_path, override=True)

    tenant_id = os.getenv("TENANT_ID")
    os.environ.setdefault("DB_NAME_PREFIX", "db_report")
    os.environ.setdefault("STORE_CODE", "5678")
    os.environ.setdefault("TERMINAL_NO", "5555")
    os.environ.setdefault("TERMINAL_ID", f"{tenant_id}-5678-5555")
    os.environ.setdefault("BUSINESS_DATE", datetime.now().strftime("%Y%m%d"))

    from kugel_common.database import database as db_helper
    mongodb_uri = os.environ.get("MONGODB_URI") or "mongodb://localhost:27017/"
    db_helper.MONGODB_URI = mongodb_uri

    yield


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
