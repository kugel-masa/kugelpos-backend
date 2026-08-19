# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Unit coverage for compressed request bodies (issue #156, FR-009).

Carrying the cart snapshot on every mutating request makes the upload large
enough that clients compress it. The middleware expands the body before anything
downstream reads it, and refuses an expansion that would exceed the ceiling —
a small forged body must not be able to expand into an out-of-memory condition.
"""

import gzip
import json
import zlib

import pytest

from kugel_common.middleware.http_compression import (
    RequestDecompressionMiddleware,
    replace_body_headers,
)


def _scope(headers):
    return {"type": "http", "method": "POST", "headers": headers}


def _receive_for(body: bytes):
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


class _Recorder:
    """Stands in for the downstream app, capturing what it was handed."""

    def __init__(self):
        self.body = None
        self.headers = None

    async def __call__(self, scope, receive, send):
        self.headers = scope["headers"]
        message = await receive()
        self.body = message.get("body", b"")


async def _collect_response(middleware, scope, receive):
    messages = []

    async def send(message):
        messages.append(message)

    await middleware(scope, receive, send)
    return messages


@pytest.mark.asyncio
async def test_gzip_body_is_expanded_before_the_app_sees_it():
    payload = json.dumps({"signedSnapshot": {"kid": "k1"}, "payload": [1, 2, 3]}).encode()
    compressed = gzip.compress(payload)
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    await middleware(
        _scope([(b"content-encoding", b"gzip"), (b"content-length", str(len(compressed)).encode())]),
        _receive_for(compressed),
        None,
    )

    assert app.body == payload
    header_names = [name for name, _ in app.headers]
    # content-encoding is gone: the body is no longer encoded, and leaving the
    # header would make downstream try to decode plain JSON.
    assert b"content-encoding" not in header_names
    # content-length describes the expanded body, not what the client measured.
    assert dict(app.headers)[b"content-length"] == str(len(payload)).encode()


@pytest.mark.asyncio
async def test_brotli_body_is_expanded():
    brotli = pytest.importorskip("brotli")
    payload = b'{"payload": [1, 2, 3]}'
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    await middleware(
        _scope([(b"content-encoding", b"br")]),
        _receive_for(brotli.compress(payload)),
        None,
    )

    assert app.body == payload


@pytest.mark.asyncio
async def test_uncompressed_body_passes_through_untouched():
    """Compression is optional; a plain body must reach the app unchanged."""
    payload = b'{"payload": []}'
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    await middleware(_scope([(b"content-type", b"application/json")]), _receive_for(payload), None)

    assert app.body == payload


@pytest.mark.asyncio
async def test_zip_bomb_is_refused_before_it_is_fully_expanded():
    """A tiny body that expands past the ceiling is rejected with 413."""
    bomb = gzip.compress(b"a" * (5 * 1024 * 1024))
    assert len(bomb) < 100_000, "the point is that the compressed form is small"
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1024, error_code="401509")

    messages = await _collect_response(
        middleware, _scope([(b"content-encoding", b"gzip")]), _receive_for(bomb)
    )

    assert messages[0]["status"] == 413
    assert b"401509" in messages[1]["body"]
    # The app was never invoked, so nothing acted on the oversized body.
    assert app.body is None


@pytest.mark.asyncio
async def test_body_at_the_ceiling_is_accepted():
    """The guard rejects only what exceeds the limit, not what meets it."""
    payload = b"a" * 1024
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1024)

    await middleware(_scope([(b"content-encoding", b"gzip")]), _receive_for(gzip.compress(payload)), None)

    assert app.body == payload


@pytest.mark.asyncio
async def test_undecodable_body_is_refused():
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    messages = await _collect_response(
        middleware, _scope([(b"content-encoding", b"gzip")]), _receive_for(b"not actually gzip")
    )

    assert messages[0]["status"] == 400
    assert app.body is None


@pytest.mark.asyncio
async def test_deflate_framing_is_accepted():
    payload = b'{"payload": []}'
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    await middleware(_scope([(b"content-encoding", b"deflate")]), _receive_for(zlib.compress(payload)), None)

    assert app.body == payload


def test_replace_body_headers_replaces_rather_than_appends():
    """A stale content-length left behind would win or confuse the server."""
    headers = [(b"content-length", b"999"), (b"content-type", b"application/json")]

    rewritten = replace_body_headers(headers, 12)

    assert rewritten.count((b"content-length", b"12")) == 1
    assert not any(name == b"content-length" and value == b"999" for name, value in rewritten)
    assert (b"content-type", b"application/json") in rewritten
