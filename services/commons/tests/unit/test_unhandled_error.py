# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""An unhandled exception is answered from inside CORS (issue #202).

Registering CORSMiddleware last makes it the outermost *user* middleware, but
Starlette builds ServerErrorMiddleware around the whole user stack — so a 500
escaping the app never passed through CORS, and a browser was given no status
and no body for the one error it most needs to read.
"""
import json
import logging

import httpx
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kugel_common.exceptions import register_exception_handlers
from kugel_common.middleware.unhandled_error import (
    UnhandledErrorMiddleware,
    add_unhandled_error_middleware,
)


ORIGIN = "https://pos.example.co.jp"


def _app(*, with_middleware: bool) -> FastAPI:
    """A service-shaped app: the real handlers, CORS registered last."""
    app = FastAPI()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    @app.get("/fine")
    async def fine():
        return {"ok": True}

    if with_middleware:
        add_unhandled_error_middleware(app)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
    )
    register_exception_handlers(app)
    return app


async def _get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.get(path, headers={"Origin": ORIGIN})


@pytest.mark.asyncio
async def test_an_unhandled_500_carries_cors_headers(caplog):
    with caplog.at_level(logging.CRITICAL):
        response = await _get(_app(with_middleware=True), "/boom")

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == ORIGIN


@pytest.mark.asyncio
async def test_without_the_middleware_the_same_500_is_unreadable(caplog):
    """Pins what this fixes: CORS registered last is not on its own enough.

    Starlette lifts a handler keyed on Exception out of ExceptionMiddleware and
    into ServerErrorMiddleware, which sits outside every user layer including
    CORS — so the service's own 500 was emitted from outside it.
    """
    with caplog.at_level(logging.CRITICAL):
        response = await _get(_app(with_middleware=False), "/boom")

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_the_payload_is_the_one_the_handler_produces(caplog):
    """A 500 must not change shape depending on which layer caught it.

    The middleware error payloads elsewhere in this package use a smaller,
    camelCase shape; this one has to stay the body clients already parse.
    """
    with caplog.at_level(logging.CRITICAL):
        caught_by_middleware = await _get(_app(with_middleware=True), "/boom")
        caught_by_handler = await _get(_app(with_middleware=False), "/boom")

    theirs = caught_by_handler.json()
    ours = caught_by_middleware.json()

    assert sorted(ours) == sorted(theirs)
    assert ours["user_error"] == theirs["user_error"]
    assert ours["code"] == theirs["code"] == 500
    assert ours["message"] == theirs["message"]
    assert ours["data"] == theirs["data"] == "unexpected"
    # Only the recorded layer differs, which is the point of recording it.
    assert ours["operation"] == "unhandled_error_middleware"
    assert theirs["operation"] == "exception_handler"


@pytest.mark.asyncio
async def test_a_successful_response_is_untouched():
    response = await _get(_app(with_middleware=True), "/fine")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_an_exception_after_the_response_started_is_re_raised(caplog):
    """There is no response left to replace, so it must not try.

    Writing a second status line over one already on the wire corrupts the
    exchange; Starlette's own ServerErrorMiddleware re-raises here too.
    """

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("too late")

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(RuntimeError):
            await UnhandledErrorMiddleware(app)({"type": "http", "headers": []}, receive, send)

    assert [m["type"] for m in sent] == ["http.response.start"], "no second response was written"


@pytest.mark.asyncio
async def test_a_non_http_scope_passes_through():
    seen = []

    async def app(scope, receive, send):
        seen.append(scope["type"])

    await UnhandledErrorMiddleware(app)({"type": "lifespan"}, None, None)

    assert seen == ["lifespan"]


# =========================================================================
# The log must not cost the response it is reporting on
# =========================================================================


class _RaisingHandler(logging.Handler):
    """A handler with no emit guard of its own.

    `logging.callHandlers` does not wrap the handlers it calls, so such a
    handler propagates into the caller — which here would be the failure path
    that still owes the client a response.
    """

    def emit(self, record):
        raise OSError("log destination is gone")


@pytest.fixture
def raising_log_handler():
    from kugel_common.middleware import unhandled_error

    handler = _RaisingHandler()
    unhandled_error.logger.addHandler(handler)
    try:
        yield
    finally:
        unhandled_error.logger.removeHandler(handler)


@pytest.mark.asyncio
async def test_a_readable_500_survives_a_failing_log(raising_log_handler):
    """Losing the log must not also lose what this middleware exists to deliver.

    Asserted on the CORS header, not on the status: a logging error escaping
    this layer still ends up as a 500, because ServerErrorMiddleware catches it
    further out — but that is the unreadable 500 from outside CORS, which is
    precisely the state #202 is about. Only the header tells the two apart.
    """
    response = await _get(_app(with_middleware=True), "/boom")

    assert response.status_code == 500
    assert response.json()["user_error"]["code"] == "900999"
    assert response.headers.get("access-control-allow-origin") == ORIGIN


@pytest.mark.asyncio
async def test_a_failing_log_does_not_replace_the_original_exception(raising_log_handler):
    """On the already-started path the exception is re-raised, and it must be *the* one.

    A logging error surfacing here would bury the fault that actually broke the
    request behind one from the reporting of it.
    """

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("the real fault")

    async def send(message):
        pass

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    with pytest.raises(RuntimeError, match="the real fault"):
        await UnhandledErrorMiddleware(app)({"type": "http", "headers": []}, receive, send)
