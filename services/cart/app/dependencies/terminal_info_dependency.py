"""
Terminal info dependency for cart service.

Terminal info is no longer cached (see #127): the terminal-JWT path builds
the document from claims with no HTTP call, and the legacy API-key path
fetches from the terminal service on each request. The previous in-process,
per-worker cache was removed because it only helped the API-key path and its
invalidation could not span workers.
"""

from fastapi import Depends, HTTPException, Query, Security, status
from typing import Optional
from logging import getLogger

from kugel_common.security import (
    api_key_header,
    oauth2_scheme,
    get_terminal_info_from_terminal_service,
    verify_terminal_token,
    terminal_claims_to_terminal_info,
)
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument

logger = getLogger(__name__)


async def get_terminal_info_with_jwt_or_apikey(
    terminal_id: Optional[str] = Query(None),
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
) -> TerminalInfoDocument:
    """
    FastAPI dependency that retrieves terminal info from JWT claims or the
    terminal service.

    Priority:
    1. If a terminal JWT is provided, extract claims directly (no HTTP call)
    2. If API key is provided, fetch from the terminal service (no caching)

    The returned TerminalInfoDocument includes a jwt_token attribute when
    constructed from JWT, enabling downstream JWT forwarding to master-data.

    Args:
        terminal_id: Optional terminal ID from query parameter (legacy flow)
        api_key: Optional API key from header (legacy flow)
        token: Optional Bearer token from Authorization header

    Returns:
        TerminalInfoDocument containing the terminal information
    """
    # Priority 1: Try terminal JWT
    if token:
        try:
            claims = verify_terminal_token(token)
            terminal_info = terminal_claims_to_terminal_info(claims)
            # Store the original JWT for forwarding to other services
            terminal_info.jwt_token = token
            logger.debug(f"Terminal info for {terminal_info.terminal_id} from JWT claims")
            return terminal_info
        except HTTPException:
            pass  # Not a terminal JWT, fall through to legacy

    # Priority 2: Legacy API key — fetch from the terminal service each call
    if terminal_id and api_key:
        logger.debug(f"Fetching terminal info for {terminal_id} from terminal service")
        return await get_terminal_info_from_terminal_service(terminal_id, api_key)

    # No valid authentication
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Terminal JWT or API key required",
    )
