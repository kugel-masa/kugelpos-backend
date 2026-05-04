# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.text_helper.TextHelper."""

from kugel_common.utils.text_helper import TextHelper


class TestSpace:
    def test_zero_width_returns_empty(self):
        assert TextHelper.space(0) == ""

    def test_positive_width_returns_spaces(self):
        assert TextHelper.space(5) == "     "

    def test_negative_width_returns_empty(self):
        # Python: "x" * -1 == ""
        assert TextHelper.space(-3) == ""


class TestComma:
    def test_thousands_separator(self):
        assert TextHelper.comma(1234567) == "1,234,567"

    def test_zero(self):
        assert TextHelper.comma(0) == "0"

    def test_negative(self):
        assert TextHelper.comma(-1234) == "-1,234"

    def test_float_truncates_decimals(self):
        # Format spec is .0f — fractional part is dropped (rounded)
        assert TextHelper.comma(1234.5) == "1,234" or TextHelper.comma(1234.5) == "1,235"


class TestYen:
    def test_positive_uses_default_mark(self):
        assert TextHelper.yen(1000) == "\\1,000"

    def test_negative_uses_single_minus(self):
        # A single leading minus sign for negatives — no double-sign.
        assert TextHelper.yen(-1000) == "-1,000"

    def test_negative_with_custom_mark_still_uses_minus(self):
        # Negatives override the currency mark with a single minus sign,
        # regardless of what mark was passed in.
        assert TextHelper.yen(-500, mark="$") == "-500"

    def test_custom_mark(self):
        assert TextHelper.yen(500, mark="$") == "$500"

    def test_zero(self):
        assert TextHelper.yen(0) == "\\0"


class TestZeroFill:
    def test_pads_to_width(self):
        assert TextHelper.zero_fill(7, 4) == "0007"

    def test_no_pad_when_already_wide(self):
        assert TextHelper.zero_fill(12345, 3) == "12345"

    def test_zero_value(self):
        assert TextHelper.zero_fill(0, 5) == "00000"


class TestTruncateText:
    def test_short_text_returned_as_is(self):
        assert TextHelper.truncate_text("hello", 10) == "hello"

    def test_truncates_when_too_long(self):
        # "hello world" is 11 chars wide; truncate to 5 yields "hello"
        assert TextHelper.truncate_text("hello world", 5) == "hello"

    def test_truncate_with_suffix(self):
        # "hello world" → keep room for "...", target_width = 8 - 3 = 5
        # Result: "hello" + "..."
        assert TextHelper.truncate_text("hello world", 8, suffix="...") == "hello..."

    def test_zero_max_width_returns_empty(self):
        assert TextHelper.truncate_text("abc", 0) == ""

    def test_negative_max_width_returns_empty(self):
        assert TextHelper.truncate_text("abc", -1) == ""

    def test_suffix_longer_than_max_width(self):
        # target_width <= 0 → just slice the suffix
        assert TextHelper.truncate_text("hello", 2, suffix="...") == ".."

    def test_multibyte_double_width(self):
        # Japanese characters are 2-cell wide; "ab漢" = 1+1+2 = 4 cells
        result = TextHelper.truncate_text("ab漢字", 3)
        assert result == "ab"  # cannot fit "漢" (2 cells) with 1 cell remaining


class TestFixedLeft:
    def test_pads_with_spaces(self):
        assert TextHelper.fixed_left("ab", 5) == "ab   "

    def test_already_wide_returns_as_is(self):
        assert TextHelper.fixed_left("hello", 3) == "hello"

    def test_truncate_when_requested(self):
        assert TextHelper.fixed_left("hello", 3, truncate=True) == "hel"

    def test_multibyte_padding(self):
        # 漢 is 2-cell wide; pad to 5 cells means 3 spaces
        assert TextHelper.fixed_left("漢", 5) == "漢   "


class TestFixedRight:
    def test_pads_left(self):
        assert TextHelper.fixed_right("ab", 5) == "   ab"

    def test_already_wide_returns_as_is(self):
        assert TextHelper.fixed_right("hello", 3) == "hello"

    def test_multibyte(self):
        assert TextHelper.fixed_right("漢", 5) == "   漢"


class TestFixedCenter:
    def test_centers_with_balanced_padding(self):
        # 5-cell field with "ab" (2 cells) → 1 left + "ab" + 2 right
        assert TextHelper.fixed_center("ab", 5) == " ab  "

    def test_even_width_padding(self):
        # 6-cell field with "ab" (2 cells) → 2 left + "ab" + 2 right
        assert TextHelper.fixed_center("ab", 6) == "  ab  "

    def test_already_wide_returns_as_is(self):
        assert TextHelper.fixed_center("hello", 3) == "hello"
