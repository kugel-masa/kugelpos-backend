# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Depends, Path, Query
from logging import getLogger
import inspect

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
    StaffCreateRequest,
    StaffUpdateRequest,
    StaffResponse,
    StaffDeleteResponse,
)
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.dependencies.get_master_services import get_staff_master_service_async
from app.dependencies.common import parse_sort

# Create a router instance for staff master endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


@router.post(
    "/tenants/{tenant_id}/staff",
    response_model=ApiResponse[StaffResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def create_staff_master_async(
    staff: StaffCreateRequest,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Create a new staff record in the master data.

    This endpoint allows creating a new staff member with their ID, name, PIN code,
    and assigned roles. Staff records are essential for authentication, authorization,
    and tracking operations in the POS system.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        staff: The staff details to create
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[StaffResponse]: Standard API response with the created staff data

    Raises:
        DocumentAlreadyExistsException: If a staff with the same ID already exists
        InvalidRequestDataException: If the request data is invalid
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Create staff request received for staff_id: {staff.id} , tenant_id: {tenant_id}.")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_staff_master_service_async(tenant_id)
    try:
        staff_doc = await master_service.create_staff_async(staff.id, staff.name, staff.pin, staff.roles)
        transformer = SchemasTransformerV1()
        return_staff = transformer.transform_staff(staff_doc)
    except Exception as e:
        logger.error(f"Error creating staff: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Staff created successfully. staff_id: {return_staff.id}",
        data=return_staff.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/staff/{staff_id}",
    response_model=ApiResponse[StaffResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_staff_master_async(
    staff_id: str,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve a specific staff record by their ID.

    This endpoint retrieves the details of a staff member identified by their unique ID.
    It returns information including name, roles, and other attributes (PIN is not returned).

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        staff_id: The unique identifier of the staff to retrieve
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[StaffResponse]: Standard API response with the staff data

    Raises:
        DocumentNotFoundException: If the staff with the given ID is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Get staff request received for staff_id: {staff_id}, tenant_id: {tenant_id}.")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_staff_master_service_async(tenant_id)
    try:
        staff_doc = await master_service.get_staff_by_id_async(staff_id)
        if staff_doc is None:
            message = f"Staff not found. staff_id: {staff_id}"
            raise DocumentNotFoundException(message, logger)
        transformer = SchemasTransformerV1()
        staff = transformer.transform_staff(staff_doc)
    except Exception as e:
        logger.error(f"Error getting staff: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Staff found. staff_id: {staff.id}",
        data=staff.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/staff",
    response_model=ApiResponse[list[StaffResponse]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_staff_master_all_async(
    tenant_id: str = Path(...),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve all staff records for a tenant.

    This endpoint returns a paginated list of all staff members for the specified tenant.
    The results can be sorted and paginated as needed. This is useful for getting a list
    of all available staff members for administration or selection purposes.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        tenant_id: The tenant identifier from the path
        limit: Maximum number of staff records to return (default: 100)
        page: Page number for pagination (default: 1)
        sort: Sorting criteria (default: id ascending)
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[list[StaffResponse]]: Standard API response with a list of staff data and pagination metadata

    Raises:
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Get all staff request received. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_staff_master_service_async(tenant_id)
    try:
        staff_docs, total_count = await master_service.get_staff_all_paginated_async(limit, page, sort)
        transformer = SchemasTransformerV1()
        staff_all = [transformer.transform_staff(staff_doc) for staff_doc in staff_docs]
    except Exception as e:
        logger.error(f"Error getting all staff: {e}")
        raise e

    metadata = PaginationMetadata(page=page, limit=limit, total_count=total_count)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"All staff found. Total count: {total_count}",
        data=[staff.model_dump() for staff in staff_all],
        metadata=metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/staff/{staff_id}",
    response_model=ApiResponse[StaffResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_staff_master_async(
    staff_id: str,
    staff: StaffUpdateRequest,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update an existing staff record.

    This endpoint allows updating the details of an existing staff member identified by their ID.
    Only the provided fields will be updated. This can be used to change a staff member's name,
    PIN code, or assigned roles.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        staff_id: The unique identifier of the staff to update
        staff: The updated staff details
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[StaffResponse]: Standard API response with the updated staff data

    Raises:
        DocumentNotFoundException: If the staff with the given ID is not found
        InvalidRequestDataException: If the request data is invalid
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Update staff request received for staff_id: {staff_id}, tenant_id: {tenant_id}.")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_staff_master_service_async(tenant_id)
    try:
        staff_doc = await master_service.update_staff_async(staff_id, staff.model_dump())
        transformer = SchemasTransformerV1()
        staff = transformer.transform_staff(staff_doc)
    except Exception as e:
        logger.error(f"Error updating staff: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Staff updated successfully. staff_id: {staff.id}",
        data=staff.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/staff/{staff_id}",
    response_model=ApiResponse[StaffDeleteResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_staff_master_async(
    staff_id: str,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete a staff record.

    This endpoint allows deleting a staff member from the system. This operation
    is permanent and cannot be undone. Once a staff member is deleted, they will no
    longer be able to log in or access the POS system.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        staff_id: The unique identifier of the staff to delete
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[StaffDeleteResponse]: Standard API response with deletion confirmation

    Raises:
        DocumentNotFoundException: If the staff with the given ID is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Delete staff request received for staff_id: {staff_id}, tenant_id: {tenant_id}.")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    master_service = await get_staff_master_service_async(tenant_id)
    try:
        await master_service.delete_staff_async(staff_id)
    except Exception as e:
        logger.error(f"Error deleting staff: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Staff deleted successfully. staff_id: {staff_id}",
        data=StaffDeleteResponse(staff_id=staff_id),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
