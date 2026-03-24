"""
Terminal info cache dependency for cart service.
"""

from fastapi import Depends, Query, Security
from typing import Optional, List
from logging import getLogger

from kugel_common.security import (
    api_key_header,
    oauth2_scheme,
    get_terminal_info_from_terminal_service,
    verify_terminal_token,
    terminal_claims_to_terminal_info,
)
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.utils.terminal_cache import TerminalInfoCache
from app.config.settings import settings

logger = getLogger(__name__)

# Create a singleton cache instance
_terminal_cache = TerminalInfoCache(ttl_seconds=settings.TERMINAL_CACHE_TTL_SECONDS)


async def get_terminal_info_with_cache(
    terminal_id: str = Query(...),
    api_key: str = Security(api_key_header),
) -> TerminalInfoDocument:
    """
    FastAPI dependency that retrieves terminal information with caching support.

    This function first checks the local cache for terminal information.
    If not found or expired, it fetches from the terminal service and caches the result.

    Args:
        terminal_id: Terminal ID from query parameter
        api_key: API key from header

    Returns:
        TerminalInfoDocument containing the terminal information
    """
    # Try to get from cache first
    cached_terminal_info = _terminal_cache.get(terminal_id)

    if cached_terminal_info is not None:
        logger.debug(f"Terminal info for {terminal_id} found in cache")
        return cached_terminal_info

    # Not in cache, fetch from terminal service
    logger.debug(f"Terminal info for {terminal_id} not in cache, fetching from service")
    terminal_info = await get_terminal_info_from_terminal_service(terminal_id, api_key)

    # Cache the result
    _terminal_cache.set(terminal_id, terminal_info)
    logger.debug(f"Terminal info for {terminal_id} cached")

    return terminal_info


async def get_terminal_info_with_jwt_or_cache(
    terminal_id: Optional[str] = Query(None),
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
) -> TerminalInfoDocument:
    """
    FastAPI dependency that retrieves terminal info from JWT claims or cache.

    Priority:
    1. If a terminal JWT is provided, extract claims directly (no HTTP call)
    2. If API key is provided, use the cached terminal service lookup (legacy)

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
        except Exception:
            pass  # Not a terminal JWT, fall through to legacy

    # Priority 2: Legacy API key + cache flow
    if terminal_id and api_key:
        return await get_terminal_info_with_cache(terminal_id, api_key)

    # No valid authentication
    from fastapi import HTTPException, status
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Terminal JWT or API key required",
    )


def clear_terminal_cache(tenant_id: Optional[str] = None) -> None:
    """
    Clear entries from the terminal cache.

    Args:
        tenant_id: If provided, clear only entries for this tenant.
                  If None, clear all entries.
    """
    _terminal_cache.clear(tenant_id)
    if tenant_id:
        logger.info(f"Terminal cache cleared for tenant: {tenant_id}")
    else:
        logger.info("Terminal cache cleared for all tenants")


def get_terminal_cache_size(tenant_id: Optional[str] = None) -> int:
    """
    Get the current size of the terminal cache.

    Args:
        tenant_id: If provided, count only entries for this tenant.
                  If None, count all entries.

    Returns:
        Number of cached items
    """
    return _terminal_cache.size(tenant_id)


def get_tenant_terminal_ids_in_cache(tenant_id: str) -> List[str]:
    """
    Get all terminal IDs cached for a specific tenant.

    Args:
        tenant_id: The tenant ID to filter by

    Returns:
        List of terminal IDs for the tenant
    """
    return _terminal_cache.get_tenant_terminal_ids(tenant_id)
