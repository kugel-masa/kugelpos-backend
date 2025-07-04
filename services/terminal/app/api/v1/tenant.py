# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Tenant Management API Module

This module defines the API endpoints for tenant and store management operations
in the Terminal service. It provides functionality for creating, retrieving, updating,
and deleting tenants and stores.
"""

from fastapi import APIRouter, status, HTTPException, Depends, Path, Query
from logging import getLogger
import httpx
import inspect

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.status_codes import StatusCodes
from kugel_common.security import oauth2_scheme

from app.database import database_setup
from app.config.settings import settings
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.api.v1.schemas import *
from app.dependencies.get_tenant_service import (
    get_tenant_service_async,
    parse_sort_stores as parse_sort,
    get_tenant_id_with_token_wrapper,
    get_tenant_id_with_security_by_query_optional_wrapper,
)

router = APIRouter()
logger = getLogger(__name__)


@router.post(
    "/tenants",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[Tenant],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def create_tenant(
    tenant: TenantCreateRequest,
    token: str = Depends(oauth2_scheme),
    tenant_id: str = Depends(get_tenant_id_with_token_wrapper),
):
    """
    Create a new tenant

    This endpoint sets up a new tenant in the system by:
    1. Creating necessary database structures for the Terminal service
    2. Initializing other services (Master Data, Cart, Report, Journal) for the tenant
    3. Creating the tenant information record

    This operation requires OAuth2 token authentication.

    Args:
        tenant: Tenant creation request with tenant ID, name, and optional tags
        token: OAuth2 authentication token
        tenant_id: Tenant ID extracted from the authentication token

    Returns:
        ApiResponse containing the created tenant information
    """
    logger.debug(f"Creating tenant for tenant {tenant_id}")

    # check tenant_id
    if tenant.tenant_id != tenant_id:
        message = f"tenant_id: {tenant.tenant_id} does not match tenant_id: {tenant_id}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    # setup database
    try:
        # setup database for terminal service
        await database_setup.execute(tenant_id=tenant_id)

        # setup database for other services
        urls = []
        urls.append(f"{settings.BASE_URL_MASTER_DATA}/tenants")
        urls.append(f"{settings.BASE_URL_CART}/tenants")
        urls.append(f"{settings.BASE_URL_REPORT}/tenants")
        urls.append(f"{settings.BASE_URL_JOURNAL}/tenants")
        urls.append(f"{settings.BASE_URL_STOCK}/tenants")
        for url in urls:
            logger.debug(f"Setting up database for tenant: {tenant_id}, url: {url}")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, headers={"Authorization": f"Bearer {token}"}, json={"tenant_id": tenant_id}
                )
                response.raise_for_status()
    except Exception as e:
        raise e

    # create tenant info
    tenant_service = await get_tenant_service_async(tenant_id=tenant_id)
    try:
        tenant_doc = await tenant_service.create_tenant_async(
            tenant_name=tenant.tenant_name, stores=[], tags=tenant.tags
        )
        return_json = SchemasTransformerV1().transform_tenant(tenant_doc).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Tenant created successfully for tenant {tenant_id}",
        data=return_json,
        operation=inspect.currentframe().f_code.co_name,
    )
    return response


@router.get(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Tenant],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_tenant(
    tenant_id: str = Path(...), tenant_id_by_auth: str = Depends(get_tenant_id_with_security_by_query_optional_wrapper)
):
    """
    Get tenant information

    This endpoint retrieves detailed information about a specific tenant.
    This operation can be authenticated using either:
    - OAuth2 token, or
    - Terminal ID + API key combination

    Args:
        tenant_id: ID of the tenant to retrieve
        tenant_id_by_auth: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing tenant information
    """
    logger.debug(f"Getting tenant for tenant {tenant_id}")

    if tenant_id != tenant_id_by_auth:
        message = f"tenant_id: {tenant_id} does not match tenant_id: {tenant_id_by_auth}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    try:
        tenant_service = await get_tenant_service_async(tenant_id=tenant_id)
        tenant_doc = await tenant_service.get_tenant_async()
        return_json = SchemasTransformerV1().transform_tenant(tenant_doc).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Tenant info for tenant {tenant_id}",
        data=return_json,
        operation=inspect.currentframe().f_code.co_name,
    )
    return response


@router.put(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Tenant],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_tenant(
    tenant: TenantUpdateRequest,
    tenant_id: str = Path(...),
    tenant_id_by_auth: str = Depends(get_tenant_id_with_token_wrapper),
):
    """
    Update tenant information

    This endpoint updates the details of a specific tenant.
    This operation requires OAuth2 token authentication.

    Args:
        tenant: Update request containing the new tenant name and/or tags
        tenant_id: ID of the tenant to update
        tenant_id_by_auth: Tenant ID extracted from authentication token

    Returns:
        ApiResponse containing updated tenant information
    """
    logger.debug(f"Update tenant for tenant {tenant_id}")

    if tenant_id_by_auth != tenant_id:
        message = f"tenant_id: path->{tenant_id} does not match tenant_id: {tenant_id_by_auth}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    try:
        tenant_service = await get_tenant_service_async(tenant_id=tenant_id)
        tenant_doc = await tenant_service.update_tenant_async(tenant_name=tenant.tenant_name, tags=tenant.tags)
        return_json = SchemasTransformerV1().transform_tenant(tenant_doc).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Tenant updated successfully for tenant {tenant_id}",
        data=return_json,
        operation=inspect.currentframe().f_code.co_name,
    )
    return response


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[TenantDeleteResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_tenant(tenant_id: str = Path(...), tenant_id_by_auth: str = Depends(get_tenant_id_with_token_wrapper)):
    """
    Delete a tenant

    This endpoint deletes a tenant from the system.
    This operation requires OAuth2 token authentication.

    Args:
        tenant_id: ID of the tenant to delete
        tenant_id_by_auth: Tenant ID extracted from authentication token

    Returns:
        ApiResponse confirming tenant deletion
    """
    logger.debug(f"Deleting tenant for tenant {tenant_id}")

    if tenant_id != tenant_id_by_auth:
        message = f"tenant_id: {tenant_id} does not match tenant_id: {tenant_id_by_auth}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    try:
        tenant_service = await get_tenant_service_async(tenant_id=tenant_id)
        await tenant_service.delete_tenant_async()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Tenant deleted successfully for tenant {tenant_id}",
        data=TenantDeleteResponse(tenant_id=tenant_id),
        operation=inspect.currentframe().f_code.co_name,
    )
    return response


@router.post(
    "/tenants/{tenant_id}/stores",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[Tenant],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def add_store(
    store: StoreCreateRequest,
    tenant_id: str = Path(...),
    tenant_id_by_auth: str = Depends(get_tenant_id_with_token_wrapper),
):
    """
    Add a store to a tenant

    This endpoint adds a new store to the specified tenant.
    This operation requires OAuth2 token authentication.

    Args:
        store: Store creation request with store code, name, and optional tags
        tenant_id: ID of the tenant to add the store to
        tenant_id_by_auth: Tenant ID extracted from authentication token

    Returns:
        ApiResponse containing updated tenant information with the new store
    """
    logger.debug(f"Adding store for tenant {tenant_id}")

    if tenant_id != tenant_id_by_auth:
        message = f"tenant_id: {tenant_id} does not match tenant_id: {tenant_id_by_auth}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    try:
        tenant_service = await get_tenant_service_async(tenant_id=tenant_id)
        tenant_doc = await tenant_service.add_store_async(
            store_code=store.store_code, store_name=store.store_name, tags=store.tags
        )
        return_json = SchemasTransformerV1().transform_tenant(tenant_doc).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Store created successfully for tenant {tenant_id}",
        data=return_json,
        operation=inspect.currentframe().f_code.co_name,
    )
    return response


@router.get(
    "/tenants/{tenant_id}/stores",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[list[Store]],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_stores(
    tenant_id: str = Path(...),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    tenant_id_by_auth: str = Depends(get_tenant_id_with_security_by_query_optional_wrapper),
):
    """
    Get a list of stores for a tenant

    This endpoint retrieves a paginated list of stores for the specified tenant.
    This operation can be authenticated using either:
    - OAuth2 token, or
    - Terminal ID + API key combination

    Args:
        tenant_id: ID of the tenant to get stores for
        limit: Maximum number of results to return per page
        page: Page number for pagination
        sort: Sorting criteria
        tenant_id_by_auth: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing list of store information
    """
    logger.debug(f"Getting stores for tenant {tenant_id_by_auth}")

    if tenant_id != tenant_id_by_auth:
        message = f"tenant_id: {tenant_id} does not match tenant_id: {tenant_id_by_auth}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    try:
        tenant_service = await get_tenant_service_async(tenant_id=tenant_id)
        stores_list = await tenant_service.get_stores_async(limit, page, sort)
        return_json = [SchemasTransformerV1().transform_store(store_doc).model_dump() for store_doc in stores_list]
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Stores info for tenant {tenant_id}",
        data=return_json,
        operation=inspect.currentframe().f_code.co_name,
    )
    return response


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Store],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_store(
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    tenant_id_by_auth: str = Depends(get_tenant_id_with_security_by_query_optional_wrapper),
):
    """
    Get store information

    This endpoint retrieves detailed information about a specific store.
    This operation can be authenticated using either:
    - OAuth2 token, or
    - Terminal ID + API key combination

    Args:
        tenant_id: ID of the tenant that owns the store
        store_code: Code of the store to retrieve
        tenant_id_by_auth: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing store information
    """
    logger.debug(f"Getting store for tenant {tenant_id}")

    if tenant_id != tenant_id_by_auth:
        message = f"tenant_id: {tenant_id} does not match tenant_id: {tenant_id_by_auth}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    try:
        tenant_service = await get_tenant_service_async(tenant_id=tenant_id)
        store_doc = await tenant_service.get_store_async(store_code=store_code)
        return_json = SchemasTransformerV1().transform_store(store_doc).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Store info for tenant {tenant_id}",
        data=return_json,
        operation=inspect.currentframe().f_code.co_name,
    )
    return response


@router.put(
    "/tenants/{tenant_id}/stores/{store_code}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Store],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_store(
    store: StoreUpdateRequest,
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    tenant_id_by_auth: str = Depends(get_tenant_id_with_token_wrapper),
):
    """
    Update store information

    This endpoint updates the details of a specific store.
    This operation requires OAuth2 token authentication.

    Args:
        store: Update request containing the new store details
        tenant_id: ID of the tenant that owns the store
        store_code: Code of the store to update
        tenant_id_by_auth: Tenant ID extracted from authentication token

    Returns:
        ApiResponse containing updated store information
    """
    logger.debug(f"Update store for tenant {tenant_id}")

    if tenant_id != tenant_id_by_auth:
        message = f"tenant_id: {tenant_id} does not match tenant_id: {tenant_id_by_auth}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    try:
        tenant_service = await get_tenant_service_async(tenant_id=tenant_id)

        update_dict = {}
        if store.store_name:
            update_dict["store_name"] = store.store_name
        if store.status:
            update_dict["status"] = store.status
        if store.business_date:
            update_dict["business_date"] = store.business_date
        if store.tags:
            update_dict["tags"] = store.tags

        store_doc = await tenant_service.update_store_async(store_code=store_code, update_dict=update_dict)
        return_json = SchemasTransformerV1().transform_store(store_doc).model_dump()

    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Store updated successfully for tenant {tenant_id}",
        data=return_json,
        operation=inspect.currentframe().f_code.co_name,
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/stores/{store_code}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[StoreDeleteResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_store(
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    tenant_id_by_auth: str = Depends(get_tenant_id_with_token_wrapper),
):
    """
    Delete a store

    This endpoint deletes a store from the specified tenant.
    This operation requires OAuth2 token authentication.

    Args:
        tenant_id: ID of the tenant that owns the store
        store_code: Code of the store to delete
        tenant_id_by_auth: Tenant ID extracted from authentication token

    Returns:
        ApiResponse confirming store deletion
    """
    logger.debug(f"Deleting store for tenant {tenant_id}")

    if tenant_id != tenant_id_by_auth:
        message = f"tenant_id: {tenant_id} does not match tenant_id: {tenant_id_by_auth}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    try:
        tenant_service = await get_tenant_service_async(tenant_id=tenant_id)
        await tenant_service.delete_store_async(store_code=store_code)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Store deleted successfully for tenant {tenant_id}",
        data=StoreDeleteResponse(store_code=store_code),
        operation=inspect.currentframe().f_code.co_name,
    )
    return response
