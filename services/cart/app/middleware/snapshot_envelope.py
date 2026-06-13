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
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or scope.get("method") not in _PEELABLE_METHODS
            or not _content_type_is_json(scope)
        ):
            await self.app(scope, receive, send)
            return

        # Buffer the full request body so we can inspect and rewrite it.
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                # Forward the disconnect; nothing to peel.
                await self.app(scope, receive, send)
                return

        snapshot, new_body = peel_snapshot_envelope(body)

        # Expose the snapshot to downstream dependencies via request.state.
        state = scope.setdefault("state", {})
        state["cart_snapshot"] = snapshot

        sent = False

        async def replay_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": new_body, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)
