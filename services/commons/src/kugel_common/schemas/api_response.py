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
Standard API response models for consistent response formatting across all microservices.

This module provides standardized Pydantic models for API responses, ensuring that
all endpoints in the application return responses with a consistent structure.
"""
from typing import Optional, Generic, TypeVar
from kugel_common.utils.misc import to_lower_camel
from kugel_common.schemas.base_schemas import BaseSchemmaModel, Metadata

T = TypeVar("T")

class UserError(BaseSchemmaModel):
    """
    User-friendly error information model.
    
    Contains structured error information that is suitable for display to end users,
    such as error codes and localized error messages.
    
    Attributes:
        code: Application-specific error code
        message: User-friendly error message suitable for display
    """
    code: Optional[str] = None
    message: Optional[str] = None

class ApiResponse(BaseSchemmaModel, Generic[T]):
    """
    Standardized API response model used by all endpoints.
    
    Provides a consistent structure for all API responses, including status information,
    error details when applicable, and the actual response data. The model is generic
    and can accommodate any data type for the response payload.
    
    Attributes:
        success: Boolean indicating if the operation was successful
        code: HTTP status code for the response
        message: System message typically used for logging or debugging
        user_error: User-friendly error information when an error occurs
        data: The actual response payload (generic type)
        metadata: Additional metadata like pagination info for list responses
        operation: Name of the operation that was performed (for tracking)
    """
    success: bool
    code: int = 200
    message: Optional[str]
    user_error: Optional[UserError] = None
    data: Optional[T]
    metadata: Optional[Metadata] = None
    operation: Optional[str] = None