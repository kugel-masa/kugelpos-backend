# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""A signed-out terminal is refused on both paths, as signed out.

The carried path refused it with "Terminal is not signed in". The cached path had
no such check and failed reading the cart, where the repository writes the
signed-in staff onto it: the terminal was told the cart did not exist (404) and a
FATAL notification went out. The unit tests stub the repository, so only a
running stack shows it. X-API-KEY is used because that path reads the terminal
afresh on each request; a JWT carries the staff it was issued with.
"""

import os
from contextlib import asynccontextmanager

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


async def _terminal(path, header, **kw):
    async with AsyncClient(base_url=os.environ.get("BASE_URL_TERMINAL")) as client:
        response = await client.post(path, headers=header, **kw)
    assert response.status_code == status.HTTP_200_OK, response.text


@asynccontextmanager
async def _signed_out(terminal_id, header):
    """Sign the shared terminal out, and back in whatever happens."""
    await _terminal(f"/terminals/{terminal_id}/sign-out", header)
    try:
        yield
    finally:
        await _terminal(f"/terminals/{terminal_id}/sign-in", header, json={"staff_id": "S001"})


async def _open_cart(http_client, terminal_id, header, carried):
    body = {"transaction_type": 101, "user_id": "99", "user_name": "Signed out"}
    if carried:
        body["carrySnapshot"] = True
    response = await http_client.post(f"/api/v1/carts?terminal_id={terminal_id}", json=body, headers=header)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]


def _refused_as_signed_out(response):
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    assert response.json()["message"] == "Terminal is not signed in"


@pytest.mark.dual_only  # no snapshot carried: needs the phase 1 fallback (#156)
@pytest.mark.asyncio
async def test_a_cached_cart_is_refused_as_signed_out_not_as_missing(http_client, api_header, opened_terminal_id):
    cart_id = (await _open_cart(http_client, opened_terminal_id, api_header, carried=False))["cartId"]

    async with _signed_out(opened_terminal_id, api_header):
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={opened_terminal_id}",
            json=[{"itemCode": "49-01", "quantity": 1}],
            headers=api_header,
        )

    _refused_as_signed_out(response)


@pytest.mark.asyncio
async def test_a_carried_cart_is_refused_as_signed_out(http_client, api_header, opened_terminal_id):
    opened = await _open_cart(http_client, opened_terminal_id, api_header, carried=True)

    async with _signed_out(opened_terminal_id, api_header):
        response = await http_client.post(
            f"/api/v1/carts/{opened['cartId']}/lineItems?terminal_id={opened_terminal_id}",
            json={"signedSnapshot": opened["signedSnapshot"], "payload": [{"itemCode": "49-01", "quantity": 1}]},
            headers=api_header,
        )

    _refused_as_signed_out(response)


@pytest.mark.dual_only  # the cart is looked up server-side, with no snapshot
@pytest.mark.asyncio
async def test_a_cart_that_is_not_there_is_still_not_found(http_client, api_header, opened_terminal_id):
    response = await http_client.post(
        f"/api/v1/carts/00000000-0000-4000-8000-000000000000/lineItems?terminal_id={opened_terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=api_header,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert response.json()["message"].startswith("Cart not found")
