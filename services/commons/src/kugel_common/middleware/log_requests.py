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

Logged bodies are bounded (issue #155): fields named in
``REQUEST_LOG_STRIP_FIELDS`` - the signed cart snapshot by default, which
carries a whole cart document on every mutating call - are replaced by a
metadata marker, and a body still above ``REQUEST_LOG_MAX_BODY_BYTES`` is
stored as a truncation marker instead.
"""

from fastapi import Request, Response
from logging import getLogger
from typing import Optional
from pydantic import ValidationError
import json
import time

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import (
    get_terminal_info,
    get_current_user,
    verify_terminal_token,
    terminal_claims_to_terminal_info,
)
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.request_log_document import RequestLog
from kugel_common.config.settings import settings
from kugel_common.utils.misc import get_app_time_str
from kugel_common.utils.log_utils import mask_api_key, parse_log_strip_fields, sanitize_log_body
from kugel_common.middleware.request_log_buffer import get_request_log_buffer

logger = getLogger(__name__)
logger_request = getLogger("requestLogger")

# Scope key a service uses to hand this middleware the marks of a client-carried
# snapshot (issue #165); see _make_snapshot_info.
SNAPSHOT_SCOPE_KEY = "request_log_snapshot"

# Parsed form of settings.REQUEST_LOG_STRIP_FIELDS, recomputed when the setting
# changes so tests (and a live reconfiguration) are not stuck with the first
# value seen.
_strip_fields_spec: str | None = None
_strip_fields: tuple = ()


def _log_strip_fields() -> tuple:
    """
    Field names the logged request/response bodies are stripped of (issue #155).

    Returns:
        Tuple of field names parsed from settings.REQUEST_LOG_STRIP_FIELDS
    """
    global _strip_fields_spec, _strip_fields
    spec = getattr(settings, "REQUEST_LOG_STRIP_FIELDS", "") or ""
    if spec != _strip_fields_spec:
        _strip_fields_spec = spec
        _strip_fields = parse_log_strip_fields(spec)
    return _strip_fields


def _log_max_body_bytes() -> int:
    """
    Size ceiling for a logged request/response body; 0 disables the backstop.

    Returns:
        Maximum body size in bytes from settings.REQUEST_LOG_MAX_BODY_BYTES
    """
    return getattr(settings, "REQUEST_LOG_MAX_BODY_BYTES", 0) or 0


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
        request_info = None
        try:
            start_time = time.time()
            try:
                request_info = await _make_request_info(request, accept_time)
            except Exception as e:
                # Reading and sanitizing the body is for the log, so a failure
                # here is the log's problem and not the request's. Left unguarded
                # it raised before the route was ever called, and the caller was
                # answered with the logger's error (issue #161). The record is
                # rebuilt from what is known in _record_request.
                logger.error(
                    f"Could not capture the request for logging: {request.method} {request.url}: {e}",
                    exc_info=True,
                )
                request_info = None
            response = await call_next(request)
            process_time_ms = int((time.time() - start_time) * 1000)
        finally:
            # Nothing in here may change what the caller gets back. This block
            # runs while the route's own exception is still in flight, so an
            # exception raised here REPLACES it - the 401 the route raised
            # arrives as a 500, and the request log is dropped along the way
            # (issue #161). Its job is observability; it does not get a vote on
            # the response.
            try:
                await _record_request(request, service_name, accept_time, request_info, response, process_time_ms)
            except Exception as e:
                logger.error(
                    f"Request log could not be written for {request.method} {request.url}: {e}",
                    exc_info=True,
                )
        return response

    return middleware


async def _record_request(
    request: Request,
    service_name: str,
    accept_time: str,
    request_info: Optional[RequestLog.RequestInfo],
    response: Optional[Response],
    process_time_ms: int,
) -> None:
    """
    Assemble the request log and hand it to the file logger and the buffer.

    Called from the middleware's `finally` and wrapped there, so nothing it does
    can reach the caller. Kept as its own function so that boundary is a single
    place rather than a block someone can extend past.
    """
    is_terminal_service = service_name == "terminal"
    terminal_info = await _get_terminal_info(request, is_terminal_service)
    user_dict = await _get_current_user(request)

    if request_info is None:
        # _make_request_info did not get to return - reading or sanitizing the
        # body failed. Record the request anyway: what it was is still worth
        # having, and it is the failures that most need a trail.
        request_info = RequestLog.RequestInfo(
            method=request.method,
            url=str(request.url),
            # Marked rather than left as None, which a reader cannot tell apart
            # from a request that legitimately had no body.
            body={"_capture_failed": True},
            accept_time=accept_time,
        )

    try:
        request_log = RequestLog(
            tenant_id=await _make_tenant_id(terminal_info, user_dict),
            client_info=await _make_client_info(request),
            request_info=request_info,
            response_info=await _make_response_info(response, process_time_ms),
            staff_info=await _make_staff_info(terminal_info),
            user_info=await _make_user_info(user_dict),
            terminal_info=await _make_terminal_info(terminal_info),
            snapshot_info=_make_snapshot_info(request),
            service_name=service_name,
        )
    except Exception as e:
        # Any one of those can raise - a response body that will not re-read, a
        # claim of the wrong shape, a field a future change makes required - and
        # each of them would otherwise cost the entire record. Guarded once, at
        # the assembly, rather than six times inside it: the point is that the
        # request is recorded, not that every part of it was resolvable.
        logger.error(
            f"Request log could not be assembled in full for {request.method} {request.url}: {e}",
            exc_info=True,
        )
        request_log = RequestLog(
            tenant_id=None,
            client_info=RequestLog.ClientInfo(ip_address=""),
            request_info=request_info,
            response_info=RequestLog.ResponseInfo(
                status_code=getattr(response, "status_code", 0) or 0,
                process_time_ms=process_time_ms,
                body={"_capture_failed": True},
            ),
            service_name=service_name,
        )
    # Log to file synchronously (fast operation)
    await _output_request_log_to_file(request_log)

    # Buffer for batched database write (insert_many)
    buffer = get_request_log_buffer()
    await buffer.add(request_log)


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
            yield body[i : i + chunk_size]

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
    # The token first, which is the order the routes themselves resolve in
    # (`get_terminal_info_with_jwt_or_apikey`: "Priority 1: Try terminal JWT").
    # A request carrying both credentials executes as the token's terminal, so
    # attributing it to the API key's would name a terminal that did not make it
    # - and the API-key branch costs an HTTP call to the terminal service that a
    # token-authenticated request has no reason to pay.
    terminal_info = _terminal_info_from_terminal_token(request)
    if terminal_info is not None:
        logger.debug(f"terminal_info from token: {terminal_info.terminal_id}")
        return terminal_info

    terminal_id = None
    api_key = request.headers.get("X-API-Key")
    logger.debug(f"api_key: {mask_api_key(api_key)}")
    if api_key is not None:
        terminal_id = request.query_params.get("terminal_id")
        logger.debug(f"query_params terminal_id: {terminal_id}")
        if not terminal_id:
            terminal_id = request.path_params.get("terminal_id")
            logger.debug(f"path_params terminal_id: {terminal_id}")

    if terminal_id and api_key:
        logger.debug(f"terminal_id: {terminal_id}, api_key: {mask_api_key(api_key)}")
        try:
            terminal_info = await get_terminal_info(terminal_id, api_key, is_terminal_service=is_terminal_service)
        except Exception:
            # `security.get_terminal_info` maps ANY HttpClientError onto
            # HTTPException(401), so a terminal service that is merely
            # unreachable arrives here as an authentication failure - and
            # unguarded it escapes the middleware's `finally`, turning a request
            # the route had already answered into a 500 and dropping its log
            # (issue #161). The sibling helper below has carried this guard, and
            # the reason for it, since long before.
            #
            # Degraded here rather than at the outer guard on purpose: returning
            # None still records the request with whatever else is known, where
            # letting it out records nothing at all.
            logger.warning(f"Could not resolve the terminal for the request log: terminal_id={terminal_id}")
            terminal_info = None

    logger.debug(f"terminal_info: {terminal_info}")
    return terminal_info


def _terminal_info_from_terminal_token(request: Request) -> TerminalInfoDocument:
    """
    Terminal attribution for a JWT-authenticated request (issue #181).

    The API-key path above resolves the terminal from `X-API-Key` plus a
    `terminal_id` parameter. A terminal-JWT request carries neither - that is the
    point of the migration - so before this the request log recorded an empty
    terminal: no store, no terminal number, no business date, no open counter,
    and no staff, for the credential the fleet is moving to. The identity
    survived only as text inside `user_info.username`.

    Read from the claims rather than looked up: the token already carries every
    field the log wants, and this runs on the response path of every request.

    Returns None - never raises. This is called from the logging middleware's
    `finally` block, so an exception here would replace whatever the route was
    returning, including the 401 that a bad token is supposed to produce (the
    defect class of issue #161).
    """
    header = request.headers.get("Authorization")
    if not header:
        return None
    try:
        claims = verify_terminal_token(header.replace("Bearer ", "").strip())
        return terminal_claims_to_terminal_info(claims)
    except Exception:
        # Not a terminal token, or not a valid one. Either way the log simply
        # has no terminal to name; the route's own dependency decides the
        # request's fate.
        logger.debug("No terminal identity in the request token")
        return None


async def _get_current_user(request: Request) -> dict:
    """
    Extract user information from the request

    Attempts to retrieve user information based on JWT token in the request headers.
    This helper is used from the request-logging middleware's `finally` block —
    if `get_current_user` raises (invalid / expired / forged JWT) we MUST NOT
    let that escape, otherwise it suppresses the original auth failure being
    propagated by the route handler and FastAPI ends up returning 500
    instead of the proper 401 to the client.

    Args:
        request: FastAPI request object

    Returns:
        Dictionary containing user information or None if not authenticated
    """
    user_dict = None
    token = request.headers.get("Authorization")
    if token:
        try:
            user_dict = await get_current_user(token.replace("Bearer ", ""))
        except Exception:
            # Bad / expired / missing-claim token — log it and leave user_dict=None.
            # The actual auth rejection is handled by the route's dependency;
            # this helper is only for enriching the request log.
            logger.debug("Could not extract user from request header (bad/expired token)")
            user_dict = None
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


async def _get_request_body(request: Request) -> tuple:
    """
    Extract and parse request body as JSON

    Args:
        request: FastAPI request object

    Returns:
        Tuple of (parsed JSON object or None if parsing fails, raw body bytes)
        - the raw bytes let the log sanitizer skip work whose outcome they
        already determine (see sanitize_log_body)
    """
    body = b""
    try:
        body = await request.body()
        json_body = json.loads(body)
        logger.debug(f"request body: {json_body}")
        return json_body, body
    except Exception:
        logger.debug("Failed to get request body")
        return None, body


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
    # `request.client` is not always populated - an ASGI scope can arrive
    # without one - and an AttributeError here costs the whole record.
    return RequestLog.ClientInfo(ip_address=request.client.host if request.client else "")


async def _make_request_info(request: Request, accept_time: str) -> RequestLog.RequestInfo:
    """
    Create request information object from request

    The body is sanitized before it is stored: bulky fields (the signed cart
    snapshot by default) are replaced by a metadata marker and anything still
    over the size budget is truncated - see issue #155.

    Args:
        request: FastAPI request object
        accept_time: Timestamp when the request was accepted

    Returns:
        RequestLog.RequestInfo object with request details
    """
    body, raw = await _get_request_body(request)
    return RequestLog.RequestInfo(
        method=request.method,
        url=str(request.url),
        body=sanitize_log_body(
            body,
            strip_fields=_log_strip_fields(),
            max_bytes=_log_max_body_bytes(),
            raw=raw,
        ),
        accept_time=accept_time,
    )


async def _make_response_info(response: Response, process_time_ms: int) -> RequestLog.ResponseInfo:
    """
    Create response information object from response

    The body is sanitized the same way the request body is (issue #155).

    Args:
        response: FastAPI response object
        process_time_ms: Request processing time in milliseconds

    Returns:
        RequestLog.ResponseInfo object with response details
    """
    if not response:
        return RequestLog.ResponseInfo(status_code=0, process_time_ms=0, body=None)

    response_body = await _get_response_body(response)
    json_body = await _parse_response_body(response_body)
    return RequestLog.ResponseInfo(
        status_code=response.status_code,
        process_time_ms=process_time_ms,
        body=sanitize_log_body(
            json_body,
            strip_fields=_log_strip_fields(),
            max_bytes=_log_max_body_bytes(),
            raw=response_body,
        ),
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
            name=terminal_info.staff.name if terminal_info.staff.name else "",
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
            is_superuser=user_dict.get("is_superuser"),
        )
    else:
        return RequestLog.UserInfo(tenant_id="", username="", is_superuser=False)


def _make_snapshot_info(request: Request) -> RequestLog.SnapshotInfo:
    """
    Snapshot marks a service left on the request scope (issue #165).

    Middleware that peels a client-carried envelope runs outside this one, so
    the envelope is gone by the time the request is logged; a service that wants
    something from it recorded puts the scalars under
    `scope["request_log_snapshot"]`. Kept to a fixed set of scalars: the body
    itself is stripped precisely to keep whole cart documents out of the log
    (issue #155).

    Args:
        request: FastAPI request object

    Returns:
        RequestLog.SnapshotInfo, or None when the request carried no snapshot
    """
    marks = request.scope.get(SNAPSHOT_SCOPE_KEY)
    if not isinstance(marks, dict):
        return None
    try:
        return RequestLog.SnapshotInfo(
            cart_id=marks.get("cart_id"),
            revision=marks.get("revision"),
            schema_version=marks.get("schema_version"),
            kid=marks.get("kid"),
        )
    except Exception:
        # Never let an odd value cost the whole request log.
        logger.debug("Could not record snapshot marks from the request scope")
        return None


async def _make_terminal_info(terminal_info: TerminalInfoDocument) -> RequestLog.TerminalInfo:
    """
    Create terminal information object from terminal document

    Args:
        terminal_info: Terminal information document if available

    Returns:
        RequestLog.TerminalInfo object with terminal details
    """
    if terminal_info:
        # Every field defaulted, not just business_date. A terminal token is
        # issued before the terminal is ever opened, and the claims for state it
        # does not have yet are simply absent - so `open_counter` arrives as
        # None, RequestLog.TerminalInfo declares it `int`, and the
        # ValidationError escapes the middleware's `finally` block: the route's
        # 200 becomes a 500 and the log is dropped (the defect class of issue
        # #161, reachable here since issue #181 started filling this in from a
        # token).
        return RequestLog.TerminalInfo(
            tenant_id=terminal_info.tenant_id or "",
            store_code=terminal_info.store_code or "",
            terminal_no=terminal_info.terminal_no or 0,
            business_date=terminal_info.business_date or "",
            open_counter=terminal_info.open_counter or 0,
        )
    else:
        return RequestLog.TerminalInfo(tenant_id="", store_code="", terminal_no=0, business_date="", open_counter=0)
