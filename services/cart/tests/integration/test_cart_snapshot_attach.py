# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for signed snapshot attachment (issues #148, #215).

A CARRIED cart-mutating response must carry a self-verifying signed snapshot
of the full cart document (masters included). Query (GET) responses carry
none, and with no signing keys configured a cache-path operation still
succeeds with a null snapshot (degraded mode).

#148 attached one to every mutating response, which was right while there was
one path. #192 split them and #215 narrowed this: a cache-path response
carries none, because the envelope on that side is refused by this same server
on the way back and there is no restore endpoint to spend it on either.
"""

import base64
import os

import pytest
from fastapi import status

from kugel_common.utils.hmac_signer import HmacSigner

from app.api.common.schemas import SnapshotEnvelope
from app.config.settings import settings
from app.services import snapshot_service

KEY_SPEC = "it-v1:" + base64.b64encode(b"integration-test-key-32-bytes!!!").decode()


@pytest.fixture
def snapshot_keys(monkeypatch):
    """Enable snapshot signing for the app under test."""
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", KEY_SPEC)
    snapshot_service.init_snapshot_signer(force=True)
    yield KEY_SPEC
    snapshot_service.init_snapshot_signer(force=True)


@pytest.fixture
def snapshot_keys_unset(monkeypatch):
    """Force degraded mode (no signing keys)."""
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", "")
    snapshot_service.init_snapshot_signer(force=True)
    yield
    snapshot_service.init_snapshot_signer(force=True)


def _api_headers():
    return {
        "X-API-KEY": "test-api-key-12345",
        "Content-Type": "application/json",
    }


def _terminal_id():
    return f"{os.environ.get('TENANT_ID')}-5678-9"


def _assert_valid_snapshot(data: dict, expected_cart_id: str | None = None) -> dict:
    """Assert the response data carries a self-verifying snapshot; return it."""
    snapshot = data.get("signedSnapshot")
    assert snapshot is not None, f"signedSnapshot missing in response data: {list(data.keys())}"
    envelope = SnapshotEnvelope(**snapshot).model_dump(mode="json")
    signature = envelope.pop("signature")
    signer = HmacSigner.from_spec(KEY_SPEC)
    assert signer.verify(envelope, envelope["kid"], signature) is True
    assert envelope["schema_version"] == snapshot_service.SNAPSHOT_SCHEMA_VERSION
    assert envelope["tenant_id"] == os.environ.get("TENANT_ID")
    assert envelope["store_code"] == "5678"
    assert envelope["terminal_no"] == 9
    if expected_cart_id is not None:
        assert envelope["cart_document"]["cart_id"] == expected_cart_id
    return envelope


async def _create_cart(http_client, user_id="9999", carry_snapshot=True):
    """Create a cart. Carried by default - that is the path that attaches."""
    body = {
        "tenant_id": os.environ.get("TENANT_ID"),
        "terminal_id": _terminal_id(),
        "operator_code": user_id,
        "operator_name": "Test Operator",
    }
    if carry_snapshot:
        body["carrySnapshot"] = True
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={_terminal_id()}",
        json=body,
        headers=_api_headers(),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]


def _carrying(snapshot, payload=None):
    """The request body shape a carried request uses."""
    return {"signedSnapshot": snapshot, "payload": payload}


@pytest.mark.asyncio
@pytest.mark.parametrize("carried", [True, False], ids=["carried", "cached"])
async def test_every_mutating_endpoint_answers_the_way_its_path_says(http_client, snapshot_keys, carried):
    """Walk the full mutating surface on BOTH paths and check what comes back.

    One walk, two answers. A carried response must carry a valid, verifiable
    envelope (#148, #192); a cache-path one must carry none (#215). Running the
    same eleven mutations both ways is what makes the second half worth
    anything: attaching an envelope on the cache path is a mistake that would
    otherwise hide in whichever endpoint the shorter test did not visit.

    Signing keys are configured for both. The cached run answers null because
    of the path, not because the server cannot sign.

    The carried run also proves the chain end to end. A carried cart is written
    nowhere, so each request has to present the envelope the previous response
    returned - eleven mutations, each spending the one before.
    """
    terminal_id = _terminal_id()
    headers = _api_headers()

    create_data = await _create_cart(http_client, carry_snapshot=carried)
    cart_id = create_data["cartId"]
    snapshot = None
    if carried:
        _assert_valid_snapshot(create_data, cart_id)
        snapshot = create_data["signedSnapshot"]
    else:
        assert create_data.get("signedSnapshot") is None, "creation attached an envelope to a cached cart"

    async def step(method: str, path: str, payload=None):
        """One mutation on whichever path this run is walking."""
        nonlocal snapshot
        body = _carrying(snapshot, payload) if carried else payload
        kwargs = {"headers": headers}
        if body is not None:
            kwargs["json"] = body
        r = await getattr(http_client, method)(f"/api/v1/carts/{cart_id}/{path}?terminal_id={terminal_id}", **kwargs)
        assert r.status_code == status.HTTP_200_OK, f"{method.upper()} {path} -> {r.status_code} {r.text}"
        data = r.json()["data"]
        if carried:
            _assert_valid_snapshot(data, cart_id)
            snapshot = data["signedSnapshot"]
        else:
            assert data.get("signedSnapshot") is None, f"{method.upper()} {path} attached an envelope to a cached cart"
        return data

    data = await step("post", "lineItems", [{"itemCode": "49-01", "quantity": 2}, {"itemCode": "49-02", "quantity": 1}])
    if carried:
        # Masters travel with the snapshot: the scanned item is embedded.
        envelope = SnapshotEnvelope(**data["signedSnapshot"]).model_dump(mode="json")
        assert "49-01" in [i["item_code"] for i in envelope["cart_document"]["masters"]["items"]]

    await step("patch", "lineItems/1/quantity", {"quantity": 3})
    await step("patch", "lineItems/1/unitPrice", {"unitPrice": 120.0})
    await step("post", "lineItems/1/discounts", [{"discountType": "DiscountAmount", "discountValue": 10}])
    await step("post", "lineItems/2/cancel")
    await step("post", "subtotal")
    await step("post", "discounts", [{"discountType": "DiscountAmount", "discountValue": 5}])
    await step("post", "resume-item-entry")
    data = await step("post", "subtotal")

    await step("post", "payments", [{"paymentCode": "01", "amount": int(data["balanceAmount"])}])
    await step("post", "bill")


@pytest.mark.asyncio
async def test_the_envelope_a_cached_cart_would_have_had_is_refused_anyway(http_client, snapshot_keys):
    """Why there is nothing to attach: this server will not take it back.

    Pinned rather than assumed, because it is the whole argument for #215. If
    a cache-path cart ever starts accepting a carried snapshot, the attachment
    should come back.

    The envelope has to be one for THIS cart, or the request fails earlier on a
    cart_id mismatch (401512) and proves nothing about the path. So the cart is
    opened carried - which is the only way to be handed an envelope for it -
    and then told it is not carried, by flipping the flag inside the envelope
    and re-signing it. That is exactly the shape the guard exists to refuse.
    """
    terminal_id = _terminal_id()
    headers = _api_headers()

    created = await _create_cart(http_client, carry_snapshot=True)
    cart_id = created["cartId"]

    envelope = SnapshotEnvelope(**created["signedSnapshot"]).model_dump(mode="json")
    envelope.pop("signature")
    envelope["cart_document"]["carry_snapshot"] = False
    signer = HmacSigner.from_spec(KEY_SPEC)
    envelope["signature"] = signer.sign(envelope)

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=_carrying(envelope, [{"itemCode": "49-01", "quantity": 1}]),
        headers=headers,
    )
    assert r.status_code == status.HTTP_409_CONFLICT, (
        f"a cart declared as cache-path accepted a carried snapshot: {r.status_code} {r.text}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("carried", [True, False], ids=["carried", "cached"])
async def test_the_cancel_endpoint_answers_the_way_its_path_says(http_client, snapshot_keys, carried):
    """The twelfth mutating endpoint, which the walk above cannot reach.

    Cancel ends the cart, so it cannot sit in the middle of a walk. Both paths
    all the same - a mistake here would be invisible to the walk either way.
    """
    create_data = await _create_cart(http_client, carry_snapshot=carried)
    cart_id = create_data["cartId"]
    kwargs = {"headers": _api_headers()}
    if carried:
        kwargs["json"] = _carrying(create_data["signedSnapshot"])
    r = await http_client.post(f"/api/v1/carts/{cart_id}/cancel?terminal_id={_terminal_id()}", **kwargs)
    assert r.status_code == status.HTTP_200_OK, r.text

    if carried:
        _assert_valid_snapshot(r.json()["data"], cart_id)
    else:
        assert r.json()["data"].get("signedSnapshot") is None


@pytest.mark.asyncio
async def test_degraded_mode_mutation_succeeds_without_snapshot(http_client, snapshot_keys_unset):
    """With no keys configured a CACHED cart's operation succeeds, field null.

    Cache-path on purpose. A carried cart has no answer in degraded mode - the
    test below is that one - and since #215 a cached response is null-snapshot
    whether or not keys are configured. What this still pins is that a missing
    signer does not turn a working mutation into a failure.
    """
    create_data = await _create_cart(http_client, carry_snapshot=False)
    cart_id = create_data["cartId"]
    assert create_data.get("signedSnapshot") is None

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={_terminal_id()}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=_api_headers(),
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["data"].get("signedSnapshot") is None


@pytest.mark.asyncio
async def test_a_carried_cart_is_not_created_when_it_cannot_be_signed(http_client, snapshot_keys_unset):
    """Degraded mode has no null-snapshot answer for a carried cart (issue #192).

    The cart above survives a null snapshot because the server still holds it.
    A cart the client declared it would carry is written nowhere, so the same
    answer would hand back an id addressing nothing — the client could neither
    carry it nor find it, and the cart would be lost at the moment of creation.

    Startup now refuses to run without a key, so reaching this needs the keys
    pulled out from under a running app, which is what the fixture does. The
    check stays because a key that loads and then fails to sign gets past
    startup, and lands here identically.
    """
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={_terminal_id()}",
        json={
            "carrySnapshot": True,
            "tenant_id": os.environ.get("TENANT_ID"),
            "terminal_id": _terminal_id(),
            "operator_code": "9999",
            "operator_name": "Test Operator",
        },
        headers=_api_headers(),
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response.text
    assert "401507" in response.text, response.text
