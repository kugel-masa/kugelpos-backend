# Copyright 2026 masa@kugel
"""Integration test conftest for cart service.

cart is the heaviest service: its e2e tests build full carts via the
cart API, which in turn reaches out to master-data (gRPC), terminal
(HTTP), and Dapr (state store + pub/sub). For this PR the integration
tier covers only the in-process tests that do not require those
mocks at scale (test_health, test_terminal_counter_rollover); the
remaining cart e2e tests stay under tests/e2e/ where they execute
against a live docker-compose stack.

Tests under this directory are auto-marked with `integration`.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest.fixture(scope="session")
def set_env_vars():
    """Integration setup: load .env.test and point db_helper at MongoDB."""
    from dotenv import load_dotenv

    CART_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cart_env_path = os.path.join(CART_DIR, ".env")
    load_dotenv(dotenv_path=cart_env_path, override=False)

    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    dotenv_path = os.path.join(ROOT_DIR, ".env.test")
    load_dotenv(dotenv_path=dotenv_path, override=True)

    os.environ.setdefault("DB_NAME_PREFIX", "db_cart")
    os.environ.setdefault("STORE_CODE", "5678")
    os.environ.setdefault("TERMINAL_ID", f"{os.environ.get('TENANT_ID', 'T9999')}-5678-9")

    from kugel_common.database import database as db_helper
    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")

    yield


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _setup_cart_db(set_env_vars):
    """Drop db_cart_<tenant> once per session so integration tests start
    from a clean state (no leftover carts from previous runs)."""
    from kugel_common.database import database as db_helper

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    db_client = await db_helper.get_client_async()
    target = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"[integration setup] Dropping database: {target}")
    await db_client.drop_database(target)
    await db_helper.close_client_async()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_db_client_per_test(_setup_cart_db):
    yield
    from kugel_common.database import database as db_helper
    try:
        await db_helper.reset_client_async()
    except Exception:
        pass


@pytest_asyncio.fixture
async def http_client(_reset_db_client_per_test):
    """In-process AsyncClient bound to the cart FastAPI app."""
    from app.main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def admin_token():
    from kugel_common.config.settings import settings
    tenant_id = os.environ.get("TENANT_ID")
    payload = {
        "sub": "admin",
        "tenant_id": tenant_id,
        "is_superuser": True,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
def admin_header(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def pytest_collection_modifyitems(config, items):
    """Mark only items located under THIS conftest's directory."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.integration)
