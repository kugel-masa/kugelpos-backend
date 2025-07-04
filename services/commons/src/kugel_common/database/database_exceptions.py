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
Database exception handling module

This module defines exception classes specific to database operations,
providing structured error handling for MongoDB interactions.
"""
import logging

class AppException(Exception):
    """
    Base class for exceptions in the application.
    
    Provides common functionality for exception handling including logging
    and the ability to wrap original exceptions for better context.
    """
    defalut_logger = logging.getLogger(__name__)
    
    def __init__(self, message, logger=None, original_exception=None):
        """
        Constructor for AppException
        
        Args:
            message: str - Error message to log and display
            logger: logging.Logger - Custom logger to use (uses default if None)
            original_exception: Exception - Original exception that triggered this exception
        """
        super().__init__(message)
        self.original_exception = original_exception

        if logger is None:
            self.defalut_logger.error(message)
        else:
            logger.error(message)

class DatabaseException(AppException):
    """ 
    Exception raised for errors in the database layer of the application.
    
    Used to handle and report MongoDB-specific errors such as connection issues,
    query failures, timeout errors, and other database-related problems.
    """
    def __init__(self, message, logger=None, original_exception=None):
        """
        Constructor for DatabaseException
        
        Args:
            message: str - Database-specific error message
            logger: logging.Logger - Custom logger to use (uses default if None)
            original_exception: Exception - Original MongoDB exception
        """
        super().__init__(message, logger, original_exception)
