# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Rollback is visible in the request log afterwards (issue #165).

The signature proves an envelope was issued unmodified, not that it is the
current one, and a stateless backend cannot know the high-water mark without the
per-request write phase 2 removed. So a replayed older envelope is accepted - and
recorded: every issued snapshot carries a higher revision, so the sequence
presented for a cart_id stops increasing exactly when one is replayed.
"""

import os

import pytest
from fastapi import status


@pytest.fixture
def api_header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


async def _cart_with_snapshots(http_client, terminal_id, header, mutations=2):
    """Create a cart and mutate it, keeping every snapshot it was handed."""
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={
            # Opened for the carried path (issue #192): every request below
            # carries the snapshot, so nothing is cached to serve a plain one.
            "carrySnapshot": True,
            "transaction_type": 101,
            "user_id": "99",
            "user_name": "Revision",
        },
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()["data"]
    cart_id, snapshots = data["cartId"], [data["signedSnapshot"]]

    for _ in range(mutations):
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json={"signedSnapshot": snapshots[-1], "payload": [{"itemCode": "49-01", "quantity": 1}]},
            headers=header,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        snapshots.append(response.json()["data"]["signedSnapshot"])

    return cart_id, snapshots


@pytest.mark.asyncio
async def test_each_issued_snapshot_advances_the_revision(http_client, api_header, opened_terminal_id):
    _, snapshots = await _cart_with_snapshots(http_client, opened_terminal_id, api_header)

    revisions = [s["cartDocument"]["revision"] for s in snapshots]
    assert revisions == sorted(revisions)
    assert len(set(revisions)) == len(revisions)  # strictly increasing
    assert snapshots[0]["schemaVersion"] == 2


@pytest.mark.asyncio
async def test_a_replayed_envelope_is_accepted(http_client, api_header, opened_terminal_id):
    """Accepted by design: a stateless backend has no high-water mark to check
    against, so the older envelope is honoured and the request log carries the
    revision that makes the rollback findable afterwards (covered in the
    integration tier, where the log buffer can be flushed deterministically)."""
    cart_id, snapshots = await _cart_with_snapshots(http_client, opened_terminal_id, api_header)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={opened_terminal_id}",
        json={"signedSnapshot": snapshots[0], "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=api_header,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    # The cart is rebuilt from the replayed envelope, so the response continues
    # from its revision rather than from the newest one issued.
    replayed = snapshots[0]["cartDocument"]["revision"]
    assert response.json()["data"]["signedSnapshot"]["cartDocument"]["revision"] == replayed + 1
