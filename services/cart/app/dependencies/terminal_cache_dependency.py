"""
Terminal info cache dependency for cart service.
"""

from fastapi import Query, Security
from typing import Optional, List
from logging import getLogger

from kugel_common.security import api_key_header, get_terminal_info_from_terminal_service
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
