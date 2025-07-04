# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
Utility functions for handling JSON-based settings in master-data service.

This module provides functions to properly serialize complex settings values
to JSON format before storing them in MongoDB, ensuring compatibility with
downstream services.
"""

import json
from typing import Any
from logging import getLogger

logger = getLogger(__name__)


def is_json_serializable(value: str) -> bool:
    """
    Check if a string value appears to be JSON data that needs serialization.

    Args:
        value: String value to check

    Returns:
        True if the value looks like JSON data (starts with [ or {)
    """
    if not isinstance(value, str):
        return False

    trimmed = value.strip()
    return trimmed.startswith(("[", "{")) and trimmed.endswith(("]", "}"))


def ensure_json_format(value: str) -> str:
    """
    Ensure that a complex setting value is stored in proper JSON format.

    This function checks if a value appears to be JSON data and ensures it's
    properly formatted with double quotes for storage in MongoDB.

    Args:
        value: The setting value to process

    Returns:
        Properly formatted JSON string or original value if not JSON

    Example:
        >>> ensure_json_format("[{'text': 'Hello', 'align': 'left'}]")
        '[{"text": "Hello", "align": "left"}]'
    """
    if not is_json_serializable(value):
        # Not JSON data, return as-is
        return value

    try:
        # Try to parse as JSON first (already properly formatted)
        parsed = json.loads(value)
        return json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError:
        pass

    try:
        # Try to parse as Python literal (single quotes)
        import ast

        parsed = ast.literal_eval(value)
        # Re-serialize as proper JSON
        return json.dumps(parsed, ensure_ascii=False)
    except (ValueError, SyntaxError) as e:
        logger.warning(f"Failed to parse setting value as JSON or literal: {e}")
        # Return original value if parsing fails
        return value


def process_setting_values(values: list[dict]) -> list[dict]:
    """
    Process a list of setting values to ensure JSON values are properly formatted.

    Args:
        values: List of setting value dictionaries

    Returns:
        List of processed setting values with JSON formatting applied
    """
    processed_values = []

    for value_dict in values:
        if "value" in value_dict and isinstance(value_dict["value"], str):
            value_dict = value_dict.copy()  # Don't modify original
            value_dict["value"] = ensure_json_format(value_dict["value"])
        processed_values.append(value_dict)

    return processed_values
