# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Pagination metadata models for master-data service.

This module provides models for pagination metadata that extends the base
Metadata class with additional fields for enhanced pagination information.
"""
from typing import Optional
from kugel_common.schemas.base_schemas import Metadata


class PaginationMetadata(Metadata):
    """
    Enhanced pagination metadata with additional navigation information.

    Extends the base Metadata class with total_pages calculation and
    navigation flags for better client-side pagination handling.

    Attributes:
        total: Total number of items across all pages
        page: Current page number (1-based)
        limit: Number of items per page
        sort: Sort criteria string (inherited)
        filter: Filter conditions (inherited)
        total_pages: Total number of pages available
        has_next: Whether there is a next page
        has_previous: Whether there is a previous page
    """

    total_pages: int
    has_next: bool
    has_previous: bool

    def __init__(
        self,
        page: int,
        limit: int,
        total_count: int,
        sort: Optional[str] = None,
        filter: Optional[dict] = None,
        **kwargs,
    ):
        """
        Initialize pagination metadata with calculated fields.

        Args:
            page: Current page number
            limit: Items per page
            total_count: Total number of items
            sort: Sort criteria string
            filter: Filter conditions dictionary
            **kwargs: Additional fields
        """
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
        has_next = page < total_pages
        has_previous = page > 1

        super().__init__(
            total=total_count,
            page=page,
            limit=limit,
            sort=sort,
            filter=filter,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
            **kwargs,
        )
