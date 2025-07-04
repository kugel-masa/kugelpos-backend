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
Exception handler utilities for API responses.

This module provides standardized exception handling for FastAPI applications,
creating consistent API error responses across all microservices.
"""
from typing import Any, Dict
from fastapi import Request, status
from fastapi.responses import JSONResponse

from kugel_common.schemas.api_response import ApiResponse, UserError
from kugel_common.exceptions.base_exceptions import AppException
from kugel_common.exceptions.error_codes import ErrorCode, ErrorMessage


def create_error_response(status_code: int, detail: str, request: Request = None, exc: Exception = None) -> ApiResponse:
    """
    Create an error response object.
    
    Generates a standardized error response that includes both internal technical
    details and user-friendly error messages.
    
    Args:
        status_code: HTTP status code
        detail: Detailed error message
        request: Request information
        exc: Exception object that triggered the error
        
    Returns:
        ApiResponse: Error response object
    """
    # Default user error information
    user_error = None
    internal_message = detail

    # For AppException, get user error information
    if isinstance(exc, AppException):
        if hasattr(exc, 'get_user_error'):
            user_error_dict = exc.get_user_error()
            if user_error_dict:
                user_error = UserError(
                    code=user_error_dict.get('code'),
                    message=user_error_dict.get('message')
                )
        # Internal message used for logging
        internal_message = str(exc)
    
    # Set default error information if user error is not provided
    if not user_error:
        # Set default error information based on status code
        error_code = get_error_code_from_status(status_code)
        user_error = UserError(
            code=error_code,
            message=ErrorMessage.get_message(error_code, detail)
        )

    # Create API response
    error_response = ApiResponse(
        success=False,
        code=status_code,
        message=internal_message,
        user_error=user_error,
        data=None
    )
    
    return error_response


def get_error_code_from_status(status_code: int) -> str:
    """
    Get error code from HTTP status code.
    
    Maps standard HTTP status codes to application-specific error codes.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        str: Error code
    """
    # Mapping of HTTP status codes to error codes
    status_to_error_code = {
        status.HTTP_400_BAD_REQUEST: ErrorCode.VALIDATION_ERROR,
        status.HTTP_401_UNAUTHORIZED: ErrorCode.AUTHENTICATION_ERROR,
        status.HTTP_403_FORBIDDEN: ErrorCode.AUTHORIZATION_ERROR,
        status.HTTP_404_NOT_FOUND: ErrorCode.RESOURCE_NOT_FOUND,
        status.HTTP_409_CONFLICT: ErrorCode.DUPLICATE_KEY,
        status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorCode.VALIDATION_ERROR,
        status.HTTP_500_INTERNAL_SERVER_ERROR: ErrorCode.SYSTEM_ERROR
    }
    
    return status_to_error_code.get(status_code, ErrorCode.UNEXPECTED_ERROR)


# Global exception handler functions
def create_http_exception_handler():
    """
    Generate a handler for HTTPException.
    
    Creates a FastAPI exception handler that properly formats HTTPException
    instances into standardized API responses.
    
    Returns:
        Async function that handles HTTPException
    """
    async def http_exception_handler(request: Request, exc):
        error_response = create_error_response(exc.status_code, exc.detail, request, exc)
        return JSONResponse(
            status_code=error_response.code,
            content=error_response.model_dump()
        )
    return http_exception_handler


def create_request_validation_exception_handler():
    """
    Generate a handler for RequestValidationError.
    
    Creates a FastAPI exception handler that properly formats validation errors
    into user-friendly error messages.
    
    Returns:
        Async function that handles RequestValidationError
    """
    async def validation_exception_handler(request: Request, exc):
        # Format validation errors appropriately
        errors = []
        for error in exc.errors():
            loc = " -> ".join([str(l) for l in error.get("loc", [])])
            msg = error.get("msg", "")
            errors.append(f"{loc}: {msg}")
        
        detail = "Invalid input data: " + "; ".join(errors)
        
        error_response = create_error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail, 
            request, 
            exc
        )
        
        # Set user error
        if not error_response.user_error:
            error_response.user_error = UserError(
                code=ErrorCode.VALIDATION_ERROR,
                message=ErrorMessage.get_message(ErrorCode.VALIDATION_ERROR)
            )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.model_dump()
        )
    return validation_exception_handler


def create_app_exception_handler():
    """
    Generate a handler for AppException.
    
    Creates a FastAPI exception handler for application-specific exceptions,
    mapping them to appropriate HTTP status codes and error messages.
    
    Returns:
        Async function that handles AppException
    """
    async def app_exception_handler(request: Request, exc: AppException):
        # Determine status code based on error type
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        if isinstance(exc, AppException):
            # Set appropriate HTTP status code based on error type
            if hasattr(exc, 'error_code'):
                status_code = get_status_from_error_code(exc.error_code, status_code)
        
        error_response = create_error_response(status_code, str(exc), request, exc)
        
        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump()
        )
    return app_exception_handler


def create_generic_exception_handler():
    """
    Generate a handler for general exceptions.
    
    Creates a FastAPI exception handler that catches all unhandled exceptions
    and formats them into standard API error responses.
    
    Returns:
        Async function that handles general exceptions
    """
    async def generic_exception_handler(request: Request, exc: Exception):
        error_response = create_error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, 
            str(exc), 
            request, 
            exc
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump()
        )
    return generic_exception_handler


def get_status_from_error_code(error_code: str, default_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR) -> int:
    """
    Get HTTP status code from error code.
    
    Maps application-specific error codes to standard HTTP status codes.
    
    Args:
        error_code: Application error code
        default_status: Default status code if no mapping is found
        
    Returns:
        int: HTTP status code
    """
    # Mapping of error codes to HTTP status codes
    if not error_code:
        return default_status
        
    category = error_code[:2] if len(error_code) >= 2 else ""
    
    # Category-based status code mapping
    category_status_map = {
        "10": status.HTTP_400_BAD_REQUEST,  # General errors
        "20": status.HTTP_401_UNAUTHORIZED,  # Authentication/Authorization errors
        "30": status.HTTP_422_UNPROCESSABLE_ENTITY,  # Input validation errors
        "40": status.HTTP_400_BAD_REQUEST,  # Business rule errors
        "50": status.HTTP_500_INTERNAL_SERVER_ERROR,  # Database/Repository errors
        "60": status.HTTP_502_BAD_GATEWAY,  # External service integration errors
        "90": status.HTTP_500_INTERNAL_SERVER_ERROR,  # System errors
    }
    
    # Individual mappings for specific error codes
    specific_status_map = {
        ErrorCode.RESOURCE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ErrorCode.DUPLICATE_KEY: status.HTTP_409_CONFLICT,
        ErrorCode.AUTHENTICATION_ERROR: status.HTTP_401_UNAUTHORIZED,
        ErrorCode.AUTHORIZATION_ERROR: status.HTTP_403_FORBIDDEN,
    }
    
    # Prioritize specific error code mappings
    if error_code in specific_status_map:
        return specific_status_map[error_code]
    
    # Category-based mapping as fallback
    return category_status_map.get(category, default_status)