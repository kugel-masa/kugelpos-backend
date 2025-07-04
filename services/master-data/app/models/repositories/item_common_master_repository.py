# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.utils.misc import get_app_time
from app.config.settings import settings
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.models.documents.item_common_master_document import ItemCommonMasterDocument

logger = getLogger(__name__)


class ItemCommonMasterRepository(AbstractRepository[ItemCommonMasterDocument]):
    """
    Repository for managing common item master data in the database.

    This class provides specific implementation for CRUD operations on common item data,
    extending the generic functionality provided by AbstractRepository. It manages
    the core item information shared across all stores and includes caching capabilities
    for performance optimization.
    """

    def __init__(
        self, db: AsyncIOMotorDatabase, tenant_id: str, item_master_documents: list[ItemCommonMasterDocument] = None
    ):
        """
        Initialize a new ItemCommonMasterRepository instance.

        Args:
            db: MongoDB database instance
            tenant_id: Identifier for the tenant whose data this repository will manage
            item_master_documents: Optional list of item documents for caching
        """
        super().__init__(settings.DB_COLLECTION_NAME_ITEM_COMMON_MASTER, ItemCommonMasterDocument, db)
        self.tenant_id = tenant_id
        self.item_master_documents = item_master_documents

    def set_item_master_documents(self, item_master_documents: list[ItemCommonMasterDocument]):
        """
        Set the cached item master documents list.

        This method allows updating the cached item documents for faster lookups.

        Args:
            item_master_documents: List of item documents to cache
        """
        self.item_master_documents = item_master_documents

    async def create_item_async(self, item_doc: ItemCommonMasterDocument) -> ItemCommonMasterDocument:
        """
        Create a new item in the database.

        This method sets the tenant ID and generates a shard key before creating the document.

        Args:
            item_doc: Item document to create

        Returns:
            The created item document

        Raises:
            RepositoryException: If there is an error during creation
        """
        logger.debug(f"ItemMasterRepository.create_item_async: {item_doc}")
        item_doc.tenant_id = self.tenant_id
        item_doc.shard_key = self.__get_shard_key(item_doc)
        success = await self.create_async(item_doc)
        if success:
            return item_doc
        else:
            raise Exception("Failed to create item")

    async def get_item_by_code_async(
        self, item_code: str, is_logical_deleted: bool = False, use_cache: bool = False
    ) -> ItemCommonMasterDocument:
        """
        Retrieve an item by its unique code.

        This method supports caching and can optionally include logically deleted items.
        When caching is enabled, items are first looked up in the cache and only fetched
        from the database if not found or expired.

        Args:
            item_code: Unique identifier for the item
            is_logical_deleted: If True, include logically deleted items in the search
            use_cache: If True, use cached items when available

        Returns:
            The matching item document, or None if not found

        Raises:
            RepositoryException: If there is an error during retrieval
        """
        if self.item_master_documents is None:
            self.item_master_documents = []

        # first check item_code exist in the list of item_master_documents
        if use_cache:
            item = next((item for item in self.item_master_documents if item.item_code == item_code), None)
            if item is not None:
                logger.debug(
                    f"ItemMasterRepository.get_item_by_code: item_code->{item_code} in the list of item_master_documents"
                )
                if item.is_expired():
                    logger.debug(f"ItemMasterRepository.get_item_by_code: item_code->{item_code} is expired")
                    self.item_master_documents.remove(item)
                else:
                    return item

        # if not found in the list or expired, then get from the database
        tenant_id = self.tenant_id
        filter = {"tenant_id": tenant_id, "item_code": item_code, "is_deleted": is_logical_deleted}
        item_doc = await self.get_one_async(filter)

        # if use_cache, add the document to the list with the cached_on field set to the current time
        if item_doc is not None and use_cache:
            item_doc.cached_on = get_app_time()
            self.item_master_documents.append(item_doc)

        return item_doc

    async def get_item_by_filter_async(
        self, query_filter: dict, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> list[ItemCommonMasterDocument]:
        """
        Retrieve items matching the specified filter with pagination and sorting.

        This method automatically adds tenant filtering to ensure data isolation.

        Args:
            query_filter: MongoDB query filter to select items
            limit: Maximum number of items to return per page
            page: Page number (1-based) to retrieve
            sort: List of tuples containing field name and sort direction

        Returns:
            List of item documents matching the query parameters

        Raises:
            RepositoryException: If there is an error during retrieval
        """
        query_filter["tenant_id"] = self.tenant_id
        logger.debug(f"query_filter->{query_filter} limit->{limit} page->{page} sort->{sort}")
        return await self.get_list_async_with_sort_and_paging(query_filter, limit, page, sort)

    async def update_item_async(self, item_code: str, update_data: dict) -> ItemCommonMasterDocument:
        """
        Update specific fields of an item.

        Args:
            item_code: Unique identifier for the item to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            The updated item document

        Raises:
            RepositoryException: If there is an error during update
        """
        filter = {"tenant_id": self.tenant_id, "item_code": item_code}
        success = await self.update_one_async(filter, update_data)
        if success:
            return await self.get_item_by_code_async(item_code)
        else:
            raise Exception(f"Failed to update item with code {item_code}")

    async def replace_item_async(
        self, item_code: str, new_document: ItemCommonMasterDocument
    ) -> ItemCommonMasterDocument:
        """
        Replace an existing item with a new document.

        Args:
            item_code: Unique identifier for the item to replace
            new_document: New item document to replace the existing one

        Returns:
            The replaced item document

        Raises:
            RepositoryException: If there is an error during replacement
        """
        filter = {"tenant_id": self.tenant_id, "item_code": item_code}
        success = await self.replace_one_async(filter, new_document)
        if success:
            return new_document
        else:
            raise Exception(f"Failed to replace item with code {item_code}")

    async def delete_item_async(self, item_code: str, is_logical: bool = False):
        """
        Delete an item from the database.

        This method supports both physical deletion and logical deletion (marking as deleted).

        Args:
            item_code: Unique identifier for the item to delete
            is_logical: If True, perform logical deletion instead of physical deletion

        Returns:
            The deleted/updated item document

        Raises:
            RepositoryException: If there is an error during deletion
        """
        filter = {"tenant_id": self.tenant_id, "item_code": item_code}

        if is_logical:
            success = await self.update_one_async(filter, {"is_deleted": True})
            if success:
                return await self.get_item_by_code_async(item_code, is_logical_deleted=True)
            else:
                raise Exception(f"Failed to logically delete item with code {item_code}")
        else:
            return await self.delete_async(filter)

    async def get_item_count_by_filter_async(self, query_filter: dict) -> int:
        """
        Get the count of items matching the specified filter.

        Args:
            query_filter: MongoDB query filter to count items

        Returns:
            Count of items matching the filter

        Raises:
            RepositoryException: If there is an error during counting
        """
        query_filter["tenant_id"] = self.tenant_id
        if self.dbcollection is None:
            await self.initialize()
        return await self.dbcollection.count_documents(query_filter)

    def __get_shard_key(self, item_master: ItemCommonMasterDocument) -> str:
        """
        Generate a shard key for the item document.

        Currently uses only the tenant ID as the sharding key.

        Args:
            item_master: Item document for which to generate a shard key

        Returns:
            String representation of the shard key
        """
        keys = []
        keys.append(item_master.tenant_id)
        return self.make_shard_key(keys)
