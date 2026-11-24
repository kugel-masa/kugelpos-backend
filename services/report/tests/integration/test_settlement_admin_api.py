# Copyright 2026 masa@kugel
"""Back office settles a session its terminal will never close (#343, review S2)."""

import os
import uuid

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper
from kugel_common.utils.service_auth import create_service_token

from app.config.settings import settings
from app.database import database_setup
from app.models.repositories.tranlog_repository import TranlogRepository

from .test_settlement_confirm import _sale

STORE = "S343ADM"
TERMINAL = 6
BC = 77
DATE = "20261124"


def _tenant() -> str:
    return os.environ.get("TENANT_ID")


def _url(terminal_no=TERMINAL) -> str:
    return f"/api/v1/tenants/{_tenant()}/stores/{STORE}/terminals/{terminal_no}/settlements"


async def _db():
    return await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{_tenant()}")


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await database_setup.execute(_tenant())
    db = await _db()

    async def wipe():
        for name in (
            settings.DB_COLLECTION_NAME_SETTLEMENT_RECORD,
            settings.DB_COLLECTION_NAME_SETTLEMENT_DAILY_REPORT,
            "log_tran",
        ):
            await db[name].delete_many({"store_code": STORE})

    await wipe()
    yield
    await wipe()


async def _orphan_sale(no=1, amount=1000):
    """A sale of a session no close will ever settle (its terminal was deleted while open)."""
    sale = _sale(no, amount=amount, business_counter=BC)
    sale.tenant_id = _tenant()
    sale.store_code = STORE
    sale.terminal_no = TERMINAL
    sale.business_date = DATE
    sale.cart_id = str(uuid.uuid4())
    await TranlogRepository(await _db(), _tenant()).create_tranlog_async(sale)


@pytest.mark.asyncio
async def test_back_office_settles_an_orphan_session_and_the_daily_report_answers(http_client, admin_header):
    await _orphan_sale()
    daily = f"/api/v1/tenants/{_tenant()}/stores/{STORE}/reports?report_scope=daily&report_type=sales&business_date={DATE}"
    blocked = await http_client.get(daily, headers=admin_header)
    assert blocked.status_code == 403, blocked.text  # 412101: the orphan holds it

    response = await http_client.post(
        _url(), json={"businessCounter": BC, "reason": "terminal deleted while open"}, headers=admin_header
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["created"] is True
    assert data["state"] == "final"
    assert data["settledKind"] == "admin"
    assert data["adminReason"] == "terminal deleted while open"
    assert data["settledBy"].startswith("admin:")
    assert data["includedCount"] == 1
    assert data["businessDate"] == DATE
    assert data["expectedCash"]["cashSales"] == 1100
    assert data["difference"] is None  # nobody counted that drawer

    answered = await http_client.get(daily, headers=admin_header)
    assert answered.status_code == 200, answered.text
    assert answered.json()["data"]["salesGross"]["amount"] == 1100


@pytest.mark.asyncio
async def test_a_settled_session_is_returned_as_stored(http_client, admin_header):
    await _orphan_sale()
    body = {"businessCounter": BC, "reason": "r"}
    first = (await http_client.post(_url(), json=body, headers=admin_header)).json()["data"]
    await _orphan_sale(no=2, amount=5000)

    again = await http_client.post(_url(), json=body, headers=admin_header)

    assert again.status_code == 200
    assert again.json()["data"]["created"] is False
    assert again.json()["data"]["settlementId"] == first["settlementId"]
    assert again.json()["data"]["includedCount"] == 1


@pytest.mark.asyncio
async def test_a_session_with_no_log_is_404(http_client, admin_header):
    response = await http_client.post(_url(), json={"businessCounter": 999, "reason": "r"}, headers=admin_header)
    assert response.status_code == 404, response.text
    assert response.json()["userError"]["code"] == "413007"


@pytest.mark.asyncio
async def test_a_reason_is_required(http_client, admin_header):
    response = await http_client.post(_url(), json={"businessCounter": BC}, headers=admin_header)
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("credential", ["api_key", "none", "other_tenant"])
async def test_other_credentials_are_refused(http_client, credential):
    headers = {
        "api_key": {"X-API-KEY": "anything"},
        "none": {},
        "other_tenant": {"Authorization": f"Bearer {create_service_token('SOMEONE_ELSE', 'terminal')}"},
    }[credential]
    response = await http_client.post(_url(), json={"businessCounter": BC, "reason": "r"}, headers=headers)
    assert response.status_code in (400, 401, 403)
