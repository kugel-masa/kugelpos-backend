# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for the phase 2 request snapshot envelope peel (issue #156)."""
import json

import pytest

from app.middleware.snapshot_envelope import (
    SnapshotEnvelopePeelMiddleware,
    peel_snapshot_envelope,
)


def test_wrapped_array_payload_is_peeled():
    """A wrapped body with an array payload yields the snapshot and the bare array."""
    env = {"schema_version": 1, "kid": "v1", "signature": "abc"}
    body = json.dumps({"signedSnapshot": env, "payload": [{"item_code": "X"}]}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot == env
    assert json.loads(new_body) == [{"item_code": "X"}]


def test_wrapped_object_payload_is_peeled():
    """A wrapped body with an object payload yields the snapshot and the bare object."""
    env = {"schema_version": 1}
    body = json.dumps({"signedSnapshot": env, "payload": {"quantity": 3}}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot == env
    assert json.loads(new_body) == {"quantity": 3}


def test_wrapped_without_payload_yields_empty_body():
    """Body-less operations wrap only the snapshot; forwarded body is empty."""
    env = {"schema_version": 1}
    body = json.dumps({"signedSnapshot": env}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot == env
    assert new_body == b""


def test_legacy_bare_array_passes_through():
    """A phase 1 bare array (no signedSnapshot key) is returned unchanged."""
    body = json.dumps([{"item_code": "X"}]).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot is None
    assert new_body == body


def test_legacy_bare_object_passes_through():
    """A phase 1 bare object without the wrapper key is returned unchanged."""
    body = json.dumps({"quantity": 3}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot is None
    assert new_body == body


def test_empty_body_passes_through():
    snapshot, new_body = peel_snapshot_envelope(b"")
    assert snapshot is None
    assert new_body == b""


def test_non_json_body_passes_through():
    """Malformed / non-JSON bodies never raise and pass through untouched."""
    body = b"not json at all"
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot is None
    assert new_body == body


def test_null_snapshot_value_is_returned_as_none_path():
    """An explicit null signedSnapshot is treated as present-but-null (no crash)."""
    body = json.dumps({"signedSnapshot": None, "payload": [{"a": 1}]}).encode()
    snapshot, new_body = peel_snapshot_envelope(body)
    assert snapshot is None
    assert json.loads(new_body) == [{"a": 1}]


# =========================================================================
# ASGI behaviour of the middleware itself (issue #156)
# =========================================================================


class _Recorder:
    """Stands in for the downstream app, capturing what it was handed."""

    def __init__(self):
        self.body = None
        self.headers = None
        self.snapshot = "<not called>"

    async def __call__(self, scope, receive, send):
        self.headers = scope["headers"]
        self.snapshot = scope.get("cart_snapshot")
        message = await receive()
        self.body = message.get("body", b"")


def _json_scope(headers=None):
    return {
        "type": "http",
        "method": "POST",
        "headers": [(b"content-type", b"application/json")] + (headers or []),
    }


def _receive_for(body: bytes):
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


@pytest.mark.asyncio
async def test_peel_corrects_content_length_to_the_payload():
    """The client measured the wrapper; the app receives only the payload.

    Leaving the original length behind would misinform anything downstream that
    trusts the header — a body-size guard, or a proxy — about a body that is now
    several kilobytes smaller.
    """
    payload = [{"itemCode": "49-01", "quantity": 1}]
    wrapped = json.dumps({"signedSnapshot": {"kid": "k1", "big": "x" * 5000}, "payload": payload}).encode()
    app = _Recorder()
    middleware = SnapshotEnvelopePeelMiddleware(app)

    await middleware(
        _json_scope([(b"content-length", str(len(wrapped)).encode())]),
        _receive_for(wrapped),
        None,
    )

    assert json.loads(app.body) == payload
    assert dict(app.headers)[b"content-length"] == str(len(app.body)).encode()
    # The wrapper's length must not survive anywhere in the header list.
    assert [v for n, v in app.headers if n == b"content-length"] == [str(len(app.body)).encode()]


@pytest.mark.asyncio
async def test_peel_leaves_a_legacy_body_and_its_length_alone():
    """A bare array is forwarded untouched, so its length is still correct."""
    body = json.dumps([{"itemCode": "49-01", "quantity": 1}]).encode()
    app = _Recorder()
    middleware = SnapshotEnvelopePeelMiddleware(app)

    await middleware(
        _json_scope([(b"content-length", str(len(body)).encode())]),
        _receive_for(body),
        None,
    )

    assert app.body == body
    assert app.snapshot is None
    assert dict(app.headers)[b"content-length"] == str(len(body)).encode()


@pytest.mark.asyncio
async def test_peel_exposes_the_snapshot_on_the_scope():
    snapshot = {"kid": "k1", "signature": "sig"}
    wrapped = json.dumps({"signedSnapshot": snapshot, "payload": []}).encode()
    app = _Recorder()
    middleware = SnapshotEnvelopePeelMiddleware(app)

    await middleware(_json_scope(), _receive_for(wrapped), None)

    assert app.snapshot == snapshot


@pytest.mark.asyncio
async def test_peel_reassembles_a_body_split_across_chunks():
    """uvicorn delivers a large body in several messages, not one."""
    payload = [{"i": n} for n in range(500)]
    wrapped = json.dumps({"signedSnapshot": {"kid": "k1"}, "payload": payload}).encode()
    midpoint = len(wrapped) // 2
    remaining = [wrapped[:midpoint], wrapped[midpoint:]]

    async def receive():
        if remaining:
            chunk = remaining.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(remaining)}
        return {"type": "http.disconnect"}

    app = _Recorder()
    middleware = SnapshotEnvelopePeelMiddleware(app)

    await middleware(_json_scope(), receive, None)

    assert json.loads(app.body) == payload


@pytest.mark.asyncio
async def test_peel_on_disconnect_does_not_invoke_the_app():
    """The client vanished mid-body.

    The app must not be handed a receive channel already drained past the
    disconnect: it would wait on a message that never arrives.
    """
    app = _Recorder()
    middleware = SnapshotEnvelopePeelMiddleware(app)

    async def receive():
        return {"type": "http.disconnect"}

    await middleware(_json_scope(), receive, None)

    assert app.snapshot == "<not called>", "the app should never have run"


@pytest.mark.asyncio
async def test_peel_skips_non_json_content_types():
    """Only JSON bodies can carry the envelope; others pass through untouched."""
    body = b"raw bytes"
    app = _Recorder()
    middleware = SnapshotEnvelopePeelMiddleware(app)

    await middleware(
        {"type": "http", "method": "POST", "headers": [(b"content-type", b"text/plain")]},
        _receive_for(body),
        None,
    )

    assert app.body == body
    assert app.snapshot is None
