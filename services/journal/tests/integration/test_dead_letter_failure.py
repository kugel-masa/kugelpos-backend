# Copyright 2026 masa@kugel
"""Journal gives up on a transaction, records it, and the replay stores it once (#230).

Through the real app and a real MongoDB: the transaction keeps failing until the
subscriber gives up, the route acknowledges and the record turns pending, and a
redelivery while the cause is still there is acknowledged at once. Once fixed,
the replay through the dead-letter API stores the transaction and its journal
once, publishes nothing, and a second replay is refused.
"""

import os
import uuid
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
from app.services.log_service import LogService

from .test_concurrent_tranlog_delivery import _tranlog

GIVE_UP = 3
DELIVERY = {DAPR_APP_TOKEN_HEADER: os.environ.get("APP_API_TOKEN", "")}


def _tenant() -> str:
    return os.environ.get("TENANT_ID")


async def _db():
    return await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{_tenant()}")


@pytest_asyncio.fixture
async def state_store():
    """Dapr's state store as memory, Slack and the delivery status replaced."""
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
    db = await _db()
    await db[COLLECTION].delete_many({})


@pytest.fixture
def user_header():
    payload = {"sub": "operator", "tenant_id": _tenant(), "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, common_settings.SECRET_KEY, algorithm=common_settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_a_failing_transaction_is_given_up_and_replayed_once(http_client, state_store, user_header):
    tran = _tranlog(_tenant(), 23090 + uuid.uuid4().int % 900).model_dump(mode="json")
    event_id = f"journal-dl-{uuid.uuid4().hex[:8]}"
    tran["event_id"] = event_id
    event = {"id": "cloud-1", "topic": "topic-tranlog", "data": tran}
    db = await _db()

    with patch.object(LogService, "receive_tranlog_async", side_effect=RuntimeError("mongo blip")):
        answers = [
            (await http_client.post("/api/v1/tranlog", json=event, headers=DELIVERY)).json()["status"]
            for _ in range(GIVE_UP)
        ]
        late = await http_client.post("/api/v1/tranlog", json=event, headers=DELIVERY)

    assert answers == ["RETRY"] * (GIVE_UP - 1) + ["SUCCESS"]
    assert late.json()["status"] == "SUCCESS"
    record = await db[COLLECTION].find_one({"_id": event_id})
    assert record["state"] == STATE_PENDING and record["service"] == "journal"
    assert record["episode_failure_count"] == GIVE_UP and record["failure_count"] == GIVE_UP + 1
    assert record["summary"]["transaction_no"] == tran["transaction_no"]
    assert await db[settings.DB_COLLECTION_NAME_TRAN].count_documents({"cart_id": tran["cart_id"]}) == 0

    with patch("kugel_common.utils.dapr_client_helper.DaprClientHelper.publish_event") as publish:
        replayed = await http_client.post(
            f"/api/v1/tenants/{_tenant()}/dead-letters/{event_id}/replay", headers=user_header
        )

    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["data"]["outcome"] == "replayed"
    publish.assert_not_called()
    assert (await db[COLLECTION].find_one({"_id": event_id}))["state"] == STATE_REPLAYED
    assert await db[settings.DB_COLLECTION_NAME_TRAN].count_documents({"cart_id": tran["cart_id"]}) == 1
    journals = await db[settings.DB_COLLECTION_NAME_JOURNAL].count_documents(
        {"terminal_no": tran["terminal_no"], "transaction_no": tran["transaction_no"], "business_date": "20260101"}
    )
    assert journals == 1

    again = await http_client.post(f"/api/v1/tenants/{_tenant()}/dead-letters/{event_id}/replay", headers=user_header)
    assert again.status_code == 409
    assert again.json()["userError"]["code"] == "411007"
