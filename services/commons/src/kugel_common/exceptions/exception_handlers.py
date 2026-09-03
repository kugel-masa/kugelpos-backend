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
FastAPI exception handler registration module

This module provides standardized exception handling for FastAPI applications,
creating consistent error responses and user-friendly messages across all microservices.
"""
from fastapi import FastAPI, status, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from logging import getLogger
import inspect

from kugel_common.schemas.api_response import ApiResponse, UserError
from kugel_common.exceptions.base_exceptions import AppException
from kugel_common.exceptions.error_codes import ErrorCode, ErrorMessage
from kugel_common.utils.log_utils import mask_validation_error_details

logger = getLogger(__name__)


def build_unexpected_error_response(exc: Exception, operation: str = "exception_handler") -> ApiResponse:
    """
    Build the structured 500 for an exception nothing else handled.

    Shared so the response does not depend on which layer catches it: the
    handler above and UnhandledErrorMiddleware, which sits inside CORS so the
    payload actually reaches a browser (issue #202), must produce the same body.

    Args:
        exc: The exception that escaped
        operation: Name recorded on the response, for tracing which layer answered

    Returns:
        ApiResponse: The 500 payload
    """
    return ApiResponse(
        success=False,
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error",
        user_error=UserError(
            code=ErrorCode.UNEXPECTED_ERROR, message=ErrorMessage.get_message(ErrorCode.UNEXPECTED_ERROR)
        ),
        data=str(exc),
        operation=operation,
    )

def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers to the FastAPI application
    
    This function registers handlers for various exception types to ensure
    consistent error handling and response formatting across the application.
    
    Args:
        app: FastAPI application instance
    """
    # Handler for HTTPException
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # Set error code and message
        error_code = ErrorCode.GENERAL_ERROR
        user_message = ErrorMessage.get_message(error_code)
        
        # Change error code based on HTTP status code
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            error_code = ErrorCode.RESOURCE_NOT_FOUND
            user_message = ErrorMessage.get_message(error_code)
        elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = ErrorCode.AUTHENTICATION_ERROR
            user_message = ErrorMessage.get_message(error_code)
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            error_code = ErrorCode.AUTHORIZATION_ERROR
            user_message = ErrorMessage.get_message(error_code)

        error_response = ApiResponse(
            success=False, 
            code=exc.status_code, 
            message=exc.detail,
            user_error=UserError(
                code=error_code,
                message=user_message
            ),
            data=str(exc),
            operation=f"{inspect.currentframe().f_code.co_name}"
        )
        logger.error(f"HTTPException: {error_response}")
        return JSONResponse(
            status_code=error_response.code, content=error_response.model_dump()
        )

    # Handler for RequestValidationError
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Format validation errors appropriately
        errors = []
        for error in exc.errors():
            loc = " -> ".join([str(l) for l in error.get("loc", [])])
            msg = error.get("msg", "")
            errors.append(f"{loc}: {msg}")
        
        detail = "Invalid input data: " + "; ".join(errors)

        # Each error carries the raw `input` that failed, and this string goes
        # to the ERROR log AND back to the caller in `data`. At a secret
        # location that value IS the credential (issue #211).
        error_response = ApiResponse(
            success=False,
            code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=detail,
            user_error=UserError(
                code=ErrorCode.VALIDATION_ERROR,
                message=ErrorMessage.get_message(ErrorCode.VALIDATION_ERROR)
            ),
            data=str(mask_validation_error_details(exc.errors())),
            operation=f"{inspect.currentframe().f_code.co_name}"
        )
        logger.error(f"RequestValidationError: {error_response}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.model_dump(),
        )

    # Handler for ValidationError
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        error_response = ApiResponse(
            success=False,
            code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation error",
            user_error=UserError(
                code=ErrorCode.VALIDATION_ERROR,
                message=ErrorMessage.get_message(ErrorCode.VALIDATION_ERROR)
            ),
            # Same input echo as RequestValidationError above.
            data=str(mask_validation_error_details(exc.errors())),
            operation=f"{inspect.currentframe().f_code.co_name}"
        )
        logger.error(f"ValidationError: {error_response}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.model_dump(),
        )

    # Handler for AppException
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        # Determine status code based on error type
        status_code = exc.status_code if hasattr(exc, 'status_code') and exc.status_code else status.HTTP_500_INTERNAL_SERVER_ERROR
        
        # Get error code and user message
        user_error = None
        if hasattr(exc, 'get_user_error'):
            user_error_dict = exc.get_user_error()
            if user_error_dict:
                user_error = UserError(
                    code=user_error_dict.get('code'),
                    message=user_error_dict.get('message')
                )
        
        # Set default user error if not provided
        if not user_error:
            user_error = UserError(
                code=ErrorCode.SYSTEM_ERROR,
                message=ErrorMessage.get_message(ErrorCode.SYSTEM_ERROR)
            )
        
        error_response = ApiResponse(
            success=False,
            code=status_code,
            message=exc.message if hasattr(exc, 'message') else str(exc),
            user_error=user_error,
            data=None,
            operation=f"{inspect.currentframe().f_code.co_name}"
        )
        
        logger.error(f"AppException: {error_response}")
        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump()
        )

    # Handler for general Exception
    #
    # Starlette lifts a handler keyed on Exception (or 500) out of
    # ExceptionMiddleware and into ServerErrorMiddleware, which it builds around
    # the whole user middleware stack - so this response is emitted outside CORS
    # and a browser cannot read it (issue #202). UnhandledErrorMiddleware runs
    # inside CORS and normally answers first; this stays as the backstop for
    # anything raised outside it.
    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception):
        error_response = build_unexpected_error_response(exc, operation=f"{inspect.currentframe().f_code.co_name}")
        logger.error(f"Exception: {error_response}")
        return JSONResponse(
            status_code=error_response.code, content=error_response.model_dump()
        )