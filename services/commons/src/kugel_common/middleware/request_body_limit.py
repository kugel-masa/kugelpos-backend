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
A ceiling on the request body every service will hold (issue #195).

FastAPI reads the body before it resolves a route's dependencies, so the body
of an unauthenticated request is buffered in full and the 401 arrives after.
That makes the amount of memory a worker spends the caller's choice: measured
against a running cart, a single 200 MB body took the process from 108 MB to
357 MB and was answered 401. A handful of concurrent ones exhausts the worker,
and a POS service being down means checkout is down.

This is not specific to any one service or content type — it is what FastAPI
does everywhere — so the ceiling is applied outermost, ahead of every other
middleware, for all methods and all content types.

A declared ``content-length`` over the ceiling is refused up front, without
reading a byte — a body that size is refused whatever it turns out to contain.
Every other request is measured as it is delivered and abandoned at the chunk
that crosses the ceiling. The header is therefore used only to refuse early,
never to permit: what is enforced is the bytes that actually arrive, so the
guarantee does not rest on the server truncating at the declared length, on the
framing headers being present, or on which HTTP version is in play.
"""

from logging import getLogger

from fastapi import FastAPI

from kugel_common.middleware.http_compression import (
    RequestBodyTooLarge,
    read_body_capped,
    replay_body,
    send_json_error,
)

logger = getLogger(__name__)

# Bodies larger than this are refused. Services override it from their own
# settings; this default only bounds one that forgets to.
DEFAULT_MAX_REQUEST_BODY_BYTES = 1024 * 1024


def _header(scope, name: bytes) -> bytes | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value
    return None


class RequestBodySizeLimitMiddleware:
    """
    Pure-ASGI middleware refusing a request body past ``max_bytes`` (issue #195).

    Must run OUTERMOST — registered LAST — so nothing buffers ahead of it.
    """

    def __init__(self, app, max_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES, error_code: str = None):
        self.app = app
        self.max_bytes = max_bytes
        # Service-specific code for the refusal, so it is traceable in the same
        # XXYYZZ scheme as every other error. The middleware sits outside the
        # app, so it cannot raise through the normal exception handlers.
        self.error_code = error_code

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        declared = _header(scope, b"content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                # An unparseable length is the server's to reject, not ours to
                # guess at; the read below bounds it regardless.
                length = None
            if length is not None and length > self.max_bytes:
                # Nothing to read: a body this size is refused whatever arrives.
                logger.warning("Rejected request declaring %d bytes, over the %d ceiling", length, self.max_bytes)
                await send_json_error(send, 413, "Request body too large", self.error_code)
                return

        # Measure what actually arrives, whatever the headers said.
        #
        # content-length is used above only to refuse early, never to permit: a
        # declaration within the ceiling is not proof that the bytes will be.
        # That h11 truncates a body at the declared length is h11's behaviour,
        # not a property of ASGI, and an HTTP/2 server may hand DATA to the
        # application before it reconciles the total. Nor is a missing framing
        # header proof that no body is coming — that only holds because HTTP/1.1
        # demands one framing or the other. Neither assumption is load-bearing
        # here: the ceiling is enforced against delivered bytes, and a request
        # with no body simply yields empty bytes in one message.
        try:
            body = await read_body_capped(receive, self.max_bytes)
        except RequestBodyTooLarge as e:
            logger.warning("Rejected oversized request body: %s", e)
            await send_json_error(send, 413, "Request body too large", self.error_code)
            return
        if body is None:
            return

        await self.app(scope, replay_body(body), send)


def add_request_body_limit_middleware(
    app: FastAPI, max_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES, error_code: str = None
) -> None:
    """
    Bound the request body this service will hold (issue #195).

    Register LAST so it runs outermost — see RequestBodySizeLimitMiddleware.

    Args:
        app: FastAPI application instance
        max_bytes: Maximum request body size; larger is refused with 413
        error_code: Service-specific error code reported on refusal
    """
    app.add_middleware(RequestBodySizeLimitMiddleware, max_bytes=max_bytes, error_code=error_code)
