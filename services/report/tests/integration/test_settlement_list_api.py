# Copyright 2026 masa@kugel
"""The store's settlement list (#343, US4, FR-020)."""

import os
import uuid

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper
from kugel_common.utils.misc import get_app_time

from app.config.settings import settings
from app.database import database_setup
from app.models.documents.settlement_record_document import SettlementRecordDocument
from app.models.repositories.settlement_record_repository import SettlementRecordRepository

STORE = "S343LIST"


def _tenant():
    return os.environ.get("TENANT_ID")


@pytest_asyncio.fixture(autouse=True)
async def _records():
    tenant = _tenant()
    await database_setup.execute(tenant)
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant}")
    collection = db[settings.DB_COLLECTION_NAME_SETTLEMENT_RECORD]
    await collection.delete_many({"store_code": STORE})
    repo = SettlementRecordRepository(db, tenant)
    for date, terminal_no, bc, final in [
        ("20261124", 2, 8, True),
        ("20261123", 1, 4, True),
        ("20261124", 1, 5, False),
    ]:
        record = SettlementRecordDocument(
            tenant_id=tenant, store_code=STORE, terminal_no=terminal_no, business_counter=bc, business_date=date,
            open_counter=1, settlement_id=str(uuid.uuid4()), settled_at="t", recorded_at="t", cutoff=get_app_time(),
            missing_count=bc % 2,
        )
        await repo.save_provisional_async(record, {"sales": {"x": 1}})
        if final:
            await repo.finalize_async(STORE, terminal_no, bc, record.settlement_id, "t")
    yield
    await collection.delete_many({"store_code": STORE})
    await db[settings.DB_COLLECTION_NAME_SETTLEMENT_DAILY_REPORT].delete_many({"store_code": STORE})


def _url(query=""):
    return f"/api/v1/tenants/{_tenant()}/stores/{STORE}/settlements{query}"


@pytest.mark.asyncio
async def test_listed_by_date_terminal_and_session_without_reports(http_client, admin_header):
    response = await http_client.get(_url(), headers=admin_header)

    assert response.status_code == 200, response.text
    body = response.json()
    rows = body["data"]
    assert [(r["businessDate"], r["terminalNo"], r["businessCounter"]) for r in rows] == [
        ("20261123", 1, 4), ("20261124", 1, 5), ("20261124", 2, 8),
    ]
    assert body["metadata"]["total"] == 3
    assert "dailyReports" not in rows[0] and "cutoff" not in rows[0]
    assert {r["state"] for r in rows} == {"provisional", "final"}


@pytest.mark.asyncio
async def test_filters_and_paging(http_client, admin_header):
    by_terminal = (await http_client.get(_url("?terminal_no=1"), headers=admin_header)).json()["data"]
    assert [r["businessCounter"] for r in by_terminal] == [4, 5]
    by_range = (await http_client.get(_url("?business_date_from=20261124&business_date_to=20261124"), headers=admin_header)).json()["data"]
    assert len(by_range) == 2
    finals = (await http_client.get(_url("?state=final"), headers=admin_header)).json()["data"]
    assert {r["businessCounter"] for r in finals} == {4, 8}
    page2 = (await http_client.get(_url("?limit=2&page=2"), headers=admin_header)).json()
    assert [r["businessCounter"] for r in page2["data"]] == [8]
    assert page2["metadata"]["total"] == 3


@pytest.mark.asyncio
async def test_half_range_is_400(http_client, admin_header):
    response = await http_client.get(_url("?business_date_from=20261124"), headers=admin_header)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_a_terminal_api_key_is_refused(http_client):
    response = await http_client.get(_url(), headers={"X-API-KEY": "anything"})
    assert response.status_code in (401, 403)
