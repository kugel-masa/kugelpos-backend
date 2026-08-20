# Copyright 2026 masa@kugel
"""Unit tests for the request-log body sanitizer (issue #155).

The middleware stores every request and response body twice (log file +
`request_log` collection). The signed cart snapshot (#148 / #156) carries a
whole cart document on every mutating call, so the sanitizer replaces it with
a metadata marker and applies a size backstop to whatever is left.
"""

import json

import pytest

from kugel_common.utils.log_utils import (
    DEFAULT_LOG_STRIP_FIELDS,
    parse_log_strip_fields,
    sanitize_log_body,
)


def _envelope(items: int = 40) -> dict:
    """A snapshot envelope shaped like the one cart issues."""
    return {
        "schema_version": 1,
        "issued_at": "2026-08-20T10:00:00",
        "kid": "v1",
        "tenant_id": "A1234",
        "store_code": "5678",
        "terminal_no": 9,
        "cart_document": {
            "cart_id": "cart-1",
            "line_items": [{"item_code": f"{i:013d}", "description": "x" * 64} for i in range(items)],
        },
        "signature": "a" * 64,
    }


class TestParseLogStripFields:
    def test_none_disables_stripping(self):
        assert parse_log_strip_fields(None) == ()

    def test_empty_disables_stripping(self):
        assert parse_log_strip_fields("") == ()

    def test_comma_separated_names_are_trimmed(self):
        assert parse_log_strip_fields(" a , b ,, c ") == ("a", "b", "c")

    def test_default_setting_value_round_trips(self):
        assert parse_log_strip_fields(",".join(DEFAULT_LOG_STRIP_FIELDS)) == DEFAULT_LOG_STRIP_FIELDS


class TestStripping:
    def test_none_body_stays_none(self):
        assert sanitize_log_body(None) is None

    def test_body_without_stripped_field_is_unchanged(self):
        body = {"itemCode": "49-1", "quantity": 2}
        assert sanitize_log_body(body) == body

    def test_camel_case_snapshot_is_replaced_by_marker(self):
        body = {"payload": {"quantity": 1}, "signedSnapshot": _envelope()}
        result = sanitize_log_body(body)
        assert result["payload"] == {"quantity": 1}
        assert result["signedSnapshot"]["_stripped"] == "signedSnapshot"

    def test_snake_case_snapshot_is_replaced_by_marker(self):
        result = sanitize_log_body({"signed_snapshot": _envelope()})
        assert result["signed_snapshot"]["_stripped"] == "signed_snapshot"

    def test_marker_keeps_scalar_metadata(self):
        marker = sanitize_log_body({"signedSnapshot": _envelope()})["signedSnapshot"]
        assert marker["kid"] == "v1"
        assert marker["schema_version"] == 1
        assert marker["issued_at"] == "2026-08-20T10:00:00"
        assert marker["terminal_no"] == 9

    def test_marker_drops_the_bulk_and_the_signature(self):
        marker = sanitize_log_body({"signedSnapshot": _envelope()})["signedSnapshot"]
        assert "cart_document" not in marker
        assert "signature" not in marker

    def test_stripping_collapses_the_logged_size(self):
        body = {"data": {"cartId": "cart-1", "signedSnapshot": _envelope()}}
        before = len(json.dumps(body))
        after = len(json.dumps(sanitize_log_body(body)))
        assert after < before / 10

    def test_nested_and_listed_snapshots_are_stripped(self):
        body = {"data": [{"signedSnapshot": _envelope()}, {"signedSnapshot": _envelope()}]}
        result = sanitize_log_body(body)
        assert all(entry["signedSnapshot"]["_stripped"] == "signedSnapshot" for entry in result["data"])

    def test_top_level_list_body_stays_a_list(self):
        result = sanitize_log_body([{"signedSnapshot": _envelope()}])
        assert isinstance(result, list)
        assert result[0]["signedSnapshot"]["_stripped"] == "signedSnapshot"

    def test_empty_strip_fields_keeps_the_snapshot(self):
        body = {"signedSnapshot": _envelope()}
        assert sanitize_log_body(body, strip_fields=()) == body

    def test_original_body_is_not_mutated(self):
        body = {"signedSnapshot": _envelope()}
        sanitize_log_body(body)
        assert "cart_document" in body["signedSnapshot"]

    def test_scalar_valued_field_still_yields_a_marker(self):
        # A client may send anything under the name; the marker must not assume a dict.
        result = sanitize_log_body({"signedSnapshot": "not-an-object"})
        assert result["signedSnapshot"] == {"_stripped": "signedSnapshot"}


class TestTruncationBackstop:
    def test_disabled_by_default(self):
        body = {"blob": "x" * 100_000}
        assert sanitize_log_body(body) == body

    def test_body_over_budget_is_replaced_by_a_marker(self):
        body = {"blob": "x" * 100_000}
        result = sanitize_log_body(body, max_bytes=1024)
        assert result["_truncated"] is True
        assert result["_encoded_bytes"] > 100_000
        assert result["_preview"].startswith('{"blob": "xxx')

    def test_body_within_budget_is_kept(self):
        body = {"blob": "x" * 100}
        assert sanitize_log_body(body, max_bytes=1024) == body

    def test_truncation_marker_is_small(self):
        result = sanitize_log_body({"blob": "x" * 100_000}, max_bytes=1024)
        assert len(json.dumps(result)) < 1024

    def test_stripping_can_bring_a_body_back_under_budget(self):
        body = {"signedSnapshot": _envelope(items=200)}
        result = sanitize_log_body(body, max_bytes=2048, raw=json.dumps(body).encode())
        assert "_truncated" not in result
        assert result["signedSnapshot"]["kid"] == "v1"

    def test_small_raw_body_skips_the_size_check(self):
        # Stripping only shrinks, so a small raw body needs no re-serialization.
        body = {"quantity": 1}
        assert sanitize_log_body(body, max_bytes=1024, raw=b'{"quantity": 1}') == body

    def test_marker_never_exceeds_a_small_budget(self):
        # The ceiling has to hold for small budgets too, not just large ones.
        for budget in (32, 64, 256):
            result = sanitize_log_body({"blob": "x" * 100_000}, max_bytes=budget)
            assert len(result["_preview"]) <= budget
            # What is left on top is the marker's own keys, not payload.
            assert len(json.dumps(result)) <= budget + 100

    @pytest.mark.parametrize("max_bytes", [0, -1])
    def test_non_positive_budget_disables_the_backstop(self, max_bytes):
        body = {"blob": "x" * 100_000}
        assert sanitize_log_body(body, max_bytes=max_bytes) == body


class TestRawByteEarlyOut:
    def test_raw_without_the_field_name_skips_the_walk(self):
        # The scan says "not present", so the body is returned as-is (identity).
        body = {"quantity": 1, "nested": {"deep": [1, 2, 3]}}
        assert sanitize_log_body(body, raw=b'{"quantity": 1}') is body

    def test_raw_mentioning_the_field_still_strips(self):
        body = {"signedSnapshot": _envelope()}
        raw = json.dumps(body).encode()
        assert sanitize_log_body(body, raw=raw)["signedSnapshot"]["_stripped"] == "signedSnapshot"

    def test_absent_raw_falls_back_to_walking(self):
        body = {"signedSnapshot": _envelope()}
        assert sanitize_log_body(body, raw=None)["signedSnapshot"]["_stripped"] == "signedSnapshot"


class TestNeverRaises:
    def test_unserializable_member_is_coerced_by_default_str(self):
        body = {"when": object()}
        result = sanitize_log_body(body, max_bytes=8)
        assert result["_truncated"] is True

    def test_deeply_nested_body_is_returned_without_raising(self):
        body = current = {}
        for _ in range(200):
            current["next"] = {}
            current = current["next"]
        current["signedSnapshot"] = _envelope()
        result = sanitize_log_body(body)
        assert isinstance(result, dict)


class TestMarkerMetadataBudget:
    def test_short_scalars_are_kept(self):
        marker = sanitize_log_body({"signedSnapshot": {"kid": "v1", "revision": 7}})["signedSnapshot"]
        assert marker["kid"] == "v1"
        assert marker["revision"] == 7

    def test_long_string_member_is_dropped(self):
        # A scalar type is no guarantee of a small value.
        body = {"signedSnapshot": {"kid": "v1", "blob": "x" * 100_000}}
        marker = sanitize_log_body(body)["signedSnapshot"]
        assert marker["kid"] == "v1"
        assert "blob" not in marker


class TestRawBytesReuse:
    def test_untouched_oversized_body_is_measured_from_raw(self):
        body = {"blob": "x" * 100_000}
        raw = json.dumps(body).encode()
        result = sanitize_log_body(body, max_bytes=1024, raw=raw)
        assert result["_encoded_bytes"] == len(raw)
        assert result["_preview"].startswith('{"blob": "xxx')

    def test_multibyte_preview_is_not_broken_by_a_byte_slice(self):
        body = {"名前": "あ" * 20_000}
        raw = json.dumps(body, ensure_ascii=False).encode()
        result = sanitize_log_body(body, max_bytes=64, raw=raw)
        assert result["_truncated"] is True
        assert len(result["_preview"]) <= 64

    def test_stripped_body_is_re_serialized_rather_than_measured_from_raw(self):
        # The raw bytes describe the pre-strip body, so they cannot be reused.
        body = {"signedSnapshot": _envelope(items=400), "quantity": 1}
        raw = json.dumps(body).encode()
        result = sanitize_log_body(body, max_bytes=4096, raw=raw)
        assert "_truncated" not in result
        assert result["quantity"] == 1


class TestDepthCap:
    def test_snapshot_above_the_cap_is_stripped(self):
        body = current = {}
        for _ in range(30):
            current["next"] = {}
            current = current["next"]
        current["signedSnapshot"] = _envelope()
        result = sanitize_log_body(body)
        node = result
        for _ in range(30):
            node = node["next"]
        assert node["signedSnapshot"]["_stripped"] == "signedSnapshot"

    def test_snapshot_deeper_than_the_cap_falls_to_the_size_backstop(self):
        # Documented limit: the walk stops at _MAX_STRIP_DEPTH (32). Anything
        # nested deeper keeps its snapshot and is bounded by the size backstop.
        body = current = {}
        for _ in range(40):
            current["next"] = {}
            current = current["next"]
        current["signedSnapshot"] = _envelope()
        result = sanitize_log_body(body, max_bytes=4096, raw=json.dumps(body).encode())
        assert result["_truncated"] is True
