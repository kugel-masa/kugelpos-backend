"""The delivery-status notification cannot fail a stored log (issue #230).

The notification to cart / terminal only moves the publisher's delivery status.
It used to run before the idempotency state was saved, and its failure failed the
event. While the publisher was unreachable every stored log was redelivered, and
with requeueing on, the subscription stalled on them.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import tran
from tests.unit.test_api_tran import make_app

TRANLOG = {
    "event_id": "evt-230",
    "tenant_id": "test-tenant",
    "store_code": "STORE01",
    "terminal_no": 1,
    "transaction_no": 100,
    "transaction_type": 101,
    "business_date": "20260101",
    "open_counter": 1,
    "business_counter": 1,
    "generate_date_time": "20260101T120000",
    "receipt_no": 1,
}


async def _post(app, data, url="/api/v1/tranlog"):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(url, json={"data": data})


def _state(seen=None):
    return (
        patch.object(tran.state_store_manager, "get_state", new_callable=AsyncMock, return_value=(seen, None)),
        patch.object(tran.state_store_manager, "save_state", new_callable=AsyncMock, return_value=(True, None)),
    )


@pytest.mark.asyncio
async def test_a_stored_log_succeeds_when_the_notification_fails():
    service = AsyncMock()
    calls = []
    get_state, save_state = _state()
    with get_state, save_state as save_mock, patch.object(tran, "_notify_pubsub_status", new_callable=AsyncMock) as notify:
        save_mock.side_effect = lambda *a, **k: calls.append("save_state") or (True, None)
        notify.side_effect = lambda *a, **k: calls.append("notify") or (_ for _ in ()).throw(RuntimeError("cart down"))
        resp = await _post(make_app(mock_log_service=service), TRANLOG)

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "SUCCESS"
    # Saved first: a redelivery of a stored log stops at the state-store check.
    assert calls == ["save_state", "notify"]


@pytest.mark.asyncio
async def test_a_redelivery_of_a_processed_log_resends_the_notification_without_a_message():
    service = AsyncMock()
    get_state, save_state = _state(seen={"event_id": "evt-230"})
    with get_state, save_state, patch.object(tran, "_notify_pubsub_status", new_callable=AsyncMock) as notify:
        resp = await _post(make_app(mock_log_service=service), TRANLOG)

    assert resp.status_code == 200, resp.text
    service.receive_tranlog_async.assert_not_awaited()
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["status"] == "received"
    # Left out, so the publisher keeps the message it holds for this service.
    assert notify.await_args.kwargs["message"] is None


@pytest.mark.asyncio
async def test_a_duplicate_at_the_db_layer_resends_the_notification():
    from kugel_common.exceptions import DuplicateKeyException

    service = AsyncMock()
    service.receive_tranlog_async.side_effect = DuplicateKeyException(
        message="duplicate", collection_name="log_tran", key={}
    )
    get_state, save_state = _state()
    with get_state, save_state, patch.object(tran, "_notify_pubsub_status", new_callable=AsyncMock) as notify:
        resp = await _post(make_app(mock_log_service=service), TRANLOG)

    assert resp.status_code == 200, resp.text
    assert notify.await_args.kwargs["status"] == "received"


@pytest.mark.asyncio
async def test_a_failure_is_retried_even_when_its_notification_fails():
    service = AsyncMock()
    service.receive_tranlog_async.side_effect = RuntimeError("db down")
    get_state, save_state = _state()
    with get_state, save_state as save_mock, patch.object(
        tran, "_notify_pubsub_status", new_callable=AsyncMock, side_effect=RuntimeError("cart down")
    ):
        resp = await _post(make_app(mock_log_service=service), TRANLOG)

    # The answer Dapr reads, not an unhandled error from the notification.
    assert resp.status_code == 500, resp.text
    assert resp.json()["status"] == "RETRY"
    save_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_log_that_does_not_match_the_schema_is_dropped():
    service = AsyncMock()
    get_state, save_state = _state()
    with get_state, save_state, patch.object(tran, "_notify_pubsub_status", new_callable=AsyncMock) as notify:
        resp = await _post(make_app(mock_log_service=service), {**TRANLOG, "terminal_no": "secret-value"})

    # Every delivery would fail the same way: dropped, not retried into the DLQ.
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "DROP"
    service.receive_tranlog_async.assert_not_awaited()
    assert notify.await_args.kwargs["status"] == "failed"
    assert "terminal_no" in notify.await_args.kwargs["message"]
    assert "secret-value" not in notify.await_args.kwargs["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "notify,data,service_name",
    [
        (tran._notify_pubsub_status_tranlog_async, TRANLOG, "cart"),
        (tran._notify_pubsub_status_terminallog_async, TRANLOG, "terminal"),
    ],
)
@pytest.mark.parametrize("message,expected", [(None, None), ("", ""), ("why", "why")])
async def test_the_message_is_sent_only_when_given(notify, data, service_name, message, expected):
    client = MagicMock()
    client.post = AsyncMock()

    @asynccontextmanager
    async def fake_client(service_name):
        yield client

    with patch.object(tran, "get_service_client", fake_client):
        await notify(data, "received", message)

    payload = client.post.await_args.kwargs["json"]
    if expected is None:
        assert "message" not in payload
    else:
        assert payload["message"] == expected
