# Copyright 2026 masa@kugel
"""A close log whose settlement cannot be made final is delivered again (#343, R-6).

Through the real pub/sub route: the first delivery fails to finalize, so Dapr is
told RETRY and the settlement stays provisional; the redelivery stores nothing
twice and makes it final.
"""

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from kugel_common.database import database as db_helper
from kugel_common.utils.dapr_app_token import DAPR_APP_TOKEN_HEADER

from app.config.settings import settings
from app.database import database_setup
from app.dependencies.get_settlement_service import get_settlement_service_async
from app.models.documents.settlement_record_document import STATE_FINAL, STATE_PROVISIONAL
from app.models.repositories.settlement_record_repository import SettlementRecordRepository
from app.services.settlement_service import SettlementRequest

STORE = "S343DLV"
TERMINAL = 5
BC = 31
DATE = "20261124"
DELIVERY = {DAPR_APP_TOKEN_HEADER: os.environ.get("APP_API_TOKEN", "")}


def _tenant() -> str:
    return os.environ.get("TENANT_ID")


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
            "log_open_close",
        ):
            await db[name].delete_many({"store_code": STORE})

    await wipe()
    # Dapr's state store as memory: the idempotency check runs for real. The
    # delivery status sent back to terminal is not under test here.
    processed: dict = {}

    async def get_state(state_id):
        return processed.get(state_id), None

    async def save_state(state_id, data):
        processed[state_id] = data
        return True, None

    with (
        patch("app.api.v1.tran.state_store_manager.get_state", side_effect=get_state),
        patch("app.api.v1.tran.state_store_manager.save_state", side_effect=save_state),
        patch("app.api.v1.tran._notify_pubsub_status", new_callable=AsyncMock),
    ):
        yield
    await wipe()


def _close_event(settlement_id: str) -> dict:
    return {
        "data": {
            "event_id": str(uuid.uuid4()),
            "tenant_id": _tenant(),
            "store_code": STORE,
            "terminal_no": TERMINAL,
            "business_date": DATE,
            "business_counter": BC,
            "open_counter": 1,
            "operation": "close",
            "generate_date_time": f"{DATE}T21:00:00",
            "settlement_id": settlement_id,
        }
    }


@pytest.mark.asyncio
async def test_a_failed_finalize_is_retried_and_the_redelivery_makes_it_final(http_client):
    service = await get_settlement_service_async(_tenant())
    with patch.object(service, "_names_async", return_value={"category_names": {}, "payment_names": ({}, {})}):
        record, _ = await service.confirm_async(
            SettlementRequest(store_code=STORE, terminal_no=TERMINAL, business_counter=BC, business_date=DATE,
                              open_counter=1, settled_at="t")
        )
    event = _close_event(record.settlement_id)
    repo = SettlementRecordRepository(await _db(), _tenant())

    with patch.object(SettlementRecordRepository, "finalize_async", side_effect=RuntimeError("mongo blip")):
        first = await http_client.post("/api/v1/opencloselog", json=event, headers=DELIVERY)

    assert first.status_code == 500, first.text
    assert first.json()["status"] == "RETRY"
    assert (await repo.get_async(STORE, TERMINAL, BC)).state == STATE_PROVISIONAL

    again = await http_client.post("/api/v1/opencloselog", json=event, headers=DELIVERY)

    assert again.status_code == 200, again.text
    stored = await repo.get_async(STORE, TERMINAL, BC)
    assert stored.state == STATE_FINAL and stored.settlement_id == record.settlement_id
    db = await _db()
    assert await db["log_open_close"].count_documents({"store_code": STORE, "operation": "close"}) == 1


@pytest.mark.asyncio
async def test_a_redelivered_close_log_after_final_changes_nothing(http_client):
    service = await get_settlement_service_async(_tenant())
    with patch.object(service, "_names_async", return_value={"category_names": {}, "payment_names": ({}, {})}):
        record, _ = await service.confirm_async(
            SettlementRequest(store_code=STORE, terminal_no=TERMINAL, business_counter=BC, business_date=DATE,
                              open_counter=1, settled_at="t")
        )
    event = _close_event(record.settlement_id)
    assert (await http_client.post("/api/v1/opencloselog", json=event, headers=DELIVERY)).status_code == 200
    repo = SettlementRecordRepository(await _db(), _tenant())
    finalized_at = (await repo.get_async(STORE, TERMINAL, BC)).finalized_at

    again = await http_client.post("/api/v1/opencloselog", json=event, headers=DELIVERY)

    assert again.status_code == 200, again.text
    stored = await repo.get_async(STORE, TERMINAL, BC)
    assert stored.state == STATE_FINAL and stored.finalized_at == finalized_at
