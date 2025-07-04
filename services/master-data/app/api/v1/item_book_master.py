# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Depends, Path, Query
from logging import getLogger
import inspect
from typing import List, Optional
import asyncio

from kugel_common.status_codes import StatusCodes
from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.schemas.api_response import ApiResponse
from app.api.common.pagination import PaginationMetadata
from kugel_common.exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    InvalidRequestDataException,
    RepositoryException,
)

from app.api.v1.schemas import (
    ItemBookCreateRequest,
    ItemBookUpdateRequest,
    ItemBookResponse,
    ItemBookDeleteResponse,
    ItemBookCategory,
    ItemBookCategoryDeleteResponse,
    ItemBookTab,
    ItemBookTabDeleteResponse,
    ItemBookButton,
    ItemBookButtonDeleteResponse,
)
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.dependencies.get_master_services import get_item_book_service_async
from app.dependencies.common import parse_sort

# Create a router instance for book item master endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


@router.post(
    "/tenants/{tenant_id}/item_books",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def create_item_book(
    item_book: ItemBookCreateRequest,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Create a new item book record.

    This endpoint allows creating a new item book with its details including title and categories.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book: The item book details to create
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the created item book data

    Raises:
        Exception: If there's an error during the creation process
    """
    logger.debug(f"create_item_book: item_book->{item_book}, tenant_id->{tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        new_item_book = await service.create_item_book_async(title=item_book.title, categories=item_book.categories)
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(new_item_book)
        logger.debug(f"return_item_book: {return_item_book}")
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message="Item Book created successfully. item_book_id: {new_item_book.item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/item_books/{item_book_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_item_book_by_id(
    item_book_id: str = Path(...),
    tenant_id: str = Path(...),
    store_code: str = Query(None),  # option for store price
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve an item book record by its ID.

    This endpoint retrieves the details of an item book identified by its unique ID.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_id: The unique ID of the item book to retrieve
        tenant_id: The tenant identifier from the path
        store_code: The store code for store-specific operations (optional)
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the item book data

    Raises:
        Exception: If there's an error during the retrieval process
    """
    logger.debug(f"get_item_book_by_id: item_book_id -> {item_book_id}, tenant_id -> {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id, store_code)

    try:
        item_book = await service.get_item_book_by_id_async(item_book_id)
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(item_book)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item Book found successfully. item_book_id: {item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/item_books/{item_book_id}/detail",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_item_book_detail_by_id(
    item_book_id: str = Path(...),
    tenant_id: str = Path(...),
    store_code: str = Query(...),  # for store price
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve detailed information of an item book by its ID.

    This endpoint retrieves detailed information of an item book identified by its unique ID.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_id: The unique ID of the item book to retrieve
        tenant_id: The tenant identifier from the path
        store_code: The store code for store-specific operations
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the detailed item book data

    Raises:
        Exception: If there's an error during the retrieval process
    """
    logger.debug(f"get_item_book_detail_by_id: item_book_id -> {item_book_id}, tenant_id -> {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id, store_code)

    try:
        item_book = await service.get_item_book_detail_by_id_async(item_book_id)
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(item_book)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item Book found successfully. item_book_id: {item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/item_books",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[list[ItemBookResponse]],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_all_item_books(
    tenant_id: str = Path(...),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve all item book records for a tenant.

    This endpoint returns a paginated list of item book records for the specified tenant.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        tenant_id: The tenant identifier from the path
        limit: Maximum number of item book records to return (default: 100)
        page: Page number for pagination (default: 1)
        sort: Sorting criteria (default: item_book_id descending)
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[list[ItemBookResponse]]: Standard API response with a list of item book data and pagination metadata

    Raises:
        Exception: If there's an error during the retrieval process
    """
    logger.debug(f"get_all_item_books: tenant_id -> {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        item_books, total_count = await service.get_item_book_all_paginated_async(limit, page, sort)
        transformer = SchemasTransformerV1()
        return_item_books = [transformer.transform_item_book(item_book) for item_book in item_books]
    except Exception as e:
        raise e

    metadata = PaginationMetadata(page=page, limit=limit, total_count=total_count)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item Books found successfully. Total count: {total_count}",
        data=return_item_books,
        metadata=metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/item_books/{item_book_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_item_book(
    item_book: ItemBookUpdateRequest,
    item_book_id: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update an existing item book record.

    This endpoint allows updating the details of an existing item book identified
    by its ID. Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book: The updated item book details
        item_book_id: The unique ID of the item book to update
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the updated item book data

    Raises:
        Exception: If there's an error during the update process
    """
    logger.debug(
        f"update_item_book: item_book -> {item_book}, item_book_id -> {item_book_id}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        updated_item_book = await service.update_item_book_async(item_book_id, item_book.dict())
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(updated_item_book)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item Book updated successfully. item_book_id: {item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/item_books/{item_book_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookDeleteResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_item_book(
    item_book_id: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete an item book record.

    This endpoint allows removing an item book identified by its unique ID.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_id: The unique ID of the item book to delete
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookDeleteResponse]: Standard API response with deletion confirmation

    Raises:
        Exception: If there's an error during the deletion process
    """
    logger.debug(f"delete_item_book: item_book_id -> {item_book_id}, tenant_id -> {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        await service.delete_item_book_async(item_book_id)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Item Book deleted successfully. item_book_id: {item_book_id}",
        data=ItemBookDeleteResponse(item_book_id=item_book_id),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/tenants/{tenant_id}/item_books/{item_book_id}/categories",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def add_category_to_item_book(
    item_book_category: ItemBookCategory,
    item_book_id: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Add a category to an item book.

    This endpoint allows adding a new category to an existing item book identified by its ID.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_category: The category details to add
        item_book_id: The unique ID of the item book to update
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the updated item book data

    Raises:
        Exception: If there's an error during the update process
    """
    logger.debug(
        f"add_category_to_item_book: item_book_category -> {item_book_category}, item_book_id -> {item_book_id}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        new_item_book = await service.add_category_to_item_book_async(item_book_id, item_book_category.model_dump())
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(new_item_book)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Category added to Item Book successfully. item_book_id: {item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_category_in_item_book(
    item_book_category: ItemBookCategory,
    item_book_id: str = Path(...),
    category_number: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update a category in an item book.

    This endpoint allows updating an existing category in an item book identified by its ID and category number.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_category: The updated category details
        item_book_id: The unique ID of the item book to update
        category_number: The unique number of the category to update
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the updated item book data

    Raises:
        Exception: If there's an error during the update process
    """
    logger.debug(
        f"update_category_in_item_book: item_book_category -> {item_book_category}, item_book_id -> {item_book_id}, category_number -> {category_number}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        updated_item_book = await service.update_category_in_item_book_async(
            item_book_id, category_number, item_book_category.model_dump()
        )
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(updated_item_book)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Category updated in Item Book successfully. item_book_id: {item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookCategoryDeleteResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_category_from_item_book(
    item_book_id: str = Path(...),
    category_number: str = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete a category from an item book.

    This endpoint allows removing a category from an item book identified by its ID and category number.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_id: The unique ID of the item book to update
        category_number: The unique number of the category to delete
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookCategoryDeleteResponse]: Standard API response with deletion confirmation

    Raises:
        Exception: If there's an error during the deletion process
    """
    logger.debug(
        f"delete_category_from_item_book: item_book_id -> {item_book_id}, category_number -> {category_number}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        await service.delete_category_from_item_book_async(item_book_id, category_number)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Category deleted from Item Book successfully. item_book_id: {item_book_id}",
        data=ItemBookCategoryDeleteResponse(item_book_id=item_book_id),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def add_tab_to_category_in_item_book(
    item_book_tab: ItemBookTab,
    item_book_id: str = Path(...),
    category_number: int = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Add a tab to a category in an item book.

    This endpoint allows adding a new tab to an existing category in an item book identified by its ID and category number.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_tab: The tab details to add
        item_book_id: The unique ID of the item book to update
        category_number: The unique number of the category to update
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the updated item book data

    Raises:
        Exception: If there's an error during the update process
    """
    logger.debug(
        f"add_tab_to_category_in_item_book: item_book_tab -> {item_book_tab}, item_book_id -> {item_book_id}, category_number -> {category_number}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        new_item_book = await service.add_tab_to_category_in_item_book_async(
            item_book_id, category_number, item_book_tab.model_dump()
        )
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(new_item_book)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Tab added to Category in Item Book successfully. item_book_id: {item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_tab_in_category_in_item_book(
    item_book_tab: ItemBookTab,
    item_book_id: str = Path(...),
    category_number: int = Path(...),
    tab_number: int = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update a tab in a category in an item book.

    This endpoint allows updating an existing tab in a category in an item book identified by its ID, category number, and tab number.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_tab: The updated tab details
        item_book_id: The unique ID of the item book to update
        category_number: The unique number of the category to update
        tab_number: The unique number of the tab to update
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the updated item book data

    Raises:
        Exception: If there's an error during the update process
    """
    logger.debug(
        f"update_tab_in_category_in_item_book: item_book_tab -> {item_book_tab}, item_book_id -> {item_book_id}, category_number -> {category_number}, tab_number -> {tab_number}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        updated_item_book = await service.update_tab_in_category_in_item_book_async(
            item_book_id, category_number, tab_number, item_book_tab.model_dump()
        )
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(updated_item_book)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Tab updated in Category in Item Book successfully. item_book_id: {item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookTabDeleteResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_tab_from_category_in_item_book(
    item_book_id: str = Path(...),
    category_number: int = Path(...),
    tab_number: int = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete a tab from a category in an item book.

    This endpoint allows removing a tab from a category in an item book identified by its ID, category number, and tab number.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_id: The unique ID of the item book to update
        category_number: The unique number of the category to update
        tab_number: The unique number of the tab to delete
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookTabDeleteResponse]: Standard API response with deletion confirmation

    Raises:
        Exception: If there's an error during the deletion process
    """
    logger.debug(
        f"delete_tab_from_category_in_item_book: item_book_id -> {item_book_id}, category_number -> {category_number}, tab_number -> {tab_number}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        await service.delete_tab_from_category_in_item_book_async(item_book_id, category_number, tab_number)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Tab deleted from Category in Item Book successfully. item_book_id: {item_book_id}",
        data=ItemBookTabDeleteResponse(item_book_id=item_book_id),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def add_button_to_tab_in_category_in_item_book(
    item_book_button: ItemBookButton,
    item_book_id: str = Path(...),
    category_number: int = Path(...),
    tab_number: int = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Add a button to a tab in a category in an item book.

    This endpoint allows adding a new button to an existing tab in a category in an item book identified by its ID, category number, and tab number.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_button: The button details to add
        item_book_id: The unique ID of the item book to update
        category_number: The unique number of the category to update
        tab_number: The unique number of the tab to update
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the updated item book data

    Raises:
        Exception: If there's an error during the update process
    """
    logger.debug(
        f"add_button_to_tab_in_category_in_item_book: item_book_button -> {item_book_button}, item_book_id -> {item_book_id}, category_number -> {category_number}, tab_number -> {tab_number}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        new_item_book = await service.add_button_to_tab_in_category_in_item_book_async(
            item_book_id, category_number, tab_number, item_book_button.model_dump()
        )
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(new_item_book)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Button added to Tab in Category in Item Book successfully. item_book_id: {item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons/pos_x/{pos_x}/pos_y/{pos_y}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_button_in_tab_in_category_in_item_book(
    item_book_button: ItemBookButton,
    item_book_id: str = Path(...),
    category_number: int = Path(...),
    tab_number: int = Path(...),
    pos_x: int = Path(...),
    pos_y: int = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update a button in a tab in a category in an item book.

    This endpoint allows updating an existing button in a tab in a category in an item book identified by its ID, category number, tab number, and button position.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_button: The updated button details
        item_book_id: The unique ID of the item book to update
        category_number: The unique number of the category to update
        tab_number: The unique number of the tab to update
        pos_x: The x position of the button to update
        pos_y: The y position of the button to update
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookResponse]: Standard API response with the updated item book data

    Raises:
        Exception: If there's an error during the update process
    """
    logger.debug(
        f"update_button_in_tab_in_category_in_item_book: item_book_id -> {item_book_id}, category_number -> {category_number}, tab_number -> {tab_number}, pos_x -> {pos_x}, pos_y -> {pos_y}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        updated_item_book = await service.update_button_in_tab_in_category_in_item_book_async(
            item_book_id, category_number, tab_number, pos_x, pos_y, item_book_button.model_dump()
        )
        transformer = SchemasTransformerV1()
        return_item_book = transformer.transform_item_book(updated_item_book)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Button updated in Tab in Category in Item Book successfully. item_book_id: {item_book_id}",
        data=return_item_book,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons/pos_x/{pos_x}/pos_y/{pos_y}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ItemBookButtonDeleteResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_button_from_tab_in_category_in_item_book(
    item_book_id: str = Path(...),
    category_number: int = Path(...),
    tab_number: int = Path(...),
    pos_x: int = Path(...),
    pos_y: int = Path(...),
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete a button from a tab in a category in an item book.

    This endpoint allows removing a button from a tab in a category in an item book identified by its ID, category number, tab number, and button position.
    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        item_book_id: The unique ID of the item book to update
        category_number: The unique number of the category to update
        tab_number: The unique number of the tab to update
        pos_x: The x position of the button to delete
        pos_y: The y position of the button to delete
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials

    Returns:
        ApiResponse[ItemBookButtonDeleteResponse]: Standard API response with deletion confirmation

    Raises:
        Exception: If there's an error during the deletion process
    """
    logger.debug(
        f"delete_button_from_tab_in_category_in_item_book: item_book_id -> {item_book_id}, category_number -> {category_number}, tab_number -> {tab_number}, pos_x -> {pos_x}, pos_y -> {pos_y}, tenant_id -> {tenant_id}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    service = await get_item_book_service_async(tenant_id)

    try:
        await service.delete_button_from_tab_in_category_in_item_book_async(
            item_book_id, category_number, tab_number, pos_x, pos_y
        )
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Button deleted from Tab in Category in Item Book successfully. item_book_id: {item_book_id}",
        data=ItemBookButtonDeleteResponse(item_book_id=item_book_id),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
