# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Depends, Path, Query
from logging import getLogger
import inspect
from typing import List

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
    TaxMasterResponse,
)
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.dependencies.get_master_services import get_tax_master_service_async
from app.dependencies.common import parse_sort

# Create a router instance for tax master endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


@router.get(
    "/tenants/{tenant_id}/taxes",
    response_model=ApiResponse[List[TaxMasterResponse]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_taxes(
    tenant_id: str = Path(...),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve all tax records for a tenant.

    This endpoint returns a paginated list of all tax rates for the specified tenant.
    The results can be sorted and paginated as needed. This is useful for getting a list
    of all available tax rates for administration or selection purposes.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        tenant_id: The tenant identifier from the path
        limit: Maximum number of tax records to return (default: 100)
        page: Page number for pagination (default: 1)
        sort: Sorting criteria (default: tax_code ascending)
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[List[TaxMasterResponse]]: Standard API response with a list of tax data and pagination metadata

    Raises:
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"get_taxes: tenant_id->{tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    service = await get_tax_master_service_async(tenant_id)
    try:
        taxes, total_count = await service.get_all_taxes_paginated_async(limit, page, sort)
        transformer = SchemasTransformerV1()
        return_taxes = [transformer.transform_tax(tax) for tax in taxes]
    except Exception as e:
        logger.error(f"Error getting taxes: {e}")
        raise e

    metadata = PaginationMetadata(page=page, limit=limit, total_count=total_count)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Taxes found successfully for tenant_id: {tenant_id}. Total count: {total_count}",
        data=[tax.model_dump() for tax in return_taxes],
        metadata=metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/taxes/{tax_code}",
    response_model=ApiResponse[TaxMasterResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_tax(
    tax_code: str,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve a specific tax record by its code.

    This endpoint retrieves the details of a tax rate identified by its unique code.
    It returns information including the description, rate value, and tax type.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        tax_code: The unique code of the tax to retrieve
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[TaxMasterResponse]: Standard API response with the tax data

    Raises:
        DocumentNotFoundException: If the tax with the given code is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"get_tax: tax_code->{tax_code}, tenant_id->{tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    service = await get_tax_master_service_async(tenant_id)
    try:
        tax = await service.get_tax_by_code_async(tax_code)
        if tax is None:
            message = f"Tax {tax_code} not found, tenant_id: {tenant_id}"
            raise DocumentNotFoundException(message, logger)
        transformer = SchemasTransformerV1()
        return_tax = transformer.transform_tax(tax)
    except Exception as e:
        logger.error(f"Error getting tax: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Tax {tax_code} found successfully for tenant_id: {tenant_id}",
        data=return_tax.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
