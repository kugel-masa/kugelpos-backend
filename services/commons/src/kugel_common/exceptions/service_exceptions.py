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
Service layer exception definitions

This module defines common exception classes for the service layer,
providing standardized error handling and appropriate HTTP status codes.
"""
import logging
from .base_exceptions import ServiceException
from .error_codes import ErrorCode, ErrorMessage
from fastapi import status

# Document-related exceptions
class DocumentNotFoundException(ServiceException):
    """
    Exception raised when a document is not found in the service layer.
    
    Used when a requested resource cannot be found in the database or
    other data source, resulting in a 404 Not Found response.
    """
    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message, 
            logger, 
            original_exception, 
            ErrorCode.RESOURCE_NOT_FOUND,
            ErrorMessage.get_message(ErrorCode.RESOURCE_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND,
            log_level=logging.WARNING
        )

class DocumentAlreadyExistsException(ServiceException):
    """
    Exception raised when a document already exists in the service layer.
    
    Used for uniqueness constraint violations when creating resources,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message, 
            logger, 
            original_exception, 
            ErrorCode.DUPLICATE_KEY,
            ErrorMessage.get_message(ErrorCode.DUPLICATE_KEY),
            status_code=status.HTTP_400_BAD_REQUEST
        )

# Request-related exceptions
class BadRequestBodyException(ServiceException):
    """
    Exception raised when a bad request body is received.
    
    Used when the request body is malformed or missing required fields,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message, 
            logger, 
            original_exception, 
            ErrorCode.VALIDATION_ERROR,
            ErrorMessage.get_message(ErrorCode.VALIDATION_ERROR),
            status_code=status.HTTP_400_BAD_REQUEST
        )

class InvalidRequestDataException(ServiceException):
    """
    Exception raised when invalid request data is received.
    
    Used when request data fails semantic validation (beyond simple schema validation),
    resulting in a 422 Unprocessable Entity response.
    """
    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message, 
            logger, 
            original_exception, 
            ErrorCode.VALIDATION_ERROR,
            ErrorMessage.get_message(ErrorCode.VALIDATION_ERROR),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

# Event and state-related exceptions
class EventBadSequenceException(ServiceException):
    """
    Exception raised when a bad sequence event is received.
    
    Used when events are received out of order or in an invalid state transition,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message, 
            logger, 
            original_exception, 
            ErrorCode.INVALID_OPERATION,
            ErrorMessage.get_message(ErrorCode.INVALID_OPERATION),
            status_code=status.HTTP_400_BAD_REQUEST
        )

class StrategyPluginException(ServiceException):
    """
    Exception raised when a strategy plugin error is received.
    
    Used when a problem occurs within a strategy implementation plugin,
    resulting in a 500 Internal Server Error response.
    """
    def __init__(self, message, logger=None, original_exception=None):
        super().__init__(
            message, 
            logger, 
            original_exception, 
            ErrorCode.SYSTEM_ERROR,
            ErrorMessage.get_message(ErrorCode.SYSTEM_ERROR),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )