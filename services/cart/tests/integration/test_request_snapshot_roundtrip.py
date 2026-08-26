# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for the phase 2 per-request snapshot path (issue #156, US1).

A mutating request that carries the last snapshot in a wrapped body
({signedSnapshot, payload}) is processed statelessly: the peel middleware
lifts the snapshot, the DI reconstructs the cart from it WITHOUT reading the
server-side cache, applies the operation, and returns a fresh snapshot. This
mirrors "continue the transaction on a backend that no longer has the cart
cached" without calling the restore API.
"""

import base64
import os

import pytest
from fastapi import status

from app.config.settings import settings
from app.services import snapshot_service

KEY_SPEC = "it-v1:" + base64.b64encode(b"integration-test-key-32-bytes!!!").decode()


@pytest.fixture
def snapshot_keys(monkeypatch):
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", KEY_SPEC)
    snapshot_service.init_snapshot_signer(force=True)
    yield KEY_SPEC
    snapshot_service.init_snapshot_signer(force=True)


def _api_headers():
    return {"X-API-KEY": "test-api-key-12345", "Content-Type": "application/json"}


def _terminal_id():
    return f"{os.environ.get('TENANT_ID')}-5678-9"


async def _delete_cart_everywhere(cart_id: str):
    """Remove the server-side copy to simulate a backend that no longer has it."""
    from kugel_common.database import database as db_helper

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"db_cart_{tenant_id}")
    await db[settings.DB_COLLECTION_NAME_CACHE_CART].delete_many({"cart_id": cart_id})


async def _create_cart_with_items(http_client):
    terminal_id = _terminal_id()
    headers = _api_headers()
    r = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={
            # Opened for the carried path (issue #192): these tests carry the snapshot on every subsequent request.
            "carrySnapshot": True,
            "tenant_id": os.environ.get("TENANT_ID"),
            "terminal_id": terminal_id,
            "operator_code": "9999",
            "operator_name": "Test Operator",
        },
        headers=headers,
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text
    created = r.json()["data"]
    cart_id = created["cartId"]

    # Carried from the first request onward, because the cart was opened that way
    # and there is no cached copy to serve a plain one (issue #192).
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": created["signedSnapshot"], "payload": [{"itemCode": "49-01", "quantity": 2}]},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    return cart_id, data["signedSnapshot"], len(data["lineItems"])


@pytest.mark.asyncio
async def test_wrapped_request_continues_after_cache_wipe(http_client, snapshot_keys):
    """Snapshot -> wipe server copy -> wrapped add-item request -> succeeds statelessly."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, line_count_before = await _create_cart_with_items(http_client)
    assert snapshot is not None, "mutating response should carry a snapshot when keys are configured"

    # Simulate a backend that no longer has the cart cached.
    await _delete_cart_everywhere(cart_id)

    # Phase 2 wrapped body: carry the snapshot + the original array payload.
    wrapped = {"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )

    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    # The cart was reconstructed from the snapshot (had the first item) and the
    # new item was applied — even though the server-side cache was wiped.
    assert len(data["lineItems"]) == line_count_before + 1
    # A fresh snapshot is returned for the next request.
    assert data["signedSnapshot"] is not None


@pytest.mark.asyncio
async def test_carried_finalize_context_drives_numbering(http_client, snapshot_keys):
    """A stateless bill uses the client-supplied seq/receipt/time (carried numbering)."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = r.json()["data"]["balanceAmount"]
    snapshot = r.json()["data"]["signedSnapshot"]

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"paymentCode": "01", "amount": int(balance)}]},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    paying_snapshot = r.json()["data"]["signedSnapshot"]
    assert paying_snapshot is not None

    # Distinctive carried values a server counter would never produce.
    finalize_ctx = {"seq": 7777, "receiptNo": 8888, "transactionDatetime": "2026-06-14T01:02:03"}
    wrapped = {"signedSnapshot": paying_snapshot, "payload": finalize_ctx}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    bill_data = r.json()["data"]
    assert bill_data["cartStatus"] == "Completed"
    # The carried finalize context drove the numbering, not server counters.
    assert bill_data["transactionNo"] == 7777, bill_data
    assert bill_data["receiptNo"] == 8888, bill_data


@pytest.mark.asyncio
async def test_carried_cancel_is_numbered_from_the_carried_context(http_client, snapshot_keys):
    """A cancellation writes a tranlog, so it is a finalize and takes the carried
    numbering too (issue #170). Without this it drew from the server counters,
    whose transaction_no shares the (business_counter, transaction_no) key space
    with the carried per-open seq."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, _ = await _create_cart_with_items(http_client)
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    snapshot = r.json()["data"]["signedSnapshot"]
    assert snapshot is not None

    # Distinctive carried values a server counter would never produce.
    wrapped = {
        "signedSnapshot": snapshot,
        "payload": {"seq": 7801, "receiptNo": 7802, "transactionDatetime": "2026-06-14T04:05:06"},
    }
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    assert data["cartStatus"] == "Cancelled"
    assert data["transactionNo"] == 7801, data
    assert data["receiptNo"] == 7802, data


@pytest.mark.asyncio
async def test_carried_cancel_rejects_a_context_without_a_snapshot(http_client, snapshot_keys):
    """Unsigned numbers are whatever the caller typed; same rule the bill path has."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, _ = await _create_cart_with_items(http_client)
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel?terminal_id={terminal_id}",
        json={"seq": 7811, "receiptNo": 7812, "transactionDatetime": "2026-06-14T04:06:07"},
        headers=headers,
    )
    assert r.status_code >= status.HTTP_400_BAD_REQUEST, r.text


async def _tranlog_count(cart_id: str) -> int:
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"db_cart_{os.environ.get('TENANT_ID')}")
    return await db["log_tran"].count_documents({"cart_id": cart_id})


async def _pay_off(http_client, cart_id: str, snapshot: dict):
    """Drive a carried cart to Paying and return the snapshot to finalize with."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = r.json()["data"]["balanceAmount"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={
            "signedSnapshot": r.json()["data"]["signedSnapshot"],
            "payload": [{"paymentCode": "01", "amount": int(balance)}],
        },
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    return r.json()["data"]["signedSnapshot"]


@pytest.mark.asyncio
async def test_a_finalize_that_cannot_be_signed_is_refused_and_repeatable(http_client, snapshot_keys, monkeypatch):
    """The costliest path this change creates (issue #192).

    A finalize writes the transaction and publishes it, and only then is the
    response built. On the carried path a response without a snapshot is refused
    with 503 rather than returned unsigned — so the client is told the request
    failed while the sale is already recorded. That is only safe if repeating it
    converges, which is what this asserts end to end:

    - the 503 does not roll the transaction back (it is already committed),
    - the repeat returns that same transaction rather than booking a second,
    - and exactly one row exists for the cart when the dust settles.

    Signing is broken here by hand because startup no longer lets a service run
    without a key: what is being simulated is a key that loads and then fails to
    sign, which is the only case left that reaches this branch.
    """
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, _ = await _create_cart_with_items(http_client)
    paying_snapshot = await _pay_off(http_client, cart_id, snapshot)

    ctx = {"seq": 5252, "receiptNo": 5253, "transactionDatetime": "2026-06-14T05:06:07"}
    wrapped = {"signedSnapshot": paying_snapshot, "payload": ctx}
    url = f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}"

    assert await _tranlog_count(cart_id) == 0, "precondition: nothing recorded yet"

    # A nested context, not the fixture's own monkeypatch: undoing this must not
    # also undo `snapshot_keys`, since the repeat below needs signing back.
    with monkeypatch.context() as broken_signing:
        broken_signing.setattr(snapshot_service, "build_envelope", lambda *a, **k: None)
        refused = await http_client.post(url, json=wrapped, headers=headers)

    assert refused.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, refused.text
    assert "401507" in refused.text, refused.text
    # The sale was recorded before the response could be built. Refusing does not
    # take it back — which is exactly why the client must repeat rather than
    # treat the 503 as "it did not happen".
    assert await _tranlog_count(cart_id) == 1

    repeated = await http_client.post(url, json=wrapped, headers=headers)

    assert repeated.status_code == status.HTTP_200_OK, repeated.text
    data = repeated.json()["data"]
    assert data["cartStatus"] == "Completed"
    assert data["transactionNo"] == 5252, data
    assert data["receiptNo"] == 5253, data
    assert data["signedSnapshot"] is not None, "the repeat has to hand back what the 503 could not"
    # Still one: the repeat returned the recorded transaction instead of booking
    # a second one against the same cart.
    assert await _tranlog_count(cart_id) == 1


@pytest.mark.asyncio
async def test_retried_carried_finalize_is_idempotent(http_client, snapshot_keys):
    """B2: a retried finalize (same snapshot + finalize context) returns the same
    result, not a 500 — the duplicate insert is handled idempotently."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, _ = await _create_cart_with_items(http_client)
    paying_snapshot = await _pay_off(http_client, cart_id, snapshot)

    ctx = {"seq": 5151, "receiptNo": 5152, "transactionDatetime": "2026-06-14T02:03:04"}
    wrapped = {"signedSnapshot": paying_snapshot, "payload": ctx}

    r1 = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", json=wrapped, headers=headers
    )
    assert r1.status_code == status.HTTP_200_OK, r1.text
    assert r1.json()["data"]["transactionNo"] == 5151

    # Retry the exact same finalize: reconstructs from the same paying snapshot,
    # produces the same (cart_id, seq) -> idempotent, same result, no 500.
    r2 = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", json=wrapped, headers=headers
    )
    assert r2.status_code == status.HTTP_200_OK, r2.text
    assert r2.json()["data"]["transactionNo"] == 5151


async def _bill_a_sale(http_client, terminal_id, headers):
    """Create -> add item -> subtotal -> pay -> (legacy) bill. Returns
    (transaction_no, paid_amount) for the committed sale."""
    cart_id, snapshot, _ = await _create_cart_with_items(http_client)
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = int(r.json()["data"]["balanceAmount"])
    snapshot = r.json()["data"]["signedSnapshot"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"paymentCode": "01", "amount": balance}]},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    snapshot = r.json()["data"]["signedSnapshot"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    return r.json()["data"]["transactionNo"], balance


@pytest.mark.asyncio
async def test_carried_void_uses_signed_finalize_context(http_client, snapshot_keys):
    """Void carries a signed finalize-context envelope (issue #156, B案): the void
    draws its per-open seq / receipt_no from the verified carried values (a stable
    cart_id, not a server counter), routed through the same envelope middleware."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = 9
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    headers = _api_headers()

    transaction_no, paid = await _bill_a_sale(http_client, terminal_id, headers)

    # Build the void's signed finalize-context envelope (the terminal would do this).
    from types import SimpleNamespace

    terminal_info = SimpleNamespace(tenant_id=tenant_id, store_code=store_code, terminal_no=terminal_no)
    void_env = snapshot_service.build_finalize_context_envelope(
        cart_id="void-cart-it-0001",
        seq=6543,  # distinctive per-open seq a server counter would never produce
        receipt_no=6544,
        transaction_datetime="2026-06-14T07:08:09",
        terminal_info=terminal_info,
    )
    assert void_env is not None

    wrapped = {"signedSnapshot": void_env, "payload": [{"paymentCode": "01", "amount": paid}]}
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}"
        f"/transactions/{transaction_no}/void?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    void_data = r.json()["data"]
    assert void_data["transactionNo"] == 6543, void_data
    assert void_data["receiptNo"] == 6544, void_data


@pytest.mark.asyncio
async def test_carried_void_rejects_tampered_seq(http_client, snapshot_keys):
    """Forging the carried void numbering (re-writing seq after signing) is rejected."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = 9
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    headers = _api_headers()

    transaction_no, paid = await _bill_a_sale(http_client, terminal_id, headers)

    from types import SimpleNamespace

    terminal_info = SimpleNamespace(tenant_id=tenant_id, store_code=store_code, terminal_no=terminal_no)
    void_env = snapshot_service.build_finalize_context_envelope(
        cart_id="void-cart-it-0002",
        seq=10,
        receipt_no=11,
        transaction_datetime="2026-06-14T07:08:09",
        terminal_info=terminal_info,
    )
    void_env["finalize_context"]["seq"] = 999999  # tamper after signing

    wrapped = {"signedSnapshot": void_env, "payload": [{"paymentCode": "01", "amount": paid}]}
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}"
        f"/transactions/{transaction_no}/void?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )
    assert r.status_code != status.HTTP_200_OK, r.text


@pytest.mark.asyncio
async def test_required_mode_rejects_snapshotless_mutation(http_client, snapshot_keys, monkeypatch):
    """B3: in REQUIRED mode a snapshot-less mutating request is rejected."""
    from app.config.settings import settings

    terminal_id = _terminal_id()
    headers = _api_headers()
    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    monkeypatch.setattr(settings, "CART_REQUEST_SNAPSHOT_MODE", "REQUIRED")

    # A snapshot-less mutating request is rejected.
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": 1}],
        headers=headers,
    )
    assert r.status_code != status.HTTP_200_OK, r.text


@pytest.mark.asyncio
async def test_snapshotless_bill_with_finalize_context_is_rejected(http_client, snapshot_keys):
    """bug_006: a finalize context (client-supplied numbering) on the
    cache-authoritative path (no signed snapshot) must be rejected — otherwise a
    phase-1 client could forge the transaction/receipt numbers."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, _ = await _create_cart_with_items(http_client)
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    balance = r.json()["data"]["balanceAmount"]
    snapshot = r.json()["data"]["signedSnapshot"]
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"paymentCode": "01", "amount": int(balance)}]},
        headers=headers,
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    # No wrapped body / no signed snapshot, but a finalize context is supplied.
    forged = {"seq": 1, "receiptNo": 2, "transactionDatetime": "2026-06-14T03:04:05"}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
        json=forged,
        headers=headers,
    )
    # Carried numbering requires the stateless (snapshot) path -> rejected.
    assert r.status_code != status.HTTP_200_OK, r.text


@pytest.mark.asyncio
async def test_tampered_wrapped_request_is_rejected(http_client, snapshot_keys):
    """A tampered carried snapshot is rejected before the operation is applied (US3)."""
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    # Tamper: bump a monetary field inside the carried cart document.
    tampered = {**snapshot}
    cart_doc = dict(tampered.get("cartDocument") or tampered.get("cart_document") or {})
    cart_doc["balanceAmount"] = 0.01
    if "cartDocument" in tampered:
        tampered["cartDocument"] = cart_doc
    else:
        tampered["cart_document"] = cart_doc

    wrapped = {"signedSnapshot": tampered, "payload": [{"itemCode": "49-01", "quantity": 1}]}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )
    # Signature mismatch -> rejected (not a successful 200).
    assert r.status_code != status.HTTP_200_OK, r.text

    # The per-request rejection is audited, and records which API it came from.
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"db_cart_{os.environ.get('TENANT_ID')}")
    logs = [
        doc
        async for doc in db[settings.DB_COLLECTION_NAME_LOG_CART_RESTORE].find(
            {"cart_id": cart_id, "result": "rejected"}
        )
    ]
    assert logs, "expected a rejected audit record for the tampered request"
    assert any((log.get("api_path") or "").endswith("/lineItems") for log in logs), logs


@pytest.mark.asyncio
async def test_snapshot_for_a_different_cart_is_rejected(http_client, snapshot_keys):
    """A validly-signed snapshot of cart B may not be used against cart A's URL.

    On the stateless path the reconstructed cart replaces the cached one, so
    without this check the operation would silently be applied to — and the
    response returned for — a cart the client never addressed (issue #156).
    """
    terminal_id = _terminal_id()
    headers = _api_headers()

    cart_a, _, _ = await _create_cart_with_items(http_client)
    cart_b, snapshot_b, _ = await _create_cart_with_items(http_client)
    assert cart_a != cart_b
    assert snapshot_b is not None

    # Address cart A but carry cart B's (genuine, untampered) snapshot.
    wrapped = {"signedSnapshot": snapshot_b, "payload": [{"itemCode": "49-01", "quantity": 1}]}
    r = await http_client.post(
        f"/api/v1/carts/{cart_a}/lineItems?terminal_id={terminal_id}",
        json=wrapped,
        headers=headers,
    )

    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
    assert r.json()["code"] == status.HTTP_400_BAD_REQUEST
    # Dedicated error code so the mismatch is distinguishable from a tamper.
    assert "401512" in r.text, r.text

    # The rejection is audited under the snapshot's cart_id (cart B).
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"db_cart_{os.environ.get('TENANT_ID')}")
    logs = [
        doc
        async for doc in db[settings.DB_COLLECTION_NAME_LOG_CART_RESTORE].find(
            {"cart_id": cart_b, "result": "rejected"}
        )
    ]
    assert logs, "expected a rejected audit record for the cross-cart request"


@pytest.mark.asyncio
async def test_gzip_compressed_wrapped_request_is_accepted(http_client, snapshot_keys):
    """A gzip-compressed wrapped request takes the stateless path (issue #156, FR-009).

    Without request decompression the peel middleware would fail to JSON-parse
    the compressed bytes and silently treat it as a legacy, snapshot-less request
    — taking the cache-authoritative path instead of the stateless one. So this
    also wipes the server-side copy: succeeding proves the snapshot was read.
    """
    import gzip as gzip_module
    import json as json_module

    terminal_id = _terminal_id()
    cart_id, snapshot, line_count_before = await _create_cart_with_items(http_client)
    await _delete_cart_everywhere(cart_id)

    wrapped = {"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]}
    body = gzip_module.compress(json_module.dumps(wrapped).encode())

    headers = {**_api_headers(), "Content-Encoding": "gzip"}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        content=body,
        headers=headers,
    )

    assert r.status_code == status.HTTP_200_OK, r.text
    assert len(r.json()["data"]["lineItems"]) == line_count_before + 1


@pytest.mark.asyncio
async def test_oversized_compressed_request_is_refused(http_client, snapshot_keys):
    """A body that expands past the ceiling is refused before it is fully expanded."""
    import gzip as gzip_module

    terminal_id = _terminal_id()
    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    # Small on the wire, far past the guard once expanded.
    bomb = gzip_module.compress(b"a" * (settings.MAX_REQUEST_BODY_BYTES + 1024))
    headers = {**_api_headers(), "Content-Encoding": "gzip"}
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        content=bomb,
        headers=headers,
    )

    assert r.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, r.text
    assert "401509" in r.text, r.text


@pytest.mark.asyncio
async def test_oversized_uncompressed_request_is_refused(http_client, snapshot_keys):
    """Not compressing must not be a way past the ceiling (issue #195).

    The decompression middleware passes an uncompressed body straight through,
    so the ceiling has to be applied where the envelope peel buffers the body.
    Driven through the real middleware stack, so it also covers the peel being
    registered with a ceiling at all — the unit tests build it directly. It does
    not pin down WHICH ceiling: the service setting and the library default are
    the same 1 MB, so a missing max_bytes would still refuse here.
    """
    terminal_id = _terminal_id()
    cart_id, _, _ = await _create_cart_with_items(http_client)

    # Plainly over the guard, with no compression to expand.
    oversized = b'[{"itemCode": "' + b"a" * (settings.MAX_REQUEST_BODY_BYTES + 1024) + b'"}]'
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        content=oversized,
        headers=_api_headers(),
    )

    assert r.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, r.text
    assert "401509" in r.text, r.text


@pytest.mark.asyncio
async def test_oversized_request_is_refused_without_credentials(http_client, snapshot_keys):
    """The refusal does not wait for authentication.

    The peel runs ahead of the route's dependencies, so an unauthenticated
    caller reaches the buffer before any 401 could be raised. The body must be
    refused on size, not read in full and then rejected on credentials.
    """
    oversized = b'[{"itemCode": "' + b"a" * (settings.MAX_REQUEST_BODY_BYTES + 1024) + b'"}]'
    r = await http_client.post(
        f"/api/v1/carts/no-such-cart/lineItems?terminal_id={_terminal_id()}",
        content=oversized,
        headers={"Content-Type": "application/json"},
    )

    assert r.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, r.text


@pytest.mark.asyncio
async def test_a_line_that_would_outgrow_the_snapshot_is_refused(http_client, snapshot_keys, monkeypatch):
    """The server must never issue a snapshot the client cannot send back (#200).

    The snapshot rides in the request body on every mutating call, so the
    request ceiling bounds it — while the cart itself had no bound. Past that
    point the terminal holds an envelope it cannot return: every following
    request is answered 413, and under CART_REQUEST_SNAPSHOT_MODE=REQUIRED the
    cart can be neither completed nor cancelled.

    The budget is lowered rather than adding thousands of line items; what is
    being tested is the refusal, not the arithmetic.
    """
    terminal_id = _terminal_id()
    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    # Below what the cart already weighs, so the next add crosses it.
    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 512)

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=_api_headers(),
    )

    assert r.status_code == status.HTTP_409_CONFLICT, r.text
    assert "401516" in r.text, r.text


@pytest.mark.asyncio
async def test_a_refused_line_leaves_the_cart_workable(http_client, snapshot_keys, monkeypatch):
    """Refused at the add, so the basket can still be settled.

    Committing the line and refusing the next request instead would reproduce
    the very state #200 is about: a cart already too big to carry. The operator
    has to be able to settle what is in the cart and start another transaction
    for the rest.
    """
    terminal_id = _terminal_id()
    cart_id, snapshot, line_count_before = await _create_cart_with_items(http_client)

    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 512)
    refused = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=_api_headers(),
    )
    assert refused.status_code == status.HTTP_409_CONFLICT, refused.text

    # The snapshot the client still holds is the one from before the refusal,
    # and it must still be good: nothing was committed against it.
    monkeypatch.undo()
    after = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=_api_headers(),
    )

    assert after.status_code == status.HTTP_200_OK, after.text
    assert len(after.json()["data"]["lineItems"]) == line_count_before + 1, "the refused line was left behind"


@pytest.mark.asyncio
async def test_a_subtotal_discount_that_would_outgrow_the_snapshot_is_refused(
    http_client, snapshot_keys, monkeypatch
):
    """Line items are not the only way a cart grows (#200, external review).

    A discount list is taken from the request and appended, with nothing
    bounding its length or how many times it is sent — so guarding only the
    add-item path left the cart able to outgrow its snapshot by another route.
    """
    terminal_id = _terminal_id()
    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    # A subtotal discount is only accepted once the cart has been subtotalled.
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=_api_headers(),
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    snapshot = r.json()["data"]["signedSnapshot"]

    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 512)

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/discounts?terminal_id={terminal_id}",
        json={
            "signedSnapshot": snapshot,
            "payload": [{"discountType": "DiscountAmount", "discountValue": 1}],
        },
        headers=_api_headers(),
    )

    assert r.status_code == status.HTTP_409_CONFLICT, r.text
    assert "401516" in r.text, r.text


@pytest.mark.asyncio
async def test_paying_is_not_refused_by_the_budget(http_client, snapshot_keys, monkeypatch):
    """Refusing a payment would be the deadlock the budget exists to prevent.

    Paying is how a cart is brought to a close. A cart that is over budget —
    opened before this guard, or after the ceiling was lowered — has to remain
    finishable, so the completion paths are deliberately exempt.
    """
    terminal_id = _terminal_id()
    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=_api_headers(),
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    data = r.json()["data"]
    balance, snapshot = data["balanceAmount"], data["signedSnapshot"]

    # Budget far below what this cart already weighs: paying must still work.
    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 512)

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={
            "signedSnapshot": snapshot,
            "payload": [{"paymentCode": "01", "amount": balance}],
        },
        headers=_api_headers(),
    )

    assert r.status_code == status.HTTP_200_OK, r.text


@pytest.mark.asyncio
async def test_a_cart_already_over_budget_can_still_be_finished(http_client, snapshot_keys, monkeypatch):
    """The migration case: a cart that was already too big when the guard arrived.

    A cart opened before this guard existed — or after the ceiling was lowered —
    can be over budget from its first guarded request. Refusing it would strand a
    basket at the till, which is the state #200 exists to prevent, so the guard
    must not reach the paths that bring a cart to a close.

    Walked end to end rather than asserted on one call: subtotal, pay and bill all
    have to work, because a cart that can be paid but not billed is stranded just
    the same.
    """
    terminal_id = _terminal_id()
    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    # From here on the cart is over budget on every request.
    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 512)

    # Adding is refused, as designed.
    refused = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 1}]},
        headers=_api_headers(),
    )
    assert refused.status_code == status.HTTP_409_CONFLICT, refused.text

    # Everything that closes the cart out must still work.
    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=_api_headers(),
    )
    assert r.status_code == status.HTTP_200_OK, f"subtotal refused: {r.text}"
    data = r.json()["data"]
    balance, snapshot = data["balanceAmount"], data["signedSnapshot"]

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"paymentCode": "01", "amount": balance}]},
        headers=_api_headers(),
    )
    assert r.status_code == status.HTTP_200_OK, f"payment refused: {r.text}"
    snapshot = r.json()["data"]["signedSnapshot"]

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=_api_headers(),
    )
    assert r.status_code == status.HTTP_200_OK, f"bill refused, the cart is stranded: {r.text}"
    assert r.json()["data"].get("transactionNo"), "the transaction did not complete"


@pytest.mark.asyncio
async def test_an_over_budget_cart_can_still_be_cancelled(http_client, snapshot_keys, monkeypatch):
    """The other way out. Refusing this strands the basket just as badly."""
    terminal_id = _terminal_id()
    cart_id, snapshot, _ = await _create_cart_with_items(http_client)

    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 512)

    r = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=_api_headers(),
    )

    assert r.status_code == status.HTTP_200_OK, f"cancel refused, the cart is stranded: {r.text}"
