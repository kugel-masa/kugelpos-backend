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
import json

import pytest

from kugel_common.models.documents.request_log_document import RequestLog

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


class TestMarksAreBoundedAndTyped:
    """What is recorded comes off an UNVERIFIED envelope.

    Extraction runs before verification and the request log is written in a
    `finally`, so a rejected request is recorded just the same. Whatever these
    marks carry, an attacker-controlled envelope chose - and the logged body is
    already capped at REQUEST_LOG_MAX_BODY_BYTES precisely to keep the log from
    being an amplifier (issue #155). These marks must not reopen that.
    """

    def test_an_oversized_cart_id_is_not_recorded(self):
        marks = snapshot_service.extract_snapshot_marks(
            {
                "schema_version": 2,
                "kid": "v1",
                "cart_document": {"cart_id": "A" * (snapshot_service.MARK_MAX_CHARS + 1)},
            }
        )

        # Dropped, not truncated: a truncated cart_id reads as a real one while
        # matching no cart.
        assert marks["cart_id"] is None
        # The bounded marks around it still survive - the request is still
        # traceable, it just does not get to name its own cart.
        assert marks["schema_version"] == 2
        assert marks["kid"] == "v1"

    def test_an_oversized_kid_is_not_recorded(self):
        marks = snapshot_service.extract_snapshot_marks(
            {"kid": "K" * (snapshot_service.MARK_MAX_CHARS + 1), "cart_document": {"cart_id": "c1"}}
        )

        assert marks["kid"] is None
        assert marks["cart_id"] == "c1"

    def test_a_real_cart_id_fits(self):
        import uuid

        cart_id = str(uuid.uuid4())
        marks = snapshot_service.extract_snapshot_marks({"cart_document": {"cart_id": cart_id}})

        assert marks["cart_id"] == cart_id

    def test_the_marks_a_hostile_envelope_can_produce_stay_small(self):
        envelope = {
            "schema_version": 2,
            "kid": "K" * 100_000,
            "cart_document": {"cart_id": "A" * 5_000_000, "revision": 3},
        }

        marks = snapshot_service.extract_snapshot_marks(envelope)

        assert len(json.dumps(marks)) < 1024

    def test_a_boolean_is_not_a_revision(self):
        # bool is a subclass of int, so an isinstance screen lets `true` through
        # and records it as revision 1 - a mark the envelope never carried.
        marks = snapshot_service.extract_snapshot_marks(
            {"schemaVersion": True, "cartDocument": {"cartId": "c1", "revision": True}}
        )

        assert marks["revision"] is None
        assert marks["schema_version"] is None

    def test_a_non_string_cart_id_costs_only_itself(self):
        # RequestLog.SnapshotInfo(cart_id=...) rejects a dict, and the logging
        # middleware drops the whole record when construction raises - so a
        # malformed envelope, the case a rejection most needs traceable, would
        # be the one that records nothing at all.
        marks = snapshot_service.extract_snapshot_marks(
            {"kid": "v1", "cart_document": {"cart_id": {"$ne": None}, "revision": 7}}
        )

        assert marks["cart_id"] is None
        assert marks["revision"] == 7
        assert marks["kid"] == "v1"
        RequestLog.SnapshotInfo(**marks)  # must not raise

    def test_audit_meta_is_bounded_too(self):
        # extract_audit_meta writes the same unverified values into the restore
        # audit trail.
        meta = snapshot_service.extract_audit_meta(
            {
                "issued_at": "I" * 5000,
                "kid": "K" * 5000,
                "terminal_no": True,
                "schema_version": 2,
                "cart_document": {"cart_id": "A" * 5000},
            }
        )

        assert meta["snapshot_issued_at"] is None
        assert meta["snapshot_kid"] is None
        assert meta["snapshot_terminal_no"] is None
        assert meta["cart_id"] is None
        assert meta["snapshot_schema_version"] == 2


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
