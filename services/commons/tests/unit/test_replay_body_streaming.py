# Copyright 2026 masa@kugel
"""A streamed response gets through a middleware that read the request body.

replay_body hands the body back to the app, and used to answer every call after
it with a fabricated http.disconnect. Starlette's StreamingResponse watches that
same receive while it streams, saw the "disconnect" at once and stopped: the
caller got a 200 and an empty body.
"""
import asyncio
import gzip

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import StreamingResponse
from starlette.routing import Route

from kugel_common.middleware.http_compression import RequestDecompressionMiddleware, replay_body
from kugel_common.middleware.request_body_limit import RequestBodySizeLimitMiddleware

CHUNKS = [f"chunk-{i}\n".encode() for i in range(50)]


async def _stream(request):
    await request.body()

    async def chunks():
        for chunk in CHUNKS:
            await asyncio.sleep(0.001)  # long enough for a disconnect watcher to act
            yield chunk

    return StreamingResponse(chunks(), media_type="text/plain")


def _as_uvicorn(app):
    """Advertise ASGI spec 2.3, as uvicorn's h11 server does: below 2.4,
    StreamingResponse watches receive for a disconnect while it streams."""

    async def wrapped(scope, receive, send):
        scope = {**scope, "asgi": {"version": "3.0", "spec_version": "2.3"}}
        await app(scope, receive, send)

    return wrapped


def _app(middleware):
    return _as_uvicorn(middleware(Starlette(routes=[Route("/stream", _stream, methods=["POST"])])))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "middleware, body, headers",
    [
        (RequestBodySizeLimitMiddleware, b'{"a": 1}', {"content-type": "application/json"}),
        (
            RequestDecompressionMiddleware,
            gzip.compress(b'{"a": 1}'),
            {"content-type": "application/json", "content-encoding": "gzip"},
        ),
    ],
)
async def test_the_whole_stream_arrives(middleware, body, headers):
    transport = httpx.ASGITransport(app=_app(middleware))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/stream", content=body, headers=headers)

    assert response.status_code == 200
    assert response.content == b"".join(CHUNKS)


@pytest.mark.asyncio
async def test_after_the_body_the_real_receive_answers():
    calls = []

    async def receive():
        calls.append(1)
        return {"type": "http.disconnect"}

    replayed = replay_body(b"abc", receive)

    assert (await replayed())["body"] == b"abc"
    assert (await replayed())["type"] == "http.disconnect"
    assert calls == [1], "the disconnect must come from the client's receive, not be made up"
