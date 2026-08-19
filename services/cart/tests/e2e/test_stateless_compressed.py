# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""E2E coverage for the phase 2 stateless path over the wire (issue #156).

The integration suite drives the app through an in-process ASGI transport, which
delivers a request body in one message and never applies a Content-Encoding.
Real uvicorn does both, and both matter here:

- a compressed body reaches the snapshot-peel middleware still compressed unless
  decompression runs outside it, and the peel JSON-parses the body — a failure
  there does not raise, it reads as "legacy request, no snapshot" and silently
  takes the cache-authoritative path (FR-009),
- a large body arrives split across several messages, and a 50-line cart is
  ~50KB raw, squarely in that range.

So these exercise the live stack: a wrapped request, the same request gzipped,
and the guards around it.
"""

import gzip
import json
import os

import pytest
from fastapi import status
@pytest.fixture
def api_header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


async def _cart_with_one_item(http_client, terminal_id, header):
    """Create a cart, add a line, and return (cart_id, snapshot, line count)."""
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "Compression Tester"},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    cart_id = response.json()["data"]["cartId"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 2}],
        headers=header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    return cart_id, data["signedSnapshot"], len(data["lineItems"])


@pytest.mark.asyncio
async def test_snapshot_is_issued_by_the_running_stack(http_client, api_header, opened_terminal_id):
    """A deployed service must actually have signing keys configured.

    Without them the feature is degraded — no snapshot is issued and every
    carried one is rejected — and every phase 2 client silently falls back to the
    server-side cache. That failure is invisible in a response, so assert it here.
    """
    terminal_id = opened_terminal_id

    _, snapshot, _ = await _cart_with_one_item(http_client, terminal_id, api_header)

    assert snapshot is not None, "SNAPSHOT_HMAC_KEYS is not configured on the running cart service"
    assert snapshot.get("signature"), snapshot


@pytest.mark.asyncio
async def test_gzipped_wrapped_request_takes_the_stateless_path(http_client, api_header, opened_terminal_id):
    """A gzip-compressed wrapped request is expanded, peeled, and applied."""
    terminal_id = opened_terminal_id

    cart_id, snapshot, line_count = await _cart_with_one_item(http_client, terminal_id, api_header)
    assert snapshot is not None

    wrapped = {"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]}
    body = gzip.compress(json.dumps(wrapped).encode())

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        content=body,
        headers={**api_header, "Content-Type": "application/json", "Content-Encoding": "gzip"},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    # The carried cart was reconstructed (it had the first line) and the new line
    # applied on top — so the snapshot was genuinely read, not ignored.
    assert len(data["lineItems"]) == line_count + 1
    assert data["signedSnapshot"] is not None


@pytest.mark.asyncio
async def test_large_gzipped_request_survives_chunked_delivery(http_client, api_header, opened_terminal_id):
    """A body big enough that uvicorn splits it must still be reassembled.

    Padding the wrapper takes the compressed body past the point where it arrives
    in one message; expanding only the first chunk would corrupt it.
    """
    terminal_id = opened_terminal_id

    cart_id, snapshot, line_count = await _cart_with_one_item(http_client, terminal_id, api_header)
    assert snapshot is not None

    # Incompressible padding, so the body stays large after gzip too. Sized from
    # the service's own ceiling — a fixed size would start failing with 413 the
    # moment REQUEST_DECOMPRESS_MAX_BYTES is lowered.
    from app.config.settings import settings

    padding = os.urandom(settings.REQUEST_DECOMPRESS_MAX_BYTES // 4).hex()
    wrapped = {
        "signedSnapshot": snapshot,
        "payload": [{"itemCode": "49-01", "quantity": 1}],
        "_padding": padding,
    }
    body = gzip.compress(json.dumps(wrapped).encode())
    assert len(body) > 64 * 1024, "the point is a body larger than one ASGI message"

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        content=body,
        headers={**api_header, "Content-Type": "application/json", "Content-Encoding": "gzip"},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert len(response.json()["data"]["lineItems"]) == line_count + 1


@pytest.mark.asyncio
async def test_zip_bomb_is_refused_over_the_wire(http_client, api_header, opened_terminal_id):
    """A tiny body expanding past the ceiling is refused with 413."""
    terminal_id = opened_terminal_id

    bomb = gzip.compress(b"a" * (2 * 1024 * 1024))
    assert len(bomb) < 50 * 1024, "the point is that the compressed form is small"

    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        content=bomb,
        headers={**api_header, "Content-Type": "application/json", "Content-Encoding": "gzip"},
    )

    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, response.text
    assert "401509" in response.text, response.text


@pytest.mark.asyncio
async def test_unsupported_encoding_is_refused_over_the_wire(http_client, api_header, opened_terminal_id):
    """An encoding the service cannot expand must not reach the app compressed."""
    terminal_id = opened_terminal_id

    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        content=b"not-really-zstd",
        headers={**api_header, "Content-Type": "application/json", "Content-Encoding": "zstd"},
    )

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, response.text


@pytest.mark.asyncio
async def test_uncompressed_requests_are_unaffected(http_client, api_header, opened_terminal_id):
    """Compression is optional; the plain path must keep working."""
    terminal_id = opened_terminal_id

    cart_id, snapshot, line_count = await _cart_with_one_item(http_client, terminal_id, api_header)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=api_header,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert len(response.json()["data"]["lineItems"]) == line_count + 1
