# Copyright 2026 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Signed cart snapshot envelope assembly and verification (issue #148).

The envelope carries the full cart document (including reference masters)
plus attribution and key metadata, signed with HMAC-SHA256 over a canonical
JSON serialization. Signing and verification both operate on the snake_case
model_dump(mode="json") representation, so wire-level camelCase aliasing
never affects the signature.

Signing is a startup requirement (issue #192): the service refuses to run
without a usable key, so no request is ever served by a process that cannot
sign. A cart the client carries exists nowhere else, so handing back a
response without a snapshot would take the cart with it - see
`require_snapshot_signer`.

Generation remains best-effort for a cart the server still holds in its
cache: a build failure there leaves the response without a snapshot and the
cart operation itself still succeeds. Verification is strict: an envelope
signed with an unknown key is always rejected.
"""

import base64
from logging import getLogger
from typing import Optional

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.hmac_signer import HmacSigner, canonical_json_bytes
from kugel_common.utils.misc import get_app_time_str

from app.config.settings import settings
from app.enums.cart_status import CartStatus
from app.exceptions import (
    SnapshotSignatureMismatchException,
    SnapshotInvalidException,
    SnapshotUnknownKidException,
    SnapshotVersionUnsupportedException,
)
from app.models.documents.cart_document import CartDocument

logger = getLogger(__name__)

# Version 2 adds the cart document's monotonic `revision` (issue #165). Version 1
# envelopes are still accepted: a client that has not migrated presents one, and
# rejecting it would break the very failover the snapshot exists for.
SNAPSHOT_SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = {1, 2}

# Cart statuses a snapshot may be restored into. Terminal states (Completed /
# Cancelled) are rejected idempotently by the caller; anything else is invalid.
RESTORABLE_STATUSES = {
    CartStatus.Idle.value,
    CartStatus.EnteringItem.value,
    CartStatus.Paying.value,
}

# Key material that ships in this repository for local development and tests, and
# is therefore public. A deployment signing with one of these has no signature
# protection at all: anyone reading the repo can mint a snapshot with any prices
# in it and the server will accept it. Detected at startup and reported loudly —
# this is more dangerous than having no key, where the feature merely degrades.
PUBLICLY_KNOWN_KEY_MATERIAL = (
    # services/docker-compose.yaml (development default)
    "a3VnZWxwb3MtZGV2LXNuYXBzaG90LWtleS0zMmJ5dGU=",
    # tests/integration/test_request_snapshot_roundtrip.py
    "aW50ZWdyYXRpb24tdGVzdC1rZXktMzItYnl0ZXMhISE=",
)

# HMAC-SHA256 produces a 32-byte tag; a key shorter than that weakens it while
# signing and verifying exactly like a real one. Documented in .env.sample as the
# minimum, and enforced at startup so the documentation is true.
MINIMUM_KEY_BYTES = 32

_signer: Optional[HmacSigner] = None
_initialized = False


def init_snapshot_signer(force: bool = False) -> Optional[HmacSigner]:
    """
    Load the snapshot signing key ring from settings. Called at startup so
    configuration errors surface immediately instead of on first request.

    An empty or malformed SNAPSHOT_HMAC_KEYS leaves the feature degraded:
    no snapshots are issued and the restore API rejects every envelope.

    A key that ships publicly in this repository is reported as an error: it
    loads and works, so nothing else would ever surface it, yet it leaves the
    signature worthless.
    """
    global _signer, _initialized
    if _initialized and not force:
        return _signer
    spec = getattr(settings, "SNAPSHOT_HMAC_KEYS", "") or ""
    if not spec.strip():
        _signer = None
        logger.warning(
            "SNAPSHOT_HMAC_KEYS is not set; cart snapshot feature is degraded "
            "(no snapshots issued, restore rejects all envelopes)"
        )
    else:
        try:
            _signer = HmacSigner.from_spec(spec)
            logger.info(
                "Snapshot signing keys loaded: kids=%s current=%s",
                _signer.kids,
                _signer.current_kid,
            )
            _warn_if_publicly_known(spec)
        except ValueError as e:
            _signer = None
            logger.error("SNAPSHOT_HMAC_KEYS is malformed; cart snapshot feature is degraded: %s", e)
    _initialized = True
    return _signer


def _short_key_ids(spec: str) -> list[str]:
    """
    Key ids in the spec whose material is below the minimum length.

    Only ever called after `HmacSigner.from_spec` has accepted the spec, so
    anything unparseable here has already been rejected and is skipped rather
    than reported twice.

    Args:
        spec: The raw SNAPSHOT_HMAC_KEYS value

    Returns:
        The offending kids, in the order they appear
    """
    short = []
    for entry in spec.split(","):
        kid, sep, encoded = entry.strip().partition(":")
        if not sep:
            continue
        try:
            key = base64.b64decode(encoded.strip(), validate=True)
        except Exception:
            continue
        if len(key) < MINIMUM_KEY_BYTES:
            short.append(kid.strip())
    return short


def _is_publicly_known(spec: str) -> bool:
    """Whether the spec contains key material committed to this repository."""
    return any(known in spec for known in PUBLICLY_KNOWN_KEY_MATERIAL)


def _warn_if_publicly_known(spec: str) -> None:
    """
    Report a signing key that is published in this repository.

    Unlike a missing key, this one works: snapshots are issued and verified, so
    every other signal looks healthy while the signature protects nothing. Fine
    for local development, catastrophic anywhere real — so say so at ERROR, where
    a missing key only warrants a warning.

    Args:
        spec: The raw SNAPSHOT_HMAC_KEYS value

    Returns:
        None
    """
    if not _is_publicly_known(spec):
        return
    logger.error(
        "SNAPSHOT_HMAC_KEYS contains key material published in this repository. "
        "Cart snapshots are effectively UNSIGNED: anyone can forge one with arbitrary "
        "prices and it will verify. This is acceptable ONLY for local development. "
        "Generate a real key: "
        "python -c \"import base64,os;print('v1:'+base64.b64encode(os.urandom(32)).decode())\""
    )


class SnapshotSigningUnavailableError(RuntimeError):
    """Raised at startup when the service has no signing key it may use.

    Not an API exception: nothing has been served yet. It propagates out of the
    lifespan hook so the process exits and the container is restarted rather
    than accepting traffic it cannot serve correctly.
    """


def require_snapshot_signer() -> HmacSigner:
    """
    Load the signing key ring and refuse to run without one (issue #192).

    A cart on the carried path is held by the client alone. A process that
    cannot sign cannot hand one back, and the client has nowhere to continue
    from - the cart is lost the moment it is created. Degrading was survivable
    only while the server-side cache was authoritative, and that cache is being
    retired, so the situation is removed instead of worked around.

    The key published in this repository is refused for the same reason it is
    reported at ERROR: it signs and verifies, so every other signal looks
    healthy while the signature protects nothing. Local stacks say so with
    `SNAPSHOT_ALLOW_INSECURE_KEY`.

    Returns:
        The loaded signer

    Raises:
        SnapshotSigningUnavailableError: no key, a malformed key, or the public
            development key without an explicit opt-in
    """
    signer = init_snapshot_signer(force=True)
    if signer is None:
        raise SnapshotSigningUnavailableError(
            "SNAPSHOT_HMAC_KEYS is unset or malformed. The cart service signs every "
            "cart it hands back to a client that carries it, so it cannot start "
            "without a key. Generate one: "
            "python -c \"import base64,os;print('v1:'+base64.b64encode(os.urandom(32)).decode())\""
        )
    short = _short_key_ids(getattr(settings, "SNAPSHOT_HMAC_KEYS", "") or "")
    if short:
        raise SnapshotSigningUnavailableError(
            f"SNAPSHOT_HMAC_KEYS entries {short} are shorter than {MINIMUM_KEY_BYTES} bytes. "
            "A short key signs and verifies exactly like a real one, so nothing else "
            "would report it. Generate a real key: "
            "python -c \"import base64,os;print('v1:'+base64.b64encode(os.urandom(32)).decode())\""
        )
    spec = getattr(settings, "SNAPSHOT_HMAC_KEYS", "") or ""
    if _is_publicly_known(spec) and not settings.SNAPSHOT_ALLOW_INSECURE_KEY:
        raise SnapshotSigningUnavailableError(
            "SNAPSHOT_HMAC_KEYS is the key published in this repository. Cart "
            "snapshots signed with it are effectively unsigned: anyone can forge one "
            "with arbitrary prices and it will verify. Supply a real key, or set "
            "SNAPSHOT_ALLOW_INSECURE_KEY=true if this really is a development stack."
        )
    return signer


def get_snapshot_signer() -> Optional[HmacSigner]:
    """Return the loaded signer, initializing lazily if startup hook was skipped."""
    if not _initialized:
        return init_snapshot_signer()
    return _signer


# A snapshot is warned about at this fraction of the budget above - not of the
# request-body ceiling.
#
# Expressed against the budget on purpose: two independent fractions of the
# ceiling can be set the wrong way round, and a warning above the refusal never
# fires at all. Against the budget the reading is direct - at 0.80, a fifth of
# the headroom is left.
#
# Nothing is refused here: this is the notice, the budget is the limit.
SNAPSHOT_SIZE_WARN_FRACTION = 0.80


def _snapshot_size_warn_bytes() -> int:
    """Warn-at size for an issued snapshot, in bytes."""
    return int(snapshot_size_refuse_bytes() * SNAPSHOT_SIZE_WARN_FRACTION)



def _envelope_payload(cart_doc: CartDocument, terminal_info: TerminalInfoDocument, kid: str) -> dict:
    """
    The signed part of an envelope for this cart.

    Shared by issuing and by measuring, so the size the size guard checks is the
    size of the thing that would actually be issued (issue #200) rather than an
    estimate that can drift from it.
    """
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "issued_at": get_app_time_str(),
        "kid": kid,
        "tenant_id": terminal_info.tenant_id,
        "store_code": terminal_info.store_code,
        "terminal_no": terminal_info.terminal_no,
        "cart_document": cart_doc.model_dump(mode="json"),
    }


# A cart is refused further growth once its snapshot would pass this fraction of
# the request-body ceiling.
#
# The snapshot is issued by the server and presented by the client on its next
# mutating request, so the ceiling bounds it - while the cart itself had no bound
# at all. Past that point the server hands the terminal an envelope it cannot
# send back: every following request is answered 413, and under
# CART_REQUEST_SNAPSHOT_MODE=REQUIRED the cart cannot be completed or cancelled
# (issue #200).
#
# Below the 75% warning, so the log says so before the till does. The remaining
# 40% covers the request payload alongside the envelope, the signature, and the
# growth of the very line being added.
SNAPSHOT_SIZE_REFUSE_FRACTION = 0.60


def snapshot_size_refuse_bytes() -> int:
    """Snapshot size past which a cart is refused further growth, in bytes."""
    return int(settings.MAX_REQUEST_BODY_BYTES * SNAPSHOT_SIZE_REFUSE_FRACTION)


def measure_envelope_bytes(cart_doc: CartDocument, terminal_info: TerminalInfoDocument) -> Optional[int]:
    """
    Size of the snapshot this cart would produce, without issuing one.

    Returns None when no signing key is configured: nothing is issued in that
    case, so there is no envelope to bound. Measured rather than estimated from
    a line count, because what a line costs depends on the item masters carried
    with it - a basket of distinct SKUs weighs more than twice one of repeats.

    Args:
        cart_doc: The cart as it would stand
        terminal_info: The terminal the envelope would be issued to

    Returns:
        Size in bytes, or None when snapshots are not being issued.
    """
    signer = get_snapshot_signer()
    if signer is None:
        return None
    # Deliberately does not bump revision: measuring must not consume one.
    return len(canonical_json_bytes(_envelope_payload(cart_doc, terminal_info, signer.current_kid)))


def build_envelope(cart_doc: CartDocument, terminal_info: TerminalInfoDocument) -> Optional[dict]:
    """
    Build and sign a snapshot envelope for the given cart.

    Returns the envelope as a snake_case dict ready to embed in a response,
    or None when generation is degraded or fails (the cart operation itself
    must not fail because of snapshot generation — NFR-004).
    """
    signer = get_snapshot_signer()
    if signer is None:
        return None
    try:
        # One snapshot is issued per mutating response, so bumping here is
        # "once per cart mutation" (issue #165). The envelope the terminal is
        # handed therefore always carries a higher revision than the one it
        # presented; replaying an older one is visible as a lower number.
        cart_doc.revision = (cart_doc.revision or 0) + 1
        payload = _envelope_payload(cart_doc, terminal_info, signer.current_kid)
        raw_size = len(canonical_json_bytes(payload))
        warn_at = _snapshot_size_warn_bytes()
        if raw_size > warn_at:
            logger.warning(
                "Snapshot for cart %s is %d bytes raw, past %d (%.0f%% of the %d byte budget): "
                "further line items are refused once the budget is reached, so the client is never "
                "handed a snapshot it cannot send back. Raise MAX_REQUEST_BODY_BYTES if real baskets "
                "reach this (R-008, issues #195 / #200)",
                cart_doc.cart_id,
                raw_size,
                warn_at,
                SNAPSHOT_SIZE_WARN_FRACTION * 100,
                snapshot_size_refuse_bytes(),
            )
        else:
            logger.debug("Snapshot for cart %s: %d bytes raw", cart_doc.cart_id, raw_size)
        return {**payload, "signature": signer.sign(payload)}
    except Exception as e:
        # Degrade: the mutation already succeeded; only the snapshot is dropped.
        logger.warning(
            "Snapshot generation failed for cart %s (degraded, error code %s): %s",
            getattr(cart_doc, "cart_id", None),
            "401507",
            e,
            exc_info=True,
        )
        return None


def build_finalize_context_envelope(
    *,
    cart_id: str,
    seq: int,
    receipt_no: int,
    transaction_datetime: str,
    terminal_info: TerminalInfoDocument,
    receipt_counter: Optional[int] = None,
) -> Optional[dict]:
    """
    Build and sign a finalize-context envelope for a void/return (issue #156, B案).

    Unlike the cart snapshot, a void/return has no in-flight cart to carry; the
    terminal instead carries the new transaction's identity — a stable
    ``cart_id`` (so a lost-ACK retry converges via downstream cart_id dedupe) and
    the per-open ``(seq, receipt_no, receipt_counter)`` / time it stamped —
    signed so the numbers cannot be forged. Wire form is the canonical snake_case payload (the signed
    bytes), transported as the ``signedSnapshot`` member of the request envelope.

    Returns None when signing is degraded (no keys configured).
    """
    signer = get_snapshot_signer()
    if signer is None:
        return None
    payload = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "issued_at": get_app_time_str(),
        "kid": signer.current_kid,
        "tenant_id": terminal_info.tenant_id,
        "store_code": terminal_info.store_code,
        "terminal_no": terminal_info.terminal_no,
        "finalize_context": {
            "cart_id": cart_id,
            "seq": seq,
            "receipt_no": receipt_no,
            # Running receipt counter (issue #166). Optional so a pre-#166
            # terminal's envelope still verifies; when present the server derives
            # the printed number from it and reports a disagreement.
            "receipt_counter": receipt_counter,
            "transaction_datetime": transaction_datetime,
        },
    }
    return {**payload, "signature": signer.sign(payload)}


def verify_finalize_context(envelope: dict) -> dict:
    """
    Verify a presented finalize-context envelope (issue #156, B案) and return its
    ``finalize_context`` dict (``cart_id`` / ``seq`` / ``receipt_no`` /
    ``transaction_datetime``).

    Mirrors :func:`verify_envelope` (shape → schema version → kid → signature),
    but carries a finalize context instead of a cart document. The caller is
    responsible for checking the envelope scope (tenant/store/terminal) against
    the authenticated terminal, exactly as the cart snapshot path does.

    Raises the same family of exceptions as :func:`verify_envelope`.
    """
    if not isinstance(envelope, dict):
        raise SnapshotInvalidException("Finalize-context envelope must be an object", logger)

    payload = {k: v for k, v in envelope.items() if k != "signature"}
    signature = envelope.get("signature")
    required = {"schema_version", "issued_at", "kid", "tenant_id", "store_code", "terminal_no", "finalize_context"}
    missing = required - payload.keys()
    if missing or not signature or not isinstance(signature, str):
        raise SnapshotInvalidException(
            f"Finalize-context envelope is malformed (missing: {sorted(missing) if missing else 'signature'})", logger
        )

    if payload["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
        raise SnapshotVersionUnsupportedException(
            f"Unsupported finalize-context schema_version: {payload['schema_version']}", logger
        )

    signer = get_snapshot_signer()
    if signer is None:
        logger.warning("Finalize-context rejected: no snapshot signing keys configured")
        raise SnapshotUnknownKidException("No snapshot signing keys configured", logger)

    kid = payload["kid"]
    try:
        valid = signer.verify(payload, kid, signature)
    except KeyError:
        logger.warning("Finalize-context rejected: unknown snapshot kid '%s'", kid)
        raise SnapshotUnknownKidException(f"Unknown snapshot signing key id: {kid}", logger)
    if not valid:
        # Security event (NFR-003): tampered or forged numbering.
        logger.warning("Finalize-context rejected: signature mismatch (kid=%s)", kid)
        raise SnapshotSignatureMismatchException("Finalize-context signature mismatch", logger)

    context = payload["finalize_context"]
    if not isinstance(context, dict):
        raise SnapshotInvalidException("Finalize-context payload is malformed", logger)
    return context


def verify_envelope(envelope: dict) -> CartDocument:
    """
    Verify a presented snapshot envelope and rebuild its cart document.

    The envelope must be a snake_case dict (callers pass
    SnapshotEnvelope.model_dump(mode="json")). Verification order: shape →
    schema version → kid → signature → cart document rebuild, so that the
    most specific error code wins.

    Raises:
        SnapshotInvalidException: Malformed envelope / missing signature /
            cart document that does not parse.
        SnapshotVersionUnsupportedException: schema_version out of range.
        SnapshotUnknownKidException: Unknown kid, or no keys configured.
        SnapshotSignatureMismatchException: Signature does not verify.
    """
    if not isinstance(envelope, dict):
        raise SnapshotInvalidException("Snapshot envelope must be an object", logger)

    payload = {k: v for k, v in envelope.items() if k != "signature"}
    signature = envelope.get("signature")
    required = {"schema_version", "issued_at", "kid", "tenant_id", "store_code", "terminal_no", "cart_document"}
    missing = required - payload.keys()
    if missing or not signature or not isinstance(signature, str):
        raise SnapshotInvalidException(
            f"Snapshot envelope is malformed (missing: {sorted(missing) if missing else 'signature'})", logger
        )

    if payload["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
        raise SnapshotVersionUnsupportedException(
            f"Unsupported snapshot schema_version: {payload['schema_version']}", logger
        )

    signer = get_snapshot_signer()
    if signer is None:
        # Security event: someone presented an envelope while keys are unconfigured.
        logger.warning("Restore rejected: no snapshot signing keys configured")
        raise SnapshotUnknownKidException("No snapshot signing keys configured", logger)

    kid = payload["kid"]
    try:
        valid = signer.verify(payload, kid, signature)
    except KeyError:
        logger.warning("Restore rejected: unknown snapshot kid '%s'", kid)
        raise SnapshotUnknownKidException(f"Unknown snapshot signing key id: {kid}", logger)
    if not valid:
        # Security event (NFR-003): tampered or forged snapshot.
        logger.warning(
            "Restore rejected: snapshot signature mismatch (kid=%s, cart_id=%s)",
            kid,
            _safe_cart_id(envelope),
        )
        raise SnapshotSignatureMismatchException("Snapshot signature mismatch", logger)

    try:
        return CartDocument(**payload["cart_document"])
    except Exception as e:
        raise SnapshotInvalidException("Snapshot cart document does not parse", logger, e)


# Longest string kept from a presented envelope. Matches the cap the body strip
# already applies to metadata it carries over (_STRIP_META_MAX_STR in
# kugel_common.utils.log_utils), so a value cannot enter the request log through
# these marks that would have been dropped from the body.
#
# Everything extracted here comes off an UNVERIFIED envelope — extraction runs
# before (and regardless of) signature verification, and a rejected request is
# logged just the same. Without a cap the caller writes an attacker-chosen
# string of any length into MongoDB, which is the amplification issue #155 was
# about. A cart_id is a uuid4 (36 chars) and a kid is a key label, so anything
# longer is not the value it claims to be.
MARK_MAX_CHARS = 128


def _mark_str(value) -> Optional[str]:
    """A string worth recording from an unverified envelope, or None.

    Over-length values are dropped rather than truncated: the body strip treats a
    long string as payload rather than metadata, and a truncated cart_id would
    read as a real one while matching no cart.
    """
    if not isinstance(value, str) or len(value) > MARK_MAX_CHARS:
        return None
    return value


def _mark_int(value) -> Optional[int]:
    """An int worth recording from an unverified envelope, or None.

    `type(...) is int` rather than isinstance: bool is a subclass of int, and a
    `revision: true` recorded as revision 1 is a fabricated mark, not a revision.
    """
    return value if type(value) is int else None


def extract_audit_meta(envelope: dict) -> dict:
    """
    Best-effort extraction of audit metadata from a presented envelope.

    Works on malformed envelopes too (rejections must still be traceable),
    so every field is optional and extraction never raises. Keys match the
    CartRestoreLogRepository.add_record_async keyword arguments.
    """
    if not isinstance(envelope, dict):
        return {"cart_id": None}

    return {
        "cart_id": _safe_cart_id(envelope),
        "snapshot_issued_at": _mark_str(envelope.get("issued_at")),
        "snapshot_terminal_no": _mark_int(envelope.get("terminal_no")),
        "snapshot_kid": _mark_str(envelope.get("kid")),
        "snapshot_schema_version": _mark_int(envelope.get("schema_version")),
        "snapshot_revision": (extract_snapshot_marks(envelope) or {}).get("revision"),
    }


def extract_snapshot_marks(envelope: dict) -> Optional[dict]:
    """
    The few scalars worth carrying into the request log (issue #165).

    Best-effort and never raising: this runs on the request path for every
    carried snapshot, including malformed ones, and its only job is to leave
    behind enough to spot a rollback afterwards - a `revision` sequence for a
    cart_id that is not increasing.

    Args:
        envelope: The presented snapshot envelope, in whatever shape it arrived

    Returns:
        Dict with cart_id / revision / schema_version / kid, or None when the
        envelope carries nothing recognisable
    """
    if not isinstance(envelope, dict):
        return None

    def pick(*names):
        """Accept both spellings: this runs before the envelope is normalised.

        The signing canonical form is snake_case, but a terminal presents the
        envelope exactly as it received it - camelCase, per the response alias
        generator - and the peel middleware sees that wire form.
        """
        for name in names:
            if name in envelope:
                return envelope[name]
        return None

    cart_document = pick("cart_document", "cartDocument")
    revision = None
    if isinstance(cart_document, dict):
        revision = cart_document.get("revision")
    schema_version = pick("schema_version", "schemaVersion")
    kid = envelope.get("kid")

    marks = {
        "cart_id": _safe_cart_id(envelope),
        "revision": _mark_int(revision),
        "schema_version": _mark_int(schema_version),
        "kid": _mark_str(kid),
    }
    return marks if any(v is not None for v in marks.values()) else None


def _safe_cart_id(envelope: dict) -> Optional[str]:
    """Best-effort cart_id extraction for logging; never raises.

    Accepts the wire form as well as the signing canonical form: an envelope
    reaches the peel middleware exactly as the terminal received it, which is
    camelCase (issue #165).

    Screened through _mark_str: a non-string here would fail RequestLog's
    SnapshotInfo validation and cost the whole record - so a malformed envelope,
    the case rejections most need traceable, would be the one that logs nothing.
    """
    try:
        cart_document = envelope.get("cart_document")
        if not isinstance(cart_document, dict):
            cart_document = envelope.get("cartDocument")
        if isinstance(cart_document, dict):
            return _mark_str(cart_document.get("cart_id")) or _mark_str(cart_document.get("cartId"))
    except Exception:
        pass
    return None
