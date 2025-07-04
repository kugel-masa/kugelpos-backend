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
Pagination models for list response standardization across all microservices.

This module provides standardized models for paginated responses, ensuring that
all list endpoints in the application return responses with consistent pagination structure.
"""
from typing import Generic, TypeVar
from kugel_common.schemas.base_schemas import BaseSchemmaModel, Metadata

T = TypeVar("T")

class PaginatedResult(BaseSchemmaModel, Generic[T]):
    """
    Generic model for paginated API responses.
    
    Provides a standardized structure for API responses that return lists of items
    with pagination metadata. The model is generic and can accommodate any data type
    for the list items.
    
    Attributes:
        data: List of items of the specified generic type
        metadata: Pagination metadata including total count, current page, and items per page
    """
    data: list[T]
    metadata: Metadata