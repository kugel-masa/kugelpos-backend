"""
Cache management endpoints for cart service.
"""

from fastapi import APIRouter, status, Depends, Request, HTTPException
from logging import getLogger
from typing import Optional

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_current_user
from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
)

# Create a router instance
router = APIRouter()

# Get logger instance
logger = getLogger(__name__)


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
