# Copyright 2026 masa@kugel
"""Integration test conftest for cart service.

Integration tests use a real MongoDB but do NOT require account, terminal,
master-data, or any other service to be running. This conftest overrides
the parent set_env_vars to a lighter setup: load .env.test and configure
MongoDB only — no token fetch, no API-key lookup, no cross-service HTTP.

Tests under this directory are auto-marked with `integration`.
"""
import os

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session")
def set_env_vars():
    """Integration setup: load .env.test and point db_helper at MongoDB."""
    CART_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cart_env_path = os.path.join(CART_DIR, ".env")
    load_dotenv(dotenv_path=cart_env_path, override=False)

    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    dotenv_path = os.path.join(ROOT_DIR, ".env.test")
    load_dotenv(dotenv_path=dotenv_path, override=True)

    os.environ.setdefault("DB_NAME_PREFIX", "db_cart")

    from kugel_common.database import database as db_helper
    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")

    yield


def pytest_collection_modifyitems(config, items):
    """Auto-mark every test collected under tests/integration/ with `integration`."""
    for item in items:
        item.add_marker(pytest.mark.integration)
