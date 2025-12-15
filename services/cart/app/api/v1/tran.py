# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, Depends, Query, Path, HTTPException
from logging import getLogger
import inspect

from kugel_common.database import database as db_helper
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_terminal_info_with_api_key, verify_pubsub_notification_auth
from kugel_common.status_codes import StatusCodes
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument

from app.services.tran_service import TranService
from app.models.repositories.terminal_counter_repository import (
    TerminalCounterRepository,
)
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.tranlog_delivery_status_repository import TranlogDeliveryStatusRepository
from app.models.repositories.settings_master_web_repository import SettingsMasterWebRepository
from app.models.repositories.payment_master_web_repository import PaymentMasterWebRepository
from app.models.repositories.transaction_status_repository import TransactionStatusRepository
from app.api.v1.schemas import (
    Cart,
    TranLineItem,
    TranPayment,
    CartCreateRequest,
    CartCreateResponse,
    PaymentRequest,
    DiscountRequest,
    Tran,
    DeliveryStatusUpdateRequest,
    DeliveryStatusUpdateResponse,
)
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.config.settings import settings
from app.exceptions import InvalidRequestDataException, InternalErrorException

# create a router instance
router = APIRouter()

# get an instance of the logger
logger = getLogger(__name__)

# get the terminal cache instance
from app.dependencies.terminal_cache_dependency import _terminal_cache


async def get_tran_service_for_pubsub_notification(
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    auth_info: dict = Depends(verify_pubsub_notification_auth),
):
    """
    Dependency injection helper for transaction service for pub/sub notifications.
    Creates and returns a configured TranService instance for delivery-status endpoints.

    Args:
        tenant_id: The tenant ID from the path
        store_code: The store code from the path
        terminal_no: The terminal number from the path
        auth_info: Authentication information from JWT or API key

    Returns:
        Configured TranService instance
    """
    # Construct terminal_id
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"

    logger.debug(f"DEBUG: get_tran_service_for_pubsub_notification called for terminal_id: {terminal_id}")
    logger.debug(f"DEBUG: auth_info: {auth_info}")

    # Try to get terminal info from cache first
    terminal_info = _terminal_cache.get(terminal_id)
    logger.debug(f"DEBUG: terminal_info from cache: {terminal_info}")

    if terminal_info is None:
        # Get terminal info from terminal service using JWT token
        from kugel_common.utils.http_client_helper import get_pooled_client
        from kugel_common.utils.service_auth import create_service_token
        from datetime import datetime, timedelta, timezone
        from jose import jwt

        logger.debug("DEBUG: Terminal not in cache, calling terminal service")

        # Use pooled client for connection reuse (eliminates 50-100ms overhead per request)
        client = await get_pooled_client(service_name="terminal")
        # Use the JWT token from the auth_info if available
        headers = {}
        if auth_info.get("auth_type") == "jwt":
            # Create a service token for inter-service communication
            service_token = create_service_token(tenant_id=tenant_id, service_name="cart-service")
            headers["Authorization"] = f"Bearer {service_token}"
            logger.debug("DEBUG: Created JWT token for terminal service")

        try:
            logger.debug(f"DEBUG: Calling terminal service with headers: {headers}")
            logger.debug(f"DEBUG: Terminal service endpoint: /terminals/{terminal_id}")

            response_data = await client.get(endpoint=f"/terminals/{terminal_id}", headers=headers)

            logger.debug(f"Terminal service response: {response_data}")

            # Transform the response to TerminalInfoDocument
            from kugel_common.security import transform_terminal_info

            terminal_info = transform_terminal_info(response_data["data"])

            # Cache the terminal info
            _terminal_cache.set(terminal_id, terminal_info)

        except Exception as e:
            logger.error(f"Failed to get terminal info from terminal service: {e}")
            logger.error(f"Error type: {type(e)}, Error details: {str(e)}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Terminal not found: {terminal_id}")

    # Create TranService
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    db_common = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_commons")

    terminal_counter_repo = TerminalCounterRepository(db=db, terminal_info=terminal_info)
    await terminal_counter_repo.initialize()
    tranlog_repo = TranlogRepository(db=db, terminal_info=terminal_info)
    await tranlog_repo.initialize()
    tranlog_delivery_status_repo = TranlogDeliveryStatusRepository(db=db_common, terminal_info=terminal_info)
    await tranlog_delivery_status_repo.initialize()
    settings_master_repo = SettingsMasterWebRepository(
        tenant_id=tenant_id,
        store_code=terminal_info.store_code,
        terminal_no=terminal_info.terminal_no,
        terminal_info=terminal_info,
    )
    payment_master_repo = PaymentMasterWebRepository(tenant_id=tenant_id, terminal_info=terminal_info)
    transaction_status_repo = TransactionStatusRepository(db=db, terminal_info=terminal_info)
    await transaction_status_repo.initialize()

    tran_service = TranService(
        terminal_info=terminal_info,
        terminal_counter_repo=terminal_counter_repo,
        tranlog_repo=tranlog_repo,
        tranlog_delivery_status_repo=tranlog_delivery_status_repo,
        settings_master_repo=settings_master_repo,
        payment_master_repo=payment_master_repo,
        transaction_status_repo=transaction_status_repo,
    )

    return tran_service


async def get_tran_service(
    terminal_info: TerminalInfoDocument = Depends(get_terminal_info_with_api_key),
):
    """
    Dependency injection helper for transaction service.
    Creates and returns a configured TranService instance for API endpoints.

    Args:
        terminal_info: Terminal information obtained from API key authentication

    Returns:
        Configured TranService instance
    """
    # db for tenant
    tenant_id = terminal_info.tenant_id
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    # db for all tenants
    db_common = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_commons")  # ← 修正

    terminal_counter_repo = TerminalCounterRepository(db=db, terminal_info=terminal_info)
    await terminal_counter_repo.initialize()
    tranlog_repo = TranlogRepository(db=db, terminal_info=terminal_info)
    await tranlog_repo.initialize()
    tranlog_delivery_status_repo = TranlogDeliveryStatusRepository(
        db=db_common, terminal_info=terminal_info  # use common db
    )
    await tranlog_delivery_status_repo.initialize()
    settings_master_repo = SettingsMasterWebRepository(
        tenant_id=tenant_id,
        store_code=terminal_info.store_code,
        terminal_no=terminal_info.terminal_no,
        terminal_info=terminal_info,
    )
    payment_master_repo = PaymentMasterWebRepository(tenant_id=tenant_id, terminal_info=terminal_info)
    transaction_status_repo = TransactionStatusRepository(db=db, terminal_info=terminal_info)
    await transaction_status_repo.initialize()

    return TranService(
        terminal_info=terminal_info,
        terminal_counter_repo=terminal_counter_repo,
        tranlog_repo=tranlog_repo,
        tranlog_delivery_status_repo=tranlog_delivery_status_repo,
        settings_master_repo=settings_master_repo,
        payment_master_repo=payment_master_repo,
        transaction_status_repo=transaction_status_repo,
    )


def parse_sort(sort: str = Query(default=None, description="?sort=field1:1,field2:-1")) -> list[tuple[str, int]]:
    """
    Parse the sort query parameter into a list of (field, direction) tuples.

    Args:
        sort: Sort string in format "field1:1,field2:-1" where 1 is ascending, -1 is descending

    Returns:
        List of tuples containing field name and sort direction (1 or -1)
    """
    sort_list = []
    if sort is None:
        sort_list = [("transaction_no", -1)]
    else:
        sort_list = [tuple(item.split(":")) for item in sort.split(",")]
        sort_list = [(field, int(order)) for field, order in sort_list]
    return sort_list


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions",
    response_model=ApiResponse[list[Tran]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_transactions_by_query(
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    business_date: str = Query(None),  # format:YYYYMMDD
    open_counter: int = Query(None),
    transaction_type: list[int] = Query(None),
    receipt_no: int = Query(None),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    include_cancelled: bool = Query(False),
    tran_service: TranService = Depends(get_tran_service),
):
    """
    Get transactions based on query parameters.

    Retrieves a paginated list of transactions matching the specified filters.
    The tenant ID in the path must match the tenant ID from the authentication token.

    Args:
        tenant_id: The tenant ID in the path
        store_code: The store code to filter by
        terminal_no: The terminal number to filter by
        business_date: Optional business date filter in YYYYMMDD format
        open_counter: Optional open counter filter
        transaction_type: Optional transaction type filter
        receipt_no: Optional receipt number filter
        limit: Maximum number of results per page (default: 100)
        page: Page number for pagination (default: 1)
        sort: Sort order specification
        include_cancelled: Whether to include cancelled transactions
        tran_service: Injected transaction service

    Returns:
        API response with a list of matching transactions

    Raises:
        HTTPException: If tenant_id doesn't match the authenticated tenant
    """
    # check tenant_id
    if tenant_id != tran_service.terminal_info.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tenant_id: {tenant_id}",
        )

    try:
        paginated_result = await tran_service.get_tranlog_by_query_async(
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            transaction_type=transaction_type,
            receipt_no=receipt_no,
            limit=limit,
            page=page,
            sort=sort,
            include_cancelled=include_cancelled,
        )
        return_tranlogs = [SchemasTransformerV1().transform_tran(tranlog=tranlog) for tranlog in paginated_result.data]
    except Exception as e:
        raise e

    logger.debug(f"metadata: {paginated_result.metadata.model_dump()}")

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Success to get transactions by query",
        data=[tranlog.model_dump() for tranlog in return_tranlogs],
        metadata=paginated_result.metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}",
    response_model=ApiResponse[Tran],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_transaction_by_tranasction_no(
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    transaction_no: int = Path(...),
    tran_service: TranService = Depends(get_tran_service),
):
    """
    Get a single transaction by its transaction number.

    Retrieves detailed information about a specific transaction identified by its number.
    The tenant ID in the path must match the tenant ID from the authentication token.

    Args:
        tenant_id: The tenant ID in the path
        store_code: The store code of the transaction
        terminal_no: The terminal number of the transaction
        transaction_no: The transaction number to retrieve
        tran_service: Injected transaction service

    Returns:
        API response with the requested transaction details

    Raises:
        HTTPException: If tenant_id doesn't match the authenticated tenant
        HTTPException: If the transaction is not found
    """
    # check tenant_id
    if tenant_id != tran_service.terminal_info.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tenant_id: {tenant_id}",
        )
    try:
        tranlog = await tran_service.get_tranlog_by_transaction_no_async(
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
        )
        return_tranlog = SchemasTransformerV1().transform_tran(tranlog=tranlog)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Success to get transaction by transaction_no",
        data=return_tranlog.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/void",
    response_model=ApiResponse[Tran],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def void_transaction_by_transaction_no(
    payments: list[PaymentRequest],
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    transaction_no: int = Path(...),
    tran_service: TranService = Depends(get_tran_service),
):
    """
    Void (cancel) a transaction.

    Marks a transaction as voided and processes any required refund payments.
    The terminal making this request must match the terminal that created the transaction.

    Args:
        payments: List of payment methods to use for refunding
        tenant_id: The tenant ID in the path
        store_code: The store code of the transaction
        terminal_no: The terminal number of the transaction
        transaction_no: The transaction number to void
        tran_service: Injected transaction service

    Returns:
        API response with the voided transaction details

    Raises:
        InvalidRequestDataException: If tenant_id, store_code, or terminal_no don't match the authenticated terminal
        HTTPException: If the transaction is not found or cannot be voided
    """
    # you can void only terminal which has terminal_id in query parameter

    # check tenant_id
    if tenant_id != tran_service.terminal_info.tenant_id:
        message = f"tenant_id in request does not match the tenant_id in the URL : req.tenant_id->{tenant_id}, tenant_id->{tran_service.terminal_info.tenant_id}"
        raise InvalidRequestDataException(message=message, logger=logger, original_exception=None)

    # check store_code
    if store_code != tran_service.terminal_info.store_code:
        message = f"store_code in request does not match the store_code in the URL : req.store_code->{store_code}, store_code->{tran_service.terminal_info.store_code}"
        raise InvalidRequestDataException(message=message, logger=logger, original_exception=None)

    # check terminal_no
    if terminal_no != tran_service.terminal_info.terminal_no:
        message = f"terminal_no in request does not match the terminal_no in the URL : req.terminal_no->{terminal_no}, terminal_no->{tran_service.terminal_info.terminal_no}"
        raise InvalidRequestDataException(message=message, logger=logger, original_exception=None)

    try:
        tranlog = await tran_service.get_tranlog_by_transaction_no_async(
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
        )
        tranlog_voided = await tran_service.void_async(
            tranlog, add_payment_list=[payment.model_dump() for payment in payments]
        )
        return_tranlog = SchemasTransformerV1().transform_tran(tranlog_voided).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Success to void transaction by transaction_no",
        data=return_tranlog,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/return",
    response_model=ApiResponse[Tran],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def return_transaction_by_transaction_no(
    payments: list[PaymentRequest],
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    transaction_no: int = Path(...),
    tran_service: TranService = Depends(get_tran_service),
):
    """
    Process a transaction return.

    Creates a return transaction based on an original transaction and processes any required refund payments.
    The terminal making this request must be in the same store as the original transaction.

    Args:
        payments: List of payment methods to use for refunding
        tenant_id: The tenant ID in the path
        store_code: The store code of the transaction
        terminal_no: The terminal number of the transaction
        transaction_no: The transaction number to process a return for
        tran_service: Injected transaction service

    Returns:
        API response with the return transaction details

    Raises:
        InvalidRequestDataException: If tenant_id or store_code don't match the authenticated terminal
        HTTPException: If the transaction is not found or cannot be returned
    """
    # you can return only terminal in the same store

    logger.debug(f"return_transaction_by_transaction_no: payments->{payments}")

    # check tenant_id
    if tenant_id != tran_service.terminal_info.tenant_id:
        message = f"tenant_id in request does not match the tenant_id in the URL : req.tenant_id->{tenant_id}, tenant_id->{tran_service.terminal_info.tenant_id}"
        raise InvalidRequestDataException(message=message, logger=logger, original_exception=None)

    # check store_code
    if store_code != tran_service.terminal_info.store_code:
        message = f"store_code in request does not match the store_code in the URL : req.store_code->{store_code}, store_code->{tran_service.terminal_info.store_code}"
        raise InvalidRequestDataException(message=message, logger=logger, original_exception=None)

    try:
        tranlog = await tran_service.get_tranlog_by_transaction_no_async(
            store_code=store_code, terminal_no=terminal_no, transaction_no=transaction_no
        )
        tranlog_returned = await tran_service.return_async(
            tranlog, add_payment_list=[payment.model_dump() for payment in payments]
        )
        return_tranlog = SchemasTransformerV1().transform_tran(tranlog_returned).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Success to return transaction by transaction_no",
        data=return_tranlog,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )

    logger.debug(f"return_transaction_by_transaction_no: response->{response}")
    return response


# notify delivery status
@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/{transaction_no}/delivery-status",
    response_model=ApiResponse[DeliveryStatusUpdateResponse],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def notify_delivery_status(
    delivery_status: DeliveryStatusUpdateRequest,
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    tran_service: TranService = Depends(get_tran_service_for_pubsub_notification),
):
    """
    Notify the delivery status of a transaction.

    Updates the delivery status of a specific transaction based on the provided information.
    The terminal making this request must be in the same store as the original transaction.

    Args:
        delivery_status: Delivery status update request containing event ID, service, status, and optional message
        tenant_id: The tenant ID in the path
        store_code: The store code of the transaction
        terminal_no: The terminal number of the transaction
        tran_service: Injected transaction service

    Returns:
        API response with the updated delivery status

    Raises:
        InvalidRequestDataException: If tenant_id or store_code don't match the authenticated terminal
        HTTPException: If the transaction is not found or cannot be updated
    """

    logger.debug(
        f"notify_delivery_status: delivery_status->{delivery_status}, tenant_id->{tenant_id}, store_code->{store_code}, terminal_no->{terminal_no}"
    )

    try:
        await tran_service.update_delivery_status_async(
            event_id=delivery_status.event_id,
            service_name=delivery_status.service,
            status=delivery_status.status,
            message=delivery_status.message,
        )

        logger.debug(f"Delivery status updated successfully for event_id: {delivery_status.event_id}")

        response_data = DeliveryStatusUpdateResponse(
            event_id=delivery_status.event_id,
            service=delivery_status.service,
            status=delivery_status.status,
            success=True,
        ).model_dump()

        logger.debug(f"Delivery status Response data: {response_data}")

    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Success to update delivery status",
        data=response_data,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )

    return response
