# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.hmac_signer."""
import base64

import pytest

from kugel_common.utils.hmac_signer import HmacSigner, canonical_json_bytes


def make_spec(*pairs: tuple[str, bytes]) -> str:
    return ",".join(f"{kid}:{base64.b64encode(key).decode()}" for kid, key in pairs)


KEY_V1 = b"0" * 32
KEY_V2 = b"1" * 32


class TestCanonicalJsonBytes:
    def test_key_order_does_not_matter(self):
        a = canonical_json_bytes({"b": 1, "a": {"y": 2, "x": 3}})
        b = canonical_json_bytes({"a": {"x": 3, "y": 2}, "b": 1})
        assert a == b

    def test_compact_separators_and_ascii_escape(self):
        out = canonical_json_bytes({"name": "テスト", "n": 1})
        assert b" " not in out
        # Non-ASCII content must be escaped so the byte form is encoding-stable
        assert out == out.decode("ascii").encode("ascii")

    def test_roundtrip_through_json_is_stable(self):
        import json

        payload = {"amount": 100.5, "items": [{"code": "A", "qty": 2}], "note": None}
        again = json.loads(canonical_json_bytes(payload))
        assert canonical_json_bytes(again) == canonical_json_bytes(payload)


class TestFromSpec:
    def test_single_key(self):
        signer = HmacSigner.from_spec(make_spec(("v1", KEY_V1)))
        assert signer.current_kid == "v1"
        assert signer.kids == ["v1"]

    def test_two_generations_first_is_current(self):
        signer = HmacSigner.from_spec(make_spec(("v2", KEY_V2), ("v1", KEY_V1)))
        assert signer.current_kid == "v2"
        assert signer.kids == ["v2", "v1"]

    @pytest.mark.parametrize("spec", ["", "   ", "v1", "v1:", ":abc", "v1:not-base64!!"])
    def test_malformed_spec_raises(self, spec):
        with pytest.raises(ValueError):
            HmacSigner.from_spec(spec)

    def test_duplicate_kid_raises(self):
        with pytest.raises(ValueError):
            HmacSigner.from_spec(make_spec(("v1", KEY_V1), ("v1", KEY_V2)))


class TestSignVerify:
    def test_sign_then_verify_with_current_kid(self):
        signer = HmacSigner.from_spec(make_spec(("v1", KEY_V1)))
        payload = {"cart_id": "abc", "amount": 100}
        sig = signer.sign(payload)
        assert signer.verify(payload, "v1", sig) is True

    def test_tampered_payload_fails(self):
        signer = HmacSigner.from_spec(make_spec(("v1", KEY_V1)))
        sig = signer.sign({"amount": 100})
        assert signer.verify({"amount": 101}, "v1", sig) is False

    def test_previous_generation_verifies_after_rotation(self):
        old = HmacSigner.from_spec(make_spec(("v1", KEY_V1)))
        payload = {"cart_id": "abc"}
        sig_v1 = old.sign(payload)

        rotated = HmacSigner.from_spec(make_spec(("v2", KEY_V2), ("v1", KEY_V1)))
        assert rotated.current_kid == "v2"
        assert rotated.verify(payload, "v1", sig_v1) is True
        # New signatures use the new key
        assert rotated.verify(payload, "v2", rotated.sign(payload)) is True

    def test_unknown_kid_raises_key_error(self):
        signer = HmacSigner.from_spec(make_spec(("v2", KEY_V2)))
        with pytest.raises(KeyError):
            signer.verify({"a": 1}, "v1", "00" * 32)

    def test_signature_is_independent_of_dict_order(self):
        signer = HmacSigner.from_spec(make_spec(("v1", KEY_V1)))
        sig = signer.sign({"b": 1, "a": 2})
        assert signer.verify({"a": 2, "b": 1}, "v1", sig) is True
