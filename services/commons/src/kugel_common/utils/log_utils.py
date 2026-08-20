"""
Logging utility functions for masking sensitive information and for keeping
logged request/response bodies bounded.
"""
import json
from typing import Any, Dict, Optional


def mask_api_key(api_key: Optional[str]) -> str:
    """
    Mask API key for safe logging.

    Args:
        api_key: The API key to mask

    Returns:
        Masked API key string

    Examples:
        - None or empty -> "****"
        - Short key (<=8 chars) -> "****"
        - Long key -> "sk_l...5678" (first 4...last 4)
    """
    if not api_key:
        return "****"

    key_length = len(api_key)

    if key_length <= 8:
        return "****"

    # For longer keys, show first 4 and last 4 characters
    return f"{api_key[:4]}...{api_key[-4:]}"


def mask_dict_api_key(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Mask api_key field in dictionary for safe logging.

    Only the top-level keys "api_key" / "API_KEY" are masked; nested
    dictionaries are not traversed (this is a shallow copy). All current
    callers pass flat documents from MongoDB, so this is sufficient.

    Args:
        data: Dictionary that may contain api_key field, or None

    Returns:
        Dictionary with masked api_key (original dict is not modified),
        or None if input was None/empty.
    """
    if not data:
        return data

    # Create a copy to avoid modifying the original
    masked_data = data.copy()

    # Mask api_key field if it exists
    if "api_key" in masked_data:
        masked_data["api_key"] = mask_api_key(masked_data["api_key"])

    # Also check for API_KEY (uppercase variant)
    if "API_KEY" in masked_data:
        masked_data["API_KEY"] = mask_api_key(masked_data["API_KEY"])

    return masked_data


# ---------------------------------------------------------------------------
# Request/response log body sanitization (issue #155)
# ---------------------------------------------------------------------------

# Fields stripped from logged request/response bodies by default.
#
# The signed cart snapshot envelope (#148 / #156) carries the full cart
# document - embedded masters included - on every cart-mutating call, so
# logging it verbatim roughly doubles the stored size of both the request log
# file and the per-tenant `request_log` collection. The envelope is
# reconstructible (it is exactly what the server issued) and the forensic
# trail for restores lives in `log_cart_restore`, so the body is dropped and
# only its scalar metadata (kid / schema_version / issued_at / ...) is kept.
DEFAULT_LOG_STRIP_FIELDS = ("signedSnapshot", "signed_snapshot")

# Scalar members never carried over into the marker left behind by a strip.
_STRIP_META_EXCLUDE = frozenset({"signature"})

# Longest string kept as marker metadata. Metadata is identifiers and
# timestamps; anything longer is payload wearing a scalar type.
_STRIP_META_MAX_STR = 128

# Nesting depth beyond which stripping stops descending. Bodies this deep are
# not something the logger needs to walk, and the cap keeps a hostile payload
# from turning the middleware into a RecursionError.
_MAX_STRIP_DEPTH = 32

# Characters of the encoded body retained when the size backstop fires. Clamped
# to the configured budget, so a small budget stays a real ceiling.
_TRUNCATION_PREVIEW_CHARS = 512


def parse_log_strip_fields(spec: Optional[str]) -> tuple:
    """
    Parse a comma-separated list of field names to strip from logged bodies.

    Args:
        spec: Comma-separated field names (e.g. "signedSnapshot,signed_snapshot").
            None or empty disables stripping.

    Returns:
        Tuple of field names with surrounding whitespace removed.
    """
    if not spec:
        return ()
    return tuple(name.strip() for name in spec.split(",") if name.strip())


def _strip_marker(field: str, value: Any) -> Dict[str, Any]:
    """
    Build the placeholder that replaces a stripped field.

    Short scalar members of a stripped object are carried over so metadata
    that has to stay queryable in the request log (signing key id, schema
    version, issue time, and any future monotonic revision - see #165)
    survives the strip. Nested objects and arrays - what makes the field bulky
    in the first place - do not, and neither does a long string, which is
    payload rather than metadata whatever its type says.

    Args:
        field: Name of the field being stripped
        value: The value being dropped

    Returns:
        Marker dictionary recording the strip plus the retained scalars
    """
    marker: Dict[str, Any] = {"_stripped": field}
    if isinstance(value, dict):
        for key, member in value.items():
            if key in _STRIP_META_EXCLUDE or isinstance(member, (dict, list)):
                continue
            if isinstance(member, str) and len(member) > _STRIP_META_MAX_STR:
                continue
            marker[key] = member
    return marker


def _strip_fields(value: Any, fields: frozenset, depth: int) -> Any:
    """
    Recursively replace `fields` in `value` with strip markers.

    Args:
        value: Parsed JSON value to walk
        fields: Field names to strip
        depth: Current nesting depth

    Returns:
        A sanitized copy; containers are rebuilt only where needed
    """
    if depth >= _MAX_STRIP_DEPTH:
        return value
    if isinstance(value, dict):
        return {
            key: _strip_marker(key, member) if key in fields else _strip_fields(member, fields, depth + 1)
            for key, member in value.items()
        }
    if isinstance(value, list):
        return [_strip_fields(member, fields, depth + 1) for member in value]
    return value


def _may_contain(raw: Optional[bytes], fields: tuple) -> bool:
    """
    Cheap pre-check: could `raw` mention any of `fields`?

    A byte-level substring scan runs in C and is effectively free next to the
    Python-level walk it guards, and the answer is "no" for every body that
    carries no stripped field - which is most of them.

    A client could hide a field name from this scan by escaping it in its own
    JSON (a ``\\u0073`` in place of the leading "s"). That only means the client's own payload
    stays in the log at full size, which the size backstop still bounds, so it
    is not worth defending against.

    Args:
        raw: The body as received, or None when it is not available
        fields: Field names that would be stripped

    Returns:
        False only when `raw` is known to mention none of the fields
    """
    if raw is None:
        return True
    return any(field.encode("utf-8") in raw for field in fields)


def sanitize_log_body(
    body: Any,
    strip_fields: tuple = DEFAULT_LOG_STRIP_FIELDS,
    max_bytes: int = 0,
    raw: Optional[bytes] = None,
) -> Any:
    """
    Sanitize a parsed request/response body before it is logged.

    Two independent steps: known-bulky fields are replaced by a metadata
    marker, then whatever is left is subject to a size backstop. Never raises -
    a body that cannot be sanitized is replaced by a marker, because this runs
    on the logging path of every request and must not affect the response.

    Args:
        body: Parsed JSON body (dict / list / None)
        strip_fields: Field names to replace with a marker; empty disables
        max_bytes: Size ceiling in bytes for the sanitized body; 0 disables
        raw: The body as received, when available. Used only to skip work that
            cannot change the outcome - walking a body whose bytes do not
            mention any stripped field, and re-serializing one that is already
            within `max_bytes` (stripping only ever shrinks it). Both are worth
            skipping: the walk costs ~2 ms on a 280 KB body, and it runs on
            every request of every service.

    Returns:
        The sanitized body, or a marker dictionary when it was truncated
    """
    if body is None:
        return None
    try:
        if strip_fields and _may_contain(raw, strip_fields):
            sanitized = _strip_fields(body, frozenset(strip_fields), 0)
        else:
            sanitized = body

        if max_bytes <= 0 or (raw is not None and len(raw) <= max_bytes):
            return sanitized

        if sanitized is body and raw is not None:
            # Nothing was stripped, so the raw bytes ARE the serialization of
            # what would be stored - no need to build it again to measure it.
            return {
                "_truncated": True,
                "_encoded_bytes": len(raw),
                "_preview": raw[: min(_TRUNCATION_PREVIEW_CHARS, max_bytes)].decode("utf-8", "replace"),
            }

        encoded = json.dumps(sanitized, default=str, ensure_ascii=False)
        encoded_bytes = len(encoded.encode("utf-8"))
        if encoded_bytes <= max_bytes:
            return sanitized
        return {
            "_truncated": True,
            "_encoded_bytes": encoded_bytes,
            "_preview": encoded[: min(_TRUNCATION_PREVIEW_CHARS, max_bytes)],
        }
    except Exception:
        # The body is unloggable (unserializable member, pathological nesting).
        # Losing it is acceptable; losing the request is not.
        return {"_sanitize_failed": True}
