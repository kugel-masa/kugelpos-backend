import pytest
import wcwidth
from kugel_common.utils.text_helper import TextHelper


class TestTextHelper:
    """Test cases for TextHelper utility class."""

    def test_truncate_text_ascii(self):
        """Test truncate_text with ASCII characters."""
        # Text shorter than max width
        assert TextHelper.truncate_text("Hello", 10) == "Hello"
        
        # Text exactly at max width
        assert TextHelper.truncate_text("Hello World", 11) == "Hello World"
        
        # Text longer than max width
        result = TextHelper.truncate_text("Very long product description here", 25)
        assert result == "Very long product descrip"
        assert wcwidth.wcswidth(result) == 25
        
    def test_truncate_text_japanese(self):
        """Test truncate_text with Japanese characters."""
        # Japanese text (each character is 2 width)
        text = "とても長い商品名です。これは30文字以上"
        
        # Truncate to 20 width
        result = TextHelper.truncate_text(text, 20)
        assert result == "とても長い商品名です"
        assert wcwidth.wcswidth(result) == 20
        
        # Truncate to 15 width (should break at character boundary)
        result = TextHelper.truncate_text(text, 15)
        assert wcwidth.wcswidth(result) <= 15
        assert wcwidth.wcswidth(result) % 2 == 0  # Should be even for Japanese
        
    def test_truncate_text_mixed(self):
        """Test truncate_text with mixed ASCII and Japanese."""
        text = "Product商品ABC"  # "Product" = 7, "商品" = 4, "ABC" = 3, total = 14
        
        # Mixed text truncation to width 10
        result = TextHelper.truncate_text(text, 10)
        assert result == "Product商"  # "Product" = 7, "商" = 2, total = 9 (next char would exceed)
        assert wcwidth.wcswidth(result) == 9  # Can't fit exactly 10 due to character boundaries
        
    def test_truncate_text_with_suffix(self):
        """Test truncate_text with suffix option."""
        text = "Very long product description here"
        
        # With suffix
        result = TextHelper.truncate_text(text, 25, "...")
        assert result == "Very long product desc..."
        assert wcwidth.wcswidth(result) == 25
        
        # Suffix takes all space
        result = TextHelper.truncate_text(text, 3, "...")
        assert result == "..."
        
    def test_truncate_text_edge_cases(self):
        """Test truncate_text edge cases."""
        # Zero width
        assert TextHelper.truncate_text("Hello", 0) == ""
        
        # Negative width
        assert TextHelper.truncate_text("Hello", -5) == ""
        
        # Empty string
        assert TextHelper.truncate_text("", 10) == ""
        
    def test_fixed_left_without_truncate(self):
        """Test fixed_left without truncate option (default behavior)."""
        # Text shorter than width - should pad
        result = TextHelper.fixed_left("Hello", 10)
        assert result == "Hello     "
        assert wcwidth.wcswidth(result) == 10
        
        # Text longer than width - no truncation by default
        result = TextHelper.fixed_left("Very long text", 5)
        assert result == "Very long text"  # No truncation
        
    def test_fixed_left_with_truncate(self):
        """Test fixed_left with truncate=True."""
        # Text shorter than width - should pad
        result = TextHelper.fixed_left("Hello", 10, truncate=True)
        assert result == "Hello     "
        assert len(result) == 10
        
        # Text longer than width - should truncate
        result = TextHelper.fixed_left("Very long text", 10, truncate=True)
        assert result == "Very long "
        assert wcwidth.wcswidth(result) == 10
        
    def test_fixed_left_japanese_truncate(self):
        """Test fixed_left with Japanese text and truncate."""
        text = "商品名です"  # 10 visual width (each char is 2 width)
        
        # Without truncate - overflow
        result = TextHelper.fixed_left(text, 8, truncate=False)
        assert wcwidth.wcswidth(result) == 10
        
        # With truncate - fits in width
        result = TextHelper.fixed_left(text, 8, truncate=True)
        # Text gets truncated to "商品名で" (8 width), no padding needed
        assert result == "商品名で"  # Exactly 8 width, no padding
        assert wcwidth.wcswidth(result) == 8
        
    def test_line_split_simulation(self):
        """Test line_split behavior simulation."""
        receipt_width = 32
        item1 = "とても長い商品名です。これは30文字以上"
        item2 = "999,999"
        
        # Calculate widths as in line_split
        len_item2 = wcwidth.wcswidth(item2)
        width_item1 = receipt_width - len_item2
        
        # Without truncate - overflow
        left_part_old = TextHelper.fixed_left(item1, width_item1, truncate=False)
        full_line_old = left_part_old + item2
        assert wcwidth.wcswidth(full_line_old) > receipt_width
        
        # With truncate - fits perfectly
        left_part_new = TextHelper.fixed_left(item1, width_item1, truncate=True)
        full_line_new = left_part_new + item2
        assert wcwidth.wcswidth(full_line_new) == receipt_width