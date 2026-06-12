# Copyright 2026 masa@kugel
"""Unit tests for snapshot envelope verification rejections (issue #148, T023)."""
import base64

import pytest

from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument

from app.config.settings import settings
from app.exceptions import (
    SnapshotSignatureMismatchException,
    SnapshotInvalidException,
    SnapshotUnknownKidException,
    SnapshotVersionUnsupportedException,
)
from app.models.documents.cart_document import CartDocument
from app.services import snapshot_service


KEY_V1 = "v1:" + base64.b64encode(b"a" * 32).decode()
KEY_V2 = "v2:" + base64.b64encode(b"b" * 32).decode()


def _make_terminal_info() -> TerminalInfoDocument:
    return TerminalInfoDocument(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        business_date="20260601",
        open_counter=1,
        staff=StaffMasterDocument(id="staff01", name="Test Staff"),
    )


def _make_cart() -> CartDocument:
    cart = CartDocument()
    cart.tenant_id = "T001"
    cart.store_code = "S001"
    cart.terminal_no = 1
    cart.cart_id = "cart-0001"
    cart.status = "EnteringItem"
    cart.balance_amount = 100.0
    return cart


@pytest.fixture
def envelope(monkeypatch):
    """A valid envelope signed with v1."""
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", KEY_V1)
    snapshot_service.init_snapshot_signer(force=True)
    env = snapshot_service.build_envelope(_make_cart(), _make_terminal_info())
    assert env is not None
    yield env
    snapshot_service.init_snapshot_signer(force=True)


class TestVerifyEnvelope:
    def test_valid_envelope_rebuilds_cart(self, envelope):
        cart = snapshot_service.verify_envelope(envelope)
        assert isinstance(cart, CartDocument)
        assert cart.cart_id == "cart-0001"
        assert cart.balance_amount == 100.0

    def test_single_byte_tamper_raises_signature_mismatch(self, envelope):
        envelope["cart_document"]["balance_amount"] = 100.1
        with pytest.raises(SnapshotSignatureMismatchException):
            snapshot_service.verify_envelope(envelope)

    def test_attribution_tamper_raises_signature_mismatch(self, envelope):
        # kid/attribution are inside the signed payload (key-swap protection)
        envelope["store_code"] = "S002"
        with pytest.raises(SnapshotSignatureMismatchException):
            snapshot_service.verify_envelope(envelope)

    def test_missing_signature_raises_invalid(self, envelope):
        envelope.pop("signature")
        with pytest.raises(SnapshotInvalidException):
            snapshot_service.verify_envelope(envelope)

    def test_missing_field_raises_invalid(self, envelope):
        envelope.pop("issued_at")
        with pytest.raises(SnapshotInvalidException):
            snapshot_service.verify_envelope(envelope)

    def test_unparseable_cart_document_raises_invalid(self, monkeypatch):
        # Re-sign an envelope whose cart_document is not a CartDocument shape,
        # so it passes signature verification but fails the rebuild.
        monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", KEY_V1)
        signer = snapshot_service.init_snapshot_signer(force=True)
        payload = {
            "schema_version": 1,
            "issued_at": "2026-06-12T00:00:00Z",
            "kid": signer.current_kid,
            "tenant_id": "T001",
            "store_code": "S001",
            "terminal_no": 1,
            "cart_document": {"line_items": "not-a-list"},
        }
        envelope = {**payload, "signature": signer.sign(payload)}
        try:
            with pytest.raises(SnapshotInvalidException):
                snapshot_service.verify_envelope(envelope)
        finally:
            snapshot_service.init_snapshot_signer(force=True)

    def test_unknown_kid_raises(self, envelope, monkeypatch):
        # Rotate to a ring that no longer contains v1
        monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", KEY_V2)
        snapshot_service.init_snapshot_signer(force=True)
        with pytest.raises(SnapshotUnknownKidException):
            snapshot_service.verify_envelope(envelope)

    def test_previous_generation_key_still_verifies(self, envelope, monkeypatch):
        # Rotation grace: current=v2, previous=v1 -> v1 envelope verifies
        monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", f"{KEY_V2},{KEY_V1}")
        snapshot_service.init_snapshot_signer(force=True)
        cart = snapshot_service.verify_envelope(envelope)
        assert cart.cart_id == "cart-0001"

    def test_unsupported_schema_version_raises(self, envelope):
        envelope["schema_version"] = 99
        with pytest.raises(SnapshotVersionUnsupportedException):
            snapshot_service.verify_envelope(envelope)

    def test_no_keys_configured_raises_unknown_kid(self, envelope, monkeypatch):
        monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", "")
        snapshot_service.init_snapshot_signer(force=True)
        with pytest.raises(SnapshotUnknownKidException):
            snapshot_service.verify_envelope(envelope)
