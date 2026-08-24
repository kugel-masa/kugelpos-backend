# Copyright 2025 masa@kugel
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
HTTP response compression middleware setup shared by all services.

Responses are gzip-compressed only when the client sends
``Accept-Encoding: gzip``, so clients that do not opt in are unaffected.
Request-body decompression (``Content-Encoding: gzip`` / ``br`` from clients)
is handled by :class:`RequestDecompressionMiddleware`, added for the
client-carried cart (issue #156, FR-009): carrying the cart snapshot on every
mutating request makes the upload large enough to be worth compressing. It
enforces a decompressed-size ceiling so a small forged body cannot expand into
an out-of-memory condition.

The same ceiling is what :func:`read_body_capped` applies, so any middleware
that has to buffer a body — here, or the cart's snapshot-envelope peel — holds
a bounded amount for a caller who has not been authenticated yet (issue #195).
"""

# zlib with wbits=47 auto-detects gzip and zlib framing, so the gzip module
# itself is not needed here.
import json
import zlib
from logging import getLogger

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

logger = getLogger(__name__)

try:  # brotli ships as a wheel on every platform we target, but stay degradable
    import brotli
except ImportError:  # pragma: no cover - exercised only on a stripped install
    brotli = None

# Responses smaller than this are sent uncompressed; gzip overhead is not
# worth it below ~1KB.
GZIP_MINIMUM_SIZE_BYTES = 1024

# Level 6 is the speed/ratio sweet spot; 9 burns CPU for a few extra percent.
GZIP_COMPRESS_LEVEL = 6


def add_gzip_response_middleware(
    app: FastAPI,
    minimum_size: int = GZIP_MINIMUM_SIZE_BYTES,
    compresslevel: int = GZIP_COMPRESS_LEVEL,
) -> None:
    """
    Enable gzip compression of responses for clients that accept it.

    Must be registered AFTER the log_requests middleware (Starlette runs the
    last-added middleware outermost): log_requests JSON-parses the response
    body for the request log, so it has to observe the body before this
    middleware compresses it.

    Args:
        app: FastAPI application instance
        minimum_size: Minimum response body size in bytes to compress
        compresslevel: gzip compression level (1-9)
    """
    app.add_middleware(GZipMiddleware, minimum_size=minimum_size, compresslevel=compresslevel)


# Decompressed request bodies larger than this are refused. Callers override it
# from their own settings; this default only bounds a service that forgets to.
DEFAULT_MAX_DECOMPRESSED_BYTES = 1024 * 1024

# Read the compressed stream in chunks so the ceiling is enforced DURING
# expansion — checking only the final size would mean already holding it.
_DECOMPRESS_CHUNK_BYTES = 64 * 1024


class RequestBodyTooLarge(Exception):
    """Raised when a request body exceeds the configured ceiling."""


async def read_body_capped(receive, max_bytes: int) -> bytes | None:
    """
    Buffer a whole request body, refusing to hold more than ``max_bytes``.

    Any ASGI middleware that needs the full body has to buffer it, and buffering
    without a ceiling lets an unauthenticated caller decide how much memory the
    worker spends: middleware runs ahead of the route's dependencies, so the body
    is already read by the time a 401 could be raised. The ceiling is checked as
    each chunk arrives, so an oversized body is abandoned mid-read rather than
    measured once it is already held.

    Accumulates into a ``bytearray``: ``bytes`` concatenation would recopy
    everything read so far on every chunk, making the cost quadratic in the
    body size — which is itself attacker-chosen.

    Args:
        receive: The ASGI receive callable
        max_bytes: Ceiling in bytes; a body exceeding it is refused

    Returns:
        The body bytes, or None if the client disconnected mid-body.

    Raises:
        RequestBodyTooLarge: The body grew past ``max_bytes``.
    """
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.request":
            body += message.get("body", b"")
            if len(body) > max_bytes:
                raise RequestBodyTooLarge(f"request body exceeds {max_bytes} bytes")
            if not message.get("more_body", False):
                break
        elif message["type"] == "http.disconnect":
            return None
    return bytes(body)


def _decompress_gzip(raw: bytes, max_bytes: int) -> bytes:
    """Expand a gzip/deflate body, refusing to exceed max_bytes."""
    # wbits 47 = auto-detect gzip or zlib framing.
    decompressor = zlib.decompressobj(47)
    out = bytearray()
    for start in range(0, len(raw), _DECOMPRESS_CHUNK_BYTES):
        out += decompressor.decompress(raw[start : start + _DECOMPRESS_CHUNK_BYTES], max_bytes - len(out) + 1)
        if len(out) > max_bytes:
            raise RequestBodyTooLarge(f"decompressed body exceeds {max_bytes} bytes")
    out += decompressor.flush()
    if len(out) > max_bytes:
        raise RequestBodyTooLarge(f"decompressed body exceeds {max_bytes} bytes")
    return bytes(out)


def _decompress_brotli(raw: bytes, max_bytes: int) -> bytes:
    """Expand a brotli body, refusing to exceed max_bytes."""
    if brotli is None:
        raise RequestBodyTooLarge("brotli request bodies are not supported on this install")
    decompressor = brotli.Decompressor()
    out = bytearray()
    for start in range(0, len(raw), _DECOMPRESS_CHUNK_BYTES):
        out += decompressor.process(raw[start : start + _DECOMPRESS_CHUNK_BYTES])
        if len(out) > max_bytes:
            raise RequestBodyTooLarge(f"decompressed body exceeds {max_bytes} bytes")
    return bytes(out)


_DECOMPRESSORS = {
    b"gzip": _decompress_gzip,
    b"deflate": _decompress_gzip,
    b"br": _decompress_brotli,
}


class RequestDecompressionMiddleware:
    """
    Pure-ASGI middleware that expands a compressed request body (issue #156).

    Clients that carry the cart snapshot on every mutating request may send the
    body with ``Content-Encoding: gzip`` or ``br`` (both standard in .NET 8).
    This expands it before anything downstream reads the body, so endpoints,
    the snapshot-envelope peel, and the request log all see plain JSON.

    Must be registered so it runs OUTERMOST — i.e. added LAST, after the peel
    middleware. The peel JSON-parses the body, and a still-compressed body would
    not parse: instead of failing it would look like a legacy request with no
    snapshot and silently take the cache-authoritative path.

    Bodies whose expansion exceeds ``max_bytes`` are refused with 413 before the
    expansion completes, so a small forged body cannot exhaust memory.
    """

    def __init__(self, app, max_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES, error_code: str = None):
        self.app = app
        self.max_bytes = max_bytes
        # Service-specific code for the refusal, so the rejection is traceable in
        # the same XXYYZZ scheme as every other error. The middleware sits outside
        # the app, so it cannot raise through the normal exception handlers.
        self.error_code = error_code

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        encoding = None
        for name, value in scope.get("headers", []):
            if name == b"content-encoding":
                encoding = value.strip().lower()
                break
        if encoding is None or encoding == b"identity":
            await self.app(scope, receive, send)
            return
        if encoding not in _DECOMPRESSORS:
            # Refuse rather than pass an encoding we cannot expand through: the
            # body would reach the app still compressed, and a JSON-parsing
            # middleware downstream would read that as "not a wrapped request"
            # and silently take the legacy path. That includes a comma-separated
            # chain such as "gzip, br", which we deliberately do not support.
            logger.warning("Rejected unsupported Content-Encoding: %s", encoding.decode(errors="replace"))
            await send_json_error(
                send,
                415,
                f"Unsupported Content-Encoding: {encoding.decode(errors='replace')}",
                self.error_code,
            )
            return

        # The compressed bytes are capped too. A body that arrives larger than the
        # largest expansion we would allow cannot be within policy once expanded,
        # so there is no reason to hold it while finding that out.
        try:
            body = await read_body_capped(receive, self.max_bytes)
        except RequestBodyTooLarge as e:
            logger.warning("Rejected oversized compressed request body: %s", e)
            await send_json_error(send, 413, "Request body too large", self.error_code)
            return
        if body is None:
            return

        try:
            body = _DECOMPRESSORS[encoding](body, self.max_bytes)
        except RequestBodyTooLarge as e:
            logger.warning("Rejected oversized compressed request body: %s", e)
            await send_json_error(send, 413, "Request body too large", self.error_code)
            return
        except Exception as e:
            logger.warning("Rejected undecodable %s request body: %s", encoding.decode(), e)
            await send_json_error(send, 400, "Malformed compressed request body", self.error_code)
            return

        scope = dict(scope)
        scope["headers"] = replace_body_headers(scope["headers"], len(body), drop_content_encoding=True)

        await self.app(scope, replay_body(body), send)


def replace_body_headers(headers, length: int, drop_content_encoding: bool = False) -> list:
    """
    Return headers with content-length set to ``length``.

    Any middleware that rewrites a request body has to correct content-length:
    the body reaching the app is no longer the one the client measured, and a
    stale value misleads anything that trusts the header (size guards, proxies).

    Args:
        headers: ASGI raw header list
        length: Byte length of the body that will actually be delivered
        drop_content_encoding: Also remove content-encoding, for a body that has
            been decompressed and is no longer encoded

    Returns:
        list: The rewritten raw header list
    """
    rewritten = [
        (name, value)
        for name, value in headers
        if name != b"content-length" and not (drop_content_encoding and name == b"content-encoding")
    ]
    rewritten.append((b"content-length", str(length).encode()))
    return rewritten


def replay_body(body: bytes):
    """Build an ASGI receive callable that delivers ``body`` once, then disconnects."""
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


async def send_json_error(send, status_code: int, message: str, error_code: str = None) -> None:
    """
    Emit a minimal JSON error without going through the app.

    Serialised with ``json.dumps`` rather than string interpolation: the
    message is not always ours. The unsupported-encoding refusal puts the
    client's own Content-Encoding header in it, and a header value may contain
    a double quote — h11 permits it — which interpolation would splice into the
    payload and hand the client an unparseable 415, hiding the very reason the
    request was refused.

    The shape is byte-for-byte what interpolation produced for a message that
    needed no escaping, so nothing that already parses these responses changes.
    """
    user_error = None if error_code is None else {"code": error_code, "message": message}
    payload = json.dumps(
        {"success": False, "code": status_code, "message": message, "userError": user_error},
        ensure_ascii=False,
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})


def add_request_decompression_middleware(
    app: FastAPI, max_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES, error_code: str = None
) -> None:
    """
    Accept compressed request bodies (issue #156, FR-009).

    Register LAST so it runs outermost — see RequestDecompressionMiddleware.

    Args:
        app: FastAPI application instance
        max_bytes: Maximum decompressed body size; larger is refused with 413
        error_code: Service-specific error code reported on refusal
    """
    app.add_middleware(RequestDecompressionMiddleware, max_bytes=max_bytes, error_code=error_code)
