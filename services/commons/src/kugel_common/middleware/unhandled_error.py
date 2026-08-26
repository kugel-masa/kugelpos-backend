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
"""
Answer an unhandled exception from inside CORS (issue #202).

Registering CORSMiddleware last makes it the outermost *user* middleware, but
Starlette builds ServerErrorMiddleware around the entire user stack:

    middleware = [Middleware(ServerErrorMiddleware, ...)]
    middleware += self.user_middleware
    middleware.append(Middleware(ExceptionMiddleware, ...))

So an exception that escapes the user stack produces a 500 that never passes
through CORS. This codebase makes that the normal path rather than an edge
case: its generic handler is registered as ``@app.exception_handler(Exception)``,
and Starlette lifts handlers keyed on ``Exception`` or ``500`` out of
ExceptionMiddleware and into ServerErrorMiddleware.

A browser is given nothing for such a response — ``fetch`` raises TypeError,
XHR reports status 0 — so the one error a developer most needs to read is the
one that stays invisible.

This middleware catches what escapes and answers with the same structured 500
the handler would have produced. Registered just inside CORS, so the response
goes out through it. The handler stays registered as the backstop for anything
raised outside this layer.
"""

from logging import getLogger

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from kugel_common.exceptions.exception_handlers import build_unexpected_error_response

logger = getLogger(__name__)


def _log(message: str, *args) -> None:
    """
    Log without letting the log break what it is reporting on.

    `logging.callHandlers` does not guard the handlers it calls, so a handler
    that raises propagates into the caller. Here that would cost the 500 this
    middleware exists to deliver, or replace the original exception on the
    already-started path with a logging error. Same reasoning as `_report` in
    kugel_common.middleware.log_requests.
    """
    try:
        logger.exception(message, *args)
    except Exception:  # pragma: no cover - only a handler that raises reaches this
        pass


class UnhandledErrorMiddleware:
    """
    Pure-ASGI middleware turning an escaping exception into the structured 500.

    Must be registered immediately BEFORE CORSMiddleware, so it runs just inside
    it: outside everything that might raise, inside the layer that makes the
    answer readable.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started = False

        async def _send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception as e:
            if started:
                # The status line is already on the wire; there is no response
                # left to replace. Let it propagate the way Starlette's own
                # ServerErrorMiddleware does, so the connection is torn down
                # rather than a second response half-written over the first.
                _log("Unhandled exception after the response had started")
                raise
            response = build_unexpected_error_response(e, operation="unhandled_error_middleware")
            _log("Unhandled exception answered as %s", response.code)
            # Emitted through JSONResponse, exactly as the handler does, so the
            # body is the one clients already parse - `user_error`, `data` and
            # `operation` included. The middleware error payloads elsewhere in
            # this package use a different, smaller shape; a 500 must not
            # silently change shape depending on which layer caught it.
            await JSONResponse(status_code=response.code, content=response.model_dump())(scope, receive, send)


def add_unhandled_error_middleware(app: FastAPI) -> None:
    """
    Answer unhandled exceptions from inside CORS (issue #202).

    Register immediately BEFORE CORSMiddleware — see UnhandledErrorMiddleware.

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(UnhandledErrorMiddleware)
