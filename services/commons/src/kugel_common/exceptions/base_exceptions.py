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
import logging
from kugel_common.exceptions.error_codes import ErrorCode, ErrorMessage

"""
Application Base Layer Exceptions

Defines the hierarchical structure of exception classes used throughout the application.
These exceptions provide consistent error handling and reporting across all layers.
"""
class AppException(Exception):
    """
    Base class for exceptions in the application.
    
    Provides common functionality for all application exceptions, including
    logging, error code management, and user-friendly error messages.
    """

    default_logger = logging.getLogger(__name__)
    
    def __init__(self, message, logger=None, original_exception=None, error_code=None, user_message=None, status_code: int = 500, log_level: int = logging.ERROR):
        """
        Constructor for AppException
        
        Parameters:
            message: str - System-level message for logging purposes
            logger: logging.Logger - The logger to use (uses default if None)
            original_exception: Exception - The original exception that was caught
            error_code: str - User-facing error code (included in API response)
            user_message: str - User-facing error message (included in API response)
            status_code: int - HTTP status code (included in API response)
            log_level: int - Logging level to use (default: logging.ERROR)
        """
        super().__init__(message)
        self.original_exception = original_exception
        self.error_code = error_code
        self.user_message = user_message
        self.status_code = status_code
        
        log_message = message
        if original_exception:
            log_message = f"{log_message}: {original_exception}"
            
        if logger is None:
            self.default_logger.log(log_level, log_message)
        else:
            logger.log(log_level, log_message)

        self.message = log_message
    
    def get_user_error(self):
        """
        Retrieves user error information for API responses.
        
        Returns:
            dict: Dictionary containing error code and message for user-facing responses
        """
        return {
            "code": self.error_code or ErrorCode.SYSTEM_ERROR,
            "message": self.user_message or ErrorMessage.get_message(ErrorCode.SYSTEM_ERROR),
        }

"""
Database Layer Exceptions
"""
class DatabaseException(AppException):
    """ 
    Exception raised for errors in the database layer of the application.
    
    Used when errors occur during direct database operations such as
    connection issues, query failures, or data corruption.
    """
    def __init__(self, message, logger=None, original_exception=None, error_code=None, user_message=None, status_code: int = 500):
        super().__init__(message, logger, original_exception, error_code, user_message, status_code)

"""
Repository Layer Exceptions
"""
class RepositoryException(AppException):
    """ 
    Exception raised for errors in the repository layer of the application.
    
    Used when errors occur during data access operations, particularly when
    working with specific collections or data entities.
    """
    def __init__(self, message, collection_name, logger=None, original_exception=None, error_code=None, user_message=None, status_code: int = 404):
        message = f"{message}: collection_name->{collection_name}"
        super().__init__(message, logger, original_exception, error_code, user_message, status_code)

"""
Service Layer Exceptions
"""
class ServiceException(AppException):
    """ 
    Exception raised for errors in the service layer of the application.
    
    Used when errors occur during business logic processing, external service
    interactions, or when coordinating multiple repository operations.
    """
    def __init__(self, message, logger=None, original_exception=None, error_code=None, user_message=None, status_code: int = 500, log_level: int = logging.ERROR):
        super().__init__(message, logger, original_exception, error_code, user_message, status_code, log_level)