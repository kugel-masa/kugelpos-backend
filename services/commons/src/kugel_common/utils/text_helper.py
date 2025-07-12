# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import wcwidth

"""
Text formatting and manipulation utilities.

This module provides helper functions for formatting text for display purposes,
particularly useful for receipt and journal printing where precise text alignment
and formatting are required.
"""

class TextHelper:
    """
    Utility class for text formatting operations.
    
    Provides static methods for common text formatting tasks such as padding,
    alignment, number formatting, and currency display. These functions are
    particularly useful for receipt generation and fixed-width text display.
    """

    @staticmethod
    def space(width: int) -> str:
        """
        Generate a string of spaces with the specified width.
        
        Args:
            width: Number of spaces to generate
            
        Returns:
            String containing the specified number of spaces
        """
        return " " * width

    @staticmethod
    def comma(value: float) -> str:
        """
        Format a number with comma separators for thousands.
        
        Args:
            value: Numeric value to format
            
        Returns:
            String representation of the number with comma separators
        """
        return "{:,.0f}".format(value)

    @staticmethod
    def yen(value: float, mark: str = '\\') -> str:
        """
        Format a currency value with the specified currency mark.
        
        Handles negative values by replacing the currency mark with a minus sign.
        
        Args:
            value: Currency value to format
            mark: Currency symbol to use (defaults to '\' for Japanese Yen)
            
        Returns:
            Formatted currency string with the appropriate symbol and comma separators
        """
        if value < 0:
            mark = "-"
        return mark + TextHelper.comma(value)

    @staticmethod
    def zero_fill(value: int, width: int) -> str:
        """
        Pad a number with leading zeros to reach the specified width.
        
        Args:
            value: Numeric value to pad
            width: Target width for the padded string
            
        Returns:
            Zero-padded string representation of the value
        """
        return str(value).zfill(width)

    @staticmethod
    def truncate_text(text: str, max_width: int, suffix: str = "") -> str:
        """
        Truncate text to fit within the specified visual width.
        
        Correctly handles multi-byte characters by truncating at character
        boundaries without breaking characters.
        
        Args:
            text: Text to truncate
            max_width: Maximum visual width
            suffix: Optional suffix to append when truncated (e.g., "...")
            
        Returns:
            Truncated text that fits within max_width
        """
        if max_width <= 0:
            return ""
            
        text_width = wcwidth.wcswidth(text)
        if text_width is None:
            text_width = 0
            
        # If text already fits, return as-is
        if text_width <= max_width:
            return text
            
        # Account for suffix width
        suffix_width = wcwidth.wcswidth(suffix) if suffix else 0
        target_width = max_width - suffix_width
        
        if target_width <= 0:
            return suffix[:max_width]
        
        # Accumulate characters from the start until the target width is reached
        result = ""
        current_width = 0
        
        for char in text:
            char_width = wcwidth.wcwidth(char)
            if char_width is None:
                char_width = 1  # Default to 1 for unknown characters
                
            if current_width + char_width > target_width:
                break
                
            result += char
            current_width += char_width
            
        return result + suffix

    @staticmethod
    def fixed_left(text: str, width: int, truncate: bool = False) -> str:
        """
        Left-align text within a field of specified width.
        
        Correctly handles multi-byte characters (e.g., Japanese text) by using
        the wcwidth library to calculate visual width.
        
        Args:
            text: Text to align
            width: Target width of the field
            truncate: If True, truncate text that exceeds width
            
        Returns:
            Left-aligned text padded with spaces to the specified width
        """
        current_width = wcwidth.wcswidth(text)
        if current_width is None:
            current_width = 0
        if truncate and current_width > width:
            text = TextHelper.truncate_text(text, width)
        padding = max(0, width - current_width)
        return text + " " * padding

    @staticmethod
    def fixed_right(text: str, width: int) -> str:
        """
        Right-align text within a field of specified width.
        
        Correctly handles multi-byte characters (e.g., Japanese text) by using
        the wcwidth library to calculate visual width.
        
        Args:
            text: Text to align
            width: Target width of the field
            
        Returns:
            Right-aligned text with the appropriate number of leading spaces
        """
        current_width = wcwidth.wcswidth(text)
        if current_width is None:
            current_width = 0
        padding = max(0, width - current_width)
        return " " * padding + text

    @staticmethod
    def fixed_center(text: str, width: int) -> str:
        """
        Center-align text within a field of specified width.
        
        Correctly handles multi-byte characters (e.g., Japanese text) by using
        the wcwidth library to calculate visual width.
        
        Args:
            text: Text to align
            width: Target width of the field
            
        Returns:
            Center-aligned text with appropriate spaces on both sides
        """
        current_width = wcwidth.wcswidth(text)
        if current_width is None:
            current_width = 0
        padding = max(0, width - current_width)
        left = padding // 2
        right = padding - left
        return " " * left + text + " " * right