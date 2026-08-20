# Copyright 2026 masa@kugel
"""Monotonic cart revision (issue #165).

The signature proves an envelope was issued unmodified; it does not prove it is
the current one. A stateless backend cannot know the high-water mark for a cart
without a per-request write, which is what phase 2 removed - so a rollback
before finalize is accepted and made visible instead: every issued snapshot
carries a higher revision, and a replayed older envelope shows up as a lower
number for the same cart_id.
"""

import base64

import pytest

from app.models.documents.cart_document import CartDocument
from app.services import snapshot_service


@pytest.fixture
def signer_enabled(monkeypatch):
    key = base64.b64encode(b"unit-test-key-32-bytes-long!!!!!").decode()
    monkeypatch.setattr(snapshot_service.settings, "SNAPSHOT_HMAC_KEYS", f"v1:{key}")
    snapshot_service.init_snapshot_signer(force=True)
    yield
    monkeypatch.setattr(snapshot_service.settings, "SNAPSHOT_HMAC_KEYS", "")
    snapshot_service.init_snapshot_signer(force=True)


def _cart(revision=0):
    cart = CartDocument()
    cart.cart_id = "cart-165"
    cart.revision = revision
    return cart


def _terminal():
    from types import SimpleNamespace

    return SimpleNamespace(tenant_id="T0001", store_code="S0001", terminal_no=1)


class TestIssuing:
    def test_every_issued_snapshot_advances_the_revision(self, signer_enabled):
        cart = _cart()

        first = snapshot_service.build_envelope(cart, _terminal())
        second = snapshot_service.build_envelope(cart, _terminal())

        assert first["cart_document"]["revision"] == 1
        assert second["cart_document"]["revision"] == 2

    def test_it_continues_from_what_the_client_carried(self, signer_enabled):
        # The cart is rebuilt from the presented snapshot, so the revision the
        # terminal holds is where the next one starts.
        cart = _cart(revision=7)

        envelope = snapshot_service.build_envelope(cart, _terminal())

        assert envelope["cart_document"]["revision"] == 8

    def test_the_revision_is_covered_by_the_signature(self, signer_enabled):
        cart = _cart()
        envelope = snapshot_service.build_envelope(cart, _terminal())

        envelope["cart_document"]["revision"] = 99  # tamper

        with pytest.raises(Exception):
            snapshot_service.verify_envelope(envelope)

    def test_envelopes_are_issued_at_schema_version_2(self, signer_enabled):
        envelope = snapshot_service.build_envelope(_cart(), _terminal())

        assert envelope["schema_version"] == 2


class TestAcceptingBothVersions:
    def test_a_version_1_envelope_is_still_accepted(self, signer_enabled):
        # A client that has not migrated presents one; refusing it would break
        # the failover the snapshot exists for.
        cart = _cart()
        envelope = snapshot_service.build_envelope(cart, _terminal())
        payload = {k: v for k, v in envelope.items() if k != "signature"}
        payload["schema_version"] = 1
        signer = snapshot_service.get_snapshot_signer()
        legacy = {**payload, "signature": signer.sign(payload)}

        restored = snapshot_service.verify_envelope(legacy)

        assert restored.cart_id == "cart-165"


class TestMarksForTheRequestLog:
    def test_marks_carry_the_revision(self, signer_enabled):
        envelope = snapshot_service.build_envelope(_cart(revision=4), _terminal())

        marks = snapshot_service.extract_snapshot_marks(envelope)

        assert marks == {"cart_id": "cart-165", "revision": 5, "schema_version": 2, "kid": "v1"}

    def test_a_version_1_envelope_has_no_revision_to_carry(self):
        marks = snapshot_service.extract_snapshot_marks(
            {"schema_version": 1, "kid": "v1", "cart_document": {"cart_id": "cart-165"}}
        )

        assert marks["revision"] is None
        assert marks["cart_id"] == "cart-165"

    def test_a_malformed_envelope_yields_nothing_rather_than_raising(self):
        # This runs on the request path for every carried snapshot, including
        # the ones that are about to be rejected.
        assert snapshot_service.extract_snapshot_marks("not-an-envelope") is None
        assert snapshot_service.extract_snapshot_marks({}) is None

    def test_a_non_integer_revision_is_dropped(self):
        marks = snapshot_service.extract_snapshot_marks(
            {"kid": "v1", "cart_document": {"cart_id": "c", "revision": "seven"}}
        )

        assert marks["revision"] is None


class TestTheWireForm:
    """The peel middleware sees the envelope as the terminal received it."""

    def test_marks_are_extracted_from_camel_case(self):
        # The signing canonical form is snake_case, but a terminal presents what
        # the response gave it, which the alias generator renders camelCase.
        marks = snapshot_service.extract_snapshot_marks(
            {
                "schemaVersion": 2,
                "kid": "v1",
                "cartDocument": {"cartId": "cart-165", "revision": 9},
            }
        )

        assert marks == {"cart_id": "cart-165", "revision": 9, "schema_version": 2, "kid": "v1"}

    def test_both_spellings_of_the_cart_id_work(self):
        assert snapshot_service.extract_snapshot_marks({"cart_document": {"cart_id": "c1"}})["cart_id"] == "c1"
        assert snapshot_service.extract_snapshot_marks({"cartDocument": {"cartId": "c2"}})["cart_id"] == "c2"
