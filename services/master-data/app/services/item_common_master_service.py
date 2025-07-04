# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

logger = getLogger(__name__)

from typing import Any

from kugel_common.exceptions import (
    DocumentAlreadyExistsException,
    DocumentNotFoundException,
    InvalidRequestDataException,
)
from app.models.documents.item_common_master_document import ItemCommonMasterDocument
from app.models.repositories.item_common_master_repository import ItemCommonMasterRepository


class ItemCommonMasterService:
    """
    Service class for managing common item master data operations.

    This service provides business logic for creating, retrieving, updating,
    and deleting common item records in the master data database.
    Common item data includes information shared across all stores like
    descriptions, standard prices, and categorization.
    """

    def __init__(
        self,
        item_common_master_repo: ItemCommonMasterRepository,
    ):
        """
        Initialize the ItemCommonMasterService with a repository.

        Args:
            item_common_master_repo: Repository for common item master data operations
        """
        logger.debug(f"ItemMasterService: {item_common_master_repo}")
        self.item_common_master_repo = item_common_master_repo

    async def create_item_async(
        self,
        item_code: str,
        description: str,
        unit_price: float,
        unit_cost: float,
        item_details: list[str],
        image_urls: list[str],
        category_code: str,
        tax_code: str,
    ) -> ItemCommonMasterDocument:
        """
        Create a new item record in the common item master database.

        Args:
            item_code: Unique identifier for the item
            description: Description of the item
            unit_price: Standard selling price per unit
            unit_cost: Cost price per unit
            item_details: List of additional item details or specifications
            image_urls: List of URLs to item images
            category_code: Category code this item belongs to
            tax_code: Tax code to apply to this item

        Returns:
            Newly created ItemCommonMasterDocument

        Raises:
            DocumentAlreadyExistsException: If an item with the given code already exists
        """

        logger.debug(f"Create item request received for item_code: {item_code}")

        # check if item exists
        item = await self.item_common_master_repo.get_item_by_code_async(item_code)
        if item is not None:
            message = f"item with item_code {item_code} already exists. tenant_id: {item.tenant_id}"
            raise DocumentAlreadyExistsException(message, logger)

        item_doc = ItemCommonMasterDocument()
        item_doc.item_code = item_code
        item_doc.description = description
        item_doc.unit_price = unit_price
        item_doc.unit_cost = unit_cost
        item_doc.item_details = item_details
        item_doc.image_urls = image_urls
        item_doc.category_code = category_code
        item_doc.tax_code = tax_code

        logger.debug(f"Item: {item_doc}")

        return await self.item_common_master_repo.create_item_async(item_doc)

    async def get_item_by_code_async(
        self, item_code: str, is_logical_deleted: bool = False
    ) -> ItemCommonMasterDocument:
        """
        Retrieve an item by its unique code.

        Args:
            item_code: Unique identifier for the item
            is_logical_deleted: If True, include logically deleted items in the search

        Returns:
            ItemCommonMasterDocument with the specified code

        Raises:
            DocumentNotFoundException: If no item with the given code exists
        """
        item = await self.item_common_master_repo.get_item_by_code_async(item_code, is_logical_deleted)
        if item is None:
            message = f"item with item_code {item_code} not found"
            raise DocumentNotFoundException(message, logger)
        return item

    async def get_item_all_async(self, limit: int, page: int, sort: list[tuple[str, int]]) -> list:
        """
        Retrieve all items with pagination and sorting.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)

        Returns:
            List of ItemCommonMasterDocument objects
        """
        items_all_in_tenant = await self.item_common_master_repo.get_item_by_filter_async({}, limit, page, sort)
        return items_all_in_tenant

    async def get_item_all_paginated_async(
        self, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> tuple[list[ItemCommonMasterDocument], int]:
        """
        Retrieve all items with pagination metadata.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction

        Returns:
            Tuple of (list of ItemCommonMasterDocument objects, total count)
        """
        items_all_in_tenant = await self.item_common_master_repo.get_item_by_filter_async({}, limit, page, sort)
        total_count = await self.item_common_master_repo.get_item_count_by_filter_async({})
        return items_all_in_tenant, total_count

    async def update_item_async(self, item_code: str, update_data: dict) -> ItemCommonMasterDocument:
        """
        Update an existing item with new data.

        Args:
            item_code: Unique identifier for the item to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated ItemCommonMasterDocument

        Raises:
            InvalidRequestDataException: If the item_code in update_data doesn't match the item_code parameter
            DocumentNotFoundException: If no item with the given code exists
        """

        # check if item_code in update_data equals item_code
        if "item_code" in update_data and update_data["item_code"] != item_code:
            message = f"item_code in update_data {update_data['item_code']} not equal to item_code {item_code}"
            raise InvalidRequestDataException(message, logger)

        # check if item exists
        item = await self.item_common_master_repo.get_item_by_code_async(item_code)
        if item is None:
            message = f"item with item_code {item_code} not found"
            raise DocumentNotFoundException(message, logger)

        # update item
        # remove item_code from update_data
        if "item_code" in update_data:
            del update_data["item_code"]
        return await self.item_common_master_repo.update_item_async(item_code, update_data)

    async def delete_item_async(self, item_code: str, is_logical: bool = False) -> None:
        """
        Delete an item from the database.

        Args:
            item_code: Unique identifier for the item to delete
            is_logical: If True, perform a logical delete (mark as deleted) instead of physical delete

        Raises:
            DocumentNotFoundException: If no item with the given code exists
        """

        if is_logical:
            item = await self.item_common_master_repo.get_item_by_code_async(
                item_code=item_code, is_logical_deleted=False
            )
        else:
            # check if item exists without checking is_deleted
            item = await self.item_common_master_repo.get_item_by_filter_async(
                query_filter={"item_code": item_code}, limit=1000, page=1, sort={"created_on": -1}
            )

        if item is None:
            message = f"item with item_code {item_code} not found"
            raise DocumentNotFoundException(message, logger)

        await self.item_common_master_repo.delete_item_async(item_code, is_logical)
        return None
