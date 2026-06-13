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
Generic HMAC-SHA256 signing utility with key-id (kid) generation management.

Payloads are signed over a canonical JSON serialization (sorted keys, compact
separators, ASCII-escaped) so that the same content always yields the same
signed byte sequence regardless of dict ordering or wire-level field aliasing.

The key ring is parsed from a CSV spec of the form "kid:base64key[,kid:base64key...]"
where the first entry is the current signing key and the remaining entries are
previous generations accepted for verification only (rotation grace).
"""
import base64
import hmac
import hashlib
import json


def canonical_json_bytes(payload: dict) -> bytes:
    """
    Serialize a JSON-compatible dict into canonical bytes for signing.

    Same content always produces the same byte sequence: keys are sorted,
    separators are compact, and non-ASCII characters are escaped.

    Args:
        payload: JSON-serializable dict (no datetime/Decimal objects; callers
            should pass data produced by model_dump(mode="json")).

    Returns:
        UTF-8 encoded canonical JSON bytes.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


class HmacSigner:
    """
    HMAC-SHA256 signer/verifier over a kid-managed key ring.

    The first key in the ring signs; every key in the ring verifies.
    """

    def __init__(self, keys: dict[str, bytes]):
        """
        Args:
            keys: Ordered mapping of kid -> raw key bytes. The first entry is
                the current signing key. Must not be empty.

        Raises:
            ValueError: If the key ring is empty or contains an empty key.
        """
        if not keys:
            raise ValueError("HMAC key ring must contain at least one key")
        for kid, key in keys.items():
            if not kid or not key:
                raise ValueError("HMAC key ring entries must have a non-empty kid and key")
        self._keys = dict(keys)
        self._current_kid = next(iter(keys))

    @classmethod
    def from_spec(cls, spec: str) -> "HmacSigner":
        """
        Build a signer from a "kid:base64key[,kid:base64key...]" spec string.

        Raises:
            ValueError: If the spec is empty, malformed, has duplicate kids,
                or contains invalid base64.
        """
        if not spec or not spec.strip():
            raise ValueError("HMAC key spec is empty")
        keys: dict[str, bytes] = {}
        for entry in spec.split(","):
            entry = entry.strip()
            if not entry:
                continue
            kid, sep, encoded = entry.partition(":")
            kid = kid.strip()
            if not sep or not kid or not encoded.strip():
                raise ValueError(f"Malformed HMAC key entry (expected 'kid:base64key'): '{entry[:16]}...'")
            if kid in keys:
                raise ValueError(f"Duplicate kid in HMAC key spec: '{kid}'")
            try:
                key = base64.b64decode(encoded.strip(), validate=True)
            except Exception as e:
                raise ValueError(f"Invalid base64 key for kid '{kid}'") from e
            if not key:
                raise ValueError(f"Empty key for kid '{kid}'")
            keys[kid] = key
        if not keys:
            raise ValueError("HMAC key spec contains no entries")
        return cls(keys)

    @property
    def current_kid(self) -> str:
        """The kid of the current signing key."""
        return self._current_kid

    @property
    def kids(self) -> list[str]:
        """All kids accepted for verification (current first)."""
        return list(self._keys.keys())

    def has_kid(self, kid: str) -> bool:
        """Return True if the kid is present in the key ring."""
        return kid in self._keys

    def sign(self, payload: dict) -> str:
        """
        Sign a payload with the current key.

        Returns:
            Hex-encoded HMAC-SHA256 over the canonical JSON of the payload.
        """
        return self._digest(self._current_kid, payload)

    def verify(self, payload: dict, kid: str, signature: str) -> bool:
        """
        Verify a signature against the key identified by kid.

        Comparison is constant-time. Returns False on mismatch.

        Raises:
            KeyError: If the kid is not in the key ring (callers distinguish
                "unknown key" from "tampered payload").
        """
        if kid not in self._keys:
            raise KeyError(kid)
        expected = self._digest(kid, payload)
        return hmac.compare_digest(expected, signature)

    def _digest(self, kid: str, payload: dict) -> str:
        return hmac.new(self._keys[kid], canonical_json_bytes(payload), hashlib.sha256).hexdigest()
