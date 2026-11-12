# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""A cart response carries the terminal's business date.

The cart is stamped with terminal_info.business_date when it is created, but the
response builder left the field out, so every cart response answered
``businessDate: null``. Read from the add-item response, the first cart-shaped
one (create answers only the id). Checked on both paths, because the carried
path builds its cart from the signed snapshot rather than the cache.
"""

import os

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient


@pytest.fixture
def api_header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


@pytest_asyncio.fixture(autouse=True)
async def _tenant_is_set_up(http_client):
    from tests.e2e.test_cart import create_tenant, get_authentication_token

    await create_tenant(http_client, await get_authentication_token())


async def _terminal_business_date(terminal_id, header):
    async with AsyncClient(base_url=os.environ.get("BASE_URL_TERMINAL")) as client:
        response = await client.get(f"/terminals/{terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["data"]["businessDate"]


async def _open_cart(http_client, terminal_id, header, carried):
    """Create a cart. The create response carries only the id (and the snapshot)."""
    body = {"transaction_type": 101, "user_id": "99", "user_name": "Business date"}
    if carried:
        body["carrySnapshot"] = True
    response = await http_client.post(f"/api/v1/carts?terminal_id={terminal_id}", json=body, headers=header)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]


@pytest.mark.dual_only  # no snapshot carried: needs the phase 1 fallback (#156)
@pytest.mark.asyncio
async def test_cached_cart_response_carries_business_date(http_client, api_header, opened_terminal_id):
    expected = await _terminal_business_date(opened_terminal_id, api_header)
    assert expected, "the opened terminal has no business date to compare against"
    cart_id = (await _open_cart(http_client, opened_terminal_id, api_header, carried=False))["cartId"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={opened_terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=api_header,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["businessDate"] == expected


@pytest.mark.asyncio
async def test_carried_cart_response_carries_business_date(http_client, api_header, opened_terminal_id):
    expected = await _terminal_business_date(opened_terminal_id, api_header)
    assert expected, "the opened terminal has no business date to compare against"
    created = await _open_cart(http_client, opened_terminal_id, api_header, carried=True)

    response = await http_client.post(
        f"/api/v1/carts/{created['cartId']}/lineItems?terminal_id={opened_terminal_id}",
        json={"signedSnapshot": created["signedSnapshot"], "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=api_header,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["businessDate"] == expected
