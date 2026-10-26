# Copyright 2026 masa@kugel
"""The pub/sub route takes only what this service's Dapr sidecar delivers (issue #134).

It carries no JWT and picks the tenant database from the event body, so before
this anyone who could reach the app port could move any tenant's stock.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from kugel_common.utils.dapr_app_token import DAPR_APP_TOKEN_HEADER

from tests.unit.test_api_stock import _make_app

FORGED = {"event_id": "evt-forged", "tenant_id": "T-ANY", "store_code": "S1", "line_items": []}


async def _post(headers):
    async with AsyncClient(transport=ASGITransport(app=_make_app()), base_url="http://test") as client:
        return await client.post("/api/v1/tranlog", json={"data": FORGED}, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [{}, {DAPR_APP_TOKEN_HEADER: "a-token-someone-guessed"}, {"Authorization": "Bearer anything"}],
    ids=["no token", "wrong token", "a bearer token instead"],
)
async def test_a_request_not_from_the_sidecar_is_refused_and_opens_no_tenant_database(headers):
    get_db = AsyncMock()
    with patch("kugel_common.database.database.get_db_async", get_db):
        response = await _post(headers)

    assert response.status_code == 401
    get_db.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_delivery_carrying_the_token_reaches_the_handler():
    get_db = AsyncMock(side_effect=RuntimeError("reached the handler"))
    with patch("kugel_common.database.database.get_db_async", get_db):
        await _post({DAPR_APP_TOKEN_HEADER: os.environ["APP_API_TOKEN"]})

    get_db.assert_awaited_once_with(f"{os.environ['DB_NAME_PREFIX']}_T-ANY")
