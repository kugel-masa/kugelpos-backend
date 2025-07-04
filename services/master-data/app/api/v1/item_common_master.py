# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Depends, Query, Path
from logging import getLogger
import inspect

from kugel_common.status_codes import StatusCodes
from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.schemas.api_response import ApiResponse
from app.api.common.pagination import PaginationMetadata
from kugel_common.exceptions import (
    RepositoryException,
    DocumentNotFoundException,
    InvalidRequestDataException,
    DocumentAlreadyExistsException,
)

from app.api.v1.schemas import (
    ItemCreateRequest,
    ItemUpdateRequest,
    ItemResponse,
    ItemDeleteResponse,
)
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.dependencies.get_master_services import get_item_master_service_async
from app.dependencies.common import parse_sort

# Create a router instance for item common master endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


@router.post(
    "/tenants/{tenant_id}/items",
    response_model=ApiResponse[ItemResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def create_item_master_async(
    item: ItemCreateRequest,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Create a new item master record.

    This endpoint allows creating a new item with common attributes like code,
    description, price, cost, and category. These items are tenant-specific and
    can be used across all stores within the tenant.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item: The item details to create
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemResponse]: Standard API response with the created item data

    Raises:
        DocumentAlreadyExistsException: If an item with the same code already exists
        InvalidRequestDataException: If the request data is invalid
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Create item request received for item_code: {item.item_code}, tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_master_service_async(tenant_id)
    try:
        logger.debug(
            f"master_service item_master_repo collection_name: {master_service.item_common_master_repo.collection_name}"
        )
        logger.debug(f"Item: {item}")
        logger.debug(f"Item.item_code: {item.item_code}")
        logger.debug(f"Item.description: {item.description}")

        item_doc = await master_service.create_item_async(
            item.item_code,
            item.description,
            item.unit_price,
            item.unit_cost,
            item.item_details,
            item.image_urls,
            item.category_code,
            item.tax_code,
        )
        transformer = SchemasTransformerV1()
        return_item = transformer.transform_item(item_doc)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Item created successfully. item_code: {return_item.item_code}",
        data=return_item.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/items/{item_code}",
    response_model=ApiResponse[ItemResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_item_master_async(
    item_code: str,
    is_logical_deleted: bool = Query(default=False),
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve a specific item master record by its code.

    This endpoint retrieves the details of an item identified by its unique code.
    By default, it only returns active items, but setting is_logical_deleted to true
    allows retrieving logically deleted items as well.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_code: The unique identifier of the item to retrieve
        is_logical_deleted: Flag to include logically deleted items
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemResponse]: Standard API response with the item data

    Raises:
        DocumentNotFoundException: If the item with the given code is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Get item request received for item_code: {item_code}, tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_master_service_async(tenant_id)
    try:
        item_doc = await master_service.get_item_by_code_async(item_code, is_logical_deleted)
        if item_doc is None:
            message = f"Item not found. item_code: {item_code}"
            raise DocumentNotFoundException(message, logger)
        transformer = SchemasTransformerV1()
        return_item = transformer.transform_item(item_doc)
    except Exception as e:
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
    "/tenants/{tenant_id}/items",
    response_model=ApiResponse[list[ItemResponse]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_item_master_all_async(
    tenant_id: str = Path(...),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve all item master records for a tenant.

    This endpoint returns a paginated list of all active items for the specified tenant.
    The results can be sorted and paginated as needed.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        tenant_id: The tenant identifier from the path
        limit: Maximum number of items to return (default: 100)
        page: Page number for pagination (default: 1)
        sort: Sorting criteria (default: item_code ascending)
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[list[ItemResponse]]: Standard API response with a list of item data and pagination metadata

    Raises:
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Get all items request received. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_master_service_async(tenant_id)
    try:
        item_docs, total_count = await master_service.get_item_all_paginated_async(limit, page, sort)
        transformer = SchemasTransformerV1()
        item_all = [transformer.transform_item(item_doc) for item_doc in item_docs]
    except Exception as e:
        raise e

    metadata = PaginationMetadata(page=page, limit=limit, total_count=total_count)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Items found. Total items: {total_count}",
        data=[item.model_dump() for item in item_all],
        metadata=metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/items/{item_code}",
    response_model=ApiResponse[ItemResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_item_master_async(
    item_code: str,
    item: ItemUpdateRequest,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update an existing item master record.

    This endpoint allows updating the details of an existing item identified by its code.
    Only the provided fields will be updated, and the item_code cannot be changed.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_code: The unique identifier of the item to update
        item: The updated item details
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemResponse]: Standard API response with the updated item data

    Raises:
        DocumentNotFoundException: If the item with the given code is not found
        InvalidRequestDataException: If the request data is invalid
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Update item request received for item_code: {item_code}, tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_master_service_async(tenant_id)
    try:
        item_doc = await master_service.update_item_async(item_code=item_code, update_data=item.model_dump())
        transformer = SchemasTransformerV1()
        item = transformer.transform_item(item_doc)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item updated successfully. item_code: {item.item_code}",
        data=item.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/items/{item_code}",
    response_model=ApiResponse[ItemDeleteResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_item_master_async(
    item_code: str,
    is_logical: bool = Query(default=False),
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete an item master record.

    This endpoint allows deleting an item either logically or physically.
    Logical deletion marks the item as deleted but keeps it in the database,
    while physical deletion completely removes it from the database.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_code: The unique identifier of the item to delete
        is_logical: Flag to perform logical (true) or physical (false) deletion
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemDeleteResponse]: Standard API response with deletion confirmation

    Raises:
        DocumentNotFoundException: If the item with the given code is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(
        f"Delete item request received for item_code: {item_code}, is_logical: {is_logical}, tenant_id: {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_item_master_service_async(tenant_id)
    try:
        await master_service.delete_item_async(item_code, is_logical)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item deleted successfully. item_code: {item_code}, logically_mode: {is_logical}",
        data=ItemDeleteResponse(item_code=item_code, is_logical=is_logical).model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
