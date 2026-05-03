# Copyright 2026 masa@kugel
"""Top-level e2e test conftest.

Drives the full docker-compose stack via raw httpx clients pointed at
the published service ports. Loads .env.test from the project root so
TENANT_ID / MONGODB_URI / etc. line up with the per-service e2e tier.
"""
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def _load_env():
    root = Path(__file__).parent.parent
    load_dotenv(root / ".env.test", override=True)
    # Default service URLs for local docker-compose
    os.environ.setdefault("URL_ACCOUNT", "http://localhost:8000")
    os.environ.setdefault("URL_TERMINAL", "http://localhost:8001")
    os.environ.setdefault("URL_MASTER_DATA", "http://localhost:8002")
    os.environ.setdefault("URL_CART", "http://localhost:8003")
    os.environ.setdefault("URL_REPORT", "http://localhost:8004")
    os.environ.setdefault("URL_JOURNAL", "http://localhost:8005")
    os.environ.setdefault("URL_STOCK", "http://localhost:8006")
    yield


def pytest_collection_modifyitems(config, items):
    """Auto-mark every test in this directory with `e2e`."""
    for item in items:
        item.add_marker(pytest.mark.e2e)
