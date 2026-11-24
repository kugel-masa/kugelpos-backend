# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from kugel_common.exceptions import RepositoryException
from pymongo.asynchronous.database import AsyncDatabase

from kugel_common.utils.misc import get_app_time
from app.config.settings import settings
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.models.documents.item_common_master_document import ItemCommonMasterDocument
from app.models.repositories.logical_delete import alive, restore_async, soft_delete_async

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
        self, db: AsyncDatabase, tenant_id: str, item_master_documents: list[ItemCommonMasterDocument] = None
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
        self, item_code: str, include_deleted: bool = False, use_cache: bool = False
    ) -> ItemCommonMasterDocument:
        """
        Retrieve an item by its unique code.

        This method supports caching and can optionally include logically deleted items.
        When caching is enabled, items are first looked up in the cache and only fetched
        from the database if not found or expired.

        Args:
            item_code: Unique identifier for the item
            include_deleted: If True, find a logically deleted item as well (issue #324).
                Before #324 this was an exact match (`is_logical_deleted`): True found
                deleted items only.
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
            if item is not None and (include_deleted or not item.is_deleted):
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
        filter = alive({"tenant_id": tenant_id, "item_code": item_code}, include_deleted)
        item_doc = await self.get_one_async(filter)

        # if use_cache, add the document to the list with the cached_on field set to the current time
        if item_doc is not None and use_cache:
            item_doc.cached_on = get_app_time()
            self.item_master_documents.append(item_doc)

        return item_doc

    async def get_item_by_filter_async(
        self,
        query_filter: dict,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
        include_deleted: bool = False,
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
        # Live items only unless asked: the list used to show logically deleted items (issue #324)
        query_filter = alive({**query_filter, "tenant_id": self.tenant_id}, include_deleted)
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
        filter = alive({"tenant_id": self.tenant_id, "item_code": item_code})
        success = await self.update_one_async(filter, update_data)
        if not success:
            # Missing, or deleted after the caller looked it up (issue #324)
            return None
        return await self.get_item_by_code_async(item_code)

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

    async def delete_item_async(self, item_code: str, is_logical: bool = True) -> bool:
        """
        Delete an item from the database, in one write.

        This method supports both physical deletion and logical deletion (marking as deleted).
        Whether the item existed is decided by that write alone, so two concurrent
        deletes of one item cannot both succeed, and the second is answered as not
        found rather than as a failure (#312).

        Args:
            item_code: Unique identifier for the item to delete
            is_logical: If True, mark the item deleted instead of removing it

        Returns:
            True when an item was deleted; False when there was none to delete (for a
            logical delete, none that was not already deleted)

        Raises:
            RepositoryException: If there is an error during deletion
        """
        if is_logical:
            return await soft_delete_async(self, {"tenant_id": self.tenant_id, "item_code": item_code})

        if self.dbcollection is None:
            await self.initialize()
        query_filter = {"tenant_id": self.tenant_id, "item_code": item_code}
        try:
            response = await self.dbcollection.delete_one(query_filter, session=self.session)
        except Exception as e:
            message = f"Failed to delete item: item_code->{item_code}"
            raise RepositoryException(message, self.collection_name, logger, e) from e
        return response.deleted_count == 1

    async def get_item_count_by_filter_async(self, query_filter: dict, include_deleted: bool = False) -> int:
        """
        Get the count of items matching the specified filter.

        Args:
            query_filter: MongoDB query filter to count items

        Returns:
            Count of items matching the filter

        Raises:
            RepositoryException: If there is an error during counting
        """
        query_filter = alive({**query_filter, "tenant_id": self.tenant_id}, include_deleted)
        if self.dbcollection is None:
            await self.initialize()
        return await self.dbcollection.count_documents(query_filter)

    async def restore_item_async(self, item_doc: ItemCommonMasterDocument) -> bool:
        """
        Restore a logically deleted item with a new document (issue #324).

        Stamped as create stamps it. Returns False when no deleted item matched.
        """
        item_doc.tenant_id = self.tenant_id
        item_doc.shard_key = self.__get_shard_key(item_doc)
        item_doc.created_at = get_app_time()
        item_doc.is_deleted = False
        return await restore_async(self, {"tenant_id": self.tenant_id, "item_code": item_doc.item_code}, item_doc)

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
