"""
Logging utility functions for masking sensitive information.
"""
import os
from typing import Any, Dict, Optional


def mask_api_key(api_key: Optional[str]) -> str:
    """
    Mask API key for safe logging.

    Args:
        api_key: The API key to mask

    Returns:
        Masked API key string

    Examples:
        - None or empty -> "****"
        - Short key (<=8 chars) -> "****"
        - Long key -> "sk_l...5678" (first 4...last 4)
    """
    # Check if masking is disabled for testing
    if os.environ.get("DISABLE_API_KEY_MASKING") == "True":
        return api_key if api_key else "****"

    if not api_key:
        return "****"

    key_length = len(api_key)

    if key_length <= 8:
        return "****"

    # For longer keys, show first 4 and last 4 characters
    return f"{api_key[:4]}...{api_key[-4:]}"


def mask_dict_api_key(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Mask api_key field in dictionary for safe logging.

    Only the top-level keys "api_key" / "API_KEY" are masked; nested
    dictionaries are not traversed (this is a shallow copy). All current
    callers pass flat documents from MongoDB, so this is sufficient.

    Args:
        data: Dictionary that may contain api_key field, or None

    Returns:
        Dictionary with masked api_key (original dict is not modified),
        or None if input was None/empty.
    """
    if not data:
        return data

    # Create a copy to avoid modifying the original
    masked_data = data.copy()

    # Mask api_key field if it exists
    if "api_key" in masked_data:
        masked_data["api_key"] = mask_api_key(masked_data["api_key"])

    # Also check for API_KEY (uppercase variant)
    if "API_KEY" in masked_data:
        masked_data["API_KEY"] = mask_api_key(masked_data["API_KEY"])

    return masked_data
