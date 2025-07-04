# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from typing import Any

from kugel_common.exceptions import DocumentNotFoundException, DocumentAlreadyExistsException
from app.models.documents.category_master_document import CategoryMasterDocument
from app.models.repositories.category_master_repository import CategoryMasterRepository

logger = getLogger(__name__)


class CategoryMasterService:
    """
    Service class for managing category master data operations.
    This service provides business logic for creating, retrieving, updating,
    and deleting category records in the master data database.
    """

    def __init__(self, category_master_repo: CategoryMasterRepository):
        """
        Initialize the CategoryMasterService with a repository.

        Args:
            category_master_repo: Repository for category master data operations
        """
        self.category_master_repo = category_master_repo

    async def create_category_async(
        self, category_code: str, description: str, description_short: str, tax_code: str
    ) -> CategoryMasterDocument:
        """
        Create a new category in the database.

        Args:
            category_code: Unique identifier for the category
            description: Detailed description of the category
            description_short: Short description of the category
            tax_code: Tax code associated with this category

        Returns:
            Newly created CategoryMasterDocument

        Raises:
            DocumentAlreadyExistsException: If a category with the given code already exists
        """

        # check if category exists
        category = await self.category_master_repo.get_category_by_code_async(category_code)
        if category is not None:
            message = f"category with code {category_code} already exists. tenant_id: {category.tenant_id}"
            raise DocumentAlreadyExistsException(message, logger)

        category_doc = CategoryMasterDocument()
        category_doc.category_code = category_code
        category_doc.description = description
        category_doc.description_short = description_short
        category_doc.tax_code = tax_code
        return await self.category_master_repo.create_category_async(category_doc)

    async def get_category_by_code_async(self, category_code: str) -> CategoryMasterDocument:
        """
        Retrieve a category by its unique code.

        Args:
            category_code: Unique identifier for the category

        Returns:
            CategoryMasterDocument with the specified code

        Raises:
            DocumentNotFoundException: If no category with the given code exists
        """
        category = await self.category_master_repo.get_category_by_code_async(category_code)
        if category is None:
            message = f"category with code {category_code} not found"
            raise DocumentNotFoundException(message, logger)
        return category

    async def get_categories_async(self, limit: int, page: int, sort: list[tuple[str, int]]) -> list:
        """
        Retrieve all categories within the tenant with pagination and sorting.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)

        Returns:
            List of CategoryMasterDocument objects
        """
        return await self.category_master_repo.get_category_by_filter_async({}, limit, page, sort)

    async def get_categories_paginated_async(self, limit: int, page: int, sort: list[tuple[str, int]]):
        """
        Retrieve all categories within the tenant with pagination metadata.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)

        Returns:
            PaginatedResult containing CategoryMasterDocument objects and metadata
        """
        return await self.category_master_repo.get_category_by_filter_paginated_async({}, limit, page, sort)

    async def update_category_async(self, category_code: str, update_data: dict) -> CategoryMasterDocument:
        """
        Update an existing category with new data.

        Args:
            category_code: Unique identifier for the category to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated CategoryMasterDocument

        Raises:
            DocumentNotFoundException: If no category with the given code exists
        """

        # check if category exists
        category = await self.category_master_repo.get_category_by_code_async(category_code)
        if category is None:
            message = f"category with code {category_code} not found"
            raise DocumentNotFoundException(message, logger)

        # update category
        return await self.category_master_repo.update_category_async(category_code, update_data)

    async def delete_category_async(self, category_code: str) -> None:
        """
        Delete a category from the database.

        Args:
            category_code: Unique identifier for the category to delete

        Raises:
            DocumentNotFoundException: If no category with the given code exists
        """
        # check if category exists
        category = await self.category_master_repo.get_category_by_code_async(category_code)
        if category is None:
            message = f"category with code {category_code} not found"
            raise DocumentNotFoundException(message, logger)

        # delete category
        return await self.category_master_repo.delete_category_async(category_code)
