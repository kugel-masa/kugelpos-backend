# Copyright 2026 masa@kugel
"""Integration test conftest for cart service.

Drives the cart FastAPI app in-process via httpx ASGITransport.
Cart's outbound dependencies are all mocked so tests run with only
MongoDB needed:

  - gRPC item-master lookup (master-data) — patched
    `get_master_data_grpc_stub` to return synthetic items.
  - HTTP master-data fallback (payments / promotions / settings) —
    respx routes return realistic shapes.
  - Terminal-service lookup for X-API-KEY auth — respx route.
  - Dapr sidecar (state store + pub/sub) on localhost:3500 — respx
    catch-all returning 204.
  - Account TOKEN_URL — respx returns the locally-generated admin JWT.
"""
import os
import re
from datetime import datetime, timedelta, timezone  # noqa: F401
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest
import pytest_asyncio
import respx
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Synthetic item / payment data used by the gRPC + HTTP mocks
# ---------------------------------------------------------------------------

# Items keyed by item_code. Prices match what services/master-data's
# test_setup_data would have populated for store 5678.
SYNTHETIC_ITEMS = {
    "49-01": {"item_name": "Item1", "price": 100.0, "tax_code": "01", "category_code": "001"},
    "49-02": {"item_name": "Item2", "price": 280.0, "tax_code": "01", "category_code": "001"},
}

# Payment master data keyed by payment_code.
SYNTHETIC_PAYMENTS = {
    "01": {"description": "Cash"},
    "11": {"description": "Cashless"},
    "12": {"description": "Cashless"},
    "99": {"description": "Other"},
}


def _make_grpc_item(item_code: str):
    """Build a MagicMock matching the gRPC ItemDetailResponse shape."""
    info = SYNTHETIC_ITEMS.get(item_code)
    response = MagicMock()
    if info:
        response.item_code = item_code
        response.item_name = info["item_name"]
        response.price = info["price"]
        response.tax_code = info["tax_code"]
        response.category_code = info["category_code"]
        response.is_active = True
    else:
        # NOT_FOUND case — empty item_code triggers cart's NotFoundException
        response.item_code = ""
        response.item_name = ""
        response.price = 0
        response.tax_code = ""
        response.category_code = ""
        response.is_active = False
    return response


# ---------------------------------------------------------------------------
# Env / DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def set_env_vars():
    """Integration env: load .env.test, configure MongoDB, set defaults."""
    from dotenv import load_dotenv

    CART_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    load_dotenv(dotenv_path=os.path.join(CART_DIR, ".env"), override=False)

    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    load_dotenv(dotenv_path=os.path.join(ROOT_DIR, ".env.test"), override=True)

    os.environ.setdefault("DB_NAME_PREFIX", "db_cart")
    os.environ.setdefault("STORE_CODE", "5678")
    os.environ.setdefault("TERMINAL_ID", f"{os.environ.get('TENANT_ID', 'T9999')}-5678-9")
    os.environ.setdefault("BASE_URL_CART", "http://localhost:8003")
    os.environ.setdefault("BASE_URL_MASTER_DATA", "http://localhost:8002/api/v1")
    os.environ.setdefault("BASE_URL_TERMINAL", "http://localhost:8001/api/v1")
    os.environ.setdefault("BASE_URL_ACCOUNT", "http://localhost:8000")
    os.environ.setdefault("TOKEN_URL", "http://localhost:8000/api/v1/accounts/token")

    from kugel_common.database import database as db_helper
    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    yield


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _setup_cart_db(set_env_vars):
    """Drop and re-initialise db_cart_<tenant> once per session."""
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
async def _reset_db_client_per_test(_setup_cart_db):
    yield
    from kugel_common.database import database as db_helper
    try:
        await db_helper.reset_client_async()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# JWT / API key fixtures
# ---------------------------------------------------------------------------

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
    terminal_id = f"{tenant_id}-5678-9"
    payload = {
        "sub": f"terminal:{terminal_id}",
        "tenant_id": tenant_id,
        "store_code": "5678",
        "terminal_no": 9,
        "terminal_id": terminal_id,
        "status": "Idle",
        "token_type": "terminal",
        "iss": "terminal-service",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
def api_key():
    return "test-api-key-12345"


# ---------------------------------------------------------------------------
# gRPC + HTTP mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_grpc_item_lookup():
    """Patch get_master_data_grpc_stub everywhere it is imported in cart.

    `from app.utils.grpc_channel_helper import get_master_data_grpc_stub`
    binds the name on the importing module, so patching the original
    location alone leaves cart's reference untouched. This fixture
    installs the patch where it is *used*.
    """
    async def _mock_get_stub(tenant_id, store_code):
        stub = MagicMock()

        async def get_item_detail(request, timeout=None):
            return _make_grpc_item(request.item_code)

        stub.GetItemDetail = AsyncMock(side_effect=get_item_detail)
        return stub

    with patch(
        "app.models.repositories.item_master_grpc_repository.get_master_data_grpc_stub",
        new=_mock_get_stub,
    ):
        yield SYNTHETIC_ITEMS


@pytest.fixture
def mock_outbound(admin_token, mock_grpc_item_lookup):
    """Catch-all respx mocks for every HTTP outbound the cart app makes:
    master-data (settings / payments / promotions / items fallback),
    terminal lookup (X-API-KEY path), Dapr sidecar, account TOKEN_URL.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_id = f"{tenant_id}-5678-9"
    base_master = os.environ.get("BASE_URL_MASTER_DATA", "http://localhost:8002/api/v1")
    base_terminal = os.environ.get("BASE_URL_TERMINAL", "http://localhost:8001/api/v1")
    token_url = os.environ.get("TOKEN_URL", "http://localhost:8000/api/v1/accounts/token")

    with respx.mock(assert_all_called=False) as respx_mock:
        # Account TOKEN_URL — return the locally-generated admin JWT
        respx_mock.post(token_url).mock(
            return_value=httpx.Response(
                200, json={"access_token": admin_token, "token_type": "bearer"}
            )
        )

        # Terminal service: GET /terminals/{id} returns an Opened terminal
        # with staff so cart's tran_service has all the data it needs.
        terminal_payload = {
            "success": True,
            "code": 200,
            "data": {
                "terminalId": terminal_id,
                "tenantId": tenant_id,
                "storeCode": store_code,
                "terminalNo": 9,
                "description": "Test Terminal",
                "functionMode": "OpenTerminal",
                "status": "Opened",
                "businessDate": datetime.now().strftime("%Y%m%d"),
                "openCounter": 1,
                "businessCounter": 1,
                "initialAmount": 50000.0,
                "physicalAmount": None,
                "staff": {"staffId": "S001", "staffName": "Staff1", "staffPin": "1234"},
                "apiKey": "test-api-key-12345",
            },
        }
        respx_mock.get(
            re.compile(rf"{re.escape(base_terminal)}/terminals/{re.escape(terminal_id)}.*")
        ).mock(return_value=httpx.Response(200, json=terminal_payload))

        # Terminal: GET /tenants/{id}/stores/{code} — store info lookup
        respx_mock.get(
            re.compile(rf"{re.escape(base_terminal)}/tenants/{tenant_id}/stores/{store_code}.*")
        ).mock(return_value=httpx.Response(200, json={
            "success": True, "code": 200,
            "data": {
                "tenantId": tenant_id,
                "storeCode": store_code,
                "storeName": "Test Store",
                "status": "Idle",
                "businessDate": datetime.now().strftime("%Y%m%d"),
                "tags": [],
            },
        }))

        # Terminal: POST /tenants/{id} — create tenant on cart's call to
        # POST /api/v1/tenants which itself fans out to other services
        respx_mock.post(
            re.compile(rf"{re.escape(base_terminal)}/tenants.*")
        ).mock(return_value=httpx.Response(201, json={
            "success": True, "code": 201, "data": None,
        }))

        # Terminal lifecycle / state mutations from test setup (PATCH /
        # function_mode, POST /sign-in / /open / /close / etc.) — return
        # 200 success no-op so test setup proceeds.
        for method in ("post", "patch", "delete", "put"):
            getattr(respx_mock, method)(
                re.compile(rf"{re.escape(base_terminal)}/terminals/.*")
            ).mock(return_value=httpx.Response(200, json={
                "success": True, "code": 200, "data": terminal_payload["data"],
            }))

        # Other services' /tenants endpoints (cart's POST /tenants fans
        # out to master-data / cart / report / journal / stock).
        for url_pattern in [
            r"http://localhost:8002/api/v1/tenants/?",  # master-data
            r"http://localhost:8003/api/v1/tenants/?",  # cart (self, but called via HTTP)
            r"http://localhost:8004/api/v1/tenants/?",  # report
            r"http://localhost:8005/api/v1/tenants/?",  # journal
            r"http://localhost:8006/api/v1/tenants/?",  # stock
        ]:
            respx_mock.post(re.compile(url_pattern)).mock(
                return_value=httpx.Response(201, json={"success": True, "code": 201})
            )

        # Master-data settings list — return empty success (cart treats
        # missing settings as defaults).
        respx_mock.get(
            re.compile(rf"{re.escape(base_master)}/tenants/{tenant_id}/settings/?($|\?)")
        ).mock(return_value=httpx.Response(200, json={
            "success": True, "code": 200, "data": [], "metadata": None,
        }))

        # Master-data settings single value — used by cart for things like
        # RECEIPT_NO_START_VALUE. The repo extracts `data.value` and uses it
        # as the doc's default_value, so return a sane numeric string here.
        respx_mock.get(
            re.compile(rf"{re.escape(base_master)}/tenants/{tenant_id}/settings/[^/]+/value")
        ).mock(return_value=httpx.Response(200, json={
            "success": True,
            "code": 200,
            "message": "ok",
            "data": {"value": "1"},
        }))

        # Master-data payment lookup
        for code, info in SYNTHETIC_PAYMENTS.items():
            respx_mock.get(
                re.compile(rf"{re.escape(base_master)}/tenants/{tenant_id}/payments/{code}.*")
            ).mock(return_value=httpx.Response(200, json={
                "success": True, "code": 200,
                "data": {
                    "paymentCode": code,
                    "description": info["description"],
                    "tenantId": tenant_id,
                },
            }))

        # Master-data active promotions (default: none)
        respx_mock.get(
            re.compile(rf"{re.escape(base_master)}/tenants/{tenant_id}/promotions/active.*")
        ).mock(return_value=httpx.Response(200, json={
            "success": True, "code": 200, "data": [],
        }))

        # Master-data item fallback web endpoint (used only if gRPC
        # fails — gRPC is patched but if route is exercised, return
        # the same synthetic items)
        for code, info in SYNTHETIC_ITEMS.items():
            respx_mock.get(
                re.compile(
                    rf"{re.escape(base_master)}/tenants/{tenant_id}/stores/{store_code}/items/{code}.*"
                )
            ).mock(return_value=httpx.Response(200, json={
                "success": True, "code": 200,
                "data": {
                    "itemCode": code,
                    "description": info["item_name"],
                    "unitPrice": info["price"],
                    "taxCode": info["tax_code"],
                    "categoryCode": info["category_code"],
                    "tenantId": tenant_id,
                    "storeCode": store_code,
                },
            }))

        # Dapr sidecar — catch-all
        for method in ("get", "post", "put", "delete"):
            getattr(respx_mock, method)(
                re.compile(r"http://localhost:3500/.*")
            ).mock(return_value=httpx.Response(204))

        yield respx_mock


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def http_client(_reset_db_client_per_test, mock_outbound):
    """In-process AsyncClient bound to the cart FastAPI app."""
    from app.main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Collection ordering / marker
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.integration)
