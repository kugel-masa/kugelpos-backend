"""
Logging utility functions for masking sensitive information and for keeping
logged request/response bodies bounded.

Two independent questions are answered here, and they are deliberately kept
apart rather than folded together:

- **Secrecy** (issue #211): what must never be written to a log sink at all.
  ``mask_sensitive_data`` replaces the value and keeps the key, so the log
  still records that a field was supplied.
- **Size** (issue #155): what is too bulky to be worth storing.
  ``sanitize_log_body`` drops the field and leaves a marker.

A field can need one, the other, or both, and neither answer implies the
other - a PIN is four characters and a signed snapshot is not a secret.
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
# Credential masking (issue #211)
# ---------------------------------------------------------------------------

# Field names whose value must never be written to a log sink, compared after
# normalisation (see `_normalize_key`) so that `pin_code`, `pinCode` and
# `PIN_CODE` are all covered. Both spellings really do occur: request and
# response bodies are lowerCamelCase (`BaseSchemaModel` sets
# `alias_generator=to_lower_camel`) while the Python schemas and the MongoDB
# documents are snake_case.
#
# `pin` is here because the staff master carries it in plain text, in requests
# (`BaseStaffCreateRequest`) and in responses (`BaseStaffResponse`) alike, and
# `password` because `UserAccount` is a plaintext password that is hashed only
# after the request log has already recorded the body.
_SECRET_FIELD_NAMES = frozenset(
    {
        "pin",
        "pincode",
        "staffpin",
        "password",
        "newpassword",
        "oldpassword",
        "currentpassword",
        "hashedpassword",
        "token",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "secret",
        "clientsecret",
        "secretkey",
        "accesskey",
        "cardno",
        "cardnumber",
        "pan",
        "maskedpan",
        # HTTP header names, for call sites that log a whole header mapping
        # (an "Authorization: Bearer <jwt>" value is the credential itself).
        "authorization",
        "xapikey",
        "daprapitoken",
    }
)

# Masked to first4...last4 rather than blanked: the partial form is what the
# existing troubleshooting workflow reads, and `mask_dict_api_key` already
# established it.
_PARTIAL_MASK_FIELD_NAMES = frozenset({"apikey"})

# Fields that are credential CONTAINERS: every value beneath them is masked
# regardless of key name. A name-based set cannot cover a field whose schema
# accepts arbitrary string keys - a caller can put the secret under `cardN0`
# or `pinCod` and the name never matches. It does not have to be deliberate
# either: the request logger records the body BEFORE FastAPI validates it, so
# a misspelled key that the schema would have rejected with a 422 is still
# written to both sinks in full.
_CREDENTIAL_CONTAINER_FIELD_NAMES = frozenset({"credentials", "credential"})


def _normalize_key(key: Any) -> str:
    """Fold a field name to its comparison form (lowercase, no separators)."""
    if not isinstance(key, str):
        return ""
    return key.replace("_", "").replace("-", "").lower()


def mask_sensitive_data(data: Any) -> Any:
    """
    Recursively mask credential fields in an arbitrarily shaped JSON value.

    Applied by the request-log middleware to request and response bodies before
    they reach either sink, and by the call sites that log a whole document or
    header mapping. Unlike `mask_dict_api_key` this traverses nested
    dictionaries and lists, because a request body is arbitrary JSON rather
    than a flat MongoDB document.

    The key is always kept and only the value is replaced, so the log still
    records the shape of what arrived. A `None` value for a secret field stays
    `None` for the same reason: it distinguishes "no PIN was supplied" from "a
    PIN was supplied", which reveals nothing and misrepresents nothing.

    Args:
        data: Parsed JSON value (dict / list / scalar), or None

    Returns:
        A masked copy; the input is never modified.
    """
    if isinstance(data, dict):
        return {key: _mask_field(key, value) for key, value in data.items()}

    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]

    return data


def _mask_field(key: Any, value: Any) -> Any:
    """Mask one field according to its name, recursing into containers."""
    normalized = _normalize_key(key)

    if normalized in _CREDENTIAL_CONTAINER_FIELD_NAMES:
        return _mask_all_values(value)

    if normalized in _PARTIAL_MASK_FIELD_NAMES:
        # `mask_api_key` measures len(), so it only accepts str (or None).
        # Request bodies are client-controlled JSON and may carry any type
        # under these names, so anything else is blanked rather than measured -
        # letting the TypeError escape would turn the log middleware into a
        # 500 for the whole request.
        if value is None or isinstance(value, str):
            return mask_api_key(value)
        return "****"

    if normalized in _SECRET_FIELD_NAMES:
        return None if value is None else "****"

    return mask_sensitive_data(value)


def _mask_all_values(value: Any) -> Any:
    """
    Blank every scalar beneath `value`, independent of key names.

    Keys and shape are preserved so a misspelled credential key stays visible
    for diagnostics; `None` is preserved to keep "not supplied" readable. The
    values themselves never reach a log sink.

    Args:
        value: The container's contents

    Returns:
        A copy with the same shape and no values
    """
    if isinstance(value, dict):
        return {key: _mask_all_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask_all_values(item) for item in value]
    return None if value is None else "****"


def mask_validation_error_details(errors: Any) -> list:
    """
    Mask the `input` echo in Pydantic validation errors.

    Each entry in `exc.errors()` carries the raw value that failed - and the
    422 handlers put `str(exc.errors())` into both the ERROR log and the
    response `data`. For an error at a secret location that echo is the
    credential itself, handed straight back to whoever sent it.

    The location is not a sufficient guard on its own. A root-level error - the
    whole body sent as an array, say - reports `loc=('body',)` with the ENTIRE
    body as its `input`, credentials included. So an input at a secret location
    is blanked whole, and every other input is still passed through
    `mask_sensitive_data`, which masks what is embedded at any depth while
    leaving the values a caller needs to see readable.

    Args:
        errors: The list returned by `ValidationError.errors()`

    Returns:
        A masked copy of the error list
    """
    masked = []
    for error in errors:
        err = dict(error)
        loc = err.get("loc") or ()
        sensitive = any(
            isinstance(part, str)
            and (
                _normalize_key(part) in _SECRET_FIELD_NAMES or _normalize_key(part) in _CREDENTIAL_CONTAINER_FIELD_NAMES
            )
            for part in loc
        )
        if sensitive:
            # The value at a secret location IS the secret: blank it whole.
            if "input" in err:
                err["input"] = None if err["input"] is None else "****"
            # ctx can embed constraint context derived from the value
            # ("String should have at least 4 characters" is harmless, but
            # a pattern mismatch context is not always).
            err.pop("ctx", None)
        elif "input" in err:
            err["input"] = mask_sensitive_data(err["input"])
        masked.append(err)
    return masked


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
        raw: The body as received, when available. Read as a measurement only,
            never as content - it is the UNMASKED body (issue #211), so nothing
            sliced out of it may be returned. Both uses survive masking because
            masking replaces values and keeps keys: a byte scan for a stripped
            field name still answers for the masked body, and a body whose raw
            form is within `max_bytes` is within it after masking too, give or
            take the difference between a secret and four asterisks. Both are
            worth skipping: the walk costs ~2 ms on a 280 KB body, and it runs
            on every request of every service.

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

        # The preview is always built from `sanitized`, never sliced out of
        # `raw`. `body` has already been through `mask_sensitive_data` by the
        # time it gets here (issue #211) and `raw` has not, so raw bytes are
        # the one thing in this function that must not become log content.
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
