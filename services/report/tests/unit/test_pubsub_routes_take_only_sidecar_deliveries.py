# Copyright 2026 masa@kugel
"""The pub/sub routes take only what this service's Dapr sidecar delivers (issue #134).

They carry no JWT and pick the tenant database from the event body, so before
this anyone who could reach the app port could write into any tenant.
"""

import os
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from kugel_common.utils.dapr_app_token import DAPR_APP_TOKEN_HEADER

from tests.unit.test_api_tran import make_app

ROUTES = ["/api/v1/tranlog", "/api/v1/cashlog", "/api/v1/opencloselog"]

FORGED = {
    "event_id": "evt-forged",
    "tenant_id": "T-ANY",
    "store_code": "S1",
    "terminal_no": 1,
    "transaction_no": 1,
}


def _logged_writes(log_service) -> list:
    return [
        log_service.receive_tranlog_async.await_args_list,
        log_service.receive_cashlog_async.await_args_list,
        log_service.receive_open_close_log_async.await_args_list,
    ]


async def _post(app, route, headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(route, json={"data": FORGED}, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    "headers",
    [{}, {DAPR_APP_TOKEN_HEADER: "a-token-someone-guessed"}, {"Authorization": "Bearer anything"}],
    ids=["no token", "wrong token", "a bearer token instead"],
)
async def test_a_request_not_from_the_sidecar_is_refused_and_writes_nothing(route, headers):
    log_service = AsyncMock()
    app = make_app(log_service)

    response = await _post(app, route, headers)

    assert response.status_code == 401
    assert _logged_writes(log_service) == [[], [], []]


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ROUTES)
async def test_a_delivery_carrying_the_token_reaches_the_handler(route):
    app = make_app(AsyncMock())

    response = await _post(app, route, {DAPR_APP_TOKEN_HEADER: os.environ["APP_API_TOKEN"]})

    assert response.status_code != 401
