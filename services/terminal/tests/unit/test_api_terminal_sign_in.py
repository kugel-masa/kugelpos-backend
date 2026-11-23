"""POST /api/v1/terminals/{terminal_id}/sign-in takes an optional PIN (issue #323)."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tests.unit.test_api_terminals import TERMINAL_ID, _make_terminal_doc, make_app

PIN = "pin-sentinel-7c1e9a"
URL = f"/api/v1/terminals/{TERMINAL_ID}/sign-in"


async def _sign_in(body):
    service = AsyncMock()
    service.sign_in_terminal_async.return_value = _make_terminal_doc(status="SignedIn")
    with patch("app.api.v1.terminal.get_terminal_service_async", return_value=service):
        async with AsyncClient(transport=ASGITransport(app=make_app()), base_url="http://test") as client:
            response = await client.post(URL, json=body)
    return response, service


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{"staffId": "S1", "pin": PIN}, {"staff_id": "S1", "pin": PIN}])
async def test_the_pin_is_passed_to_the_service(body):
    response, service = await _sign_in(body)

    assert response.status_code == 200, response.text
    service.sign_in_terminal_async.assert_awaited_once_with("S1", PIN)


@pytest.mark.asyncio
async def test_a_request_without_a_pin_is_still_accepted():
    response, service = await _sign_in({"staffId": "S1"})

    assert response.status_code == 200, response.text
    service.sign_in_terminal_async.assert_awaited_once_with("S1", None)


@pytest.mark.asyncio
async def test_the_route_does_not_log_the_pin(caplog):
    caplog.set_level(logging.DEBUG)

    response, _ = await _sign_in({"staffId": "S1", "pin": PIN})

    assert response.status_code == 200
    assert PIN not in response.text
    assert PIN not in "\n".join(r.getMessage() for r in caplog.records)
