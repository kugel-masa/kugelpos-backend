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
import os
import zlib

import pytest

from kugel_common.middleware.http_compression import (
    RequestBodyTooLarge,
    RequestDecompressionMiddleware,
    read_body_capped,
    replace_body_headers,
)


def _scope(headers):
    return {"type": "http", "method": "POST", "headers": headers}


def _receive_chunks(chunks):
    """Deliver the body across several http.request messages, as uvicorn does."""
    remaining = list(chunks)

    async def receive():
        if remaining:
            chunk = remaining.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(remaining)}
        return {"type": "http.disconnect"}

    return receive


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

    messages = await _collect_response(middleware, _scope([(b"content-encoding", b"gzip")]), _receive_for(bomb))

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


@pytest.mark.asyncio
async def test_body_split_across_chunks_is_reassembled():
    """uvicorn hands a large body over in several messages, not one.

    A 50-line cart snapshot is ~50KB raw, well into the range where the body
    arrives split — expanding only the first chunk would corrupt every large
    request.
    """
    payload = json.dumps({"payload": [{"i": n} for n in range(500)]}).encode()
    compressed = gzip.compress(payload)
    midpoint = len(compressed) // 2
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    await middleware(
        _scope([(b"content-encoding", b"gzip")]),
        _receive_chunks([compressed[:midpoint], compressed[midpoint:]]),
        None,
    )

    assert app.body == payload


@pytest.mark.asyncio
async def test_unsupported_encoding_is_refused_not_passed_through():
    """An encoding we cannot expand must not reach the app still compressed.

    Passing it through would leave a JSON-parsing middleware downstream reading
    it as "not a wrapped request" and silently taking the legacy path — the exact
    failure this middleware exists to prevent.
    """
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000, error_code="401509")

    messages = await _collect_response(middleware, _scope([(b"content-encoding", b"zstd")]), _receive_for(b"whatever"))

    assert messages[0]["status"] == 415
    assert app.body is None


@pytest.mark.asyncio
async def test_chained_encoding_is_refused():
    """ "gzip, br" is legal HTTP but we expand a single encoding only."""
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    messages = await _collect_response(
        middleware, _scope([(b"content-encoding", b"gzip, br")]), _receive_for(b"whatever")
    )

    assert messages[0]["status"] == 415
    assert app.body is None


@pytest.mark.asyncio
async def test_identity_encoding_passes_through():
    """ "identity" explicitly means no encoding, so it is not an error."""
    payload = b'{"payload": []}'
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    await middleware(_scope([(b"content-encoding", b"identity")]), _receive_for(payload), None)

    assert app.body == payload


@pytest.mark.asyncio
async def test_encoding_header_is_matched_case_insensitively():
    """Header values are not case-sensitive; a client may send "GZIP"."""
    payload = b'{"payload": []}'
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    await middleware(_scope([(b"content-encoding", b"  GZIP ")]), _receive_for(gzip.compress(payload)), None)

    assert app.body == payload


@pytest.mark.asyncio
async def test_brotli_body_is_refused_when_the_library_is_absent():
    """Degrade to a clear refusal, never to a silently mis-read body."""
    import kugel_common.middleware.http_compression as module

    original = module.brotli
    module.brotli = None
    try:
        app = _Recorder()
        middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)
        messages = await _collect_response(
            middleware, _scope([(b"content-encoding", b"br")]), _receive_for(b"anything")
        )
        assert messages[0]["status"] == 413
        assert app.body is None
    finally:
        module.brotli = original


@pytest.mark.asyncio
async def test_disconnect_mid_body_does_not_invoke_the_app():
    """The client vanished; there is no complete body to act on."""
    app = _Recorder()
    middleware = RequestDecompressionMiddleware(app, max_bytes=1_000_000)

    async def receive():
        return {"type": "http.disconnect"}

    await middleware(_scope([(b"content-encoding", b"gzip")]), receive, None)

    assert app.body is None


# =========================================================================
# The read itself is bounded (issue #195)
# =========================================================================


@pytest.mark.asyncio
async def test_read_body_capped_returns_the_whole_body_within_the_ceiling():
    body = b"x" * 100
    assert await read_body_capped(_receive_for(body), 100) == body


@pytest.mark.asyncio
async def test_read_body_capped_reassembles_chunks():
    assert await read_body_capped(_receive_chunks([b"ab", b"cd", b"ef"]), 16) == b"abcdef"


@pytest.mark.asyncio
async def test_read_body_capped_stops_at_the_chunk_that_crosses_the_ceiling():
    """Refusing after reading to the end would mean holding what we refuse."""
    delivered = 0

    async def receive():
        nonlocal delivered
        delivered += 1
        return {"type": "http.request", "body": b"x" * 8, "more_body": True}

    with pytest.raises(RequestBodyTooLarge):
        await read_body_capped(receive, 16)
    assert delivered == 3, "the read continued past the chunk that crossed the limit"


@pytest.mark.asyncio
async def test_read_body_capped_reports_a_disconnect_as_none():
    async def receive():
        return {"type": "http.disconnect"}

    assert await read_body_capped(receive, 16) is None


@pytest.mark.asyncio
async def test_oversized_compressed_body_is_refused_before_expansion():
    """A compressed body larger than the largest expansion we would allow.

    It cannot be within policy once expanded, so it is refused as it arrives
    rather than held while we find that out.
    """
    middleware = RequestDecompressionMiddleware(_Recorder(), max_bytes=1024)
    # Random bytes barely compress, so the compressed form stays over the ceiling.
    compressed = gzip.compress(os.urandom(4096))
    assert len(compressed) > 1024

    messages = await _collect_response(
        middleware,
        _scope([(b"content-encoding", b"gzip")]),
        _receive_for(compressed),
    )

    assert messages[0]["status"] == 413
