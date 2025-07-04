# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Depends, Query, Path
from logging import getLogger
import inspect
from typing import Optional

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.status_codes import StatusCodes

from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.api.v1.schemas import *
from app.dependencies.get_terminal_service import (
    get_terminal_service_async,
    parse_sort,
    get_tenant_id_with_token_wrapper,
    get_tenant_id_with_security_wrapper,
    get_tenant_id_with_security_by_query_optional_wrapper,
    get_tenant_id_for_pubsub_notification,
)

router = APIRouter()
logger = getLogger(__name__)

# API endpoints


@router.post(
    "/terminals",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[Terminal],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def create_terminal(terminal: TerminalCreateRequest, tenant_id: str = Depends(get_tenant_id_with_token_wrapper)):
    """
    Create a new terminal

    This endpoint creates a new terminal for a store with the provided details.
    Requires token authentication (no terminal ID/API key needed since the terminal doesn't exist yet).

    Args:
        terminal: Terminal creation request with store code, terminal number, and description
        tenant_id: Tenant ID extracted from authentication token

    Returns:
        ApiResponse containing the created terminal information
    """
    # create terminal info
    terminal_id = f"{tenant_id}-{terminal.store_code}-{terminal.terminal_no}"
    terminal_service = await get_terminal_service_async(tenant_id=tenant_id, terminal_id=terminal_id)

    logger.debug(
        f"Creating terminal for tenant {terminal_service.staff_master_repo.tenant_id}, "
        f"store {terminal.store_code}, terminal {terminal.terminal_no} "
    )

    try:
        terminal_info = await terminal_service.create_terminal_async(
            store_code=terminal.store_code, terminal_no=terminal.terminal_no, description=terminal.description
        )  # tenant_id is known
        return_json = SchemasTransformerV1().transform_terminal(terminal_info).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Terminal Created. terminal_id: {terminal_info.terminal_id}",
        data=return_json,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/terminals",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[list[Terminal]],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_terminals(
    limit: int = Query(100, description="Limit the number of results"),
    page: int = Query(1, description="Page number"),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    tenant_id: str = Depends(get_tenant_id_with_security_by_query_optional_wrapper),
    store_code: Optional[str] = Query(None, description="Filter by store code"),
):
    """
    Get a list of terminals

    This endpoint retrieves a paginated list of terminals for the authenticated tenant.
    Optional filtering by store code is supported.

    Args:
        limit: Maximum number of results to return per page
        page: Page number for pagination
        sort: Sorting criteria
        tenant_id: Tenant ID extracted from authentication
        store_code: Optional filter to show only terminals from a specific store

    Returns:
        ApiResponse containing list of terminal information
    """
    logger.debug("Getting terminals")
    terminal_service = await get_terminal_service_async(tenant_id)
    try:
        paginated_result = await terminal_service.get_terminal_info_list_paginated_async(
            limit=limit, page=page, sort=sort, store_code=store_code
        )
        return_json = [
            SchemasTransformerV1().transform_terminal(terminal).model_dump() for terminal in paginated_result.data
        ]
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminals Retrieved. count: {len(paginated_result.data)}",
        data=return_json,
        metadata=paginated_result.metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/terminals/{terminal_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Terminal],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_terminal(terminal_id: str, tenant_id: str = Depends(get_tenant_id_with_security_wrapper)):
    """
    Get terminal information

    This endpoint retrieves detailed information about a specific terminal.

    Args:
        terminal_id: ID of the terminal to retrieve
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing terminal information
    """
    logger.debug(f"Getting terminal for terminal {terminal_id}")
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)
    try:
        terminal_info = await terminal_service.get_terminal_info_async()
        return_json = SchemasTransformerV1().transform_terminal(terminal_info).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Retrieved. terminal_id: {terminal_id}",
        data=return_json,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.delete(
    "/terminals/{terminal_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[TerminalDeleteResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def delete_terminal(terminal_id: str, tenant_id: str = Depends(get_tenant_id_with_token_wrapper)):
    """
    Delete a terminal

    This endpoint deletes a terminal from the system.
    Requires OAuth2 token authentication.

    Args:
        terminal_id: ID of the terminal to delete
        tenant_id: Tenant ID extracted from authentication token

    Returns:
        ApiResponse confirming terminal deletion
    """
    logger.debug(f"Deleting terminal for terminal {terminal_id}")
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)

    try:
        await terminal_service.delete_terminal_async()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Deleted. terminal_id: {terminal_id}",
        data=TerminalDeleteResponse(terminal_id=terminal_id),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.patch(
    "/terminals/{terminal_id}/description",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Terminal],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_terminal_description(
    terminal_id: str,
    terminal_update: TerminalUpdateRequest,
    tenant_id: str = Depends(get_tenant_id_with_security_wrapper),
):
    """
    Update terminal description

    This endpoint updates the description of a specific terminal.

    Args:
        terminal_id: ID of the terminal to update
        terminal_update: Update request containing the new description
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing updated terminal information
    """
    logger.debug(
        f"Updating terminal description for terminal {terminal_id}, terminal_description: {terminal_update.description}"
    )
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)
    try:
        terminal_info = await terminal_service.update_terminal_description_async(terminal_update.description)
        return_json = SchemasTransformerV1().transform_terminal(terminal_info).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Description Updated. terminal_id: {terminal_id}",
        data=return_json,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.patch(
    "/terminals/{terminal_id}/function_mode",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Terminal],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_terminal_function_mode(
    terminal_id: str,
    terminal_function_mode: UpdateFunctionModeRequest,
    tenant_id: str = Depends(get_tenant_id_with_security_wrapper),
):
    """
    Update terminal function mode

    This endpoint updates the operating mode of a terminal (e.g., Sales, Returns, etc.).
    The function mode determines what operations are available on the terminal.

    Args:
        terminal_id: ID of the terminal to update
        terminal_function_mode: Update request containing the new function mode
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing updated terminal information
    """
    logger.debug(
        f"Updating terminal function mode for terminal {terminal_id}, terminal_function_mode: {terminal_function_mode}"
    )
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)

    try:
        terminal_info = await terminal_service.update_terminal_function_mode_async(terminal_function_mode.function_mode)
        return_json = SchemasTransformerV1().transform_terminal(terminal_info).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Function Mode Updated. terminal_id: {terminal_id}",
        data=return_json,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/terminals/{terminal_id}/sign-in",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Terminal],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_404_NOT_FOUND: StatusCodes.get(status.HTTP_404_NOT_FOUND),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def terminal_signin(
    terminal_id: str,
    terminal_signin: TerminalSignInRequest,
    tenant_id: str = Depends(get_tenant_id_with_security_wrapper),
):
    """
    Sign in to a terminal

    This endpoint associates a staff member with a terminal for the duration of their shift.
    A terminal must have a staff member signed in before most operations can be performed.

    Args:
        terminal_id: ID of the terminal to sign into
        terminal_signin: Sign-in request containing staff ID
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing updated terminal information with staff details
    """
    logger.debug(f"Signing in terminal for terminal {terminal_id}, terminal_signin: {terminal_signin}")
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)

    try:
        terminal_info = await terminal_service.sign_in_terminal_async(terminal_signin.staff_id)
        return_json = SchemasTransformerV1().transform_terminal(terminal_info).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Signed In. terminal_id: {terminal_id} staff_id: {terminal_signin.staff_id}",
        data=return_json,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/terminals/{terminal_id}/sign-out",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[Terminal],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def terminal_signout(terminal_id: str, tenant_id: str = Depends(get_tenant_id_with_security_wrapper)):
    """
    Sign out from a terminal

    This endpoint removes the current staff association from a terminal
    at the end of their shift or when changing operators.

    Args:
        terminal_id: ID of the terminal to sign out from
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing updated terminal information without staff details
    """
    logger.debug(f"Signing out terminal for terminal {terminal_id}")
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)
    try:
        terminal_info = await terminal_service.sign_out_terminal_async()
        return_json = SchemasTransformerV1().transform_terminal(terminal_info).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Signed Out. terminal_id: {terminal_id}",
        data=return_json,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/terminals/{terminal_id}/open",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[TerminalOpenResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def terminal_open(
    terminal_id: str,
    terminal_open: TerminalOpenRequest = None,
    tenant_id: str = Depends(get_tenant_id_with_security_wrapper),
):
    """
    Open a terminal for business operations

    This endpoint transitions a terminal to the 'opened' state,
    making it ready for sales and other business operations.
    It also records the initial cash amount in the drawer.

    Args:
        terminal_id: ID of the terminal to open
        terminal_open: Open request containing initial cash amount
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing terminal opening log details
    """
    logger.debug(f"Opening terminal for terminal {terminal_id}, terminal_open: {terminal_open}")
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)
    try:
        if terminal_open is None:
            terminal_open = TerminalOpenRequest()
        open_log = await terminal_service.open_terminal_async(terminal_open.initial_amount)
        return_json = SchemasTransformerV1().transform_open_log(open_log).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Opened. terminal_id: {terminal_id}",
        data=return_json,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/terminals/{terminal_id}/close",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[TerminalCloseResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def terminal_close(
    terminal_id: str,
    terminal_close: TerminalCloseRequest = None,
    tenant_id: str = Depends(get_tenant_id_with_security_wrapper),
):
    """
    Close a terminal after business operations

    This endpoint transitions a terminal to the 'closed' state,
    ending the current business session. It records the final
    physical cash amount in the drawer and creates a closing report.

    Args:
        terminal_id: ID of the terminal to close
        terminal_close: Close request containing final physical cash amount
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing terminal closing log details
    """
    logger.debug(f"Closing terminal for terminal {terminal_id}")
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)
    try:
        if terminal_close is None:
            terminal_close = TerminalCloseRequest()
        close_log = await terminal_service.close_terminal_async(terminal_close.physical_amount)
        return_json = SchemasTransformerV1().transform_close_log(close_log).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Closed. terminal_id: {terminal_id}",
        data=return_json,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/terminals/{terminal_id}/cash-in",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[CashInOutResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def terminal_cash_in(
    terminal_id: str, cash_in: CashInOutRequest, tenant_id: str = Depends(get_tenant_id_with_security_wrapper)
):
    """
    Add cash to a terminal drawer

    This endpoint records cash being added to the terminal drawer
    and generates a receipt for the transaction.

    Args:
        terminal_id: ID of the terminal for cash deposit
        cash_in: Cash in request with amount and optional description
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing cash transaction details and receipt text
    """
    logger.debug(f"Cashing in terminal for terminal {terminal_id}, cash_in: {cash_in}")
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)
    try:
        if cash_in.description is None:
            cash_in.description = "Cash In (Default)"
        cash_in_result = await terminal_service.cash_in_out_async(cash_in.amount, cash_in.description)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Cashed In. terminal_id: {terminal_id}, amount: {cash_in.amount}, description: {cash_in.description}",
        data=CashInOutResponse(
            terminal_id=terminal_id,
            amount=cash_in_result.amount,
            description=cash_in_result.description,
            receipt_text=cash_in_result.receipt_text,
            journal_text=cash_in_result.journal_text,
        ),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/terminals/{terminal_id}/cash-out",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[CashInOutResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def terminal_cash_out(
    terminal_id: str, cash_out: CashInOutRequest, tenant_id: str = Depends(get_tenant_id_with_security_wrapper)
):
    """
    Remove cash from a terminal drawer

    This endpoint records cash being removed from the terminal drawer
    and generates a receipt for the transaction.

    Args:
        terminal_id: ID of the terminal for cash withdrawal
        cash_out: Cash out request with amount and optional description
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing cash transaction details and receipt text
    """
    logger.debug(f"Cashing out terminal for terminal {terminal_id}, cash_out: {cash_out}")
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)
    try:
        if cash_out.description is None:
            cash_out.description = "Cash Out (Default)"
        cash_out.amount = -cash_out.amount  # convert to negative amount
        cash_out_result = await terminal_service.cash_in_out_async(cash_out.amount, cash_out.description)
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Terminal Cashed Out. terminal_id: {terminal_id}, amount: {cash_out.amount}, description: {cash_out.description}",
        data=CashInOutResponse(
            terminal_id=terminal_id,
            amount=cash_out_result.amount,
            description=cash_out_result.description,
            receipt_text=cash_out_result.receipt_text,
            journal_text=cash_out_result.journal_text,
        ),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.post(
    "/terminals/{terminal_id}/delivery-status",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[DeliveryStatusUpdateResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def update_delivery_status(
    terminal_id: str,
    delivery_status: DeliveryStatusUpdateRequest,
    tenant_id: str = Depends(get_tenant_id_for_pubsub_notification),
):
    """
    Update the delivery status of a transaction

    This endpoint updates the delivery status of a transaction
    and generates a receipt for the transaction.

    Args:
        terminal_id: ID of the terminal for cash withdrawal
        delivery_status: Delivery status update request with event ID, service, and status
        tenant_id: Tenant ID extracted from authentication

    Returns:
        ApiResponse containing delivery status update details
    """
    logger.debug(f"Updating delivery status for terminal {terminal_id}, delivery_status: {delivery_status}")
    terminal_service = await get_terminal_service_async(tenant_id, terminal_id)
    try:
        await terminal_service.update_delivery_status_async(
            event_id=delivery_status.event_id,
            service_name=delivery_status.service,
            status=delivery_status.status,
            message=delivery_status.message,
        )
        response_data = DeliveryStatusUpdateResponse(
            event_id=delivery_status.event_id,
            service=delivery_status.service,
            status=delivery_status.status,
            success=True,
        ).model_dump()
    except Exception as e:
        raise e

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Delivery Status Updated. terminal_id: {terminal_id}, event_id: {delivery_status.event_id}, service: {delivery_status.service}, status: {delivery_status.status}",
        data=response_data,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
