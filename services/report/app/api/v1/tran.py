# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, Depends, Path, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from logging import getLogger
import json
import aiohttp
import inspect
from typing import Any, Dict, Optional

from kugel_common.database import database as db_helper
from kugel_common.exceptions import DuplicateKeyException
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import bind_body_identity, get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.status_codes import StatusCodes
from kugel_common.utils.log_utils import mask_loggable, mask_sensitive_data
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.utils.dapr_app_token import make_dapr_app_token_verifier
from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.utils.service_auth import create_service_token

from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.api.v1.schemas import TranResponse
from app.services.log_service import LogService
from app.config.settings import settings

from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.documents.open_close_log import OpenCloseLog
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.config.settings import settings
from app.exceptions import ExternalServiceException
from app.utils.state_store_manager import state_store_manager
from kugel_common.utils.log_utils import describe_exception
from kugel_common.dead_letter.document import describe_failure
from kugel_common.dead_letter.failure import DeadLetterUnrecordable, FailureDecision, record_failure
from kugel_common.dead_letter.outcome import HandlerOutcome, OutcomeKind
from kugel_common.dead_letter.unrecordable import notify_unrecordable

# Create a router instance for transaction-related endpoints
router = APIRouter()

# The pub/sub routes below carry no JWT and pick the tenant database from the
# event body, so they accept only what this service's own Dapr sidecar
# delivers (issue #134).
verify_dapr_app_token = make_dapr_app_token_verifier(lambda: settings.APP_API_TOKEN)

# Get a logger instance for this module
logger = getLogger(__name__)


# Legacy functions that use the StateStoreManager  # These are kept for backwards compatibility
async def save_state(state_id: str, state_data: dict) -> bool:
    """
    Save a state to the Dapr statestore for idempotent message processing.

    This function uses the StateStoreManager with circuit breaker pattern.

    Args:
        state_id: The unique ID for the state (typically the message ID)
        state_data: The data to store in the state

    Returns:
        bool: True if the state was saved successfully, False otherwise
    """
    success, _ = await state_store_manager.save_state(state_id, state_data)
    return success


async def get_state(state_id: str) -> dict:
    """
    Get a state from the Dapr statestore by its ID.

    This function uses the StateStoreManager with circuit breaker pattern.

    Args:
        state_id: The unique ID for the state (typically the message ID)

    Returns:
        dict: The state data if found, None if not found
    """
    state_data, _ = await state_store_manager.get_state(state_id)
    return state_data


async def get_log_service(tenant_id: str = Path(...)) -> LogService:
    """
    Create a LogService instance for a specific tenant.

    This dependency function is used for REST API endpoints that specify
    the tenant_id in the path.

    Args:
        tenant_id: The tenant identifier from the path parameter

    Returns:
        LogService: A configured LogService instance for the tenant
    """
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return LogService(
        tran_repository=TranlogRepository(db=db, tenant_id=tenant_id),
        cash_in_out_log_repository=CashInOutLogRepository(db=db, tenant_id=tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db=db, tenant_id=tenant_id),
    )


async def get_log_service_from_request(request: Request) -> LogService:
    """
    Extract tenant_id from a Dapr pub/sub request and create a LogService.

    This dependency function is used for Dapr pub/sub event handlers that
    receive tenant_id in the request body.

    Args:
        request: The FastAPI request containing the pub/sub message

    Returns:
        LogService: A configured LogService instance for the tenant

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
        # Without a tenant there is no database to record it in: announced
        # instead, and left to the redelivery and dlq-* (#230, R-6)
        await notify_unrecordable(
            service="report",
            topic=LOG_TYPE_TOPICS.get(request.url.path.rsplit("/", 1)[-1]),
            tenant_id=None,
            event_id=req_json.get("data", {}).get("event_id"),
            reason="tenant_id is missing",
        )
        raise HTTPException(status_code=400, detail="tenant_id is required in request data")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return LogService(
        tran_repository=TranlogRepository(db=db, tenant_id=tenant_id),
        cash_in_out_log_repository=CashInOutLogRepository(db=db, tenant_id=tenant_id),
        open_close_log_repository=OpenCloseLogRepository(db=db, tenant_id=tenant_id),
    )


# Which log each subscribed topic carries: (log type, model, LogService method)
TOPIC_HANDLERS = {
    "topic-tranlog": ("tranlog", BaseTransaction, "receive_tranlog_async"),
    "topic-cashlog": ("cashlog", CashInOutLog, "receive_cashlog_async"),
    "topic-opencloselog": ("opencloselog", OpenCloseLog, "receive_open_close_log_async"),
}
LOG_TYPE_TOPICS = {log_type: topic for topic, (log_type, _, _) in TOPIC_HANDLERS.items()}


async def process_log_event(message: dict, topic: str, log_service: Optional[LogService] = None) -> HandlerOutcome:
    """
    The handler core: process one CloudEvent and say what happened (#230, R-3).

    Shared by the subscription routes and the dead-letter replay. It neither
    records a failure nor tells the publisher; the caller does, each its own way.
    Idempotent by event_id (state store) and by the unique indexes.

    Args:
        message: The CloudEvent Dapr delivered (``data`` holds the log)
        topic: The topic it came from
        log_service: Given by a subscription route; built here for a replay

    Returns:
        HandlerOutcome: processed, already processed, dropped (with the failing
            fields) or failed (with the exception)
    """
    log_type, log_model, method_name = TOPIC_HANDLERS[topic]
    data = message.get("data") if isinstance(message, dict) else None
    data = data if isinstance(data, dict) else {}
    event_id = data.get("event_id")
    if not event_id:
        return HandlerOutcome.dropped("event_id is required")
    try:
        try:
            log_data = log_model(**data)
        except ValidationError as validation_error:
            # The same payload fails the same way on every delivery. Only the
            # names of the failing fields are kept: an open/close log carries a
            # whole terminal document, secrets included (issue #211).
            failed_fields = [".".join(str(part) for part in err.get("loc", ())) for err in validation_error.errors()]
            logger.error(f"{log_type} does not match the schema; dropped. event_id: {event_id}, fields: {failed_fields}")
            return HandlerOutcome.dropped(f"{log_type} does not match the schema: {failed_fields}")
        # Masked before serializing: `model_dump_json()` returns a string, and
        # masking a string does nothing. An open/close log carries a whole
        # terminal document (issue #211).
        log_info = json.dumps(mask_loggable(log_data), default=str, ensure_ascii=False)
        # Check if message already processed (idempotency check) using event_id
        result, error_msg = await state_store_manager.get_state(event_id)
        if error_msg:
            logger.error(
                f"Error checking for duplicates: {error_msg}. Proceeding with caution for event_id: {event_id}"
            )
            # We continue processing since we cannot be sure if this is a duplicate
            # This could potentially lead to duplicate processing but it's better than failing
        if result:
            logger.warning(f"Message already processed. event_id: {event_id}, {log_type}: {log_info}")
            return HandlerOutcome.already_processed()

        if log_service is None:
            log_service = await get_log_service(tenant_id=data.get("tenant_id"))
        logger.debug(f"Received {log_type} new message: {mask_sensitive_data(message)}")
        await getattr(log_service, method_name)(log_data)
        logger.info(f"{log_type} received successfully. event_id: {event_id}, {log_type}: {log_info}")

        # Saved before the notification: the log is stored, so from here on a
        # redelivery must stop at the state-store check.
        success, error_msg = await state_store_manager.save_state(event_id, {"event_id": event_id})
        if not success:
            logger.error(f"Failed to save state: {error_msg}. event_id: {event_id}, {log_type}: {log_info}")
            # We continue processing since the message has already been handled
            # This could potentially lead to duplicate processing on subsequent retries
        return HandlerOutcome.processed()

    except DuplicateKeyException as e:
        # The state-store idempotency check missed (state evicted, TTL
        # expired, or store unreachable) and the duplicate slipped through
        # to the DB layer, where the unique index rejected it. Treat this
        # as success — the data already exists, no further action needed.
        # Returning RETRY here would cause Dapr to redeliver indefinitely.
        logger.warning(
            f"Duplicate {log_type} caught at DB layer (idempotency state-store miss). event_id: {event_id}, error: {describe_exception(e)}"
        )
        # Best-effort: persist the state so subsequent retries short-circuit
        # at the state-store check.
        try:
            await state_store_manager.save_state(event_id, {"event_id": event_id})
        except Exception as save_exc:
            logger.warning(f"Failed to save state after duplicate detection: {save_exc}")
        return HandlerOutcome.already_processed()
    except Exception as e:
        logger.error(f"Error processing {log_type}. message: {mask_sensitive_data(message)}, Error: {describe_exception(e)}")
        return HandlerOutcome.failed(e)


async def notify_processed(message: dict, topic: str) -> None:
    """Tell the publisher a replayed event is stored here (best-effort, #230)."""
    log_type = TOPIC_HANDLERS[topic][0]
    data = message.get("data") or {}
    await _notify_received_best_effort(log_type, data, data.get("event_id"), message="")


async def _record_failure(message: dict, topic: str, outcome: HandlerOutcome) -> bool:
    """
    Count the failure as a dead-letter candidate (#230, R-4).

    Returns:
        bool: True to acknowledge (the event is recorded), False to ask for
            redelivery (still counting, or the record could not be written)
    """
    data = message.get("data") or {}
    tenant_id = data.get("tenant_id")
    try:
        db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
        decision = await record_failure(db=db, service="report", topic=topic, message=message, error=outcome.failure)
    except DeadLetterUnrecordable:
        return False
    except Exception as e:  # noqa: BLE001 - asking for redelivery is always safe
        await notify_unrecordable(
            service="report", topic=topic, tenant_id=tenant_id, event_id=data.get("event_id"), reason=type(e).__name__
        )
        return False
    return decision in (FailureDecision.GAVE_UP, FailureDecision.ALREADY_RECORDED)


async def handle_log(request: Request, topic: str, log_service: LogService):
    """
    The subscription route: run the core and answer Dapr (#230, R-3).

    Args:
        request: The FastAPI request containing the pub/sub message
        topic: The topic the route subscribes
        log_service: The tenant's LogService, from the dependency

    Returns:
        JSONResponse: The Dapr subscription status (SUCCESS / RETRY / DROP)
            with the HTTP status code Dapr acts on
    """
    log_type = TOPIC_HANDLERS[topic][0]
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
                    "operation": "handle_log",
                },
                # 200, not 400: Dapr retries any non-2xx response, so a 400
                # would redeliver a message that can never succeed. DROP is
                # honoured only on a 2xx.
                status_code=status.HTTP_200_OK,
            )
        outcome = await process_log_event(message, topic, log_service)
    except Exception as e:
        logger.error(f"Error reading {log_type}. event_id: {event_id}, Error: {describe_exception(e)}")
        outcome = HandlerOutcome.failed(e)

    data = message.get("data", {}) if isinstance(message, dict) else {}
    if outcome.kind is OutcomeKind.PROCESSED:
        # An empty message clears a failure an earlier attempt left with the publisher.
        await _notify_received_best_effort(log_type, data, event_id, message="")
        return JSONResponse(content={"status": "SUCCESS", "operation": "handle_log"}, status_code=status.HTTP_200_OK)
    if outcome.kind is OutcomeKind.ALREADY_PROCESSED:
        # The notification of the first delivery may have been lost.
        await _notify_received_best_effort(log_type, data, event_id)
        return JSONResponse(content={"status": "SUCCESS", "operation": "handle_log"}, status_code=status.HTTP_200_OK)
    if outcome.kind is OutcomeKind.DROPPED:
        return await _drop_invalid_log(log_type, data, event_id, outcome.reason)

    # Failed. Best-effort, like the other notifications: if it raised, the
    # answer below would never reach Dapr.
    try:
        await _notify_pubsub_status(
            log_type=log_type,
            data_dict=data,
            status="failed",
            # Sent to the publisher: described for a response, not a log (#318)
            message=f"Error processing {log_type}: {describe_failure(outcome.failure)}",
        )
    except Exception as notify_exc:
        logger.warning(f"Failed to notify the publisher of the failure. event_id={event_id}: {notify_exc}")
    if await _record_failure(message, topic, outcome):
        return JSONResponse(
            content={"status": "SUCCESS", "message": "recorded as a dead letter", "operation": "handle_log"},
            status_code=status.HTTP_200_OK,
        )
    return JSONResponse(
        content={"status": "RETRY", "message": describe_failure(outcome.failure), "operation": "handle_log"},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def _drop_invalid_log(log_type: str, data_dict: dict, event_id: str, reason: Optional[str]) -> JSONResponse:
    """
    Drop a log that does not match its schema, and tell the publisher.

    The same payload fails the same way on every delivery, so a RETRY would only
    spend the redelivery budget (issue #230). The reason names the failing
    fields only: an open/close log carries a whole terminal document, secrets
    included (issue #211).
    """
    try:
        await _notify_pubsub_status(log_type=log_type, data_dict=data_dict, status="failed", message=reason)
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
    # Implementation for notifying the Pub/Sub service
    # This is a placeholder and should be replaced with actual notification logic
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
            f"Failed to notify Pub/Sub service. log_type: {log_type}, status: {status}, message: {message}"
        )
        raise ExternalServiceException(message=message, logger=logger, original_exception=e) from e

    return None


async def _notify_pubsub_status_tranlog_async(tran_dict: dict, status: str, message: Optional[str] = None) -> None:
    """
    Notify the Pub/Sub service about the status of a transaction log.

    Args:
        tran_dict: The transaction data dictionary
        status: The status of the transaction (e.g., "received", "failed")
        message: Optional message to include in the notification
    """
    # Implementation for notifying the Pub/Sub service
    # This is a placeholder and should be replaced with actual notification logic
    event_id = tran_dict["event_id"]
    tenant_id = tran_dict["tenant_id"]
    store_code = tran_dict["store_code"]
    terminal_no_str = str(tran_dict["terminal_no"])
    transaction_no_str = str(tran_dict["transaction_no"])
    terminal_id = tenant_id + "-" + store_code + "-" + terminal_no_str

    # Try to use JWT token first
    try:
        service_name = "report"
        service_token = create_service_token(tenant_id=tenant_id, service_name=service_name)
        headers = {"Authorization": f"Bearer {service_token}"}
        logger.debug("Using JWT token for pub/sub notification")
    except Exception as e:
        # Fall back to API key for backward compatibility
        logger.warning(f"Failed to create service token: {e}. Falling back to API key.")
        api_key = settings.PUBSUB_NOTIFY_API_KEY
        if not api_key:
            logger.warning("API key is not set. Cannot notify Pub/Sub service.")
            api_key = ""
        headers = {"X-API-Key": api_key}

    payload = {"event_id": event_id, "service": service_name, "status": status}
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
    """
    Notify the Pub/Sub service about the status of a terminal log.

    Args:
        terminal_dict: The terminal data dictionary
        status: The status of the terminal log (e.g., "received", "failed")
        message: Optional message to include in the notification
    """
    # Implementation for notifying the Pub/Sub service
    # This is a placeholder and should be replaced with actual notification logic
    event_id = terminal_dict["event_id"]
    tenant_id = terminal_dict["tenant_id"]
    store_code = terminal_dict["store_code"]
    terminal_no_str = str(terminal_dict["terminal_no"])
    terminal_id = tenant_id + "-" + store_code + "-" + terminal_no_str
    # Try to use JWT token first
    try:
        service_name = "report"
        service_token = create_service_token(tenant_id=tenant_id, service_name=service_name)
        headers = {"Authorization": f"Bearer {service_token}"}
        logger.debug("Using JWT token for pub/sub notification")
    except Exception as e:
        # Fall back to API key for backward compatibility
        logger.warning(f"Failed to create service token: {e}. Falling back to API key.")
        api_key = settings.PUBSUB_NOTIFY_API_KEY
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


@router.post("/tranlog", dependencies=[Depends(verify_dapr_app_token)])
async def handle_tranlog(request: Request, log_service: LogService = Depends(get_log_service_from_request)):
    """
    Handle transaction logs received via Dapr pub/sub.

    This endpoint is called by Dapr when a transaction log message is published
    to the 'topic-tranlog' topic in the 'pubsub-tranlog-report' component.

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

    return await handle_log(request, "topic-tranlog", log_service)


@router.post("/cashlog", dependencies=[Depends(verify_dapr_app_token)])
async def handle_cashlog(request: Request, log_service: LogService = Depends(get_log_service_from_request)):
    """
    Handle cash in/out logs received via Dapr pub/sub.

    This endpoint is called by Dapr when a cash log message is published
    to the 'topic-cashlog' topic in the 'pubsub-cashlog-report' component.

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

    return await handle_log(request, "topic-cashlog", log_service)


@router.post("/opencloselog", dependencies=[Depends(verify_dapr_app_token)])
async def handle_opencloselog(request: Request, log_service: LogService = Depends(get_log_service_from_request)):
    """
    Handle terminal open/close logs received via Dapr pub/sub.

    This endpoint is called by Dapr when an open/close log message is published
    to the 'topic-opencloselog' topic in the 'pubsub-opencloselog-report' component.

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

    return await handle_log(request, "topic-opencloselog", log_service)


@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions",
    response_model=ApiResponse[TranResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_CONTENT: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_CONTENT),
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
    bind_body_identity(tran_data_obj, tenant_id, store_code, terminal_no, logger)
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
