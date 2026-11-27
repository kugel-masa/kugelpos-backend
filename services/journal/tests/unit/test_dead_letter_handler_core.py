"""The handler core and the subscription route, apart (#230, R-3).

The core says what happened and nothing else; the route answers Dapr, tells the
publisher, and counts failures toward giving up. A replay uses the same core, so
a failure during a replay must come back as a failure, never as a success.
"""
import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import tran
from kugel_common.dead_letter.outcome import OutcomeKind
from kugel_common.utils.dapr_app_token import DAPR_APP_TOKEN_HEADER
from fastapi import FastAPI

from app.api.v1.tran import get_log_service_from_request

DAPR = {DAPR_APP_TOKEN_HEADER: os.environ["APP_API_TOKEN"]}


def make_app(mock_log_service):
    app = FastAPI()
    app.include_router(tran.router, prefix="/api/v1")
    app.dependency_overrides[get_log_service_from_request] = lambda: mock_log_service
    return app

CASHLOG = {"event_id": "evt-1", "tenant_id": "T1", "store_code": "S1", "terminal_no": 1}


def state(seen=None):
    return (
        patch.object(tran.state_store_manager, "get_state", new_callable=AsyncMock, return_value=(seen, None)),
        patch.object(tran.state_store_manager, "save_state", new_callable=AsyncMock, return_value=(True, None)),
    )


@pytest.mark.asyncio
async def test_the_core_processes_without_telling_anyone():
    service = AsyncMock()
    get_state, save_state = state()
    with get_state, save_state as saved, patch.object(tran, "_notify_pubsub_status", new_callable=AsyncMock) as notify, patch.object(
        tran, "record_failure", new_callable=AsyncMock
    ) as record:
        outcome = await tran.process_log_event({"data": CASHLOG}, "topic-cashlog", service)
    assert outcome.kind is OutcomeKind.PROCESSED
    service.receive_cashlog_async.assert_awaited_once()
    saved.assert_awaited_once()
    notify.assert_not_awaited()
    record.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_core_reports_a_failure_as_a_failure():
    service = AsyncMock()
    service.receive_cashlog_async.side_effect = RuntimeError("db down")
    get_state, save_state = state()
    with get_state, save_state as saved, patch.object(tran, "record_failure", new_callable=AsyncMock) as record:
        outcome = await tran.process_log_event({"data": CASHLOG}, "topic-cashlog", service)
    assert outcome.kind is OutcomeKind.FAILED
    assert isinstance(outcome.error, RuntimeError)
    saved.assert_not_awaited()
    record.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_core_reports_an_already_processed_event():
    service = AsyncMock()
    get_state, save_state = state(seen={"event_id": "evt-1"})
    with get_state, save_state:
        outcome = await tran.process_log_event({"data": CASHLOG}, "topic-cashlog", service)
    assert outcome.kind is OutcomeKind.ALREADY_PROCESSED
    service.receive_cashlog_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_core_drops_a_log_that_does_not_match_its_schema_naming_fields_only():
    get_state, save_state = state()
    with get_state, save_state:
        outcome = await tran.process_log_event(
            {"data": {**CASHLOG, "terminal_no": "secret-not-a-number"}}, "topic-cashlog", AsyncMock()
        )
    assert outcome.kind is OutcomeKind.DROPPED
    assert "terminal_no" in outcome.reason and "secret" not in outcome.reason


@pytest.mark.asyncio
async def test_the_core_builds_the_log_service_for_a_replay():
    service = AsyncMock()
    get_state, save_state = state()
    with get_state, save_state, patch.object(tran, "get_log_service", new_callable=AsyncMock, return_value=service) as build:
        outcome = await tran.process_log_event({"data": CASHLOG}, "topic-cashlog")
    assert outcome.kind is OutcomeKind.PROCESSED
    build.assert_awaited_once_with(tenant_id="T1")


@pytest.mark.asyncio
@pytest.mark.dead_letter_writes
@pytest.mark.parametrize("acknowledged, status_code, dapr_status", [(True, 200, "SUCCESS"), (False, 500, "RETRY")])
async def test_the_route_acknowledges_a_failure_only_once_it_is_recorded(acknowledged, status_code, dapr_status):
    service = AsyncMock()
    service.receive_cashlog_async.side_effect = RuntimeError("db down")
    get_state, save_state = state()
    with get_state, save_state, patch.object(tran, "_notify_pubsub_status", new_callable=AsyncMock) as notify, patch.object(
        tran, "_record_failure", new_callable=AsyncMock, return_value=acknowledged
    ) as record:
        async with AsyncClient(transport=ASGITransport(app=make_app(mock_log_service=service)), base_url="http://t") as c:
            resp = await c.post("/api/v1/cashlog", headers=DAPR, json={"data": CASHLOG})
    assert resp.status_code == status_code and resp.json()["status"] == dapr_status
    record.assert_awaited_once()
    assert record.await_args.args[1] == "topic-cashlog"
    # The publisher still hears of the failure, as before
    assert notify.await_args.kwargs["status"] == "failed"


@pytest.mark.asyncio
@pytest.mark.dead_letter_writes
async def test_a_failure_is_counted_with_the_tenant_database_and_the_exception():
    from kugel_common.dead_letter.failure import FailureDecision
    from kugel_common.dead_letter.outcome import HandlerOutcome

    error = RuntimeError("x")
    with patch.object(tran.db_helper, "get_db_async", new_callable=AsyncMock, return_value="db") as get_db, patch.object(
        tran, "record_failure", new_callable=AsyncMock, return_value=FailureDecision.GAVE_UP
    ) as record:
        assert await tran._record_failure({"data": CASHLOG}, "topic-cashlog", HandlerOutcome.failed(error)) is True
    get_db.assert_awaited_once_with(f"{tran.settings.DB_NAME_PREFIX}_T1")
    assert record.await_args.kwargs == {
        "db": "db", "service": "journal", "topic": "topic-cashlog", "message": {"data": CASHLOG}, "error": error,
    }


@pytest.mark.asyncio
@pytest.mark.dead_letter_writes
async def test_an_unrecordable_failure_asks_for_redelivery():
    from kugel_common.dead_letter.failure import DeadLetterUnrecordable
    from kugel_common.dead_letter.outcome import HandlerOutcome

    with patch.object(tran.db_helper, "get_db_async", new_callable=AsyncMock), patch.object(
        tran, "record_failure", new_callable=AsyncMock, side_effect=DeadLetterUnrecordable("down")
    ):
        assert await tran._record_failure({"data": CASHLOG}, "topic-cashlog", HandlerOutcome.failed("x")) is False


@pytest.mark.asyncio
async def test_an_event_without_a_tenant_is_announced_and_refused():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(tran.router, prefix="/api/v1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/cashlog", headers=DAPR, json={"data": {"event_id": "evt-9"}})
    assert resp.status_code == 400
    tran.notify_unrecordable.assert_awaited_once()
    kwargs = tran.notify_unrecordable.await_args.kwargs
    assert kwargs["topic"] == "topic-cashlog" and kwargs["event_id"] == "evt-9" and kwargs["tenant_id"] is None


@pytest.mark.asyncio
async def test_a_replayed_event_tells_the_publisher_it_is_stored():
    with patch.object(tran, "_notify_pubsub_status", new_callable=AsyncMock) as notify:
        await tran.notify_processed({"data": CASHLOG}, "topic-cashlog")
    assert notify.await_args.kwargs["status"] == "received"
    assert notify.await_args.kwargs["log_type"] == "cashlog"
