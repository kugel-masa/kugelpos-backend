# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

logger = getLogger(__name__)

from kugel_common.exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    InvalidRequestDataException,
)
from app.models.documents.item_store_master_document import ItemStoreMasterDocument
from app.models.repositories.item_store_master_repository import ItemStoreMasterRepository
from app.models.repositories.item_common_master_repository import ItemCommonMasterRepository
from app.models.documents.item_store_detail_document import ItemStoreDetailDocument


class ItemStoreMasterService:
    """
    Service class for managing store-specific item master data operations.

    This service provides business logic for creating, retrieving, updating,
    and deleting store-specific item records in the master data database.
    Store-specific item data includes store-specific prices that can override
    the standard prices from the common item master.
    """

    def __init__(
        self,
        item_store_master_repo: ItemStoreMasterRepository,
        item_common_master_repo: ItemCommonMasterRepository,
    ):
        """
        Initialize the ItemStoreMasterService with repositories.

        Args:
            item_store_master_repo: Repository for store-specific item master data operations
            item_common_master_repo: Repository for common item master data operations
        """
        self.item_store_master_repo = item_store_master_repo
        self.item_common_master_repo = item_common_master_repo

    async def create_item_async(
        self,
        item_code: str,
        store_price: float,
    ) -> ItemStoreMasterDocument:
        """
        Create a new store-specific item record in the database.

        Args:
            item_code: Unique identifier for the item (must exist in common item master)
            store_price: Store-specific price for this item

        Returns:
            Newly created ItemStoreMasterDocument

        Raises:
            DocumentNotFoundException: If the item does not exist in the common item master
            DocumentAlreadyExistsException: If a store-specific record for this item already exists
        """

        logger.debug(f"Create item store request received for item_code: {item_code}")

        # check if item common exists
        item_common = await self.item_common_master_repo.get_item_by_code_async(item_code)
        if item_common is None:
            message = f"item with item_code {item_code} not found in item_common_master"
            raise DocumentNotFoundException(message, logger)

        # check if item store exists already
        item_store = await self.item_store_master_repo.get_item_store_by_code(item_code)
        if item_store is not None:
            message = f"item with item_code {item_code} already exists. tenant_id: {item_store.tenant_id}"
            raise DocumentAlreadyExistsException(message, logger)

        item_store_doc = ItemStoreMasterDocument()
        item_store_doc.item_code = item_code
        item_store_doc.store_price = store_price

        logger.debug(f"Item: {item_store_doc}")

        return await self.item_store_master_repo.create_item_store_async(item_store_doc)

    async def get_item_by_code_async(self, item_code: str) -> ItemStoreMasterDocument:
        """
        Retrieve a store-specific item record by its unique code.

        Args:
            item_code: Unique identifier for the item

        Returns:
            ItemStoreMasterDocument with the specified code

        Raises:
            DocumentNotFoundException: If no store-specific item record with the given code exists
        """
        item = await self.item_store_master_repo.get_item_store_by_code(item_code)
        if item is None:
            message = f"item store with item_code {item_code} not found"
            raise DocumentNotFoundException(message, logger)
        return item

    async def get_item_all_async(self, limit: int, page: int, sort: list[tuple[str, int]]) -> list:
        """
        Retrieve all store-specific item records with pagination and sorting.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)

        Returns:
            List of ItemStoreMasterDocument objects
        """
        items_all_in_store = await self.item_store_master_repo.get_item_store_by_filter_async({}, limit, page, sort)
        return items_all_in_store

    async def get_item_all_paginated_async(
        self, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> tuple[list[ItemStoreMasterDocument], int]:
        """
        Retrieve all store-specific item records with pagination metadata.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction

        Returns:
            Tuple of (list of ItemStoreMasterDocument objects, total count)
        """
        items_all_in_store = await self.item_store_master_repo.get_item_store_by_filter_async({}, limit, page, sort)
        total_count = await self.item_store_master_repo.get_item_count_by_filter_async({})
        return items_all_in_store, total_count

    async def get_item_store_detail_by_code_async(self, item_code: str) -> ItemStoreDetailDocument:
        """
        Retrieve a detailed item record combining common and store-specific information.

        This method merges data from both common and store-specific item records
        to provide a complete view of an item with store-specific overrides applied.

        Args:
            item_code: Unique identifier for the item

        Returns:
            ItemStoreDetailDocument containing combined item data

        Raises:
            DocumentNotFoundException: If the item does not exist in the common item master
        """

        logger.debug(f"get_item_store_detail_by_code_async request received for item_code: {item_code}")

        item_detail_doc = ItemStoreDetailDocument()

        item_common = await self.item_common_master_repo.get_item_by_code_async(
            item_code=item_code, is_logical_deleted=False, use_cache=False
        )
        if item_common is None:
            message = f"item common with item_code {item_code} not found"
            raise DocumentNotFoundException(message, logger)
        else:
            logger.debug(f"item_common: {item_common}")
            item_detail_doc.tenant_id = item_common.tenant_id
            item_detail_doc.item_code = item_common.item_code
            item_detail_doc.description = item_common.description
            item_detail_doc.description_short = item_common.description_short
            item_detail_doc.description_long = item_common.description_long
            item_detail_doc.unit_price = item_common.unit_price
            item_detail_doc.unit_cost = item_common.unit_cost
            item_detail_doc.item_details = item_common.item_details
            item_detail_doc.image_urls = item_common.image_urls
            item_detail_doc.category_code = item_common.category_code
            item_detail_doc.tax_code = item_common.tax_code
            item_detail_doc.is_discount_restricted = item_common.is_discount_restricted
            item_detail_doc.updated_at = item_common.updated_at
            item_detail_doc.created_at = item_common.created_at

        item_store = await self.item_store_master_repo.get_item_store_by_code(item_code=item_code)
        if item_store is None:
            message = f"item store detail with item_code {item_code} not found"
            # raise DocumentNotFoundException(message, logger)
            logger.info(message)
        else:
            logger.debug(f"item_store: {item_store}")
            item_detail_doc.store_code = item_store.store_code
            item_detail_doc.store_price = item_store.store_price
            item_detail_doc.updated_at = item_store.updated_at
            item_detail_doc.created_at = item_store.created_at

        return item_detail_doc

    async def update_item_async(self, item_code: str, update_data: dict) -> ItemStoreMasterDocument:
        """
        Update an existing store-specific item record with new data.

        Args:
            item_code: Unique identifier for the item to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated ItemStoreMasterDocument

        Raises:
            InvalidRequestDataException: If the item_code in update_data doesn't match the item_code parameter
            DocumentNotFoundException: If no store-specific item record with the given code exists
        """

        # check if item_code in update_data equals item_code
        if "item_code" in update_data and update_data["item_code"] != item_code:
            message = f"item_code in update_data {update_data['item_code']} not equal to item_code {item_code}"
            raise InvalidRequestDataException(message, logger)

        # check if item exists
        item = await self.item_store_master_repo.get_item_store_by_code(item_code)
        if item is None:
            message = f"item with item_code {item_code} not found"
            raise DocumentNotFoundException(message, logger)

        # update item
        # remove item_code from update_data
        if "item_code" in update_data:
            del update_data["item_code"]
        return await self.item_store_master_repo.update_item_store_async(item_code, update_data)

    async def delete_item_async(self, item_code: str) -> None:
        """
        Delete a store-specific item record from the database.

        Args:
            item_code: Unique identifier for the item to delete

        Raises:
            DocumentNotFoundException: If no store-specific item record with the given code exists
        """

        item = await self.item_store_master_repo.get_item_store_by_code(item_code)
        if item is None:
            message = f"item with item_code {item_code} not found"
            raise DocumentNotFoundException(message, logger)

        await self.item_store_master_repo.delete_item_store_async(item_code)
        return None
