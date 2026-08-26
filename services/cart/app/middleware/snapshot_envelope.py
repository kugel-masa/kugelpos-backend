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
Client-carried cart phase 2 (issue #156): request snapshot envelope peel.

Phase 2 clients send cart-mutating requests in a uniform wrapped body:

    { "signedSnapshot": <envelope>, "payload": <original body> }

This ASGI middleware peels ``signedSnapshot`` off the body, stashes it on
``request.state.cart_snapshot`` (read by the cart-service dependency to take
the stateless path), and forwards ``payload`` as the request body so existing
endpoint signatures (e.g. ``list[Item]``) are unchanged. Legacy phase 1 bodies
(a bare array/object/none with no ``signedSnapshot`` key) pass through
untouched and take the cache-authoritative path (DUAL mode).

The peel runs OUTSIDE the request-logging middleware so the large snapshot is
not duplicated into the request log (NFR-005 / issue #155): the log observes
only the peeled payload.
"""

from logging import getLogger
import json

from kugel_common.middleware.http_compression import (
    DEFAULT_MAX_DECOMPRESSED_BYTES,
    RequestBodyTooLarge,
    read_body_capped,
    replace_body_headers,
    replay_body,
    send_json_error,
)
from kugel_common.middleware.log_requests import SNAPSHOT_SCOPE_KEY

from app.services import snapshot_service

logger = getLogger(__name__)

SNAPSHOT_KEY = "signedSnapshot"
PAYLOAD_KEY = "payload"

# Methods whose bodies may carry a wrapped snapshot.
_PEELABLE_METHODS = frozenset({"POST", "PUT", "PATCH"})


def peel_snapshot_envelope(raw_body: bytes) -> tuple[dict | None, bytes]:
    """
    Split a wrapped request body into (snapshot, payload-body-bytes).

    If ``raw_body`` is a JSON object carrying a ``signedSnapshot`` key, returns
    the snapshot dict and the re-serialized ``payload`` (the original endpoint
    body shape; empty bytes when ``payload`` is absent — body-less operations).
    Otherwise returns ``(None, raw_body)`` unchanged. Never raises: non-JSON or
    non-wrapper bodies (phase 1 / legacy) pass through.

    Args:
        raw_body: The raw request body bytes.

    Returns:
        Tuple of (snapshot dict or None, body bytes to forward downstream).
    """
    if not raw_body:
        return None, raw_body
    try:
        parsed = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError):
        return None, raw_body
    if not isinstance(parsed, dict) or SNAPSHOT_KEY not in parsed:
        return None, raw_body
    snapshot = parsed.get(SNAPSHOT_KEY)
    if PAYLOAD_KEY not in parsed:
        # body-less operation (subtotal / bill / cancel / resume): no payload.
        return snapshot, b""
    return snapshot, json.dumps(parsed[PAYLOAD_KEY]).encode("utf-8")


def _content_type_is_json(scope) -> bool:
    for name, value in scope.get("headers", []):
        if name == b"content-type":
            return b"application/json" in value.lower()
    return False


class SnapshotEnvelopePeelMiddleware:
    """
    Pure-ASGI middleware that peels the phase 2 snapshot envelope (see module
    docstring). Registered outside the request-logging middleware.

    Peeling means buffering the whole body, and this middleware runs ahead of the
    route's dependencies: its entry condition is method and content type only, so
    an unauthenticated caller reaches the buffer and the 401 arrives after. The
    body is therefore read under the same ceiling the decompression middleware
    applies to an expanded body (issue #195) — a size refused after decompression
    is refused when it arrives that size to begin with, which is the case a
    caller reaches simply by not compressing.
    """

    def __init__(self, app, max_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES, error_code: str = None):
        self.app = app
        self.max_bytes = max_bytes
        # Service-specific code for the refusal: the middleware sits outside the
        # app, so it cannot raise through the normal exception handlers.
        self.error_code = error_code

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or scope.get("method") not in _PEELABLE_METHODS
            or not _content_type_is_json(scope)
        ):
            await self.app(scope, receive, send)
            return

        # Buffer the full request body so we can inspect and rewrite it, under a
        # ceiling: whoever sends it has not been authenticated yet.
        try:
            body = await read_body_capped(receive, self.max_bytes)
        except RequestBodyTooLarge as e:
            logger.warning("Rejected oversized request body: %s", e)
            await send_json_error(send, 413, "Request body too large", self.error_code)
            return
        if body is None:
            # The client is gone mid-body. Do not hand the app a receive channel
            # we have already drained past the disconnect — it would wait on a
            # message that never comes. There is nothing to serve.
            return

        snapshot, new_body = peel_snapshot_envelope(body)

        # Expose the peeled snapshot to downstream dependencies via a dedicated
        # scope key (read with request.scope.get("cart_snapshot")). A top-level
        # scope key is robust across Starlette versions, unlike scope["state"]
        # which the framework may initialize/replace.
        scope = dict(scope)
        scope["cart_snapshot"] = snapshot
        # The request log runs inside this middleware, so by the time it sees the
        # body the envelope is gone. Leave the few scalars worth recording where
        # it can find them (issue #165) - the revision is what makes a replayed
        # older envelope visible after the fact.
        marks = snapshot_service.extract_snapshot_marks(snapshot) if snapshot is not None else None
        if marks is not None:
            scope[SNAPSHOT_SCOPE_KEY] = marks
        # Peeling changes the body length, so content-length must follow it:
        # the value the client sent describes the wrapper, not the payload now
        # being delivered, and anything downstream that trusts the header would
        # read the wrong size.
        if new_body != body:
            scope["headers"] = replace_body_headers(scope["headers"], len(new_body))

        await self.app(scope, replay_body(new_body), send)
