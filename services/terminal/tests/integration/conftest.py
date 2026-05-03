# Copyright 2026 masa@kugel
"""Integration test conftest for terminal service.

Drives the terminal FastAPI app in-process via httpx ASGITransport.
- Outbound HTTP calls (to master-data / cart / report / journal / stock
  during POST /tenants, plus Dapr sidecar on port 3500) are mocked via
  respx.
- Admin JWTs are generated locally with the shared SECRET_KEY.
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
async def _setup_terminal_db(set_env_vars):
    """Drop and re-initialize the terminal test DB once per session.

    BASE_URL_STOCK is not in the parent conftest; set a default here so
    the in-process app's settings can be loaded.
    """
    os.environ.setdefault("BASE_URL_STOCK", "http://localhost:8006/api/v1")

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
async def _reset_db_client_per_test(_setup_terminal_db):
    yield
    from kugel_common.database import database as db_helper
    try:
        await db_helper.reset_client_async()
    except Exception:
        pass


@pytest_asyncio.fixture
async def http_client(_reset_db_client_per_test):
    """In-process AsyncClient bound to the terminal FastAPI app."""
    from app.main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def admin_token():
    """Locally-generated admin JWT — replaces fetching from account."""
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
def mock_outbound_services():
    """Mock POST /tenants on every downstream service that terminal's
    POST /api/v1/tenants fans out to (master-data, cart, report,
    journal, stock), plus any Dapr sidecar publishes.
    """
    success_response = httpx.Response(
        201, json={"success": True, "code": 201, "message": "tenant created", "data": None}
    )

    with respx.mock(assert_all_called=False) as respx_mock:
        # Downstream tenants endpoints — terminal POSTs to each on tenant create
        for url_pattern in [
            r"http://localhost:8002/api/v1/tenants/?",  # master-data
            r"http://localhost:8003/api/v1/tenants/?",  # cart
            r"http://localhost:8004/api/v1/tenants/?",  # report
            r"http://localhost:8005/api/v1/tenants/?",  # journal
            r"http://localhost:8006/api/v1/tenants/?",  # stock
        ]:
            respx_mock.post(re.compile(url_pattern)).mock(return_value=success_response)

        # Dapr sidecar publish/state — broad accept-anything route
        respx_mock.post(re.compile(r"http://localhost:3500/v1\.0/.*")).mock(
            return_value=httpx.Response(204)
        )
        respx_mock.get(re.compile(r"http://localhost:3500/v1\.0/.*")).mock(
            return_value=httpx.Response(204)
        )
        respx_mock.delete(re.compile(r"http://localhost:3500/v1\.0/.*")).mock(
            return_value=httpx.Response(204)
        )
        yield respx_mock


def pytest_collection_modifyitems(config, items):
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.integration)
