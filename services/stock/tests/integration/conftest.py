# Copyright 2026 masa@kugel
"""Integration test conftest for stock service.

Drives the stock FastAPI app in-process via httpx ASGITransport.
Outbound HTTP includes Dapr sidecar (state store, pub/sub) — mocked via
respx — and the kugel_common terminal-service lookup for X-API-KEY auth.
"""
import os

# Module-level, because kugel_common's `settings` singleton freezes on first
# import: anything assigned from a fixture lands too late to be seen. Declaring
# the same set the service lists in REQUIRED_SERVICE_URLS keeps the run hermetic
# and keeps it working if the tier ever starts driving the app's lifespan, which
# verifies exactly this set at startup (#159).
os.environ["BASE_URL_TERMINAL"] = "http://localhost:8001/api/v1"
os.environ["BASE_URL_MASTER_DATA"] = "http://localhost:8002/api/v1"
os.environ["BASE_URL_CART"] = "http://localhost:8003/api/v1"
os.environ["TOKEN_URL"] = "http://localhost:8000/api/v1/accounts/token"
import re
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import pytest_asyncio
import respx
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _setup_stock_db(set_env_vars):
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
async def _reset_db_client_per_test(_setup_stock_db):
    yield
    from kugel_common.database import database as db_helper
    try:
        await db_helper.reset_client_async()
    except Exception:
        pass


@pytest_asyncio.fixture
async def http_client(_reset_db_client_per_test, mock_dapr_sidecar):
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
def mock_dapr_sidecar(admin_token):
    """Catch-all respx routes covering everything the stock integration
    tier might call out to: the Dapr sidecar (state store, pub/sub),
    the account service (TOKEN_URL — returns the locally-generated admin
    JWT so existing test code that fetches it keeps working), and the
    terminal service (X-API-KEY auth path).
    """
    tenant_id = os.environ.get("TENANT_ID")
    terminal_id = f"{tenant_id}-5678-9"
    # Resolve against the same settings object the app uses
    # (http_client_helper._get_service_url), so a route can never be registered
    # at a URL the app will not request.
    from kugel_common.config.settings import settings

    base_terminal = settings.BASE_URL_TERMINAL
    token_url = settings.TOKEN_URL

    with respx.mock(assert_all_called=False) as respx_mock:
        # Dapr sidecar (3500)
        respx_mock.post(re.compile(r"http://localhost:3500/v1\.0/.*")).mock(
            return_value=httpx.Response(204)
        )
        respx_mock.get(re.compile(r"http://localhost:3500/v1\.0/.*")).mock(
            return_value=httpx.Response(204)
        )
        respx_mock.delete(re.compile(r"http://localhost:3500/v1\.0/.*")).mock(
            return_value=httpx.Response(204)
        )

        # Account TOKEN_URL — return the locally-generated admin JWT so
        # existing tests that fetch it via httpx still get a usable token.
        if token_url:
            respx_mock.post(token_url).mock(
                return_value=httpx.Response(
                    200, json={"access_token": admin_token, "token_type": "bearer"}
                )
            )

        # Terminal service lookup for X-API-KEY auth
        respx_mock.get(
            re.compile(rf"{re.escape(base_terminal)}/terminals/{re.escape(terminal_id)}.*")
        ).mock(
            return_value=httpx.Response(200, json={
                "success": True,
                "code": 200,
                "data": {
                    "terminalId": terminal_id,
                    "tenantId": tenant_id,
                    "storeCode": "5678",
                    "terminalNo": 9,
                    "apiKey": "test-api-key-12345",
                    "status": "Idle",
                },
            })
        )
        yield respx_mock


def pytest_collection_modifyitems(config, items):
    """Auto-mark integration; ensure test_setup_data runs first."""
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
