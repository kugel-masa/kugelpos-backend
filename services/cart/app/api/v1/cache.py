"""
Cache management endpoints for cart service.
"""

from fastapi import APIRouter, status, Depends
from logging import getLogger

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_current_user
from app.dependencies.terminal_cache_dependency import (
    clear_terminal_cache,
    get_terminal_cache_size,
    get_tenant_terminal_ids_in_cache,
)

# Create a router instance
router = APIRouter()

# Get logger instance
logger = getLogger(__name__)


@router.get(
    "/cache/terminal/status",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Get terminal cache status",
    description="Get current status of the terminal information cache",
)
async def get_cache_status(current_user: dict = Depends(get_current_user)) -> ApiResponse[dict]:
    """
    Get the current status of the terminal cache for the authenticated user's tenant.

    Returns:
        Cache status including size and terminal IDs for the tenant
    """
    tenant_id = current_user.get("tenant_id")

    # Get cache statistics for this tenant
    tenant_cache_size = get_terminal_cache_size(tenant_id)
    total_cache_size = get_terminal_cache_size()  # Total across all tenants
    cached_terminal_ids = get_tenant_terminal_ids_in_cache(tenant_id)

    return ApiResponse(
        data={
            "cache_type": "terminal_info",
            "tenant_id": tenant_id,
            "tenant_cache_size": tenant_cache_size,
            "total_cache_size": total_cache_size,
            "cached_terminal_ids": cached_terminal_ids,
            "status": "active",
        }
    )


@router.delete(
    "/cache/terminal",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Clear terminal cache",
    description="Clear all entries from the terminal information cache",
)
async def clear_cache(current_user: dict = Depends(get_current_user)) -> ApiResponse[dict]:
    """
    Clear terminal cache entries for the authenticated user's tenant.

    Returns:
        Confirmation of cache clearing with details
    """
    tenant_id = current_user.get("tenant_id")
    username = current_user.get("username")

    # Get count before clearing
    items_before = get_terminal_cache_size(tenant_id)

    # Clear cache for this tenant only
    clear_terminal_cache(tenant_id)
    logger.info(f"Terminal cache cleared for tenant {tenant_id} by user: {username}")

    return ApiResponse(
        data={
            "message": f"Terminal cache cleared successfully for tenant {tenant_id}",
            "cache_type": "terminal_info",
            "tenant_id": tenant_id,
            "items_cleared": items_before,
        }
    )
