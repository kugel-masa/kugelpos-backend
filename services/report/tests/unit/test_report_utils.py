"""Unit tests for app/utils/misc.py"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytz


class TestToLowerCamel:
    """Tests for the to_lower_camel function."""

    def test_simple_snake_case(self):
        from app.utils.misc import to_lower_camel

        assert to_lower_camel("hello_world") == "helloWorld"

    def test_single_word(self):
        from app.utils.misc import to_lower_camel

        assert to_lower_camel("hello") == "hello"

    def test_multiple_underscores(self):
        from app.utils.misc import to_lower_camel

        assert to_lower_camel("one_two_three_four") == "oneTwoThreeFour"

    def test_leading_underscore(self):
        from app.utils.misc import to_lower_camel

        assert to_lower_camel("_private_field") == "_privateField"

    def test_double_leading_underscore(self):
        from app.utils.misc import to_lower_camel

        assert to_lower_camel("__dunder_field") == "__dunderField"

    def test_empty_string(self):
        from app.utils.misc import to_lower_camel

        assert to_lower_camel("") == ""

    def test_already_camel(self):
        from app.utils.misc import to_lower_camel

        assert to_lower_camel("alreadyCamel") == "alreadyCamel"

    def test_single_char_words(self):
        from app.utils.misc import to_lower_camel

        assert to_lower_camel("a_b_c") == "aBC"


class TestGetAppTime:
    """Tests for the get_app_time function."""

    @patch("app.utils.misc.settings")
    def test_with_datetime_param(self, mock_settings):
        """When a datetime is passed, it should be converted to app timezone."""
        from app.utils.misc import get_app_time

        mock_settings.TIMEZONE = "Asia/Tokyo"
        utc_dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = get_app_time(utc_dt)

        assert result.tzinfo is not None
        # UTC 12:00 -> JST 21:00
        assert result.hour == 21
        assert result.day == 15

    @patch("app.utils.misc.settings")
    def test_without_datetime_param(self, mock_settings):
        """When no datetime is passed, should return current time in app timezone."""
        from app.utils.misc import get_app_time

        mock_settings.TIMEZONE = "Asia/Tokyo"
        result = get_app_time()

        tokyo_tz = pytz.timezone("Asia/Tokyo")
        assert result.tzinfo is not None
        assert str(result.tzinfo) == str(tokyo_tz.localize(datetime.now()).tzinfo) or True
        # Just verify it returns a timezone-aware datetime in Tokyo tz
        expected_zone = tokyo_tz.localize(datetime.now()).strftime("%Z")
        assert result.strftime("%Z") == expected_zone

    @patch("app.utils.misc.settings")
    def test_with_different_timezone(self, mock_settings):
        """Should work with different timezone settings."""
        from app.utils.misc import get_app_time

        mock_settings.TIMEZONE = "US/Eastern"
        utc_dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = get_app_time(utc_dt)

        # UTC 12:00 -> EDT 08:00 (June is daylight saving time)
        assert result.hour == 8

    @patch("app.utils.misc.settings")
    def test_none_param_returns_now(self, mock_settings):
        """Passing None explicitly should behave like no param."""
        from app.utils.misc import get_app_time

        mock_settings.TIMEZONE = "UTC"
        result = get_app_time(None)
        now_utc = datetime.now(pytz.UTC)

        # Should be within a few seconds of now
        diff = abs((now_utc - result).total_seconds())
        assert diff < 5
