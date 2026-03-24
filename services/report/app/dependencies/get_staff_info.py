# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
Dependency injection functions for extracting staff information from requests.
"""

from fastapi import Depends, Query, Security
from typing import Optional
from logging import getLogger

from kugel_common.security import api_key_header, oauth2_scheme, get_terminal_info, get_current_user, verify_terminal_token

logger = getLogger(__name__)


async def get_requesting_staff_id(
    terminal_id: Optional[str] = Query(None, description="Terminal ID for api_key authentication"),
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[str]:
    """
    Extract the staff ID from the current request context.

    For API key authentication:
    - Gets the terminal info which contains the current staff

    For JWT token authentication:
    - Returns None as JWT tokens typically don't contain staff information
    - The user themselves might be staff, but we treat this differently

    Args:
        terminal_id: Terminal ID when using API key authentication
        api_key: API key from the security header
        token: OAuth2 JWT token

    Returns:
        Staff ID if available, None otherwise
    """
    try:
        # If using API key authentication with terminal
        if terminal_id and api_key:
            logger.debug(f"Getting staff info from terminal: {terminal_id}")
            terminal_info = await get_terminal_info(terminal_id, api_key)

            # Extract staff ID from terminal info if available
            if terminal_info and terminal_info.staff:
                logger.debug(f"Found staff ID: {terminal_info.staff.id}")
                return terminal_info.staff.id
            else:
                logger.debug("No staff logged into terminal")
                return None

        # If using JWT token authentication
        elif token:
            # Try terminal JWT first to extract staff_id from claims
            try:
                terminal_claims = verify_terminal_token(token)
                staff_id = terminal_claims.get("staff_id")
                if staff_id:
                    logger.debug(f"Found staff ID from terminal JWT: {staff_id}")
                    return staff_id
                logger.debug("Terminal JWT has no staff_id (not signed in)")
                return None
            except Exception:
                pass  # Not a terminal token, fall through
            # User JWT - no staff info available
            return None

    except Exception as e:
        logger.warning(f"Failed to get staff info: {str(e)}")

    return None
