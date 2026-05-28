"""
Cache management endpoints for cart service.
"""

from fastapi import APIRouter, status, Depends, Request, HTTPException
from logging import getLogger
from typing import Optional

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_current_user
from app.dependencies.terminal_cache_dependency import (
    clear_terminal_cache,
    get_terminal_cache_size,
    get_tenant_terminal_ids_in_cache,
)
from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
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
        success=True,
        code=status.HTTP_200_OK,
        message="Cache status retrieved successfully",
        data={
            "cache_type": "terminal_info",
            "tenant_id": tenant_id,
            "tenant_cache_size": tenant_cache_size,
            "total_cache_size": total_cache_size,
            "cached_terminal_ids": cached_terminal_ids,
            "status": "active",
        },
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
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal cache cleared successfully for tenant {tenant_id}",
        data={
            "cache_type": "terminal_info",
            "tenant_id": tenant_id,
            "items_cleared": items_before,
        },
    )


@router.delete(
    "/cache/master-data",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Invalidate master-data cache",
    description=(
        "Invalidate the shared master-data cache for a namespace by bumping its "
        "generation counter. Used operationally after master-data changes that must "
        "be reflected before the namespace TTL expires."
    ),
)
async def invalidate_master_data_cache(
    request: Request,
    namespace: str,
    store_code: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict]:
    """
    Invalidate the master-data cache for the given namespace within the
    authenticated tenant (optionally scoped to a store).

    Args:
        namespace: cache namespace (e.g. "promotion_master", "item_master")
        store_code: store scope; omit for tenant-wide namespaces

    Returns:
        Confirmation including the new generation value
    """
    # Cache invalidation forces subsequent reads to miss and re-fetch from
    # master-data; restrict it to privileged callers to avoid a regular
    # terminal triggering a cache stampede against the master-data service.
    if not (current_user.get("is_superuser") or current_user.get("is_service_account")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master-data cache invalidation requires a superuser or service account",
        )

    tenant_id = current_user.get("tenant_id")
    username = current_user.get("username")

    backend = request.app.state.master_cache_backend
    gen_key = AbstractMasterDataRepository.build_generation_key(
        tenant_id, store_code, namespace
    )
    new_generation = await backend.increment(gen_key)
    logger.info(
        "master-data cache invalidated: tenant=%s namespace=%s store=%s by user=%s",
        tenant_id, namespace, store_code or "_", username,
    )

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Master-data cache invalidated for namespace {namespace}",
        data={
            "cache_type": "master_data",
            "tenant_id": tenant_id,
            "namespace": namespace,
            "store_code": store_code,
            "new_generation": new_generation,
        },
    )
