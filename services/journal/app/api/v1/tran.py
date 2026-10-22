# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, Depends, Path, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from typing import Optional
from logging import getLogger
import json
import aiohttp
import inspect

from kugel_common.database import database as db_helper
from kugel_common.exceptions import DuplicateKeyException
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.status_codes import StatusCodes
from kugel_common.utils.log_utils import mask_loggable, mask_sensitive_data
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
        # The pub/sub envelope carries whatever the producer sent (issue #211).
        logger.error(f"tenant_id is required. request: {mask_sensitive_data(req_json)}")
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
        JSONResponse: The Dapr subscription status (SUCCESS / RETRY / DROP)
            with the HTTP status code Dapr acts on
    """
    # Bound before the try, so that the error branches can name them even when
    # the body cannot be read.
    message: dict = {}
    event_id = ""
    try:
        message = await request.json()

        # Check if this is a health check message and handle it early
        if message.get("data", {}).get("test") == "health-check":
            logger.debug(f"Health check message received for {log_type}, ignoring")
            return JSONResponse(
                content={"status": "SUCCESS", "operation": "health_check_drop"}, status_code=status.HTTP_200_OK
            )

        # Check if the message contains the required fields
        event_id = message.get("data", {}).get("event_id")
        if not event_id:
            logger.error(f"event_id is missing in the message data. message: {mask_sensitive_data(message)}")
            return JSONResponse(
                content={
                    "status": "DROP",
                    "message": "event_id is required",
                    "operation": f"{inspect.currentframe().f_code.co_name}",
                },
                # 200, not 400: Dapr retries any non-2xx response, so a 400
                # would redeliver a message that can never succeed. DROP is
                # honoured only on a 2xx.
                status_code=status.HTTP_200_OK,
            )

        try:
            log_data = log_model(**message["data"])
        except ValidationError as validation_error:
            return await _drop_invalid_log(log_type, message["data"], event_id, validation_error)
        # Masked before serializing: `model_dump_json()` returns a string, and
        # masking a string does nothing. An open/close log carries a whole
        # terminal document (issue #211).
        log_info = json.dumps(mask_loggable(log_data), default=str, ensure_ascii=False)

        # Check if the message has already been processed
        result = await get_state(event_id)
        if result:
            logger.warning(f"Message already processed. event_id: {event_id}, {log_type}: {log_info}")
            # The notification of the first delivery may have been lost.
            await _notify_received_best_effort(log_type, message["data"], event_id)
            return JSONResponse(
                content={"status": "SUCCESS", "operation": f"{inspect.currentframe().f_code.co_name}"},
                status_code=status.HTTP_200_OK,
            )

        # Process the log data
        logger.debug(f"Received {log_type} new message: {mask_sensitive_data(message)}")
        await receive_method(log_data)
        logger.info(f"{log_type} received successfully. event_id: {event_id}, {log_type}: {log_info}")

        # Saved before the notification: the log is stored, so from here on a
        # redelivery must stop at the state-store check.
        await save_state(event_id, {"event_id": event_id})

        # An empty message clears a failure an earlier attempt left with the publisher.
        await _notify_received_best_effort(log_type, message["data"], event_id, message="")

        logger.info(f"Processed event id: {event_id}")

        # Return a success response
        return JSONResponse(
            content={"status": "SUCCESS", "operation": f"{inspect.currentframe().f_code.co_name}"},
            status_code=status.HTTP_200_OK,
        )
    except DuplicateKeyException as e:
        # The state-store idempotency check missed (state evicted, TTL
        # expired, or store unreachable) and the duplicate slipped through
        # to the DB layer, where the unique index rejected it. Treat this
        # as success — the data already exists, no further action needed.
        # Returning RETRY here would cause Dapr to redeliver indefinitely.
        logger.warning(
            f"Duplicate {log_type} caught at DB layer (idempotency state-store miss). event_id: {event_id}, error: {e}"
        )
        # Best-effort: persist the state so subsequent retries short-circuit
        # at the state-store check.
        try:
            await save_state(event_id, {"event_id": event_id})
        except Exception as save_exc:
            logger.warning(f"Failed to save state after duplicate detection: {save_exc}")
        await _notify_received_best_effort(log_type, message["data"], event_id)
        return JSONResponse(
            content={
                "status": "SUCCESS",
                "message": "duplicate detected at DB layer; treated as already-processed",
                "operation": f"{inspect.currentframe().f_code.co_name}",
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        err_message = f"Failed to receive {log_type}. message: {mask_sensitive_data(message)}, Error: {e}"
        logger.error(err_message)
        # Best-effort, like the other notifications: if it raised, the answer
        # below would never reach Dapr.
        try:
            await _notify_pubsub_status(
                log_type=log_type, data_dict=message.get("data", {}), status="failed", message=err_message
            )
        except Exception as notify_exc:
            logger.warning(f"Failed to notify the publisher of the failure. event_id={event_id}: {notify_exc}")
        return JSONResponse(
            content={
                "status": "RETRY",
                "message": str(e),
                "operation": f"{inspect.currentframe().f_code.co_name}",
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


async def _drop_invalid_log(log_type: str, data_dict: dict, event_id: str, error: ValidationError) -> JSONResponse:
    """
    Drop a log that does not match its schema, and tell the publisher.

    The same payload fails the same way on every delivery, so a RETRY would only
    spend the redelivery budget before the message reached the dead-letter queue
    (issue #230). Only the names of the failing fields are reported: an open/close
    log carries a whole terminal document, secrets included (issue #211).
    """
    failed_fields = [".".join(str(part) for part in err.get("loc", ())) for err in error.errors()]
    logger.error(f"{log_type} does not match the schema; dropped. event_id: {event_id}, fields: {failed_fields}")
    try:
        await _notify_pubsub_status(
            log_type=log_type,
            data_dict=data_dict,
            status="failed",
            message=f"{log_type} does not match the schema: {failed_fields}",
        )
    except Exception as notify_exc:
        logger.warning(f"Failed to notify the publisher of the dropped {log_type}. event_id={event_id}: {notify_exc}")
    return JSONResponse(
        content={"status": "DROP", "message": f"{log_type} does not match the schema", "operation": "handle_log"},
        status_code=status.HTTP_200_OK,
    )


async def _notify_received_best_effort(
    log_type: str, data_dict: dict, event_id: str, message: Optional[str] = None
) -> None:
    """
    Tell the publisher this log is stored here, without ever raising (issue #230).

    The notification only moves the publisher's delivery status; the log is
    already saved. Letting its failure fail the event turned an unreachable cart
    or terminal into redeliveries of events that had been stored, which blocked
    the subscription for as long as the publisher was down.

    Called on every path that ends with the log stored: the first delivery, and a
    redelivery found already processed. Without the second, a notification lost on
    the first delivery was never sent again.

    Args:
        message: Sent only when given. A redelivery leaves it out, so the publisher
            keeps the message it already holds for this service.
    """
    try:
        await _notify_pubsub_status(log_type=log_type, data_dict=data_dict, status="received", message=message)
    except Exception as notify_exc:
        logger.warning(
            f"Failed to notify the publisher. event_id={event_id} log_type={log_type}: {notify_exc}. "
            "The log is stored; treating the message as consumed."
        )


async def _notify_pubsub_status(log_type: str, data_dict: dict, status: str, message: Optional[str] = None) -> None:
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


async def _notify_pubsub_status_tranlog_async(tran_dict: dict, status: str, message: Optional[str] = None) -> None:
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

    payload = {"event_id": event_id, "service": "journal", "status": status}
    # Left out when not given: the publisher then keeps the message it holds.
    if message is not None:
        payload["message"] = message
    async with get_service_client(service_name="cart") as client:
        params = {"terminal_id": terminal_id}
        endpoint = f"/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no_str}/transactions/{transaction_no_str}/delivery-status"
        await client.post(endpoint=endpoint, headers=headers, params=params, json=payload)
    logger.info(f"tranlog Pub/Sub service notified successfully. event_id: {event_id}, json: {payload}")
    return None


async def _notify_pubsub_status_terminallog_async(
    terminal_dict: dict, status: str, message: Optional[str] = None
) -> None:
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

    payload = {"event_id": event_id, "service": service_name, "status": status}
    # Left out when not given: the publisher then keeps the message it holds.
    if message is not None:
        payload["message"] = message
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
    # All BaseTransaction fields are Optional (so the model can be reused for
    # partial updates / pub-sub envelopes), but this endpoint requires the
    # nested sales / staff / user blocks to build a JournalDocument
    # downstream. Raise 400 here instead of letting AttributeError bubble
    # up as a 500.
    for field in ("sales", "staff", "user"):
        if getattr(tran_data_obj, field) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"missing required field: {field}",
            )
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
