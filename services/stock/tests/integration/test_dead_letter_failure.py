# Copyright 2026 masa@kugel
"""Stock gives up on a transaction, records it, and the replay moves stock once (#230).

Through the real app and a real MongoDB: the first delivery applies one item
and fails on the next, later deliveries fail outright, and on the give-up
delivery the route acknowledges and the record turns pending. The cause is
fixed and the transaction is replayed through the dead-letter API: every item
ends at its quantity once, nothing is published to the topic again (other
subscribers are not reached), and a second replay is refused (FR-009, FR-010,
SC-004).
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
from app.services.stock_service import StockService

GIVE_UP = 3
DELIVERY = {DAPR_APP_TOKEN_HEADER: os.environ.get("APP_API_TOKEN", "")}


def _tenant() -> str:
    return os.environ.get("TENANT_ID")


async def _db():
    return await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{_tenant()}")


@pytest_asyncio.fixture
async def state_store():
    """Dapr's state store as memory, Slack and the cart notice replaced."""
    processed: dict = {}

    async def get_state(state_id):
        return processed.get(state_id), None

    async def save_state(state_id, data):
        processed[state_id] = data
        return True, None

    with (
        patch("app.api.v1.stock.state_store_manager.get_state", side_effect=get_state),
        patch("app.api.v1.stock.state_store_manager.save_state", side_effect=save_state),
        patch("app.api.v1.stock._notify_pubsub_status", new_callable=AsyncMock),
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


def _event(store_code: str, items: list[tuple[str, int]]) -> dict:
    event_id = f"stock-dl-{uuid.uuid4().hex[:8]}"
    return {
        "id": "cloud-1",
        "topic": "topic-tranlog",
        "data": {
            "event_id": event_id,
            "tenant_id": _tenant(),
            "store_code": store_code,
            "terminal_no": 1,
            "transaction_no": 7,
            "cart_id": f"cart-{uuid.uuid4()}",
            "transaction_type": 101,
            "sales": {"is_cancelled": False},
            "line_items": [
                {"item_code": item_code, "quantity": quantity, "is_cancelled": False}
                for item_code, quantity in items
            ],
        },
    }


async def _quantities(store_code: str, items: list[str]) -> list[float]:
    service = StockService(await _db())
    result = []
    for item in items:
        stock = await service.get_stock_async(_tenant(), store_code, item)
        result.append(stock.current_quantity if stock else 0)
    return result


@pytest.mark.asyncio
async def test_a_partly_applied_transaction_is_given_up_and_replayed_once(
    http_client, state_store, user_header, mock_dapr_sidecar, test_store_code
):
    items = [f"DL-{n}-{uuid.uuid4().hex[:6]}" for n in range(3)]
    event = _event(test_store_code, [(items[0], 1), (items[1], 2), (items[2], 3)])
    event_id = event["data"]["event_id"]

    original = StockService.update_stock_async
    calls = 0

    async def fail_from_the_second_item(self, **kwargs):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise RuntimeError("database went away")
        return await original(self, **kwargs)

    with patch.object(StockService, "update_stock_async", fail_from_the_second_item):
        answers = [
            (await http_client.post("/api/v1/tranlog", json=event, headers=DELIVERY)).json()["status"]
            for _ in range(GIVE_UP)
        ]
        # A redelivery after the give-up, with the cause still there, is
        # acknowledged at once
        late = await http_client.post("/api/v1/tranlog", json=event, headers=DELIVERY)

    assert answers == ["RETRY"] * (GIVE_UP - 1) + ["SUCCESS"]
    assert late.json()["status"] == "SUCCESS"
    assert await _quantities(test_store_code, items) == [-1, 0, 0]
    db = await _db()
    record = await db[COLLECTION].find_one({"_id": event_id})
    assert record["state"] == STATE_PENDING and record["service"] == "stock"
    assert record["episode_failure_count"] == GIVE_UP and record["failure_count"] == GIVE_UP + 1
    assert record["last_error"] == "RuntimeError"

    published_before = [c for c in mock_dapr_sidecar.calls if "/v1.0/publish/" in str(c.request.url)]
    replayed = await http_client.post(
        f"/api/v1/tenants/{_tenant()}/dead-letters/{event_id}/replay", headers=user_header
    )

    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["data"]["outcome"] == "replayed"
    # Every item once: the first is not applied a second time
    assert await _quantities(test_store_code, items) == [-1, -2, -3]
    assert (await db[COLLECTION].find_one({"_id": event_id}))["state"] == STATE_REPLAYED
    assert event_id in state_store
    # The replay calls stock's own handler; nothing goes back to the topic
    published_after = [c for c in mock_dapr_sidecar.calls if "/v1.0/publish/" in str(c.request.url)]
    assert published_after == published_before

    again = await http_client.post(f"/api/v1/tenants/{_tenant()}/dead-letters/{event_id}/replay", headers=user_header)
    assert again.status_code == 409
    assert again.json()["userError"]["code"] == "414404"
    # A redelivery of the replayed event stops at the state store
    assert (await http_client.post("/api/v1/tranlog", json=event, headers=DELIVERY)).json()["status"] == "SUCCESS"
    assert await _quantities(test_store_code, items) == [-1, -2, -3]
