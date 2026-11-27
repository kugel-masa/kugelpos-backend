# Copyright 2026 masa@kugel
"""Replaying a sale of a settled session leaves the settlement alone (#230 US2-6, #343).

Through the real app: a late sale of a session that is already settled keeps
failing until the subscriber gives up and records it; the cause is fixed and
the sale is replayed through the dead-letter API. The sale is stored, but the
final settlement record and the frozen daily reports stay as they were: the
daily report counts the sale as missing, the flash report shows it.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt
import pytest
import pytest_asyncio

from kugel_common.config.settings import settings as common_settings
from kugel_common.database import database as db_helper
from kugel_common.dead_letter import failure
from kugel_common.dead_letter.document import COLLECTION, STATE_PENDING, STATE_REPLAYED
from kugel_common.utils.dapr_app_token import DAPR_APP_TOKEN_HEADER

from app.config.settings import settings
from app.database import database_setup
from app.models.documents.settlement_record_document import STATE_FINAL
from app.models.repositories.settlement_record_repository import SettlementRecordRepository
from app.services.log_service import LogService

from .test_daily_from_settlement import STORE, TENANT, _open, _sale, _service, _settle, _terminal_daily

GIVE_UP = 3
DELIVERY = {DAPR_APP_TOKEN_HEADER: os.environ.get("APP_API_TOKEN", "")}


@pytest_asyncio.fixture
async def db():
    database = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{TENANT}")
    await database.client.drop_database(database.name)
    await database_setup.execute(TENANT)
    yield database
    await database.client.drop_database(database.name)


@pytest.fixture
def state_store():
    """Dapr's state store as memory: the idempotency check runs for real."""
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
        patch("kugel_common.dead_letter.alerts.send", new_callable=AsyncMock, return_value=True),
        patch.object(failure, "give_up_after_failures", lambda: GIVE_UP),
    ):
        yield processed


@pytest.fixture
def user_header():
    payload = {"sub": "operator", "tenant_id": TENANT, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, common_settings.SECRET_KEY, algorithm=common_settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


async def _frozen(db) -> tuple[list[dict], list[dict]]:
    records = await db[settings.DB_COLLECTION_NAME_SETTLEMENT_RECORD].find({}, {"_id": 0}).to_list(None)
    reports = await db[settings.DB_COLLECTION_NAME_SETTLEMENT_DAILY_REPORT].find({}, {"_id": 0}).to_list(None)
    return records, reports


@pytest.mark.asyncio
async def test_replaying_a_late_sale_of_a_settled_session_keeps_the_settlement(
    db, state_store, http_client, user_header
):
    await _open(db, 1, 5)
    await _service(db).tran_repository.create_tranlog_async(_sale(1, 5, 1))
    await _settle(db, 1, 5, seq=2)
    frozen_before = await _frozen(db)
    daily_before = await _terminal_daily(db, 1)
    assert daily_before.sales_gross.amount == 1100

    late = _sale(1, 5, 2, amount=5000).model_dump(mode="json")
    late["event_id"] = "late-sale-1"
    event = {"id": "cloud-1", "topic": "topic-tranlog", "data": late}

    # The late sale keeps failing until the subscriber gives up and records it
    with patch.object(LogService, "receive_tranlog_async", side_effect=RuntimeError("mongo blip")):
        answers = [
            (await http_client.post("/api/v1/tranlog", json=event, headers=DELIVERY)).json()["status"]
            for _ in range(GIVE_UP)
        ]
    assert answers == ["RETRY"] * (GIVE_UP - 1) + ["SUCCESS"]
    record = await db[COLLECTION].find_one({"_id": "late-sale-1"})
    assert record["state"] == STATE_PENDING and record["topic"] == "topic-tranlog"

    # The cause is fixed; the operator replays it
    replayed = await http_client.post(
        f"/api/v1/tenants/{TENANT}/dead-letters/late-sale-1/replay", headers=user_header
    )

    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["data"]["outcome"] == "replayed"
    assert (await db[COLLECTION].find_one({"_id": "late-sale-1"}))["state"] == STATE_REPLAYED
    assert "late-sale-1" in state_store
    # The sale is stored once ...
    assert await db[settings.DB_COLLECTION_NAME_TRAN].count_documents({"store_code": STORE}) == 2
    # ... but the settlement and its frozen reports are untouched
    assert await _frozen(db) == frozen_before
    settled = await SettlementRecordRepository(db, TENANT).get_async(STORE, 1, 5)
    assert settled.state == STATE_FINAL
    daily_after = await _terminal_daily(db, 1)
    assert daily_after.sales_gross.amount == 1100
    assert daily_after.missing_count == 1
    flash = await _service(db).get_report_for_terminal_async(
        store_code=STORE, terminal_no=1, report_scope="flash", report_type="sales", business_date="20261124",
        limit=100, page=1,
    )
    assert flash.sales_gross.amount == 6600

    # A second replay is refused: the record is no longer pending
    again = await http_client.post(f"/api/v1/tenants/{TENANT}/dead-letters/late-sale-1/replay", headers=user_header)
    assert again.status_code == 409
    assert again.json()["userError"]["code"] == "413009"
