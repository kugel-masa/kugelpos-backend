# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Terminal API key storage (issue #136).

A terminal's API key is stored only as its SHA-256 digest, in `api_key_hash`.
The key is 256 bits from `secrets.token_urlsafe(32)`, so a fast, unsalted digest
is enough: nothing is gained by a slow hash against a key that cannot be guessed,
and an unsalted digest can still be looked up by index when the terminal is not
known. The plaintext is shown once, when the key is issued.

Documents written before this change hold the plaintext in `api_key`. They are
still accepted, and sealed - digest written, plaintext removed - the first time
they are verified, and by the terminal service's tenant setup. Sealing is
one-way (a terminal service from before it cannot verify a sealed key), so
SEAL_LEGACY_TERMINAL_API_KEYS turns it off while an older revision may run.
"""
import hashlib
import hmac
from logging import getLogger
from typing import Any, Mapping, Optional

from kugel_common.config.settings import settings

logger = getLogger(__name__)

API_KEY_HASH_FIELD = "api_key_hash"
LEGACY_API_KEY_FIELD = "api_key"


def hash_api_key(api_key: str) -> str:
    """
    Digest of a terminal API key, as stored in `api_key_hash`.

    Args:
        api_key: The plaintext API key

    Returns:
        Hex-encoded SHA-256 digest
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def legacy_plaintext_api_key(terminal_dict: Mapping[str, Any]) -> Optional[str]:
    """
    The plaintext API key of a document that has not been sealed yet.

    Args:
        terminal_dict: A terminal document as stored

    Returns:
        The plaintext key, or None when the document holds a digest or no key
    """
    if terminal_dict.get(API_KEY_HASH_FIELD):
        return None
    legacy = terminal_dict.get(LEGACY_API_KEY_FIELD)
    return legacy if isinstance(legacy, str) and legacy else None


def api_key_matches(terminal_dict: Mapping[str, Any], api_key: Any) -> bool:
    """
    Whether a presented API key is the one stored for a terminal.

    Compares in constant time, against the digest when the document has one and
    against a legacy plaintext key otherwise.

    Args:
        terminal_dict: A terminal document as stored
        api_key: The key the caller presented (anything a header can carry)

    Returns:
        True when the key matches
    """
    if not isinstance(api_key, str) or not api_key:
        return False
    stored_hash = terminal_dict.get(API_KEY_HASH_FIELD)
    if isinstance(stored_hash, str) and stored_hash:
        return hmac.compare_digest(stored_hash, hash_api_key(api_key))
    legacy = legacy_plaintext_api_key(terminal_dict)
    if legacy is None:
        return False
    return hmac.compare_digest(legacy.encode("utf-8"), api_key.encode("utf-8"))


def leftover_plaintext_api_key(terminal_dict: Mapping[str, Any]) -> Optional[str]:
    """
    A plaintext key left on a document that already holds a digest.

    Verification ignores it - the digest wins - but it is still a readable key
    in the database, and must go.

    Args:
        terminal_dict: A terminal document as stored

    Returns:
        The leftover plaintext, or None
    """
    if not terminal_dict.get(API_KEY_HASH_FIELD):
        return None
    leftover = terminal_dict.get(LEGACY_API_KEY_FIELD)
    return leftover if isinstance(leftover, str) and leftover else None


async def seal_legacy_api_key_async(collection, terminal_dict: Mapping[str, Any]) -> bool:
    """
    Remove a plaintext key from a document, in place.

    A legacy document gets the digest of its plaintext; a document that already
    holds a digest only loses the plaintext left beside it. Either way the write
    matches on the plaintext as read, so a key reissued in the meantime is left
    alone. Does nothing while SEAL_LEGACY_TERMINAL_API_KEYS is off. A failure is
    logged and swallowed: the caller has already verified the key, and sealing
    is retried on the next verification.

    Args:
        collection: The terminal info collection (Motor)
        terminal_dict: The document as read

    Returns:
        True when the document was changed
    """
    if not settings.SEAL_LEGACY_TERMINAL_API_KEYS:
        return False
    legacy = legacy_plaintext_api_key(terminal_dict)
    if legacy is not None:
        plaintext = legacy
        update = {"$set": {API_KEY_HASH_FIELD: hash_api_key(legacy)}, "$unset": {LEGACY_API_KEY_FIELD: ""}}
    else:
        plaintext = leftover_plaintext_api_key(terminal_dict)
        if plaintext is None:
            return False
        update = {"$unset": {LEGACY_API_KEY_FIELD: ""}}
    try:
        result = await collection.update_one({"_id": terminal_dict["_id"], LEGACY_API_KEY_FIELD: plaintext}, update)
    except Exception as e:
        logger.warning(f"Failed to seal the plaintext api_key of terminal {terminal_dict.get('terminal_id')}: {e}")
        return False
    return result.modified_count == 1
