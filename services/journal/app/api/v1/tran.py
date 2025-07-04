# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, Depends, Path, Request, HTTPException
from pydantic import BaseModel
from logging import getLogger
import aiohttp
import inspect

from kugel_common.database import database as db_helper
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.status_codes import StatusCodes
from app.config.settings import settings
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.utils.service_auth import create_service_token

from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.api.v1.schemas import TranResponse
from app.services.log_service import LogService
from app.services.journal_service import JournalService
from app.models.repositories.journal_repository import JournalRepository
from app.utils.state_store_manager import state_store_manager

from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.documents.open_close_log import OpenCloseLog
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.config.settings import settings
from asyncio import Lock
from app.exceptions import (
    ExternalServiceException,
)

# Create a router instance for transaction-related endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


async def save_state(state_id: str, state_data: dict) -> bool:
    """
    Save a state to the Dapr statestore for idempotent message processing.

    This function is used to track processed message IDs to prevent duplicate processing.
    The state is stored in the Dapr statestore with the message ID as the key.

    Args:
        state_id: The unique ID for the state (typically the message ID)
        state_data: The data to store in the state

    Returns:
        bool: True if the state was saved successfully, False otherwise
    """
    success, error = await state_store_manager.save_state(state_id, state_data)
    if not success:
        logger.error(f"Failed to save state. state_id: {state_id}, error: {error}")
        return False
    return True


async def get_state(state_id: str) -> dict:
    """
    Get a state from the Dapr statestore by its ID.

    This function is used to check if a message has been processed before,
    which is essential for the idempotent handling of pub/sub messages.

    Args:
        state_id: The unique ID for the state (typically the message ID)

    Returns:
        dict: The state data if found, None if not found
    """
    state_data, error = await state_store_manager.get_state(state_id)
    if error:
        logger.error(f"Error retrieving state. state_id: {state_id}, error: {error}")
        return None
    return state_data


async def get_log_service(tenant_id: str = Path(...)) -> LogService:
    """
    Dependency function to create and inject a LogService instance.

    This function is used for REST API endpoints that specify
    the tenant_id in the path.

    Args:
        tenant_id: The tenant identifier from the path parameter

    Returns:
        LogService: Configured instance with all required repositories and services
    """
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return LogService(
        tran_repository=TranlogRepository(db=db, tenant_id=tenant_id),
        cash_in_out_log_repository=CashInOutLogRepository(db=db, tenant_id=tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db=db, tenant_id=tenant_id),
        journal_service=JournalService(JournalRepository(db=db, tenant_id=tenant_id)),
    )


async def get_log_service_from_request(request: Request) -> LogService:
    """
    Extract tenant_id from a Dapr pub/sub request and create a LogService.

    This function is used for Dapr pub/sub event handlers that receive
    tenant_id in the request body. It creates all necessary repositories
    and services for processing the various types of logs.

    Args:
        request: The FastAPI request containing the pub/sub message

    Returns:
        LogService: Configured instance with all required repositories and services

    Raises:
        HTTPException: 400 if tenant_id is missing from request data
    """
    req_json = await request.json()

    # Check if this is a health check message
    if req_json.get("data", {}).get("test") == "health-check":
        logger.debug("Health check message detected, returning None for LogService")
        return None

    tenant_id = req_json.get("data", {}).get("tenant_id", "")
    if not tenant_id:
        logger.error(f"tenant_id is required. request: {req_json}")
        raise HTTPException(status_code=400, detail="tenant_id is required in request data")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return LogService(
        tran_repository=TranlogRepository(db=db, tenant_id=tenant_id),
        cash_in_out_log_repository=CashInOutLogRepository(db=db, tenant_id=tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db=db, tenant_id=tenant_id),
        journal_service=JournalService(JournalRepository(db=db, tenant_id=tenant_id)),
    )


async def handle_log(request: Request, log_type: str, log_model: BaseModel, receive_method):
    """
    Handle incoming logs from Dapr pub/sub and process them.
    This function is responsible for receiving logs, checking for duplicates,
    and notifying the Pub/Sub service about the status of the logs.
    Args:
        request: The FastAPI request containing the pub/sub message
        log_type: The type of log (e.g., "tranlog", "cashlog", "opencloselog")
        log_model: The Pydantic model for the log data
        receive_method: The method to call for processing the log data
    Returns:
       None
    """
    try:
        message = await request.json()

        # Check if this is a health check message and handle it early
        if message.get("data", {}).get("test") == "health-check":
            logger.debug(f"Health check message received for {log_type}, ignoring")
            return {"status": "SUCCESS", "operation": "health_check_drop"}, status.HTTP_200_OK

        # Check if the message contains the required fields
        event_id = message.get("data", {}).get("event_id")
        if not event_id:
            logger.error(f"event_id is missing in the message data. message: {message}")
            return {
                "status": "DROP",
                "message": "event_id is required",
                "operation": f"{inspect.currentframe().f_code.co_name}",
            }, status.HTTP_400_BAD_REQUEST

        log_data = log_model(**message["data"])
        log_info = log_data.model_dump_json()

        # Check if the event_id is present in the message
        if not event_id:
            logger.error(f"event_id is required in message data. message: {message}")
            return {
                "status": "DROP",
                "message": "event_id is required",
                "operation": f"{inspect.currentframe().f_code.co_name}",
            }, status.HTTP_400_BAD_REQUEST

        # Check if the message has already been processed
        result = await get_state(event_id)
        if result:
            logger.warning(f"Message already processed. event_id: {event_id}, {log_type}: {log_info}")
            return {"status": "SUCCESS", "operation": f"{inspect.currentframe().f_code.co_name}"}, status.HTTP_200_OK

        # Process the log data
        logger.debug(f"Received {log_type} new message: {message}")
        await receive_method(log_data)
        logger.info(f"{log_type} received successfully. event_id: {event_id}, {log_type}: {log_info}")

        # Notify the Pub/Sub service about the status of the log
        await _notify_pubsub_status(log_type=log_type, data_dict=message["data"], status="received")

        # Save the state to prevent duplicate processing
        await save_state(event_id, {"event_id": event_id})

        logger.info(f"Processed event id: {event_id}")

        # Return a success response
        return {"status": "SUCCESS", "operation": f"{inspect.currentframe().f_code.co_name}"}, status.HTTP_200_OK
    except Exception as e:
        err_message = f"Failed to receive {log_type}. message: {message}, Error: {e}"
        logger.error(err_message)
        await _notify_pubsub_status(log_type=log_type, data_dict=message["data"], status="failed", message=err_message)
        return {
            "status": "RETRY",
            "message": str(e),
            "operation": f"{inspect.currentframe().f_code.co_name}",
        }, status.HTTP_500_INTERNAL_SERVER_ERROR


async def _notify_pubsub_status(log_type: str, data_dict: dict, status: str, message: str = "") -> None:
    """
    Notify the Pub/Sub service about the status of a transaction log.
    Args:
        log_type: The type of log (e.g., "tranlog", "cashlog", "opencloselog")
        data_dict: The transaction data dictionary
        status: The status of the transaction (e.g., "received", "failed")
        message: Optional message to include in the notification
    """
    try:
        if log_type == "tranlog":
            await _notify_pubsub_status_tranlog_async(data_dict, status, message)
        elif log_type == "cashlog":
            await _notify_pubsub_status_terminallog_async(data_dict, status, message)
        elif log_type == "opencloselog":
            await _notify_pubsub_status_terminallog_async(data_dict, status, message)
        else:
            logger.warning(f"Unknown log type: {log_type}. Cannot notify Pub/Sub service.")
    except Exception as e:
        message = (
            f"Failed to notify Pub/Sub service. log_type: {log_type}, status: {status}, message: {message}, Error: {e}"
        )
        raise ExternalServiceException(message=message, logger=logger, original_exception=e) from e
    return None


async def _notify_pubsub_status_tranlog_async(tran_dict: dict, status: str, message: str = "") -> None:
    event_id = tran_dict["event_id"]
    tenant_id = tran_dict["tenant_id"]
    store_code = tran_dict["store_code"]
    terminal_no_str = str(tran_dict["terminal_no"])
    transaction_no_str = str(tran_dict["transaction_no"])
    terminal_id = tenant_id + "-" + store_code + "-" + terminal_no_str

    # Try to use JWT token first
    try:
        service_token = create_service_token(tenant_id=tenant_id, service_name="journal")
        headers = {"Authorization": f"Bearer {service_token}"}
        logger.debug("Using JWT token for pub/sub notification")
    except Exception as e:
        # Fall back to API key for backward compatibility
        logger.warning(f"Failed to create service token: {e}. Falling back to API key.")
        api_key = settings.PUBSUB_NOTIFY_API_KEY if hasattr(settings, "PUBSUB_NOTIFY_API_KEY") else ""
        if not api_key:
            logger.warning("API key is not set. Cannot notify Pub/Sub service.")
            api_key = ""
        headers = {"X-API-Key": api_key}

    payload = {"event_id": event_id, "service": "journal", "status": status, "message": message}
    async with get_service_client(service_name="cart") as client:
        params = {"terminal_id": terminal_id}
        endpoint = f"/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no_str}/transactions/{transaction_no_str}/delivery-status"
        await client.post(endpoint=endpoint, headers=headers, params=params, json=payload)
    logger.info(f"tranlog Pub/Sub service notified successfully. event_id: {event_id}, json: {payload}")
    return None


async def _notify_pubsub_status_terminallog_async(terminal_dict: dict, status: str, message: str = "") -> None:
    event_id = terminal_dict["event_id"]
    tenant_id = terminal_dict["tenant_id"]
    store_code = terminal_dict["store_code"]
    terminal_no_str = str(terminal_dict["terminal_no"])
    terminal_id = tenant_id + "-" + store_code + "-" + terminal_no_str

    # Try to use JWT token first
    try:
        service_name = "journal"
        service_token = create_service_token(tenant_id=tenant_id, service_name=service_name)
        headers = {"Authorization": f"Bearer {service_token}"}
        logger.debug("Using JWT token for pub/sub notification")
    except Exception as e:
        # Fall back to API key for backward compatibility
        logger.warning(f"Failed to create service token: {e}. Falling back to API key.")
        api_key = settings.PUBSUB_NOTIFY_API_KEY if hasattr(settings, "PUBSUB_NOTIFY_API_KEY") else ""
        if not api_key:
            logger.warning("API key is not set. Cannot notify Pub/Sub service.")
            api_key = ""
        headers = {"X-API-Key": api_key}

    payload = {"event_id": event_id, "service": service_name, "status": status, "message": message}
    async with get_service_client(service_name="terminal") as client:
        params = {"terminal_id": terminal_id}
        endpoint = f"/terminals/{terminal_id}/delivery-status"
        await client.post(endpoint=endpoint, headers=headers, params=params, json=payload)
    logger.info(f"terminallog Pub/Sub service notified successfully. event_id: {event_id}, json: {payload}")
    return None


@router.post("/tranlog")
async def handle_tranlog(request: Request, log_service: LogService = Depends(get_log_service_from_request)):
    """
    Handle transaction logs received via Dapr pub/sub.

    This endpoint is called by Dapr when a transaction log message is published
    to the 'topic-tranlog' topic. It processes the transaction data and generates
    the corresponding journal entries.

    The journal service uses this data to create human-readable receipt text
    and maintains a searchable record of all transactions.

    Args:
        request: The FastAPI request containing the pub/sub message
        log_service: The LogService instance from the dependency

    Returns:
        dict: A status response with HTTP status code
    """
    # Handle health check messages without LogService
    if log_service is None:
        message = await request.json()
        if message.get("data", {}).get("test") == "health-check":
            logger.debug("Health check message received for tranlog, returning success")
            return {"status": "SUCCESS", "operation": "health_check_drop"}
        raise HTTPException(status_code=500, detail="Log service not initialized")

    return await handle_log(request, "tranlog", BaseTransaction, log_service.receive_tranlog_async)


@router.post("/cashlog")
async def handle_cashlog(request: Request, log_service: LogService = Depends(get_log_service_from_request)):
    """
    Handle cash in/out logs received via Dapr pub/sub.

    This endpoint is called by Dapr when a cash log message is published
    to the 'topic-cashlog' topic. It processes the cash movement data and
    generates the corresponding journal entries.

    Cash logs represent non-sales cash movements like float, paid-ins, and payouts.

    Args:
        request: The FastAPI request containing the pub/sub message
        log_service: The LogService instance from the dependency

    Returns:
        dict: A status response with HTTP status code
    """
    # Handle health check messages without LogService
    if log_service is None:
        message = await request.json()
        if message.get("data", {}).get("test") == "health-check":
            logger.debug("Health check message received for cashlog, returning success")
            return {"status": "SUCCESS", "operation": "health_check_drop"}
        raise HTTPException(status_code=500, detail="Log service not initialized")

    return await handle_log(request, "cashlog", CashInOutLog, log_service.receive_cashlog_async)


@router.post("/opencloselog")
async def handle_opencloselog(request: Request, log_service: LogService = Depends(get_log_service_from_request)):
    """
    Handle terminal open/close logs received via Dapr pub/sub.

    This endpoint is called by Dapr when an open/close log message is published
    to the 'topic-opencloselog' topic. It processes the terminal session data
    and generates the corresponding journal entries.

    These logs mark the beginning and end of a terminal's business session
    and include details like starting cash, ending cash, and reconciliation.

    Args:
        request: The FastAPI request containing the pub/sub message
        log_service: The LogService instance from the dependency

    Returns:
        dict: A status response with HTTP status code
    """
    # Handle health check messages without LogService
    if log_service is None:
        message = await request.json()
        if message.get("data", {}).get("test") == "health-check":
            logger.debug("Health check message received for opencloselog, returning success")
            return {"status": "SUCCESS", "operation": "health_check_drop"}
        raise HTTPException(status_code=500, detail="Log service not initialized")

    return await handle_log(request, "opencloselog", OpenCloseLog, log_service.receive_open_close_log_async)


@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions",
    response_model=ApiResponse[TranResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def receive_transactions(
    tran_data: dict,
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminal_no: str = Path(...),
    tran_service: LogService = Depends(get_log_service),
):
    """
    Direct API endpoint for receiving transaction data.

    This endpoint can be used as an alternative to the Dapr pub/sub mechanism
    when direct REST API calls are preferred. It requires authentication via
    token or API key.

    The function validates the tenant ID from the security credentials,
    processes the transaction data, and generates the corresponding journal entries.

    Args:
        tran_data: Transaction data in JSON format
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID extracted from security credentials
        store_code: The store code from the path
        terminal_no: The terminal number from the path
        tran_service: The LogService instance from the dependency

    Returns:
        ApiResponse[TranResponse]: A standard API response with transaction confirmation
    """
    logger.info(
        f"Received transaction request. tenant_id: {tenant_id}, store_code: {store_code}, terminal_no: {terminal_no}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    tran_data_obj = BaseTransaction(**tran_data)
    await tran_service.receive_tranlog_async(tran_data_obj)
    tran_res = SchemasTransformerV1().transform_tran_response(tran_data_obj)

    response = ApiResponse(
        success=True,
        code=status.HTTP_201_CREATED,
        message=f"Transaction received successfully. tenant_id: {tenant_id}, store_code: {store_code}, terminal_no: {terminal_no}, transaction_no: {tran_res.transaction_no}",
        data=tran_res.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response
