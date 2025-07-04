# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Body, Depends, Query, Request, status, Path, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import inspect
import asyncio
import json

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.schemas.base_schemas import Metadata
from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.status_codes import StatusCodes
from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.utils.service_auth import create_service_token
from app.api.v1.schemas import (
    StockUpdateRequest,
    SetMinimumQuantityRequest,
    CreateSnapshotRequest,
    SetReorderParametersRequest,
    StockResponse,
    StockUpdateResponse,
    StockSnapshotResponse,
)
from app.api.v1.schemas_transformer import StockTransformer, StockUpdateTransformer, SnapshotTransformer
from app.models.schemas.snapshot_schedule import SnapshotScheduleCreate, SnapshotScheduleResponse
from app.dependencies.get_stock_service import get_stock_service, get_snapshot_service
from app.services.stock_service import StockService
from app.services.snapshot_service import SnapshotService
from app.exceptions.stock_exceptions import StockNotFoundError, SnapshotNotFoundError, ExternalServiceError
from app.utils.state_store_manager import state_store_manager

# setup logger
logger = getLogger(__name__)

# Create API router
router = APIRouter(tags=["stock"])


# Stock endpoints
@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/stock",
    response_model=ApiResponse[PaginatedResult[StockResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get stock list for a store",
    description="Get all stock items for a store with pagination",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_store_stocks(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    stock_service: StockService = Depends(get_stock_service),
):
    """Get all stocks for a store"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    # Calculate skip from page
    skip = (page - 1) * limit

    stocks, total_count = await stock_service.get_store_stocks_async(tenant_id, store_code, skip, limit)

    # Transform documents to response models
    items = [StockTransformer.to_response(stock) for stock in stocks]

    # Create paginated result
    paginated_result = PaginatedResult(
        data=items, metadata=Metadata(total=total_count, page=page, limit=limit, sort=None, filter=None)
    )

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Stock list retrieved successfully",
        data=paginated_result,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/stock/low",
    response_model=ApiResponse[PaginatedResult[StockResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get low stock items",
    description="Get items with stock below minimum quantity",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_low_stocks(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    stock_service: StockService = Depends(get_stock_service),
):
    """Get items with low stock"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    stocks, total_count = await stock_service.get_low_stocks_async(tenant_id, store_code)

    # Transform documents to response models
    items = [StockTransformer.to_response(stock) for stock in stocks]

    # Create paginated result (no pagination for low stocks, returns all)
    paginated_result = PaginatedResult(
        data=items, metadata=Metadata(total=total_count, page=1, limit=total_count, sort=None, filter=None)
    )

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Low stock items retrieved successfully",
        data=paginated_result,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/stock/snapshot",
    response_model=ApiResponse[StockSnapshotResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create stock snapshot",
    description="Create a snapshot of current stock levels",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def create_snapshot(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    snapshot_request: CreateSnapshotRequest = Body(CreateSnapshotRequest(), by_alias=True),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
):
    """Create a stock snapshot"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    # Use terminal_id as created_by if not specified
    created_by = snapshot_request.created_by
    if created_by == "system" and terminal_id:
        created_by = terminal_id

    snapshot = await snapshot_service.create_snapshot_async(tenant_id, store_code, created_by)

    return ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message="Snapshot created successfully",
        data=SnapshotTransformer.to_response(snapshot),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/stock/snapshots",
    response_model=ApiResponse[PaginatedResult[StockSnapshotResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get stock snapshots by date range",
    description="Get list of stock snapshots filtered by generate_date_time range",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_snapshots_by_date_range(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
):
    """Get stock snapshots filtered by generate_date_time range"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    # Calculate skip from page
    skip = (page - 1) * limit

    snapshots, total_count = await snapshot_service.get_snapshots_by_generate_date_time_async(
        tenant_id, store_code, start_date, end_date, skip, limit
    )

    # Transform documents to response models
    items = [SnapshotTransformer.to_response(snapshot) for snapshot in snapshots]

    # Build filter metadata
    filter_metadata = {}
    if start_date:
        filter_metadata["start_date"] = start_date
    if end_date:
        filter_metadata["end_date"] = end_date

    # Create paginated result
    paginated_result = PaginatedResult(
        data=items,
        metadata=Metadata(
            total=total_count,
            page=page,
            limit=limit,
            sort="generate_date_time:-1",
            filter=filter_metadata if filter_metadata else None,
        ),
    )

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Snapshots retrieved successfully",
        data=paginated_result,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}",
    response_model=ApiResponse[StockSnapshotResponse],
    status_code=status.HTTP_200_OK,
    summary="Get stock snapshot by ID",
    description="Get a specific stock snapshot by its ID",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"description": "Snapshot not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_snapshot_by_id(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    snapshot_id: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),
):
    """Get a specific snapshot"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    snapshot = await snapshot_service.get_snapshot_by_id_async(snapshot_id)

    if snapshot is None:
        raise SnapshotNotFoundError(message=f"Snapshot {snapshot_id} not found", logger=logger)

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Snapshot retrieved successfully",
        data=SnapshotTransformer.to_response(snapshot),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/stock/reorder-alerts",
    response_model=ApiResponse[PaginatedResult[StockResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get reorder alert items",
    description="Get items with stock at or below reorder point",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_reorder_alerts(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    stock_service: StockService = Depends(get_stock_service),
):
    """Get items that need reordering"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    stocks, total_count = await stock_service.get_reorder_alerts_async(tenant_id, store_code)

    # Transform documents to response models
    items = [StockTransformer.to_response(stock) for stock in stocks]

    # Create paginated result (no pagination for reorder alerts, returns all)
    paginated_result = PaginatedResult(
        data=items, metadata=Metadata(total=total_count, page=1, limit=total_count, sort=None, filter=None)
    )

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Reorder alert items retrieved successfully",
        data=paginated_result,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}",
    response_model=ApiResponse[StockResponse],
    status_code=status.HTTP_200_OK,
    summary="Get stock for an item",
    description="Get current stock information for a specific item",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"description": "Stock not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_stock(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    item_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    stock_service: StockService = Depends(get_stock_service),
):
    """Get current stock for an item"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    stock = await stock_service.get_stock_async(tenant_id, store_code, item_code)

    if stock is None:
        raise StockNotFoundError(message=f"Stock not found for item {item_code} in store {store_code}", logger=logger)

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Stock retrieved successfully",
        data=StockTransformer.to_response(stock),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.put(
    "/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update",
    response_model=ApiResponse[StockUpdateResponse],
    status_code=status.HTTP_200_OK,
    summary="Update stock quantity",
    description="Update stock quantity for an item and record the update",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def update_stock(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    item_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    update_request: StockUpdateRequest = Body(..., by_alias=True),
    stock_service: StockService = Depends(get_stock_service),
):
    """Update stock quantity"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    # Extract operator ID from terminal_id if available
    operator_id = update_request.operator_id
    if not operator_id and terminal_id:
        operator_id = terminal_id

    update_record = await stock_service.update_stock_async(
        tenant_id=tenant_id,
        store_code=store_code,
        item_code=item_code,
        quantity_change=update_request.quantity_change,
        update_type=update_request.update_type,
        reference_id=update_request.reference_id,
        operator_id=operator_id,
        note=update_request.note,
    )

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Stock updated successfully",
        data=StockUpdateTransformer.to_response(update_record),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/history",
    response_model=ApiResponse[PaginatedResult[StockUpdateResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get stock update history",
    description="Get stock update history for an item",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_stock_history(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    item_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    stock_service: StockService = Depends(get_stock_service),
):
    """Get stock update history for an item"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    # Calculate skip from page
    skip = (page - 1) * limit

    updates, total_count = await stock_service.get_stock_history_async(tenant_id, store_code, item_code, skip, limit)

    # Transform documents to response models
    items = [StockUpdateTransformer.to_response(update) for update in updates]

    # Create paginated result
    paginated_result = PaginatedResult(
        data=items, metadata=Metadata(total=total_count, page=page, limit=limit, sort=None, filter=None)
    )

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Stock history retrieved successfully",
        data=paginated_result,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.put(
    "/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/minimum",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    summary="Set minimum stock quantity",
    description="Set minimum stock quantity for alerts",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"description": "Stock not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def set_minimum_quantity(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    item_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    minimum_request: SetMinimumQuantityRequest = Body(..., by_alias=True),
    stock_service: StockService = Depends(get_stock_service),
):
    """Set minimum quantity for an item"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    success = await stock_service.set_minimum_quantity_async(
        tenant_id, store_code, item_code, minimum_request.minimum_quantity
    )

    if not success:
        raise StockNotFoundError(message=f"Failed to set minimum quantity for item {item_code}", logger=logger)

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Minimum quantity set successfully",
        data=None,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


@router.put(
    "/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/reorder",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    summary="Set reorder parameters",
    description="Set reorder point and quantity for an item",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"description": "Stock not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def set_reorder_parameters(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    item_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    reorder_request: SetReorderParametersRequest = Body(..., by_alias=True),
    stock_service: StockService = Depends(get_stock_service),
):
    """Set reorder point and quantity for an item"""

    # Verify tenant ID matches security context
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    success = await stock_service.set_reorder_parameters_async(
        tenant_id, store_code, item_code, reorder_request.reorder_point, reorder_request.reorder_quantity
    )

    if not success:
        raise StockNotFoundError(message=f"Failed to set reorder parameters for item {item_code}", logger=logger)

    return ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message="Reorder parameters set successfully",
        data=None,
        operation=f"{inspect.currentframe().f_code.co_name}",
    )


# Snapshot endpoints  # Helper functions for pubsub notifications
async def _notify_pubsub_status_tranlog_async(tran_dict: dict, status: str, message: str = "") -> None:
    """
    Notify the cart service about the status of a transaction log.

    Args:
        tran_dict: The transaction data dictionary
        status: The status of the transaction (e.g., "received", "failed")
        message: Optional message to include in the notification
    """
    event_id = tran_dict.get("event_id")
    tenant_id = tran_dict.get("tenant_id")
    store_code = tran_dict.get("store_code")
    terminal_no_str = str(tran_dict.get("terminal_no"))
    transaction_no_str = str(tran_dict.get("transaction_no"))

    # Try to use JWT token first
    try:
        service_name = "stock"
        service_token = create_service_token(tenant_id=tenant_id, service_name=service_name)
        headers = {"Authorization": f"Bearer {service_token}"}
        logger.debug("Using JWT token for pub/sub notification")
    except Exception as e:
        # Fall back to API key for backward compatibility
        logger.warning(f"Failed to create service token: {e}. Falling back to API key.")
        from app.config.settings import settings

        api_key = getattr(settings, "PUBSUB_NOTIFY_API_KEY", None)
        if not api_key:
            logger.warning("API key is not set. Cannot notify Pub/Sub service.")
            api_key = ""
        headers = {"X-API-Key": api_key}

    payload = {"event_id": event_id, "service": service_name, "status": status, "message": message}

    try:
        async with get_service_client(service_name="cart") as client:
            terminal_id = f"{tenant_id}-{store_code}-{terminal_no_str}"
            params = {"terminal_id": terminal_id}
            endpoint = f"/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no_str}/transactions/{transaction_no_str}/delivery-status"
            await client.post(endpoint=endpoint, headers=headers, params=params, json=payload)

        logger.info(f"tranlog Pub/Sub service notified successfully. event_id: {event_id}, json: {payload}")
    except Exception as e:
        logger.error(f"Failed to notify cart service: {e}")
        raise ExternalServiceError(
            message=f"Failed to notify cart service: {str(e)}", logger=logger, original_exception=e
        )


async def _notify_pubsub_status(log_type: str, log_dict: dict, status: str, message: str = "") -> None:
    """
    Route notification to appropriate handler based on log type.

    Args:
        log_type: Type of log (tranlog, cashlog, opencloselog)
        log_dict: The log data dictionary
        status: The status of the log processing
        message: Optional message to include in the notification
    """
    if log_type == "tranlog":
        await _notify_pubsub_status_tranlog_async(log_dict, status, message)
    # Add other log types here if needed in the future


# PubSub handlers
@router.post(
    "/tranlog",
    summary="Handle transaction log from cart service",
    description="Process transaction log to update stock quantities",
)
async def handle_transaction_log(request: Request):
    """Handle transaction log from pubsub"""
    try:
        # Get message data
        message = await request.json()
        data = message.get("data", {})

        # Check if this is a health check message
        if data.get("test") == "health-check":
            logger.debug("Received health check message, ignoring")
            return JSONResponse(content={"status": "SUCCESS"}, status_code=status.HTTP_200_OK)

        logger.info(f"Received transaction log: {data}")

        # Extract event_id for idempotency
        event_id = data.get("event_id")
        if not event_id:
            logger.error("Missing event_id in transaction log")
            return JSONResponse(
                content={"status": "DROP", "message": "Missing event_id"}, status_code=status.HTTP_400_BAD_REQUEST
            )

        # Extract tenant_id to create service instance
        tenant_id = data.get("tenant_id")
        if not tenant_id:
            logger.error(f"Missing tenant_id in transaction log: {data}")
            return JSONResponse(
                content={"status": "DROP", "message": "Missing tenant_id"}, status_code=status.HTTP_400_BAD_REQUEST
            )

        # Create stock service instance
        from kugel_common.database import database as db_helper
        from app.config.settings import settings
        from app.dependencies.get_alert_service import get_alert_service

        db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
        alert_service = get_alert_service()
        stock_service = StockService(db, alert_service)

        # Check for duplicate processing
        existing_state, error_msg = await state_store_manager.get_state(event_id)
        if existing_state:
            logger.info(f"Duplicate transaction log received: {event_id}")
            # Still notify cart service about duplicate
            asyncio.create_task(_notify_pubsub_status("tranlog", data, "received", "Duplicate event"))
            return JSONResponse(
                content={"status": "SUCCESS"}, status_code=status.HTTP_200_OK  # Already processed, no need to retry
            )

        # Process the transaction directly without validation
        # The cart service sends the full transaction data, not the simplified TransactionLog schema
        await stock_service.process_transaction_async(data)

        # Save state for idempotency
        state_saved, save_error = await state_store_manager.save_state(event_id, {"event_id": event_id})

        if not state_saved:
            logger.warning(f"Failed to save state for event {event_id}: {save_error}")

        # Notify cart service of successful processing
        asyncio.create_task(_notify_pubsub_status("tranlog", data, "received"))

        return JSONResponse(content={"status": "SUCCESS"}, status_code=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error processing transaction log: {e}")
        # Notify cart service of failure
        try:
            asyncio.create_task(_notify_pubsub_status("tranlog", data, "failed", str(e)))
        except:
            logger.error("Failed to send failure notification")

        return JSONResponse(
            content={"status": "RETRY", "message": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Snapshot Schedule Management endpoints
@router.get(
    "/tenants/{tenant_id}/stock/snapshot-schedule",
    response_model=ApiResponse[SnapshotScheduleResponse],
    status_code=status.HTTP_200_OK,
    summary="Get snapshot schedule configuration",
    description="Get the snapshot schedule configuration for a tenant",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Schedule not found"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_snapshot_schedule(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """Get snapshot schedule configuration for a tenant."""
    from app.config.settings import settings
    from kugel_common.database import database as db_helper
    from app.repositories.snapshot_schedule_repository import SnapshotScheduleRepository
    from app.models.documents.snapshot_schedule_document import SnapshotScheduleDocument

    # Verify tenant ID
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    try:
        # Get database and repository
        db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
        repo = SnapshotScheduleRepository(db)

        # Get schedule
        schedule = await repo.get_by_tenant_id(tenant_id)

        if not schedule:
            # Return default schedule if none exists
            now = datetime.now(timezone.utc)
            schedule = SnapshotScheduleDocument(
                tenant_id=tenant_id,
                enabled=settings.DEFAULT_SNAPSHOT_ENABLED,
                schedule_interval=settings.DEFAULT_SNAPSHOT_INTERVAL,
                schedule_hour=settings.DEFAULT_SNAPSHOT_HOUR,
                schedule_minute=settings.DEFAULT_SNAPSHOT_MINUTE,
                retention_days=settings.DEFAULT_SNAPSHOT_RETENTION_DAYS,
                target_stores=["all"],
                created_at=now,
                updated_at=now,
                created_by="system",
                updated_by="system",
            )

        return ApiResponse[SnapshotScheduleResponse](
            code=status.HTTP_200_OK,
            message="Snapshot schedule retrieved successfully",
            success=True,
            data=SnapshotScheduleResponse(**schedule.model_dump(by_alias=False)),
        )

    except Exception as e:
        logger.error(f"Error getting snapshot schedule: {e}")
        raise


@router.put(
    "/tenants/{tenant_id}/stock/snapshot-schedule",
    response_model=ApiResponse[SnapshotScheduleResponse],
    status_code=status.HTTP_200_OK,
    summary="Update snapshot schedule configuration",
    description="Update the snapshot schedule configuration for a tenant",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def update_snapshot_schedule(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    schedule_data: SnapshotScheduleCreate = Body(...),
):
    """Update snapshot schedule configuration for a tenant."""
    from app.config.settings import settings
    from kugel_common.database import database as db_helper
    from app.repositories.snapshot_schedule_repository import SnapshotScheduleRepository
    from app.models.documents.snapshot_schedule_document import SnapshotScheduleDocument
    from app.dependencies.get_scheduler import get_scheduler

    # Verify tenant ID
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    # Validate retention days
    if schedule_data.retention_days < settings.MIN_SNAPSHOT_RETENTION_DAYS:
        raise ValueError(f"retention_days must be at least {settings.MIN_SNAPSHOT_RETENTION_DAYS}")
    if schedule_data.retention_days > settings.MAX_SNAPSHOT_RETENTION_DAYS:
        raise ValueError(f"retention_days must not exceed {settings.MAX_SNAPSHOT_RETENTION_DAYS}")

    # Validate schedule parameters based on interval
    if schedule_data.schedule_interval == "weekly" and schedule_data.schedule_day_of_week is None:
        raise ValueError("schedule_day_of_week is required for weekly schedules")
    if schedule_data.schedule_interval == "monthly" and schedule_data.schedule_day_of_month is None:
        raise ValueError("schedule_day_of_month is required for monthly schedules")

    try:
        # Get database and repository
        db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
        repo = SnapshotScheduleRepository(db)

        # Create or update schedule document
        schedule = SnapshotScheduleDocument(tenant_id=tenant_id, **schedule_data.model_dump())

        # Get user info from token/api key
        user_info = getattr(request.state, "user", None)
        if user_info:
            schedule.updated_by = user_info.get("username", "system")

        # Save to database
        saved_schedule = await repo.upsert_schedule(schedule)

        # Update scheduler if it exists
        scheduler = get_scheduler()
        if scheduler:
            await scheduler.update_tenant_schedule(saved_schedule)

        return ApiResponse[SnapshotScheduleResponse](
            code=status.HTTP_200_OK,
            message="Snapshot schedule updated successfully",
            success=True,
            data=SnapshotScheduleResponse(**saved_schedule.model_dump(by_alias=False)),
        )

    except Exception as e:
        logger.error(f"Error updating snapshot schedule: {e}")
        raise


@router.delete(
    "/tenants/{tenant_id}/stock/snapshot-schedule",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete snapshot schedule configuration",
    description="Delete the snapshot schedule configuration for a tenant (reverts to defaults)",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def delete_snapshot_schedule(
    request: Request,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
):
    """Delete snapshot schedule configuration for a tenant."""
    from app.config.settings import settings
    from kugel_common.database import database as db_helper
    from app.repositories.snapshot_schedule_repository import SnapshotScheduleRepository
    from app.dependencies.get_scheduler import get_scheduler

    # Verify tenant ID
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)

    try:
        # Get database and repository
        db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
        repo = SnapshotScheduleRepository(db)

        # Get existing schedule
        schedule = await repo.get_by_tenant_id(tenant_id)

        if schedule:
            # Delete from database
            await repo.delete_async({"tenant_id": tenant_id})

            # Remove from scheduler if it exists
            scheduler = get_scheduler()
            if scheduler:
                await scheduler.remove_tenant_schedule(tenant_id)

        return ApiResponse[dict](
            code=status.HTTP_200_OK,
            message="Snapshot schedule deleted successfully",
            success=True,
            data={"deleted": True},
        )

    except Exception as e:
        logger.error(f"Error deleting snapshot schedule: {e}")
        raise


@router.websocket("/ws/{tenant_id}/{store_code}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str, store_code: str):
    """
    WebSocket endpoint for real-time stock alerts.

    Args:
        websocket: The WebSocket connection
        tenant_id: Tenant identifier
        store_code: Store code
        token: JWT token for authentication
    """
    logger.info(f"WebSocket connection attempt: tenant={tenant_id}, store={store_code}")

    try:
        # Import dependencies
        from app.dependencies.get_alert_service import get_alert_service
        from app.services.stock_service import StockService
        from kugel_common.database import database as db_helper
        from app.config.settings import settings
        from kugel_common.security import verify_token
    except Exception as e:
        logger.error(f"Import error in WebSocket: {e}", exc_info=True)
        raise

    # Extract token from query parameters
    from urllib.parse import parse_qs, urlparse

    query_params = parse_qs(urlparse(str(websocket.url)).query)
    token = query_params.get("token", [None])[0]

    logger.info(f"Token extracted: {token is not None}")

    # Verify token before accepting connection
    if not token:
        await websocket.accept()
        await websocket.close(code=1008, reason="No token provided")
        return

    try:
        # Verify the token
        payload = verify_token(token)
        token_tenant_id = payload.get("tenant_id")

        # Verify tenant_id matches
        if token_tenant_id != tenant_id:
            await websocket.accept()
            await websocket.close(code=1008, reason="Tenant ID mismatch")
            return

    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        await websocket.accept()
        await websocket.close(code=1008, reason="Authentication failed")
        return

    # Get services
    alert_service = get_alert_service()
    if not alert_service:
        logger.error("Alert service not available")
        await websocket.accept()
        await websocket.close(code=1011, reason="Alert service not available")
        return

    # Get connection manager from alert service
    connection_manager = alert_service.connection_manager

    # Accept the connection
    await connection_manager.connect(websocket, tenant_id, store_code)

    try:
        # Send initial connection confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection",
                    "status": "connected",
                    "tenant_id": tenant_id,
                    "store_code": store_code,
                    "message": "Connected to stock alert service",
                }
            )
        )

        # Get and send current alerts
        db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
        stock_service = StockService(db, alert_service)

        # Get items below reorder point
        reorder_alerts, _ = await stock_service.get_reorder_alerts_async(tenant_id, store_code)
        for stock in reorder_alerts:
            await alert_service.send_alert(
                {
                    "type": "stock_alert",
                    "alert_type": "reorder_point",
                    "tenant_id": stock.tenant_id,
                    "store_code": stock.store_code,
                    "item_code": stock.item_code,
                    "current_quantity": stock.current_quantity,
                    "reorder_point": stock.reorder_point,
                    "reorder_quantity": stock.reorder_quantity,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        # Get items below minimum stock
        low_stocks, _ = await stock_service.get_low_stocks_async(tenant_id, store_code)
        for stock in low_stocks:
            await alert_service.send_alert(
                {
                    "type": "stock_alert",
                    "alert_type": "minimum_stock",
                    "tenant_id": stock.tenant_id,
                    "store_code": stock.store_code,
                    "item_code": stock.item_code,
                    "current_quantity": stock.current_quantity,
                    "minimum_quantity": stock.minimum_quantity,
                    "reorder_quantity": stock.reorder_quantity,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        # Keep connection alive and handle messages
        while True:
            # Wait for messages from client (ping/pong)
            data = await websocket.receive_text()

            # Handle ping messages
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket, tenant_id, store_code)
        logger.info(f"WebSocket disconnected for tenant {tenant_id}, store {store_code}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await connection_manager.disconnect(websocket, tenant_id, store_code)
