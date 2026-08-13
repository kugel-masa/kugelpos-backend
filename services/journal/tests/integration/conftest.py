# Copyright 2026 masa@kugel
"""Integration test conftest for journal service.

Integration tests use a real MongoDB but drive the FastAPI app in-process
via httpx ASGITransport. Outbound HTTP that the journal app would
normally make (currently only the terminal-service lookup for API-key
verification) is mocked with respx. Admin / terminal JWTs are generated
locally with the shared SECRET_KEY instead of fetched from the account
service.

Tests under this directory are auto-marked with `integration`.
"""
import os

# Module-level, because kugel_common's `settings` singleton freezes on first
# import: anything assigned from a fixture lands too late to be seen. Declaring
# the same set the service lists in REQUIRED_SERVICE_URLS keeps the run hermetic
# and keeps it working if the tier ever starts driving the app's lifespan, which
# verifies exactly this set at startup (#159).
os.environ["BASE_URL_TERMINAL"] = "http://localhost:8001/api/v1"
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
async def _setup_journal_db(set_env_vars):
    """Drop and re-initialize the journal test DB once per session, then
    seed the journal entries that read-side tests query.

    Closes the session-loop client at session start so per-test loops can
    create their own clients (motor is loop-bound).
    """
    from kugel_common.database import database as db_helper
    from app.database import database_setup
    from app.models.documents.jornal_document import JournalDocument
    from app.models.repositories.journal_repository import JournalRepository
    from kugel_common.utils.misc import get_app_time, get_app_time_str

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    db_client = await db_helper.get_client_async()
    tenant_id = os.environ.get("TENANT_ID")
    target = f"{os.environ.get('DB_NAME_PREFIX')}_{tenant_id}"
    print(f"[integration setup] Dropping database: {target}")
    await db_client.drop_database(target)

    # Recreate collections / indexes
    await database_setup.execute(tenant_id=tenant_id)

    # Seed two journal entries used by read-side tests.
    db = await db_helper.get_db_async(target)
    journal_repo = JournalRepository(db, tenant_id)
    store_code = os.environ.get("STORE_CODE")
    terminal_no = int(os.environ.get("TERMINAL_NO"))
    business_date_str = get_app_time().strftime("%Y%m%d")

    for seq, recipt_no, with_amount in [(122, 788, False), (123, 789, True)]:
        kwargs = dict(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            journal_seq_no=seq,
            transaction_no=455 if seq == 122 else 456,
            transaction_type=101,
            business_date=business_date_str,
            open_counter=1,
            business_counter=1,
            generate_date_time=get_app_time_str(),
            receipt_no=recipt_no,
            content="example_content",
            journal_text="example_journal_text",
            receipt_text="example_receipt_text",
        )
        if with_amount:
            kwargs.update(amount=19800.0, quantity=10, staff_id="S001", user_id="U001")
        await journal_repo.create_journal_async(journal_doc=JournalDocument(**kwargs))

    await db_helper.close_client_async()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_db_client_per_test(_setup_journal_db):
    """Reset the singleton MongoDB client between tests so each runs
    with a client bound to its own event loop.
    """
    yield
    from kugel_common.database import database as db_helper
    try:
        await db_helper.reset_client_async()
    except Exception:
        pass


@pytest_asyncio.fixture
async def http_client(_reset_db_client_per_test, mock_outbound):
    """In-process HTTP client driving the journal FastAPI app.

    No uvicorn or docker-compose stack is needed — only MongoDB.
    `mock_outbound` ensures every cross-service HTTP call is intercepted.
    """
    from app.main import app

    # raise_app_exceptions=False so HTTPException raised inside the app
    # surfaces as a regular HTTP response (e.g. 401), instead of being
    # propagated up into the test (which is what httpx 0.28+ does by
    # default and which conflicts with starlette BaseHTTPMiddleware).
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def admin_token():
    """Locally-generated admin JWT — replaces fetching from account service."""
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
def terminal_jwt():
    """Locally-generated terminal JWT (token_type='terminal')."""
    from kugel_common.config.settings import settings
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = int(os.environ.get("TERMINAL_NO", "9"))
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    payload = {
        "sub": f"terminal:{terminal_id}",
        "tenant_id": tenant_id,
        "store_code": store_code,
        "terminal_no": terminal_no,
        "terminal_id": terminal_id,
        "status": "Idle",
        "token_type": "terminal",
        "iss": "terminal-service",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
def api_key():
    """Static API key used by integration tests."""
    return "test-api-key-12345"


@pytest.fixture
def mock_outbound(api_key):
    """Catch-all respx mocks for every cross-service HTTP call journal
    makes:
    - GET terminal /terminals/{id} for X-API-KEY verification
      (via get_terminal_info_from_terminal_service in kugel_common.security)
    - POST cart /tenants/.../transactions/.../delivery-status (pubsub
      completion notify)
    - POST terminal /terminals/{id}/delivery-status (terminallog pubsub
      completion notify)

    `assert_all_called=False` because most tests don't trigger every
    notification path; respx still INTERCEPTS unmocked calls and raises,
    which is the contract that proves cross-service independence.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = int(os.environ.get("TERMINAL_NO", "9"))
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    # Resolve against the same settings object the app uses
    # (http_client_helper._get_service_url), so a route can never be registered
    # at a URL the app will not request.
    from kugel_common.config.settings import settings

    base_terminal = settings.BASE_URL_TERMINAL
    base_cart = settings.BASE_URL_CART

    terminal_payload = {
        "success": True,
        "code": 200,
        "message": f"Terminal Retrieved. terminal_id: {terminal_id}",
        "userError": None,
        "data": {
            "terminalId": terminal_id,
            "tenantId": tenant_id,
            "storeCode": store_code,
            "terminalNo": terminal_no,
            "description": "test terminal",
            "functionMode": "Sales",
            "status": "Idle",
            "businessDate": None,
            "openCounter": 0,
            "businessCounter": 0,
            "initialAmount": 0.0,
            "physicalAmount": None,
            "staff": None,
            "apiKey": api_key,
        },
        "metadata": None,
        "operation": "get_terminal",
    }

    with respx.mock(assert_all_called=False) as respx_mock:
        # Terminal: GET /terminals/{id} for X-API-KEY auth
        respx_mock.get(
            re.compile(rf"{re.escape(base_terminal)}/terminals/{re.escape(terminal_id)}.*")
        ).mock(return_value=httpx.Response(200, json=terminal_payload))
        # Terminal: POST /terminals/{id}/delivery-status (pubsub notify)
        respx_mock.post(
            re.compile(rf"{re.escape(base_terminal)}/terminals/.+/delivery-status.*")
        ).mock(return_value=httpx.Response(200, json={"success": True}))
        # Cart: POST .../transactions/.../delivery-status (pubsub notify)
        respx_mock.post(
            re.compile(rf"{re.escape(base_cart)}/tenants/.+/transactions/.+/delivery-status.*")
        ).mock(return_value=httpx.Response(200, json={"success": True}))
        yield respx_mock


@pytest.fixture
def mock_terminal_service(mock_outbound):
    """Backwards-compat alias — older tests request `mock_terminal_service`
    explicitly; the broader `mock_outbound` covers it."""
    return mock_outbound


def pytest_collection_modifyitems(config, items):
    """Mark only items located under THIS conftest's directory."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.integration)
