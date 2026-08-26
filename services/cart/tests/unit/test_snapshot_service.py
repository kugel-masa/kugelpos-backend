# Copyright 2026 masa@kugel
"""Unit tests for app.services.snapshot_service (envelope assembly, T011)."""

import base64
import json

import pytest

from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.hmac_signer import HmacSigner, canonical_json_bytes

from app.config.settings import settings
from app.models.documents.cart_document import CartDocument
from app.services import snapshot_service

KEY_SPEC = "v1:" + base64.b64encode(b"k" * 32).decode()


def _make_terminal_info(**overrides) -> TerminalInfoDocument:
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        business_date="20260601",
        open_counter=1,
        staff=StaffMasterDocument(id="staff01", name="Test Staff"),
    )
    defaults.update(overrides)
    return TerminalInfoDocument(**defaults)


def _make_cart(**overrides) -> CartDocument:
    cart = CartDocument()
    cart.tenant_id = "T001"
    cart.store_code = "S001"
    cart.terminal_no = 1
    cart.cart_id = "cart-0001"
    cart.status = "EnteringItem"
    for key, value in overrides.items():
        setattr(cart, key, value)
    return cart


@pytest.fixture
def signer_enabled(monkeypatch):
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", KEY_SPEC)
    snapshot_service.init_snapshot_signer(force=True)
    yield
    snapshot_service.init_snapshot_signer(force=True)


@pytest.fixture
def signer_disabled(monkeypatch):
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", "")
    snapshot_service.init_snapshot_signer(force=True)
    yield
    snapshot_service.init_snapshot_signer(force=True)


class TestBuildEnvelope:
    def test_envelope_fields_and_signature(self, signer_enabled):
        cart = _make_cart()
        envelope = snapshot_service.build_envelope(cart, _make_terminal_info())

        assert envelope is not None
        assert envelope["schema_version"] == snapshot_service.SNAPSHOT_SCHEMA_VERSION
        assert envelope["kid"] == "v1"
        assert envelope["tenant_id"] == "T001"
        assert envelope["store_code"] == "S001"
        assert envelope["terminal_no"] == 1
        assert envelope["cart_document"] == cart.model_dump(mode="json")
        assert envelope["issued_at"]

        # The signature self-verifies over everything except `signature`
        signer = HmacSigner.from_spec(KEY_SPEC)
        payload = {k: v for k, v in envelope.items() if k != "signature"}
        assert signer.verify(payload, envelope["kid"], envelope["signature"]) is True

    def test_signature_survives_json_roundtrip(self, signer_enabled):
        # The client stores/transmits the envelope as JSON text; the bytes
        # rebuilt from the parsed dict must verify identically.
        envelope = snapshot_service.build_envelope(_make_cart(), _make_terminal_info())
        roundtripped = json.loads(json.dumps(envelope))

        signer = HmacSigner.from_spec(KEY_SPEC)
        payload = {k: v for k, v in roundtripped.items() if k != "signature"}
        assert signer.verify(payload, roundtripped["kid"], roundtripped["signature"]) is True

    def test_masters_are_included(self, signer_enabled):
        cart = _make_cart()
        envelope = snapshot_service.build_envelope(cart, _make_terminal_info())
        assert "masters" in envelope["cart_document"]

    def test_no_keys_returns_none(self, signer_disabled):
        assert snapshot_service.build_envelope(_make_cart(), _make_terminal_info()) is None

    def test_malformed_keys_degrade_to_none(self, monkeypatch):
        monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", "not-a-valid-spec")
        snapshot_service.init_snapshot_signer(force=True)
        try:
            assert snapshot_service.build_envelope(_make_cart(), _make_terminal_info()) is None
        finally:
            snapshot_service.init_snapshot_signer(force=True)

    def test_generation_failure_degrades_without_raising(self, signer_enabled, caplog):
        class BrokenCart:
            cart_id = "broken"

            def model_dump(self, mode=None):
                raise RuntimeError("boom")

        result = snapshot_service.build_envelope(BrokenCart(), _make_terminal_info())
        assert result is None
        assert any("Snapshot generation failed" in r.message for r in caplog.records)

    def test_size_warning_over_threshold(self, signer_enabled, monkeypatch, caplog):
        monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 12)
        import logging

        with caplog.at_level(logging.WARNING):
            envelope = snapshot_service.build_envelope(_make_cart(), _make_terminal_info())
        assert envelope is not None  # warn only, never drop the snapshot
        assert any("bytes raw" in r.getMessage() and "budget" in r.getMessage() for r in caplog.records)

    def test_the_warning_tracks_the_ceiling_that_will_refuse_the_snapshot(self, signer_enabled, monkeypatch, caplog):
        """One number, not two kept in step by hand (issue #195).

        The snapshot is warned about because the client has to send it back, so
        the size worth warning at is a fraction of the request ceiling. Raising
        the ceiling must move the warning with it, not leave a stale threshold
        firing on every large basket.
        """
        import logging

        monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 12)
        with caplog.at_level(logging.WARNING):
            assert snapshot_service.build_envelope(_make_cart(), _make_terminal_info()) is not None
        assert caplog.records, "a snapshot past 75% of a 12 byte ceiling should warn"

        caplog.clear()
        monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 4 * 1024 * 1024)
        with caplog.at_level(logging.WARNING):
            assert snapshot_service.build_envelope(_make_cart(), _make_terminal_info()) is not None
        assert not caplog.records, "the same snapshot must be silent once the ceiling is raised"


# =========================================================================
# The cart is bounded by what the client can send back (issue #200)
# =========================================================================


class TestTheSizeBudget:
    """The server must never issue a snapshot it will not accept back.

    The snapshot is bounded by MAX_REQUEST_BODY_BYTES because the client has to
    present it on the next mutating request; the cart itself had no bound at
    all. Past that point the terminal holds an envelope it cannot return, and
    under CART_REQUEST_SNAPSHOT_MODE=REQUIRED the cart can be neither completed
    nor cancelled.
    """

    def test_the_notice_comes_before_the_refusal(self):
        """Two fractions of the ceiling could be set the wrong way round.

        A warning above the refusal never fires: the cart is stopped first. The
        warning is therefore a fraction of the budget, not of the ceiling.
        """
        assert snapshot_service._snapshot_size_warn_bytes() < snapshot_service.snapshot_size_refuse_bytes()

    def test_the_budget_leaves_room_for_the_rest_of_the_request(self):
        """The envelope is not the whole body: the payload rides with it."""
        assert snapshot_service.snapshot_size_refuse_bytes() < settings.MAX_REQUEST_BODY_BYTES

    def test_both_move_with_the_ceiling(self, monkeypatch):
        """Raising the ceiling must raise the budget, not leave it stranded."""
        monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 8 * 1024 * 1024)
        assert snapshot_service.snapshot_size_refuse_bytes() == int(8 * 1024 * 1024 * 0.60)
        assert snapshot_service._snapshot_size_warn_bytes() < snapshot_service.snapshot_size_refuse_bytes()

    def test_measuring_does_not_issue_a_revision(self, signer_enabled):
        """Measuring must not consume what issuing consumes.

        build_envelope bumps revision once per issued snapshot (issue #165); a
        probe that did the same would advance it on every add and make the
        number meaningless as a replay signal.
        """
        cart = _make_cart()
        before = cart.revision

        snapshot_service.measure_envelope_bytes(cart, _make_terminal_info())

        assert cart.revision == before

    def test_the_measurement_is_the_size_of_what_would_be_issued(self, signer_enabled):
        """An estimate that can drift from the real envelope is not a guard."""
        cart = _make_cart()
        terminal = _make_terminal_info()

        measured = snapshot_service.measure_envelope_bytes(cart, terminal)
        issued = snapshot_service.build_envelope(cart, terminal)
        actual = len(canonical_json_bytes({k: v for k, v in issued.items() if k != "signature"}))

        # The issued one carries the bumped revision and a later timestamp, so
        # allow for those digits rather than demanding equality.
        assert abs(actual - measured) < 64

    def test_nothing_is_measured_when_no_snapshot_would_be_issued(self, monkeypatch):
        """No signing key means no envelope, so there is nothing to bound."""
        monkeypatch.setattr(snapshot_service, "get_snapshot_signer", lambda: None)

        assert snapshot_service.measure_envelope_bytes(_make_cart(), _make_terminal_info()) is None
