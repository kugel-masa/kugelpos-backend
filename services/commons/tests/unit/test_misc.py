# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.misc."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytz

from kugel_common.utils.misc import get_app_time, get_app_time_str, to_lower_camel


class TestGetAppTime:
    def test_converts_provided_datetime_to_app_timezone(self):
        utc_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with patch("kugel_common.utils.misc.settings") as mock_settings:
            mock_settings.TIMEZONE = "Asia/Tokyo"
            result = get_app_time(utc_dt)
        assert result.tzinfo is not None
        assert str(result.tzinfo) == "Asia/Tokyo"
        # 0:00 UTC = 9:00 JST
        assert result.hour == 9

    def test_no_arg_returns_now_in_app_timezone(self):
        with patch("kugel_common.utils.misc.settings") as mock_settings:
            mock_settings.TIMEZONE = "UTC"
            result = get_app_time()
        assert result.tzinfo is not None
        # Approximately "now"
        delta = abs((datetime.now(pytz.UTC) - result).total_seconds())
        assert delta < 5

    def test_aware_datetime_in_other_zone_is_converted(self):
        # 12:00 in Tokyo = 03:00 in UTC
        tokyo_dt = pytz.timezone("Asia/Tokyo").localize(datetime(2026, 1, 1, 12, 0))
        with patch("kugel_common.utils.misc.settings") as mock_settings:
            mock_settings.TIMEZONE = "UTC"
            result = get_app_time(tokyo_dt)
        assert result.hour == 3
        assert str(result.tzinfo) == "UTC"


class TestGetAppTimeStr:
    def test_returns_iso_string_for_provided_datetime(self):
        utc_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with patch("kugel_common.utils.misc.settings") as mock_settings:
            mock_settings.TIMEZONE = "UTC"
            result = get_app_time_str(utc_dt)
        # ISO format starts with the date
        assert result.startswith("2026-01-01T00:00:00")

    def test_no_arg_returns_iso_now(self):
        with patch("kugel_common.utils.misc.settings") as mock_settings:
            mock_settings.TIMEZONE = "UTC"
            result = get_app_time_str()
        # parse round-trip
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None


class TestToLowerCamel:
    def test_simple_snake_to_camel(self):
        assert to_lower_camel("snake_case_string") == "snakeCaseString"

    def test_single_word_unchanged(self):
        assert to_lower_camel("word") == "word"

    def test_empty_string(self):
        assert to_lower_camel("") == ""

    def test_leading_underscore_preserved(self):
        assert to_lower_camel("_private_field") == "_privateField"

    def test_multiple_leading_underscores_preserved(self):
        assert to_lower_camel("__dunder_field") == "__dunderField"

    def test_trailing_underscore_yields_empty_word(self):
        # "field_" → ["field", ""] → "field" + "" = "field"
        assert to_lower_camel("field_") == "field"

    def test_consecutive_inner_underscores(self):
        # "a__b" → ["a", "", "b"] → "a" + "" + "B" = "aB"
        assert to_lower_camel("a__b") == "aB"

    def test_preserves_first_word_case(self):
        # The first word is appended as-is (no lowercasing)
        assert to_lower_camel("ID_value") == "IDValue"
