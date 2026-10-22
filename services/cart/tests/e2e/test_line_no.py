"""A line number from the URL names a line, or is refused (issue #137).

`lineNo` was used as a raw list index: 0 and negative numbers wrapped round
and cancelled a line the client never named, and a number past the end
answered 500. Carried throughout, so it runs under both snapshot modes.
"""

import os

import pytest
import pytest_asyncio
from fastapi import status


@pytest.fixture
def api_header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


@pytest_asyncio.fixture(autouse=True)
async def _tenant_is_set_up(http_client):
    from tests.e2e.test_cart import create_tenant, get_authentication_token

    await create_tenant(http_client, await get_authentication_token())


async def _cart_with_two_lines(http_client, terminal_id, header):
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "Line numbers", "carrySnapshot": True},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()["data"]
    cart_id, snapshot = data["cartId"], data["signedSnapshot"]
    for _ in range(2):
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]},
            headers=header,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        snapshot = response.json()["data"]["signedSnapshot"]
    return cart_id, snapshot


async def _cancel(http_client, terminal_id, header, cart_id, snapshot, line_no):
    return await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems/{line_no}/cancel?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=header,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("line_no", [0, -1, 99])
async def test_a_line_number_that_names_no_line_is_refused(http_client, api_header, opened_terminal_id, line_no):
    cart_id, snapshot = await _cart_with_two_lines(http_client, opened_terminal_id, api_header)

    response = await _cancel(http_client, opened_terminal_id, api_header, cart_id, snapshot, line_no)

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert "402006" in response.text


@pytest.mark.asyncio
async def test_the_named_line_is_the_one_cancelled(http_client, api_header, opened_terminal_id):
    cart_id, snapshot = await _cart_with_two_lines(http_client, opened_terminal_id, api_header)

    response = await _cancel(http_client, opened_terminal_id, api_header, cart_id, snapshot, 2)

    assert response.status_code == status.HTTP_200_OK, response.text
    lines = {line["lineNo"]: line["isCancelled"] for line in response.json()["data"]["lineItems"]}
    assert lines == {1: False, 2: True}
