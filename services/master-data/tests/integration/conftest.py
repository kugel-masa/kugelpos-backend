# Copyright 2026 masa@kugel
"""Integration test conftest for master-data service.

Drives the master-data FastAPI app in-process via httpx ASGITransport.
master-data makes no outbound HTTP calls of its own (CRUD-only), so the
only mocks needed are for the optional API-key auth path which goes
through kugel_common's terminal-service lookup.
"""
import os
import re
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import pytest_asyncio
import respx
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _setup_master_data_db(set_env_vars):
    """Drop and re-initialize the master-data test DB once per session."""
    from kugel_common.database import database as db_helper
    from app.database import database_setup

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    db_client = await db_helper.get_client_async()
    target = f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}"
    print(f"[integration setup] Dropping database: {target}")
    await db_client.drop_database(target)

    tenant_id = os.environ.get("TENANT_ID")
    await database_setup.execute(tenant_id)
    await db_helper.close_client_async()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_db_client_per_test(_setup_master_data_db):
    yield
    from kugel_common.database import database as db_helper
    try:
        await db_helper.reset_client_async()
    except Exception:
        pass


@pytest_asyncio.fixture
async def http_client(_reset_db_client_per_test):
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


@pytest.fixture
def terminal_jwt():
    """Locally-generated terminal JWT (token_type='terminal')."""
    from kugel_common.config.settings import settings
    tenant_id = os.environ.get("TENANT_ID")
    payload = {
        "sub": f"terminal:{tenant_id}-5678-9",
        "tenant_id": tenant_id,
        "store_code": "5678",
        "terminal_no": 9,
        "terminal_id": f"{tenant_id}-5678-9",
        "status": "Idle",
        "token_type": "terminal",
        "iss": "terminal-service",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
def api_key():
    return "test-api-key-12345"


@pytest.fixture
def mock_terminal_service(api_key):
    """Mock the terminal-service lookup for the X-API-KEY auth path."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = "5678"
    terminal_no = 9
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    base_terminal = os.environ.get("BASE_URL_TERMINAL")

    payload = {
        "success": True,
        "code": 200,
        "data": {
            "terminalId": terminal_id,
            "tenantId": tenant_id,
            "storeCode": store_code,
            "terminalNo": terminal_no,
            "apiKey": api_key,
            "status": "Idle",
        },
    }

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(
            re.compile(rf"{re.escape(base_terminal)}/terminals/{re.escape(terminal_id)}.*")
        ).mock(return_value=httpx.Response(200, json=payload))
        yield respx_mock


def pytest_collection_modifyitems(config, items):
    """Mark items in this dir with `integration` and ensure
    test_setup_data runs first — downstream tests (test_operations,
    test_promotion_master) depend on the staff / category / item /
    payment / settings seed it produces.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    own = []
    other = []
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.integration)
            own.append(item)
        else:
            other.append(item)
    setups = [i for i in own if "test_setup_data" in i.nodeid]
    rest = [i for i in own if "test_setup_data" not in i.nodeid]
    items[:] = other + setups + rest
