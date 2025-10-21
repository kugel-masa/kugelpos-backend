# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Request logging middleware for FastAPI applications

This module provides middleware to log all incoming API requests and their responses
for auditing and debugging purposes. It captures request details, response information,
user context, terminal information and authentication details, storing them both in
log files and in the database.
"""
from fastapi import Request, Response
from logging import getLogger
from pydantic import ValidationError
import json
import time
import asyncio

from kugel_common.database import database as db_helper
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_terminal_info, get_current_user
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.repositories.request_log_repository import RequestLogRepository
from kugel_common.models.documents.request_log_document import RequestLog
from kugel_common.config.settings import settings
from kugel_common.utils.misc import get_app_time_str

logger = getLogger(__name__)
logger_request = getLogger("requestLogger")

def log_requests(service_name: str = "NO_SERVICE_NAME"):
    """
    FastAPI middleware factory for request logging
    
    Creates a middleware that logs all requests and responses, including details
    about the client, request content, response content, and processing time.
    
    Args:
        service_name: Name of the service using this middleware (e.g., "terminal")
        
    Returns:
        An async middleware function to be used with FastAPI
    """
    async def middleware(request: Request, call_next):
        logger.debug(f"service_name: {service_name}")
        
        # Check if this is a WebSocket upgrade request
        if request.headers.get("upgrade", "").lower() == "websocket":
            logger.debug(f"WebSocket upgrade request detected, bypassing logging middleware")
            # Pass through WebSocket requests without logging
            return await call_next(request)
        
        accept_time = get_app_time_str()
        process_time_ms = 0
        response: Response = None
        try:
            start_time = time.time()
            request_info = await _make_request_info(request, accept_time)
            response = await call_next(request)
            process_time_ms = int((time.time() - start_time) * 1000)
        except Exception as e:
            raise
        finally:
            is_terminal_service = True if service_name == "terminal" else False
            terminal_info = await _get_terminal_info(request, is_terminal_service)
            user_dict = await _get_current_user(request)
            request_log = RequestLog(
                tenant_id=await _make_tenant_id(terminal_info, user_dict),
                client_info=await _make_client_info(request),
                request_info=request_info,
                response_info=await _make_response_info(response, process_time_ms),
                staff_info=await _make_staff_info(terminal_info),
                user_info=await _make_user_info(user_dict),
                terminal_info=await _make_terminal_info(terminal_info),
                service_name=service_name  # Add service name to the log
            )
            # Log to file synchronously (fast operation)
            await _output_request_log_to_file(request_log)

            # Log to database asynchronously (fire-and-forget)
            # This prevents database write latency from blocking API responses
            asyncio.create_task(_output_request_log_to_db_async(request_log))
        return response
    return middleware

async def _output_request_log_to_file(request_log: RequestLog):
    """
    Output request log information to the log file
    
    Args:
        request_log: RequestLog document containing all request/response information
    """
    logger_request.info(
        f"\n[Client:]\n"
        f"ip_address-> {request_log.client_info.ip_address}\n"
        f"[Request:]\n"
        f"method-> {request_log.request_info.method}\n"
        f"url-> {request_log.request_info.url}\n"
        f"body-> {request_log.request_info.body}\n"
        f"[Response:]\n"
        f"status_code-> {request_log.response_info.status_code}\n"
        f"process_time_ms-> {request_log.response_info.process_time_ms}\n"
        f"body-> {request_log.response_info.body}\n"
        f"[SignIn:]\n"
        f"staff_id-> {request_log.staff_info.id if request_log.staff_info else None}\n"
        f"staff_name-> {request_log.staff_info.name if request_log.staff_info else None}\n"
        f"[Terminal:]\n"
        f"tenant_id-> {request_log.terminal_info.tenant_id if request_log.terminal_info else None}\n"
        f"store_code-> {request_log.terminal_info.store_code if request_log.terminal_info else None}\n"
        f"terminal_no-> {request_log.terminal_info.terminal_no if request_log.terminal_info else None}\n"
        f"[Account:]\n"
        f"tenant_id-> {request_log.user_info.tenant_id if request_log.user_info else None}\n"
        f"user_name-> {request_log.user_info.username if request_log.user_info else None}\n"
        f"is_superuser-> {request_log.user_info.is_superuser if request_log.user_info else None}\n"
    )

async def _output_request_log_to_db_async(request_log: RequestLog):
    """
    Store the request log in the database asynchronously (fire-and-forget)

    This function is designed to run as a background task without blocking
    the HTTP response. Any exceptions are caught and logged to prevent
    unhandled task exceptions.

    Saves the request log to both the common database and tenant-specific database
    for audit trail and analytics purposes.

    Args:
        request_log: RequestLog document containing all request/response information
    """
    try:
        await _output_request_log_to_db(request_log)
    except Exception as e:
        # Log the error but don't propagate it to avoid unhandled task exceptions
        logger.error(
            f"Background task failed to write request log to database: "
            f"url={request_log.request_info.url}, "
            f"method={request_log.request_info.method}, "
            f"error={e}",
            exc_info=True
        )

async def _output_request_log_to_db(request_log: RequestLog):
    """
    Store the request log in the database

    Internal function that performs the actual database write operation.
    This is called by _output_request_log_to_db_async in a background task.

    Args:
        request_log: RequestLog document containing all request/response information
    """
    tenant_id = request_log.tenant_id

    db_list = []
    db_list.append(f"{settings.DB_NAME_PREFIX}_commons")
    if tenant_id:
        db_list.append(f"{settings.DB_NAME_PREFIX}_{tenant_id}")

    for db_name in db_list:
        logger.debug(f"db_name: {db_name}")
        db = await db_helper.get_db_async(db_name)
        request_log_repository = RequestLogRepository(db)
        try:
            await request_log_repository.create_request_log_async(request_log)
        except Exception as e:
            logger.error(f"Failed to output request log to db: request_log->{request_log},  error->{e}")

async def _create_async_iterator(body: bytes, chunk_size: int = 1024) -> bytes:
    """
    Create an async iterator for response body streaming
    
    This is used to read the response body without consuming it, allowing the
    original body to still be sent to the client.
    
    Args:
        body: Response body bytes
        chunk_size: Size of chunks to yield
        
    Returns:
        Async generator for body chunks
    """
    async def async_generator():
        for i in range(0, len(body), chunk_size):
            yield body[i:i + chunk_size]
    return async_generator()

async def _get_terminal_info(request: Request, is_terminal_service: bool = False) -> TerminalInfoDocument:
    """
    Extract terminal information from the request
    
    Attempts to retrieve terminal information based on API key and terminal ID
    in the request headers, query parameters, or path parameters.
    
    Args:
        request: FastAPI request object
        is_terminal_service: Whether the request is to the terminal service itself
        
    Returns:
        TerminalInfoDocument or None if terminal information cannot be retrieved
    """
    terminal_info = None
    terminal_id = None

    api_key = request.headers.get("X-API-Key")
    logger.debug(f"api_key: {api_key}")
    if api_key is not None:
        terminal_id = request.query_params.get("terminal_id")
        logger.debug(f"query_params terminal_id: {terminal_id}")
        if not terminal_id:
            terminal_id = request.path_params.get("terminal_id") 
            logger.debug(f"path_params terminal_id: {terminal_id}")

    if terminal_id and api_key:
        logger.debug(f"terminal_id: {terminal_id}, api_key")
        terminal_info = await get_terminal_info(terminal_id, api_key, is_terminal_service=is_terminal_service)

    logger.debug(f"terminal_info: {terminal_info}")
    return terminal_info

async def _get_current_user(request: Request) -> dict:
    """
    Extract user information from the request
    
    Attempts to retrieve user information based on JWT token in the request headers.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dictionary containing user information or None if not authenticated
    """
    user_dict = None
    token = request.headers.get("Authorization")
    if token:
        user_dict = await get_current_user(token.replace("Bearer ", ""))
    logger.debug(f"user_dict: {user_dict}")
    return user_dict

async def _get_response_body(response):
    """
    Extract response body without consuming it
    
    Reads the response body and creates a new iterator so the body can still
    be sent to the client.
    
    Args:
        response: FastAPI response object
        
    Returns:
        Response body as bytes or None if body cannot be read
    """
    response_body = b""
    try:
        async for chunk in response.body_iterator:
            response_body += chunk
        response.body_iterator = await _create_async_iterator(response_body)
        return response_body
    except Exception:
        return None

async def _parse_response_body(response_body: bytes):
    """
    Parse response body bytes as JSON
    
    Args:
        response_body: Response body as bytes
        
    Returns:
        Parsed JSON object or None if parsing fails
    """
    try:
        return json.loads(response_body.decode())
    except Exception:
        return None

async def _get_request_body(request: Request):
    """
    Extract and parse request body as JSON
    
    Args:
        request: FastAPI request object
        
    Returns:
        Parsed JSON object or None if parsing fails
    """
    try:
        body = await request.body()
        json_body = json.loads(body)
        logger.debug(f"request body: {json_body}")
        return json_body
    except Exception:
        logger.debug("Failed to get request body")
        return None

async def _make_tenant_id(terminal_info: TerminalInfoDocument, user_dict: dict) -> str:
    """
    Determine tenant ID from available context
    
    Attempts to extract tenant ID from terminal information or user information.
    
    Args:
        terminal_info: Terminal information if available
        user_dict: User information if available
        
    Returns:
        Tenant ID string or None if not available
    """
    tenant_id = None
    if terminal_info:
        tenant_id = terminal_info.tenant_id
        logger.debug(f"terminal_info: {terminal_info}, tenant_id: {tenant_id}")
    elif user_dict:
        tenant_id = user_dict.get("tenant_id")
        logger.debug(f"user_dict: {user_dict}, tenant_id: {tenant_id}")
    return tenant_id

async def _make_client_info(request: Request) -> RequestLog.ClientInfo:
    """
    Create client information object from request
    
    Args:
        request: FastAPI request object
        
    Returns:
        RequestLog.ClientInfo object with client IP address
    """
    return RequestLog.ClientInfo(ip_address=request.client.host)
    
async def _make_request_info(request: Request, accept_time: str) -> RequestLog.RequestInfo:
    """
    Create request information object from request
    
    Args:
        request: FastAPI request object
        accept_time: Timestamp when the request was accepted
        
    Returns:
        RequestLog.RequestInfo object with request details
    """
    return RequestLog.RequestInfo(
        method=request.method, 
        url=str(request.url), 
        body=await _get_request_body(request),
        accept_time=accept_time
    )

async def _make_response_info(response: Response, process_time_ms: int) -> RequestLog.ResponseInfo:
    """
    Create response information object from response
    
    Args:
        response: FastAPI response object
        process_time_ms: Request processing time in milliseconds
        
    Returns:
        RequestLog.ResponseInfo object with response details
    """
    if not response:
        return RequestLog.ResponseInfo(
            status_code=0,
            process_time_ms=0,
            body=None
        )

    response_body = await _get_response_body(response)
    json_body = await _parse_response_body(response_body)
    return RequestLog.ResponseInfo(
        status_code=response.status_code,
        process_time_ms=process_time_ms,
        body=json_body
    )

async def _make_staff_info(terminal_info: TerminalInfoDocument) -> RequestLog.StaffInfo:
    """
    Create staff information object from terminal information
    
    Args:
        terminal_info: Terminal information if available
        
    Returns:
        RequestLog.StaffInfo object with staff details
    """
    if terminal_info and terminal_info.staff:
        return RequestLog.StaffInfo(
            id=terminal_info.staff.id if terminal_info.staff.id else "",
            name=terminal_info.staff.name if terminal_info.staff.name else ""
        )
    else:
        return RequestLog.StaffInfo(id="", name="")

async def _make_user_info(user_dict: dict) -> RequestLog.UserInfo:
    """
    Create user information object from user dictionary
    
    Args:
        user_dict: User information dictionary from JWT token
        
    Returns:
        RequestLog.UserInfo object with user details
    """
    if user_dict:
        return RequestLog.UserInfo(
            tenant_id=user_dict.get("tenant_id"),
            username=user_dict.get("username"),
            is_superuser=user_dict.get("is_superuser")
        )
    else:
        return RequestLog.UserInfo(tenant_id="", username="", is_superuser=False)

async def _make_terminal_info(terminal_info: TerminalInfoDocument) -> RequestLog.TerminalInfo:
    """
    Create terminal information object from terminal document
    
    Args:
        terminal_info: Terminal information document if available
        
    Returns:
        RequestLog.TerminalInfo object with terminal details
    """
    if terminal_info:
        return RequestLog.TerminalInfo(
            tenant_id=terminal_info.tenant_id,
            store_code=terminal_info.store_code,
            terminal_no=terminal_info.terminal_no,
            business_date=terminal_info.business_date if terminal_info.business_date else "",
            open_counter=terminal_info.open_counter
        )
    else:
        return RequestLog.TerminalInfo(tenant_id="", store_code="", terminal_no=0, business_date="", open_counter=0)