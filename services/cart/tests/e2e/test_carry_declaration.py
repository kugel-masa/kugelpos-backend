# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""One cart, one path (issue #192).

The path used to be chosen per request, on whether a snapshot came with it. The
carried path writes nothing to the cache, so a cart built up by carried requests
left the cache holding it as it was at creation — and one snapshot-less request
continued from there, dropping everything in between and answering with a
correctly signed snapshot of a cart missing it. No error, nothing in the log to
say what went.

The client now says at creation which way it will work, and the other way is
refused. End to end because what is being asserted is the refusal a client
actually receives, and because the carried path's whole point is that no
server-side state is involved.
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


async def _create(http_client, terminal_id, header, carry_snapshot):
    body = {"transaction_type": 101, "user_id": "99", "user_name": "Carry declaration"}
    if carry_snapshot is not None:
        body["carrySnapshot"] = carry_snapshot
    response = await http_client.post(f"/api/v1/carts?terminal_id={terminal_id}", json=body, headers=header)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()["data"]
    return data["cartId"], data["signedSnapshot"]


async def _add_carried(http_client, terminal_id, header, cart_id, snapshot):
    return await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=header,
    )


async def _add_plain(http_client, terminal_id, header, cart_id):
    return await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=header,
    )


class TestACartOpenedToBeCarried:
    @pytest.mark.asyncio
    async def test_carried_requests_work(self, http_client, api_header, opened_terminal_id):
        cart_id, snapshot = await _create(http_client, opened_terminal_id, api_header, carry_snapshot=True)

        response = await _add_carried(http_client, opened_terminal_id, api_header, cart_id, snapshot)

        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()["data"]["lineItems"]) == 1

    @pytest.mark.dual_only  # no snapshot carried: needs the phase 1 fallback (#156)

    @pytest.mark.asyncio
    async def test_a_request_without_its_snapshot_is_refused(self, http_client, api_header, opened_terminal_id):
        """The defect, closed. Nothing was cached, so there is nothing to continue from."""
        cart_id, snapshot = await _create(http_client, opened_terminal_id, api_header, carry_snapshot=True)
        for _ in range(2):
            response = await _add_carried(http_client, opened_terminal_id, api_header, cart_id, snapshot)
            snapshot = response.json()["data"]["signedSnapshot"]
        assert len(response.json()["data"]["lineItems"]) == 2, "precondition: the carried cart has two lines"

        plain = await _add_plain(http_client, opened_terminal_id, api_header, cart_id)

        assert plain.status_code == status.HTTP_404_NOT_FOUND, (
            f"a snapshot-less request continued from a stale cart: {plain.text[:200]}"
        )
        assert "401002" in plain.text


class TestACartOpenedForTheCache:
    @pytest.mark.dual_only  # no snapshot carried: needs the phase 1 fallback (#156)
    @pytest.mark.asyncio
    async def test_requests_without_a_snapshot_work(self, http_client, api_header, opened_terminal_id):
        cart_id, _ = await _create(http_client, opened_terminal_id, api_header, carry_snapshot=False)

        response = await _add_plain(http_client, opened_terminal_id, api_header, cart_id)

        assert response.status_code == status.HTTP_200_OK, response.text

    @pytest.mark.dual_only  # no snapshot carried: needs the phase 1 fallback (#156)

    @pytest.mark.asyncio
    async def test_carrying_it_is_refused(self, http_client, api_header, opened_terminal_id):
        """The other direction, and it matters as much.

        Declaring the cache path and then carrying leaves the cache copy behind
        while the cart moves on — which is the same silent loss, reached from
        the other side.
        """
        cart_id, snapshot = await _create(http_client, opened_terminal_id, api_header, carry_snapshot=False)

        response = await _add_carried(http_client, opened_terminal_id, api_header, cart_id, snapshot)

        assert response.status_code != status.HTTP_200_OK, "a cache-path cart was carried"
        assert response.status_code == status.HTTP_409_CONFLICT, response.text
        assert "401515" in response.text


class TestSayingNothing:
    @pytest.mark.dual_only  # no snapshot carried: needs the phase 1 fallback (#156)
    @pytest.mark.asyncio
    async def test_it_means_the_cache_path(self, http_client, api_header, opened_terminal_id):
        # What a client that predates the field means by omitting it. Its
        # behaviour has to be exactly what it was.
        cart_id, _ = await _create(http_client, opened_terminal_id, api_header, carry_snapshot=None)

        response = await _add_plain(http_client, opened_terminal_id, api_header, cart_id)

        assert response.status_code == status.HTTP_200_OK, response.text
