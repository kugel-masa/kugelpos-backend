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
Repository layer exception definitions

This module defines common exception classes for the repository layer,
providing standardized error handling and appropriate HTTP status codes.
"""
from .base_exceptions import RepositoryException
from .error_codes import ErrorCode, ErrorMessage
from fastapi import status

class NotFoundException(RepositoryException):
    """
    Exception raised when a document is not found in the repository layer.
    
    Used when a requested resource cannot be found in the database,
    resulting in a 404 Not Found response.
    """
    def __init__(self, message, collection_name, find_key, logger=None, original_exception=None):
        message = f"{message}: find_key->{find_key}"
        super().__init__(
            message, 
            collection_name, 
            logger, 
            original_exception, 
            ErrorCode.RESOURCE_NOT_FOUND,
            ErrorMessage.get_message(ErrorCode.RESOURCE_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND
        )

class CannotCreateException(RepositoryException):
    """
    Exception raised when a document cannot be created in the repository layer.
    
    Used when an attempt to create a new document in the database fails,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, collection_name, document, logger=None, original_exception=None):
        message = f"{message}: document->{document}"
        super().__init__(
            message, 
            collection_name, 
            logger, 
            original_exception, 
            ErrorCode.CANNOT_CREATE,
            ErrorMessage.get_message(ErrorCode.CANNOT_CREATE),
            status_code=status.HTTP_400_BAD_REQUEST
        )

class CannotDeleteException(RepositoryException):
    """
    Exception raised when a document cannot be deleted.
    
    Used when an attempt to delete a document from the database fails,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, collection_name, delete_key, logger=None, original_exception=None):
        message = f"{message}: delete_key->{delete_key}"
        super().__init__(
            message, 
            collection_name, 
            logger, 
            original_exception, 
            ErrorCode.CANNOT_DELETE,
            ErrorMessage.get_message(ErrorCode.CANNOT_DELETE),
            status_code=status.HTTP_400_BAD_REQUEST
        )

class UpdateNotWorkException(RepositoryException):
    """
    Exception raised when an update operation fails.
    
    Used when an attempt to update a document in the database fails,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, collection_name, update_key, logger=None, original_exception=None):
        message = f"{message}: update_key->{update_key}"
        super().__init__(
            message, 
            collection_name, 
            logger, 
            original_exception, 
            ErrorCode.UPDATE_NOT_WORK,
            ErrorMessage.get_message(ErrorCode.UPDATE_NOT_WORK),
            status_code=status.HTTP_400_BAD_REQUEST
        )

class ReplaceNotWorkException(RepositoryException):
    """
    Exception raised when a document replacement operation fails.
    
    Used when an attempt to replace an entire document in the database fails,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, collection_name, update_key, logger=None, original_exception=None):
        message = f"{message}: update_key->{update_key}"
        super().__init__(
            message, 
            collection_name, 
            logger, 
            original_exception, 
            ErrorCode.REPLACE_NOT_WORK,
            ErrorMessage.get_message(ErrorCode.REPLACE_NOT_WORK),
            status_code=status.HTTP_400_BAD_REQUEST
        )

class DeleteChildExistException(RepositoryException):
    """
    Exception raised when child documents exist that prevent deletion.
    
    Used when an attempt to delete a document fails because it has child documents,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, collection_name, delete_key, logger=None, original_exception=None):
        message = f"{message}: delete_key->{delete_key}"
        super().__init__(
            message, 
            collection_name, 
            logger, 
            original_exception, 
            ErrorCode.DELETE_CHILD_EXIST,
            ErrorMessage.get_message(ErrorCode.DELETE_CHILD_EXIST),
            status_code=status.HTTP_400_BAD_REQUEST
        )

class AlreadyExistException(RepositoryException):
    """
    Exception raised when a document already exists.
    
    Used when an attempt to create a document fails because one with the same key already exists,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, collection_name, find_key, logger=None, original_exception=None):
        message = f"{message}: find_key->{find_key}"
        super().__init__(
            message, 
            collection_name, 
            logger, 
            original_exception, 
            ErrorCode.DUPLICATE_KEY,
            ErrorMessage.get_message(ErrorCode.DUPLICATE_KEY),
            status_code=status.HTTP_400_BAD_REQUEST
        )

class DuplicateKeyException(RepositoryException):
    """
    Exception raised when a duplicate key is found.
    
    Used when an attempt to create or update a document violates a unique constraint,
    resulting in a 400 Bad Request response.
    """
    def __init__(self, message, collection_name, key, logger=None, original_exception=None):
        message = f"{message}: key->{key}"
        super().__init__(
            message, 
            collection_name, 
            logger, 
            original_exception, 
            ErrorCode.DUPLICATE_KEY,
            ErrorMessage.get_message(ErrorCode.DUPLICATE_KEY),
            status_code=status.HTTP_400_BAD_REQUEST
        )

class LoadDataNoExistException(RepositoryException):
    """
    Exception raised when required data does not exist during a load operation.
    
    Used when an attempt to load data from a source fails because the data does not exist,
    resulting in a 404 Not Found response.
    """
    def __init__(self, message, data_name, logger=None, original_exception=None):
        message = f"{message}: data_name->{data_name}"
        super().__init__(
            message, 
            "load_data", 
            logger, 
            original_exception, 
            ErrorCode.RESOURCE_NOT_FOUND,
            ErrorMessage.get_message(ErrorCode.RESOURCE_NOT_FOUND),
            status_code=status.HTTP_404_NOT_FOUND
        )