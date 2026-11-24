# Copyright 2026 masa@kugel
"""The internal settlement endpoints accept only a service account of the path's tenant (#343, FR-022)."""

import os

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper
from kugel_common.utils.service_auth import create_service_token

from app.config.settings import settings
from app.database import database_setup

STORE = "S343API"
TERMINAL = 9


def _tenant() -> str:
    return os.environ.get("TENANT_ID")


def _url(tenant=None, path="settlements") -> str:
    return f"/api/v1/internal/tenants/{tenant or _tenant()}/stores/{STORE}/terminals/{TERMINAL}/{path}"


BODY = {"businessCounter": 4, "businessDate": "20261124", "openCounter": 1, "settledAt": "20261124T21:00:00", "seq": 0}
PREVIEW = "?business_counter=4&business_date=20261124&open_counter=1"


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await database_setup.execute(_tenant())
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{_tenant()}")
    await db[settings.DB_COLLECTION_NAME_SETTLEMENT_RECORD].delete_many({"store_code": STORE})
    yield
    await db[settings.DB_COLLECTION_NAME_SETTLEMENT_RECORD].delete_many({"store_code": STORE})
    await db[settings.DB_COLLECTION_NAME_SETTLEMENT_DAILY_REPORT].delete_many({"store_code": STORE})


def _service():
    return {"Authorization": f"Bearer {create_service_token(_tenant(), 'terminal')}"}


@pytest.mark.asyncio
async def test_a_service_account_confirms_and_previews(http_client):
    response = await http_client.post(_url(), json=BODY, headers=_service())

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["state"] == "provisional"
    assert data["created"] is True
    assert data["includedCount"] == 0 and data["missingCount"] == 0
    assert data["expectedCash"]["total"] == 0

    preview = await http_client.get(_url(path="settlement-preview") + PREVIEW, headers=_service())
    assert preview.status_code == 200, preview.text
    assert preview.json()["data"]["settled"] is False


@pytest.mark.asyncio
async def test_another_tenants_service_account_is_refused(http_client):
    other = {"Authorization": f"Bearer {create_service_token('SOMEONE_ELSE', 'terminal')}"}
    response = await http_client.post(_url(), json=BODY, headers=other)
    # verify_tenant_id answers 400, as on every internal endpoint
    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("credential", ["user", "api_key", "none"])
async def test_other_credentials_are_refused(http_client, admin_header, credential):
    headers = {"user": admin_header, "api_key": {"X-API-KEY": "anything"}, "none": {}}[credential]
    response = await http_client.post(_url(), json=BODY, headers=headers)
    assert response.status_code in (401, 403)
    preview = await http_client.get(_url(path="settlement-preview") + PREVIEW, headers=headers)
    assert preview.status_code in (401, 403)


@pytest.mark.asyncio
async def test_a_bad_request_is_422(http_client):
    response = await http_client.post(_url(), json={**BODY, "businessDate": "2026-11-24"}, headers=_service())
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("service_name", ["cart", "stock", "journal", "report"])
async def test_only_terminal_may_settle(http_client, service_name):
    """Least privilege: a service account of the tenant, but not terminal's, is refused."""
    other = {"Authorization": f"Bearer {create_service_token(_tenant(), service_name)}"}

    response = await http_client.post(_url(), json=BODY, headers=other)
    preview = await http_client.get(_url(path="settlement-preview") + PREVIEW, headers=other)

    assert response.status_code == 403, response.text
    assert preview.status_code == 403, preview.text
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{_tenant()}")
    assert await db[settings.DB_COLLECTION_NAME_SETTLEMENT_RECORD].count_documents({"store_code": STORE}) == 0
