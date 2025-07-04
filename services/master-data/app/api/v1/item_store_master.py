# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Depends, Query, Path
from logging import getLogger
import inspect

from kugel_common.status_codes import StatusCodes
from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.schemas.api_response import ApiResponse
from app.api.common.pagination import PaginationMetadata
from kugel_common.exceptions import (
    InvalidRequestDataException,
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    RepositoryException,
)

from app.api.v1.schemas import (
    ItemStoreCreateRequest,
    ItemStoreUpdateRequest,
    ItemStoreResponse,
    ItemStoreDeleteResponse,
    ItemStoreDetailResponse,
)
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.dependencies.get_master_services import get_item_store_master_service_async
from app.dependencies.common import parse_sort

# Create a router instance for item store master endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/items",
    response_model=ApiResponse[ItemStoreResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def create_item_master_async(
    item_store: ItemStoreCreateRequest,
    store_code: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Create a new store-specific item master record.

    This endpoint allows creating store-specific information for an existing common item.
    Store-specific details typically include a store-specific price that may differ
    from the default price defined in the common item master.

    This allows individual stores within a tenant to have unique pricing for the same items.
    The item must already exist in the common item master before store-specific data can be added.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_store: The store-specific item details to create
        store_code: The store code to create the item for
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemStoreResponse]: Standard API response with the created store item data

    Raises:
        DocumentAlreadyExistsException: If store-specific data for this item already exists
        InvalidRequestDataException: If the request data is invalid
        DocumentNotFoundException: If the common item doesn't exist in the item_common_master
        RepositoryException: If there's an error during database operations
    """
    logger.info(
        f"Create item request received for item_code: {item_store.item_code}, tenant_id: {tenant_id}, store_code: {store_code}"
    )
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_store_master_service_async(tenant_id, store_code)
    try:
        item_store_doc = await master_service.create_item_async(
            item_code=item_store.item_code, store_price=item_store.store_price
        )
        transformer = SchemasTransformerV1()
        return_item_store = transformer.transform_item_store(item_store_doc)
    except Exception as e:
        logger.error(f"Error creating item store: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Item Store created successfully. item_code: {return_item_store.item_code}",
        data=return_item_store.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/items/{item_code}",
    response_model=ApiResponse[ItemStoreResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_item_store_master_async(
    item_code: str,
    store_code: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve a specific store-specific item record by its code.

    This endpoint retrieves the store-specific details of an item identified by its unique code.
    This provides only the store-specific information like price overrides, not the complete
    item details from the common master.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_code: The unique identifier of the item to retrieve
        store_code: The store code to get the item for
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemStoreResponse]: Standard API response with the store item data

    Raises:
        DocumentNotFoundException: If the store-specific item with the given code is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(
        f"Get item request received for item_code: {item_code}, tenant_id: {tenant_id}, store_code: {store_code}"
    )
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_store_master_service_async(tenant_id, store_code)
    try:
        item_store_doc = await master_service.get_item_by_code_async(item_code)
        if item_store_doc is None:
            message = f"Item not found. item_code: {item_code}"
            raise DocumentNotFoundException(message, logger)
        transformer = SchemasTransformerV1()
        return_item = transformer.transform_item_store(item_store_doc)
    except Exception as e:
        logger.error(f"Error getting item store: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item found. item_code: {return_item.item_code}",
        data=return_item.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/items",
    response_model=ApiResponse[list[ItemStoreResponse]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_item_store_master_all_async(
    store_code: str = Path(...),
    tenant_id: str = Path(...),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve all store-specific item records for a specific store.

    This endpoint returns a paginated list of all store-specific item data for
    the specified store. The results can be sorted and paginated as needed.
    This is useful for getting a list of all items with store-specific prices
    or other overrides.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        store_code: The store code to get items for
        tenant_id: The tenant identifier from the path
        limit: Maximum number of items to return (default: 100)
        page: Page number for pagination (default: 1)
        sort: Sorting criteria (default: item_code ascending)
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[list[ItemStoreResponse]]: Standard API response with a list of store item data and pagination metadata

    Raises:
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Get all items in store request received. tenant_id: {tenant_id}, store_code: {store_code}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_store_master_service_async(tenant_id, store_code)
    try:
        item_store_docs, total_count = await master_service.get_item_all_paginated_async(limit, page, sort)
        logger.debug(f"Items found. {item_store_docs}")
        transformer = SchemasTransformerV1()
        item_all_in_store = [transformer.transform_item_store(item_store_doc) for item_store_doc in item_store_docs]
    except Exception as e:
        logger.error(f"Error getting all items: {e}")
        raise e

    metadata = PaginationMetadata(page=page, limit=limit, total_count=total_count)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Items found. Total items: {total_count}",
        data=[item.model_dump() for item in item_all_in_store],
        metadata=metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/stores/{store_code}/items/{item_code}",
    response_model=ApiResponse[ItemStoreResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_item_store_master_async(
    item_code: str,
    item_store: ItemStoreUpdateRequest,
    store_code: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update an existing store-specific item record.

    This endpoint allows updating the store-specific details of an item identified
    by its code. It can be used to modify the store-specific price override.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_code: The unique identifier of the item to update
        item_store: The updated store-specific item details
        store_code: The store code to update the item for
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemStoreResponse]: Standard API response with the updated store item data

    Raises:
        DocumentNotFoundException: If the store-specific item with the given code is not found
        InvalidRequestDataException: If the request data is invalid
        RepositoryException: If there's an error during database operations
    """
    logger.info(
        f"Update item store request received for item_code: {item_code}, tenant_id: {tenant_id}, store_code: {store_code}"
    )
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_store_master_service_async(tenant_id, store_code)
    try:
        item_store_doc = await master_service.update_item_async(
            item_code=item_code, update_data=item_store.model_dump()
        )
        transformer = SchemasTransformerV1()
        item_store = transformer.transform_item_store(item_store_doc)
    except Exception as e:
        logger.error(f"Error updating item store: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item store updated successfully. item_code: {item_store.item_code}",
        data=item_store.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/stores/{store_code}/items/{item_code}",
    response_model=ApiResponse[ItemStoreDeleteResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_item_store_master_async(
    item_code: str,
    store_code: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete a store-specific item record.

    This endpoint allows removing store-specific item data completely from the system.
    This does not delete the item from the common item master, only the store-specific
    overrides. After deletion, the store will use the default values from the common
    item master.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_code: The unique identifier of the item to delete
        store_code: The store code to delete the item for
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemStoreDeleteResponse]: Standard API response with deletion confirmation

    Raises:
        DocumentNotFoundException: If the store-specific item with the given code is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(
        f"Delete item store request received for item_code: {item_code}, tenant_id: {tenant_id}, store_code: {store_code}"
    )
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_store_master_service_async(tenant_id, store_code)
    try:
        await master_service.delete_item_async(item_code)
    except Exception as e:
        logger.error(f"Error deleting item store: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item store deleted successfully. item_code: {item_code}",
        data=ItemStoreDeleteResponse(item_code=item_code).model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/items/{item_code}/details",
    response_model=ApiResponse[ItemStoreDetailResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_item_store_master_detail_async(
    item_code: str = Path(...),
    store_code: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve detailed item information combining common and store-specific data.

    This endpoint provides a comprehensive view of an item by combining the
    common item data (from item_common_master) with any store-specific overrides
    (from item_store_master). This is particularly useful for POS terminals
    that need complete item information including both common attributes and
    any store-specific pricing.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_code: The unique identifier of the item to retrieve
        store_code: The store code to get the item for
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemStoreDetailResponse]: Standard API response with the combined item data

    Raises:
        DocumentNotFoundException: If the item with the given code is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(
        f"Get item detail request received for item_code: {item_code}, tenant_id: {tenant_id}, store_code: {store_code}"
    )
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_store_master_service_async(tenant_id, store_code)
    try:
        item_store_detail = await master_service.get_item_store_detail_by_code_async(item_code)
        if item_store_detail is None:
            message = f"Item not found. item_code: {item_code}"
            raise DocumentNotFoundException(message, logger)
        transformer = SchemasTransformerV1()
        return_item = transformer.transform_item_store_detail(item_store_detail)
    except Exception as e:
        logger.error(f"Error getting item store detail: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item found. item_code: {return_item.item_code}",
        data=return_item.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
