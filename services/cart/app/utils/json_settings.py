# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
Utility functions for handling JSON-based settings.

This module provides functions to properly serialize and deserialize
settings that need to be stored as JSON strings in MongoDB.
"""

import json
from typing import Any
from logging import getLogger

logger = getLogger(__name__)


def serialize_setting_value(value: Any) -> str:
    """
    Serialize a setting value to a JSON string for storage.

    This function ensures that complex data types (lists, dicts) are
    properly serialized to JSON format with double quotes, avoiding
    the Python str() representation with single quotes.

    Args:
        value: The value to serialize (can be dict, list, str, etc.)

    Returns:
        JSON string representation of the value

    Example:
        >>> serialize_setting_value([{"text": "Hello", "align": "left"}])
        '[{"text": "Hello", "align": "left"}]'
    """
    if isinstance(value, str):
        # Already a string, return as-is
        return value

    try:
        # Serialize to JSON with double quotes
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize setting value: {e}")
        # Fallback to string representation
        return str(value)


def deserialize_setting_value(value_str: str) -> Any:
    """
    Deserialize a setting value from a JSON string.

    This function handles both standard JSON format and Python
    literal format (with single quotes) that may exist in legacy data.

    Args:
        value_str: The string value to deserialize

    Returns:
        Deserialized value (dict, list, etc.) or original string if parsing fails

    Example:
        >>> deserialize_setting_value('[{"text": "Hello", "align": "left"}]')
        [{'text': 'Hello', 'align': 'left'}]
        >>> deserialize_setting_value("[{'text': 'Hello', 'align': 'left'}]")
        [{'text': 'Hello', 'align': 'left'}]
    """
    if not isinstance(value_str, str):
        return value_str

    # Try standard JSON parsing first
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        pass

    # Try Python literal evaluation for legacy data
    try:
        import ast

        return ast.literal_eval(value_str)
    except (ValueError, SyntaxError):
        pass

    # Return original string if parsing fails
    return value_str


def prepare_receipt_headers_for_storage(headers: list[dict]) -> str:
    """
    Prepare receipt headers for storage in settings.

    Args:
        headers: List of header configurations

    Returns:
        JSON string representation

    Example:
        >>> headers = [
        ...     {"text": "Welcome", "align": "center"},
        ...     {"text": "", "align": "left"},  # blank line
        ...     {"text": "Tax Invoice", "align": "center"}
        ... ]
        >>> prepare_receipt_headers_for_storage(headers)
        '[{"text": "Welcome", "align": "center"}, {"text": "", "align": "left"}, {"text": "Tax Invoice", "align": "center"}]'
    """
    return serialize_setting_value(headers)


def prepare_receipt_footers_for_storage(footers: list[dict]) -> str:
    """
    Prepare receipt footers for storage in settings.

    Args:
        footers: List of footer configurations

    Returns:
        JSON string representation

    Example:
        >>> footers = [
        ...     {"text": "", "align": "left"},  # blank line
        ...     {"text": "Thank you!", "align": "center"},
        ...     {"text": "Visit again!", "align": "center"}
        ... ]
        >>> prepare_receipt_footers_for_storage(footers)
        '[{"text": "", "align": "left"}, {"text": "Thank you!", "align": "center"}, {"text": "Visit again!", "align": "center"}]'
    """
    return serialize_setting_value(footers)
