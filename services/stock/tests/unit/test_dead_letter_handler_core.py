"""The handler core and the subscription route of stock, apart (#230, R-3)."""
import os
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import stock
from kugel_common.dead_letter.outcome import HandlerOutcome, OutcomeKind
from kugel_common.utils.dapr_app_token import DAPR_APP_TOKEN_HEADER

DAPR = {DAPR_APP_TOKEN_HEADER: os.environ["APP_API_TOKEN"]}
TRAN = {"event_id": "evt-1", "tenant_id": "T1", "store_code": "S1", "terminal_no": 1, "line_items": []}


def environment(stack, seen=None, fails=None):
    service = AsyncMock()
    if fails:
        service.process_transaction_async.side_effect = fails
    stack.enter_context(patch.object(stock.state_store_manager, "get_state", new_callable=AsyncMock, return_value=(seen, None)))
    saved = stack.enter_context(
        patch.object(stock.state_store_manager, "save_state", new_callable=AsyncMock, return_value=(True, None))
    )
    stack.enter_context(patch("app.api.v1.stock.StockService", return_value=service))
    stack.enter_context(patch("kugel_common.database.database.get_db_async", new_callable=AsyncMock))
    stack.enter_context(patch("app.dependencies.get_alert_service.get_alert_service", return_value=None))
    notify = stack.enter_context(patch.object(stock, "_notify_pubsub_status", new_callable=AsyncMock))
    return service, saved, notify


@pytest.mark.asyncio
async def test_the_core_processes_without_telling_anyone():
    with ExitStack() as stack:
        service, saved, notify = environment(stack)
        outcome = await stock.process_transaction_event({"data": TRAN})
    assert outcome.kind is OutcomeKind.PROCESSED
    service.process_transaction_async.assert_awaited_once()
    saved.assert_awaited_once()
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_core_reports_a_failure_as_a_failure():
    with ExitStack() as stack:
        service, saved, notify = environment(stack, fails=RuntimeError("db down"))
        outcome = await stock.process_transaction_event({"data": TRAN})
    assert outcome.kind is OutcomeKind.FAILED and isinstance(outcome.error, RuntimeError)
    saved.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_core_reports_an_already_processed_event():
    with ExitStack() as stack:
        service, _, _ = environment(stack, seen={"event_id": "evt-1"})
        outcome = await stock.process_transaction_event({"data": TRAN})
    assert outcome.kind is OutcomeKind.ALREADY_PROCESSED
    service.process_transaction_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_core_drops_an_event_without_a_tenant():
    outcome = await stock.process_transaction_event({"data": {"event_id": "evt-1"}})
    assert outcome.kind is OutcomeKind.DROPPED


def app():
    app = FastAPI()
    app.include_router(stock.router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
@pytest.mark.dead_letter_writes
@pytest.mark.parametrize("acknowledged, status_code, dapr_status", [(True, 200, "SUCCESS"), (False, 500, "RETRY")])
async def test_the_route_acknowledges_a_failure_only_once_it_is_recorded(acknowledged, status_code, dapr_status):
    with ExitStack() as stack:
        environment(stack, fails=RuntimeError("db down"))
        record = stack.enter_context(
            patch.object(stock, "_record_failure", new_callable=AsyncMock, return_value=acknowledged)
        )
        async with AsyncClient(transport=ASGITransport(app=app()), base_url="http://t") as c:
            resp = await c.post("/api/v1/tranlog", headers=DAPR, json={"data": TRAN})
    assert resp.status_code == status_code and resp.json()["status"] == dapr_status
    record.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_route_still_drops_an_event_without_a_tenant():
    async with AsyncClient(transport=ASGITransport(app=app()), base_url="http://t") as c:
        resp = await c.post("/api/v1/tranlog", headers=DAPR, json={"data": {"event_id": "evt-1"}})
    assert resp.status_code == 200 and resp.json()["status"] == "DROP"


@pytest.mark.asyncio
async def test_the_route_does_not_log_the_transaction_content(caplog):
    with ExitStack() as stack:
        environment(stack)
        async with AsyncClient(transport=ASGITransport(app=app()), base_url="http://t") as c:
            await c.post(
                "/api/v1/tranlog", headers=DAPR, json={"data": {**TRAN, "customer": {"api_key": "secret-key"}}}
            )
    assert "secret-key" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.dead_letter_writes
async def test_a_failure_is_counted_for_stock():
    from kugel_common.dead_letter.failure import FailureDecision

    error = RuntimeError("x")
    with patch("kugel_common.database.database.get_db_async", new_callable=AsyncMock, return_value="db"), patch.object(
        stock, "record_failure", new_callable=AsyncMock, return_value=FailureDecision.ALREADY_RECORDED
    ) as record:
        assert await stock._record_failure({"data": TRAN}, "topic-tranlog", HandlerOutcome.failed(error)) is True
    assert record.await_args.kwargs["service"] == "stock" and record.await_args.kwargs["error"] is error
