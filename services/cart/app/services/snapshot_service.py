# Copyright 2026 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Signed cart snapshot envelope assembly and verification (issue #148).

The envelope carries the full cart document (including reference masters)
plus attribution and key metadata, signed with HMAC-SHA256 over a canonical
JSON serialization. Signing and verification both operate on the snake_case
model_dump(mode="json") representation, so wire-level camelCase aliasing
never affects the signature.

Snapshot generation is best-effort (degraded mode): a failure to build or
sign a snapshot must never fail the underlying cart operation. Verification
is strict: with no keys configured, every envelope is rejected.
"""
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

SNAPSHOT_SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = {1}

# Cart statuses a snapshot may be restored into. Terminal states (Completed /
# Cancelled) are rejected idempotently by the caller; anything else is invalid.
RESTORABLE_STATUSES = {
    CartStatus.Idle.value,
    CartStatus.EnteringItem.value,
    CartStatus.Paying.value,
}

_signer: Optional[HmacSigner] = None
_initialized = False


def init_snapshot_signer(force: bool = False) -> Optional[HmacSigner]:
    """
    Load the snapshot signing key ring from settings. Called at startup so
    configuration errors surface immediately instead of on first request.

    An empty or malformed SNAPSHOT_HMAC_KEYS leaves the feature degraded:
    no snapshots are issued and the restore API rejects every envelope.
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
        except ValueError as e:
            _signer = None
            logger.error(
                "SNAPSHOT_HMAC_KEYS is malformed; cart snapshot feature is degraded: %s", e
            )
    _initialized = True
    return _signer


def get_snapshot_signer() -> Optional[HmacSigner]:
    """Return the loaded signer, initializing lazily if startup hook was skipped."""
    if not _initialized:
        return init_snapshot_signer()
    return _signer


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
        payload = {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "issued_at": get_app_time_str(),
            "kid": signer.current_kid,
            "tenant_id": terminal_info.tenant_id,
            "store_code": terminal_info.store_code,
            "terminal_no": terminal_info.terminal_no,
            "cart_document": cart_doc.model_dump(mode="json"),
        }
        raw_size = len(canonical_json_bytes(payload))
        if raw_size > settings.SNAPSHOT_SIZE_WARN_BYTES:
            logger.warning(
                "Snapshot for cart %s is %d bytes raw (threshold %d); "
                "consider revisiting the size budget (R-008)",
                cart_doc.cart_id,
                raw_size,
                settings.SNAPSHOT_SIZE_WARN_BYTES,
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


def extract_audit_meta(envelope: dict) -> dict:
    """
    Best-effort extraction of audit metadata from a presented envelope.

    Works on malformed envelopes too (rejections must still be traceable),
    so every field is optional and extraction never raises. Keys match the
    CartRestoreLogRepository.add_record_async keyword arguments.
    """
    if not isinstance(envelope, dict):
        return {"cart_id": None}

    def _as(value, types):
        return value if isinstance(value, types) else None

    return {
        "cart_id": _safe_cart_id(envelope),
        "snapshot_issued_at": _as(envelope.get("issued_at"), str),
        "snapshot_terminal_no": _as(envelope.get("terminal_no"), int),
        "snapshot_kid": _as(envelope.get("kid"), str),
        "snapshot_schema_version": _as(envelope.get("schema_version"), int),
    }


def _safe_cart_id(envelope: dict) -> Optional[str]:
    """Best-effort cart_id extraction for logging; never raises."""
    try:
        cart_document = envelope.get("cart_document")
        if isinstance(cart_document, dict):
            return cart_document.get("cart_id")
    except Exception:
        pass
    return None
