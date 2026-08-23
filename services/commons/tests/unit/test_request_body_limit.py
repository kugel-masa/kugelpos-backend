# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Unit coverage for the request-body ceiling every service carries (issue #195).

FastAPI reads the body before it resolves a route's dependencies, so an
unauthenticated caller's body is buffered in full and the 401 arrives after.
The ceiling runs outermost, for every method and content type, so the memory a
worker spends is not the caller's to choose.
"""

import pytest

from kugel_common.middleware.request_body_limit import (
    DEFAULT_MAX_REQUEST_BODY_BYTES,
    RequestBodySizeLimitMiddleware,
)


class _Recorder:
    """Stands in for the downstream app, capturing what it was handed."""

    def __init__(self):
        self.called = False
        self.body = None

    async def __call__(self, scope, receive, send):
        self.called = True
        message = await receive()
        self.body = message.get("body", b"")


def _scope(headers, method="POST"):
    return {"type": "http", "method": method, "headers": headers}


def _receive_for(body: bytes):
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


async def _collect(middleware, scope, receive):
    messages = []

    async def send(message):
        messages.append(message)

    await middleware(scope, receive, send)
    return messages


@pytest.mark.asyncio
async def test_declared_length_over_the_ceiling_is_refused_without_reading():
    """The refusal costs nothing: content-length is checked before a byte is read."""
    app = _Recorder()
    middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024, error_code="300005")

    read = False

    async def receive():
        nonlocal read
        read = True
        return {"type": "http.request", "body": b"x" * 4096, "more_body": False}

    messages = await _collect(middleware, _scope([(b"content-length", b"4096")]), receive)

    assert messages[0]["status"] == 413
    assert not read, "the body was read despite the declared length being refused"
    assert not app.called


@pytest.mark.asyncio
async def test_declared_length_within_the_ceiling_reaches_the_app_intact():
    """A normal request is delivered unchanged."""
    app = _Recorder()
    middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)
    receive = _receive_for(b"x" * 100)

    await middleware(_scope([(b"content-length", b"100")]), receive, None)

    assert app.called
    assert app.body == b"x" * 100


@pytest.mark.asyncio
async def test_a_body_exceeding_its_declared_length_is_still_refused():
    """content-length refuses early; it never grants permission.

    A declaration within the ceiling is not proof the bytes will be. That h11
    truncates at the declared length is h11's behaviour, not a property of ASGI
    (external review of #195), so the ceiling is enforced against what actually
    arrives.
    """
    delivered = 0

    async def receive():
        nonlocal delivered
        delivered += 1
        return {"type": "http.request", "body": b"x" * 512, "more_body": True}

    app = _Recorder()
    middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)

    messages = await _collect(middleware, _scope([(b"content-length", b"100")]), receive)

    assert messages[0]["status"] == 413, "a small declared length was taken at its word"
    assert delivered == 3
    assert not app.called


@pytest.mark.asyncio
async def test_the_ceiling_does_not_depend_on_the_content_type():
    """The gap this closes was reachable by changing one header (issue #195)."""
    for content_type in (b"application/json", b"text/plain", b"application/octet-stream"):
        app = _Recorder()
        middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)
        headers = [(b"content-length", b"4096"), (b"content-type", content_type)]

        messages = await _collect(middleware, _scope(headers), _receive_for(b"x" * 4096))

        assert messages[0]["status"] == 413, content_type
        assert not app.called, content_type


@pytest.mark.asyncio
async def test_the_ceiling_does_not_depend_on_the_method():
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        app = _Recorder()
        middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)

        messages = await _collect(
            middleware, _scope([(b"content-length", b"4096")], method=method), _receive_for(b"x" * 4096)
        )

        assert messages[0]["status"] == 413, method


@pytest.mark.asyncio
async def test_a_body_with_no_declared_length_is_bounded_as_it_is_read():
    """Nothing to check in advance, so it is held under the ceiling instead."""
    delivered = 0

    async def receive():
        nonlocal delivered
        delivered += 1
        return {"type": "http.request", "body": b"x" * 512, "more_body": True}

    app = _Recorder()
    middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)
    headers = [(b"transfer-encoding", b"chunked")]

    messages = await _collect(middleware, _scope(headers), receive)

    assert messages[0]["status"] == 413
    assert delivered == 3, "the read continued past the chunk that crossed the ceiling"
    assert not app.called


@pytest.mark.asyncio
async def test_chunked_body_within_the_ceiling_reaches_the_app():
    app = _Recorder()
    middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)
    headers = [(b"transfer-encoding", b"chunked")]

    await middleware(_scope(headers), _receive_for(b"small"), None)

    assert app.called
    assert app.body == b"small"


@pytest.mark.asyncio
async def test_a_bodyless_request_reaches_the_app():
    """A request with no body yields empty bytes; nothing has to guess first."""
    app = _Recorder()
    middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)

    await middleware(_scope([], method="GET"), _receive_for(b""), None)

    assert app.called
    assert app.body == b""


@pytest.mark.asyncio
async def test_a_body_framed_without_either_header_is_still_bounded():
    """HTTP/2 frames a body with neither content-length nor chunked.

    Reading the absence of both as "no body" would hold only because HTTP/1.1
    requires one framing or the other — it would switch the ceiling off wholesale
    on a server that speaks HTTP/2 (external review of #195).
    """
    delivered = 0

    async def receive():
        nonlocal delivered
        delivered += 1
        return {"type": "http.request", "body": b"x" * 512, "more_body": True}

    app = _Recorder()
    middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)

    messages = await _collect(middleware, _scope([]), receive)

    assert messages[0]["status"] == 413
    assert delivered == 3
    assert not app.called


@pytest.mark.asyncio
async def test_a_websocket_scope_passes_through():
    app = _Recorder()
    middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)

    await middleware({"type": "websocket", "headers": []}, _receive_for(b""), None)

    assert app.called


@pytest.mark.asyncio
async def test_an_unparseable_length_falls_back_to_reading_under_the_ceiling():
    """A malformed header must not be read as permission to skip the ceiling."""
    app = _Recorder()
    middleware = RequestBodySizeLimitMiddleware(app, max_bytes=1024)
    headers = [(b"content-length", b"not-a-number")]

    messages = await _collect(middleware, _scope(headers), _receive_for(b"x" * 4096))

    assert messages[0]["status"] == 413
    assert not app.called


def test_the_default_ceiling_matches_the_decompression_ceiling():
    """One number for what a service will hold, however the body arrives."""
    from kugel_common.middleware.http_compression import DEFAULT_MAX_DECOMPRESSED_BYTES

    assert DEFAULT_MAX_REQUEST_BODY_BYTES == DEFAULT_MAX_DECOMPRESSED_BYTES
