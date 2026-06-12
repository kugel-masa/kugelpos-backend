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
from datetime import datetime, timedelta, timezone
from kugel_common.utils.misc import get_app_time

import httpx
import jwt
import pytest
import pytest_asyncio
import respx
from dotenv import load_dotenv
from httpx import AsyncClient, ASGITransport


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
    os.environ.setdefault("BUSINESS_DATE", get_app_time().strftime("%Y%m%d"))

    from kugel_common.database import database as db_helper
    mongodb_uri = os.environ.get("MONGODB_URI") or "mongodb://localhost:27017/"
    db_helper.MONGODB_URI = mongodb_uri

    yield


@pytest.fixture
def mock_outbound():
    """Catch-all respx mocks for every HTTP outbound report makes.

    report's ReportService pulls in a TerminalInfoWebRepository (calls
    terminal /terminals) plus item/category master-data web repos. None
    of those services should be required for integration tests to run,
    so register stub responses here.

    `assert_all_called=False` because not every test exercises every
    endpoint; respx still INTERCEPTS unmocked calls and raises, which is
    the contract that proves cross-service independence.
    """
    base_terminal = os.environ.get("BASE_URL_TERMINAL", "http://localhost:8001/api/v1")
    base_master = os.environ.get("BASE_URL_MASTER_DATA", "http://localhost:8002/api/v1")
    tenant_id = os.environ.get("TENANT_ID")

    with respx.mock(assert_all_called=False) as respx_mock:
        # Terminal service — list / single
        respx_mock.get(f"{base_terminal}/terminals").mock(
            return_value=httpx.Response(200, json={"success": True, "code": 200, "data": []})
        )
        import re
        respx_mock.get(
            re.compile(rf"{re.escape(base_terminal)}/terminals/[^/?]+.*")
        ).mock(return_value=httpx.Response(200, json={
            "success": True, "code": 200,
            "data": {
                "terminalId": f"{tenant_id}-5678-5555",
                "tenantId": tenant_id, "storeCode": "5678",
                "terminalNo": 5555, "description": "Test",
                "functionMode": "Sales", "status": "Opened",
                "businessDate": get_app_time().strftime("%Y%m%d"),
                "openCounter": 1, "businessCounter": 1,
                "initialAmount": 0.0, "physicalAmount": None,
                "staff": {"staffId": "S001", "staffName": "Staff", "staffPin": "1234"},
                "apiKey": "test-api-key",
            },
        }))
        # Master-data items / categories
        respx_mock.get(
            re.compile(rf"{re.escape(base_master)}/tenants/{tenant_id}/.*items.*")
        ).mock(return_value=httpx.Response(200, json={
            "success": True, "code": 200, "data": {
                "itemCode": "0", "description": "Stub Item",
                "unitPrice": 0.0, "taxCode": "01", "categoryCode": "001",
            },
        }))
        respx_mock.get(
            re.compile(rf"{re.escape(base_master)}/tenants/{tenant_id}/categories.*")
        ).mock(return_value=httpx.Response(200, json={
            "success": True, "code": 200, "data": {
                "categoryCode": "001", "description": "Stub Cat",
                "descriptionShort": "SC", "taxCode": "01",
            },
        }))
        yield respx_mock


@pytest_asyncio.fixture
async def http_client(set_env_vars, mock_outbound):
    """In-process AsyncClient bound to the report FastAPI app."""
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
    """Mark only items located under THIS conftest's directory.

    pytest invokes the hook with the full `items` list collected from the
    whole session — without the path filter, the marker would apply to
    every test in the project, not just this tier.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.integration)
