# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
Type definitions for receipt header and footer configurations.

This module provides type-safe definitions for receipt customization
including headers and footers with text alignment options.
"""

from typing import TypedDict, Literal, List

# Valid alignment options for receipt text
AlignmentType = Literal["left", "center", "right"]

# Set of valid alignments for validation
VALID_ALIGNMENTS = {"left", "center", "right"}

# Default alignment when none specified or invalid
DEFAULT_ALIGNMENT: AlignmentType = "left"


class ReceiptLineConfig(TypedDict):
    """
    Configuration for a single line in receipt header or footer.

    Attributes:
        text: The text content to display (empty string creates blank line)
        align: Text alignment (left, center, or right)
    """

    text: str
    align: AlignmentType


def validate_receipt_line(line_data: dict) -> ReceiptLineConfig | None:
    """
    Validate and convert raw receipt line data to typed format.

    Args:
        line_data: Raw dictionary containing line configuration

    Returns:
        Validated ReceiptLineConfig or None if invalid
    """
    if not isinstance(line_data, dict):
        return None

    # textが存在しない場合は空文字列として扱う
    text = line_data.get("text", "")
    if not isinstance(text, str):
        return None

    align = line_data.get("align", DEFAULT_ALIGNMENT)
    if align not in VALID_ALIGNMENTS:
        align = DEFAULT_ALIGNMENT

    return ReceiptLineConfig(text=text, align=align)


def validate_receipt_lines(lines_data: List[dict]) -> List[ReceiptLineConfig]:
    """
    Validate and convert a list of receipt line configurations.

    Args:
        lines_data: List of raw dictionaries containing line configurations

    Returns:
        List of validated ReceiptLineConfig objects
    """
    validated_lines = []

    if not isinstance(lines_data, list):
        return validated_lines

    for line_data in lines_data:
        validated_line = validate_receipt_line(line_data)
        if validated_line is not None:  # 空のテキストも許可
            validated_lines.append(validated_line)

    return validated_lines
