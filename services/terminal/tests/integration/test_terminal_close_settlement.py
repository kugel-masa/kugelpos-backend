# Copyright 2026 masa@kugel
"""Closing a terminal goes through report's settlement (#343, US1, US5)."""
import asyncio
import os
import re

import httpx
import pytest
from fastapi import status

from kugel_common.config.settings import settings as common_settings

from .test_terminal_lifecycle import _TERMINAL_NO_COUNTER, _create_terminal

# Terminal numbers of their own: the shared counter starting at 50 would otherwise
# walk into the fixed numbers other tests use (9, 99).
_TERMINAL_NO_COUNTER[0] = max(_TERMINAL_NO_COUNTER[0], 300)

SETTLE = re.compile(rf"{re.escape(common_settings.BASE_URL_REPORT)}/internal/tenants/[^/]+/stores/[^/]+/terminals/\d+/settlements")


async def _post(http_client, terminal_id, api_key, action, body=None):
    return await http_client.post(
        f"/api/v1/terminals/{terminal_id}/{action}", json=body or {}, headers={"X-API-KEY": api_key}
    )


async def _open_terminal(http_client, admin_header):
    terminal_id, api_key = await _create_terminal(http_client, admin_header)
    assert (await _post(http_client, terminal_id, api_key, "sign-in", {"staff_id": "S001"})).status_code == 200
    assert (await _post(http_client, terminal_id, api_key, "open", {"initial_amount": 10000.0})).status_code == 200
    return terminal_id, api_key


async def _status(http_client, admin_header, terminal_id):
    response = await http_client.get(f"/api/v1/terminals/{terminal_id}", headers=admin_header)
    return response.json()["data"]["status"]


async def _close_logs(terminal_id):
    from kugel_common.database import database as db_helper

    from app.config.settings import settings

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    terminal_no = int(terminal_id.rsplit("-", 1)[1])
    return await db[settings.DB_COLLECTION_NAME_OPEN_CLOSE_LOG].count_documents(
        {"terminal_no": terminal_no, "operation": "close"}
    )


@pytest.mark.asyncio
async def test_close_answers_and_prints_the_settlement(http_client, admin_header, mock_outbound_services):
    terminal_id, api_key = await _open_terminal(http_client, admin_header)

    response = await _post(http_client, terminal_id, api_key, "close", {"physicalAmount": 9500.0, "seq": 3})

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["settlementId"]
    assert data["expectedCashTotal"] == 0.0
    assert data["missingCount"] == 0
    assert "あるべき現金" in data["receiptText"]
    sent = [c for c in mock_outbound_services.calls if SETTLE.match(str(c.request.url))][-1]
    assert b'"seq":3' in sent.request.content.replace(b" ", b"")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer",
    [httpx.Response(503, json={"success": False}), httpx.Response(500, json={"success": False}), httpx.ConnectError("down")],
    ids=["503", "500", "unreachable"],
)
async def test_report_unavailable_refuses_the_close_and_leaves_the_terminal_open(
    http_client, admin_header, mock_outbound_services, answer
):
    terminal_id, api_key = await _open_terminal(http_client, admin_header)
    route = mock_outbound_services.post(SETTLE)
    if isinstance(answer, Exception):
        route.mock(side_effect=answer)
    else:
        route.mock(return_value=answer)

    response = await _post(http_client, terminal_id, api_key, "close", {"physicalAmount": 9500.0})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response.text
    assert response.json()["userError"]["code"] == "406016"
    assert await _status(http_client, admin_header, terminal_id) == "Opened"
    assert await _close_logs(terminal_id) == 0

    # Report is back: the close goes through.
    from .conftest import _settlement_answer

    route.mock(side_effect=_settlement_answer)
    response = await _post(http_client, terminal_id, api_key, "close", {"physicalAmount": 9500.0})
    assert response.status_code == status.HTTP_200_OK, response.text
    assert await _status(http_client, admin_header, terminal_id) == "Closed"
    assert await _close_logs(terminal_id) == 1


@pytest.mark.asyncio
async def test_of_two_closes_at_once_one_closes_the_terminal(http_client, admin_header, mock_outbound_services):
    terminal_id, api_key = await _open_terminal(http_client, admin_header)

    first, second = await asyncio.gather(
        _post(http_client, terminal_id, api_key, "close", {"physicalAmount": 1.0}),
        _post(http_client, terminal_id, api_key, "close", {"physicalAmount": 2.0}),
    )

    winner, loser = sorted([first, second], key=lambda r: r.status_code)
    assert winner.status_code == status.HTTP_200_OK, winner.text
    # The loser is refused as already closed, whether it found the terminal
    # closed or its transaction collided with the winner's (WriteConflict)
    assert loser.status_code == status.HTTP_400_BAD_REQUEST, loser.text
    assert loser.json()["userError"]["code"] == "406003"
    assert await _close_logs(terminal_id) == 1
    assert await _status(http_client, admin_header, terminal_id) == "Closed"


@pytest.mark.asyncio
async def test_closing_a_closed_terminal_is_refused_as_before(http_client, admin_header, mock_outbound_services):
    terminal_id, api_key = await _open_terminal(http_client, admin_header)
    assert (await _post(http_client, terminal_id, api_key, "close", {"physicalAmount": 1.0})).status_code == 200

    response = await _post(http_client, terminal_id, api_key, "close", {"physicalAmount": 1.0})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["userError"]["code"] == "406003"


@pytest.mark.asyncio
async def test_close_preview_asks_report_and_stores_nothing(http_client, admin_header, mock_outbound_services):
    terminal_id, api_key = await _open_terminal(http_client, admin_header)

    response = await http_client.get(
        f"/api/v1/terminals/{terminal_id}/close-preview?seq=4&physical_amount=100", headers={"X-API-KEY": api_key}
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["settled"] is False
    assert data["expectedCashTotal"] == 0.0
    preview_calls = [c for c in mock_outbound_services.calls if "/settlement-preview" in str(c.request.url)]
    assert preview_calls and preview_calls[-1].request.url.params["seq"] == "4"
    assert await _status(http_client, admin_header, terminal_id) == "Opened"
    assert await _close_logs(terminal_id) == 0


@pytest.mark.asyncio
async def test_close_preview_of_a_terminal_not_open_is_refused(http_client, admin_header, mock_outbound_services):
    terminal_id, api_key = await _create_terminal(http_client, admin_header)

    response = await http_client.get(f"/api/v1/terminals/{terminal_id}/close-preview", headers={"X-API-KEY": api_key})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["userError"]["code"] == "406003"


@pytest.mark.asyncio
async def test_close_preview_with_report_down_is_503(http_client, admin_header, mock_outbound_services):
    terminal_id, api_key = await _open_terminal(http_client, admin_header)
    # The same pattern as conftest's route, so respx replaces that route's answer
    preview = re.compile(
        rf"{re.escape(common_settings.BASE_URL_REPORT)}/internal/tenants/[^/]+/stores/[^/]+/terminals/\d+/settlement-preview"
    )
    mock_outbound_services.get(preview).mock(return_value=httpx.Response(503, json={"success": False}))

    response = await http_client.get(f"/api/v1/terminals/{terminal_id}/close-preview", headers={"X-API-KEY": api_key})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["userError"]["code"] == "406016"
