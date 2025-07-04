# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Depends, Path, Query
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
    PaymentCreateRequest,
    PaymentUpdateRequest,
    PaymentResponse,
    PaymentDeleteResponse,
)
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.dependencies.get_master_services import get_payment_master_service_async
from app.dependencies.common import parse_sort

# Create a router instance for payment master endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


@router.post(
    "/tenants/{tenant_id}/payments",
    response_model=ApiResponse[PaymentResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def create_payment(
    payment: PaymentCreateRequest,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Create a new payment method record.

    This endpoint allows creating a new payment method with its code, description,
    and various flags that control its behavior in the POS system such as whether
    it can handle refunds, allow deposits over the amount, give change, etc.

    Payment methods are essential for transaction processing and define how sales
    are settled in the POS system (cash, credit card, gift card, etc.).

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        payment: The payment method details to create
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[PaymentResponse]: Standard API response with the created payment method data

    Raises:
        DocumentAlreadyExistsException: If a payment method with the same code already exists
        InvalidRequestDataException: If the request data is invalid
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Create payment request received for payment_code: {payment.payment_code}, tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    service = await get_payment_master_service_async(tenant_id)
    try:
        new_payment = await service.create_payment_async(
            payment.payment_code,
            payment.description,
            payment.limit_amount,
            payment.can_refund,
            payment.can_deposit_over,
            payment.can_change,
            payment.is_active,
        )
        transformer = SchemasTransformerV1()
        return_payment = transformer.transform_payment(new_payment)
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Payment created. payment_code: {return_payment.payment_code}",
        data=return_payment.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/payments",
    response_model=ApiResponse[list[PaymentResponse]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_all_payments(
    tenant_id: str = Path(...),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve all payment methods for a tenant.

    This endpoint returns a paginated list of all payment methods for the specified tenant.
    The results can be sorted and paginated as needed. This is typically used to populate
    payment method selection screens or to view all available payment methods for administration.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        tenant_id: The tenant identifier from the path
        limit: Maximum number of payment methods to return (default: 100)
        page: Page number for pagination (default: 1)
        sort: Sorting criteria (default: payment_code ascending)
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[list[PaymentResponse]]: Standard API response with a list of payment method data and pagination metadata

    Raises:
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Get all payments request received. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    service = await get_payment_master_service_async(tenant_id)
    try:
        payments, total_count = await service.get_all_payments_paginated(limit, page, sort)
        transformer = SchemasTransformerV1()
        payment_all = [transformer.transform_payment(payment) for payment in payments]
    except Exception as e:
        logger.error(f"Error getting payments: {e}")
        raise e

    metadata = PaginationMetadata(page=page, limit=limit, total_count=total_count)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Payments found. Total payments: {total_count}",
        data=[payment.model_dump() for payment in payment_all],
        metadata=metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/payments/{payment_code}",
    response_model=ApiResponse[PaymentResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_payment(
    payment_code: str,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Retrieve a specific payment method by its code.

    This endpoint retrieves the details of a payment method identified by its unique code.
    It returns all attributes of the payment method including its description and behavior flags.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        payment_code: The unique code of the payment method to retrieve
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[PaymentResponse]: Standard API response with the payment method data

    Raises:
        DocumentNotFoundException: If the payment method with the given code is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Get payment request received for payment_code: {payment_code}. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    service = await get_payment_master_service_async(tenant_id)
    try:
        payment = await service.get_payment_by_code(payment_code)
        if payment is None:
            message = f"Payment not found. payment_code: {payment_code}"
            raise DocumentNotFoundException(message, logger)
        transformer = SchemasTransformerV1()
        return_payment = transformer.transform_payment(payment)
    except Exception as e:
        logger.error(f"Error getting payment: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Payment found. payment_code: {return_payment.payment_code}",
        data=return_payment.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.put(
    "/tenants/{tenant_id}/payments/{payment_code}",
    response_model=ApiResponse[PaymentResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_payment(
    payment_code: str,
    payment: PaymentUpdateRequest,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Update an existing payment method.

    This endpoint allows updating the details of an existing payment method identified
    by its code. It can be used to modify the description, limit amount, or behavior flags
    such as whether the payment method can be used for refunds or allows giving change.

    The payment_code itself cannot be changed, as it serves as a unique identifier.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        payment_code: The unique code of the payment method to update
        payment: The updated payment method details
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[PaymentResponse]: Standard API response with the updated payment method data

    Raises:
        DocumentNotFoundException: If the payment method with the given code is not found
        InvalidRequestDataException: If the request data is invalid
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Update payment request received for payment_code: {payment_code}. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    service = await get_payment_master_service_async(tenant_id)
    try:
        updated_payment = await service.update_payment_async(
            payment_code=payment_code, update_data=payment.model_dump()
        )
        transformer = SchemasTransformerV1()
        payment = transformer.transform_payment(updated_payment)
    except Exception as e:
        logger.error(f"Error updating payment: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Payment updated. payment_code: {payment.payment_code}",
        data=payment.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/tenants/{tenant_id}/payments/{payment_code}",
    response_model=ApiResponse[PaymentDeleteResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_payment(
    payment_code: str,
    tenant_id: str = Path(...),
    tenant_id_in_token: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """
    Delete a payment method.

    This endpoint allows removing a payment method completely from the system.
    Caution should be exercised as deleting payment methods that were used in
    past transactions can cause reporting and analysis issues.

    It's generally recommended to deactivate payment methods (setting is_active to false)
    rather than deleting them if they have been used in transactions.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        payment_code: The unique code of the payment method to delete
        tenant_id: The tenant identifier from the path
        tenant_id_in_token: The tenant ID from security credentials

    Returns:
        ApiResponse[PaymentDeleteResponse]: Standard API response with deletion confirmation

    Raises:
        DocumentNotFoundException: If the payment method with the given code is not found
        RepositoryException: If there's an error during database operations
    """
    logger.info(f"Delete payment request received for payment_code: {payment_code}. tenant_id: {tenant_id}")
    verify_tenant_id(tenant_id, tenant_id_in_token, logger)
    service = await get_payment_master_service_async(tenant_id)
    try:
        await service.delete_payment_async(payment_code)
    except Exception as e:
        logger.error(f"Error deleting payment: {e}")
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Payment deleted. payment_code: {payment_code}",
        data=PaymentDeleteResponse(payment_code=payment_code).model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
