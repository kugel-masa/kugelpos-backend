# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.models.documents.item_store_master_document import ItemStoreMasterDocument
from app.config.settings import settings

logger = getLogger(__name__)


class ItemStoreMasterRepository(AbstractRepository[ItemStoreMasterDocument]):
    """
    Repository for managing store-specific item master data in the database.

    This class provides specific implementation for CRUD operations on store-specific item data,
    extending the generic functionality provided by AbstractRepository. It handles
    store-specific overrides for items, such as custom pricing at individual store locations.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str, store_code: str):
        """
        Initialize a new ItemStoreMasterRepository instance.

        Args:
            db: MongoDB database instance
            tenant_id: Identifier for the tenant whose data this repository will manage
            store_code: Identifier for the specific store
        """
        super().__init__(settings.DB_COLLECTION_NAME_ITEM_STORE_MASTER, ItemStoreMasterDocument, db)
        self.tenant_id = tenant_id
        self.store_code = store_code

    async def create_item_store_async(self, item_store_doc: ItemStoreMasterDocument) -> ItemStoreMasterDocument:
        """
        Create a new store-specific item record in the database.

        This method sets the tenant ID, store code, and generates a shard key before creating the document.

        Args:
            item_store_doc: Store-specific item document to create

        Returns:
            The created store-specific item document
        """
        item_store_doc.tenant_id = self.tenant_id
        item_store_doc.store_code = self.store_code
        item_store_doc.shard_key = self.__get_shard_key(item_store_doc)
        success = await self.create_async(item_store_doc)
        if success:
            return item_store_doc
        else:
            raise Exception("Failed to create item store")

    async def get_item_store_by_code(self, item_code: str) -> ItemStoreMasterDocument:
        """
        Retrieve a store-specific item record by its unique code.

        Args:
            item_code: Unique identifier for the item

        Returns:
            The matching store-specific item document, or None if not found
        """
        filter = {"tenant_id": self.tenant_id, "store_code": self.store_code, "item_code": item_code}
        return await self.get_one_async(filter)

    async def get_item_store_by_filter_async(
        self, query_filter: dict, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> list[ItemStoreMasterDocument]:
        """
        Retrieve store-specific items matching the specified filter with pagination and sorting.

        This method automatically adds tenant and store filtering to ensure data isolation.

        Args:
            query_filter: MongoDB query filter to select items
            limit: Maximum number of items to return per page
            page: Page number (1-based) to retrieve
            sort: List of tuples containing field name and sort direction

        Returns:
            List of store-specific item documents matching the query parameters
        """
        query_filter["tenant_id"] = self.tenant_id
        query_filter["store_code"] = self.store_code
        logger.debug(f"query_filter: {query_filter} limit: {limit} page: {page} sort: {sort}")
        return await self.get_list_async_with_sort_and_paging(query_filter, limit, page, sort)

    async def update_item_store_async(self, item_code: str, update_data: dict) -> ItemStoreMasterDocument:
        """
        Update specific fields of a store-specific item.

        Args:
            item_code: Unique identifier for the item to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            The updated store-specific item document
        """
        filter = {"tenant_id": self.tenant_id, "store_code": self.store_code, "item_code": item_code}
        success = await self.update_one_async(filter, update_data)
        if success:
            return await self.get_item_store_by_code(item_code)
        else:
            raise Exception(f"Failed to update item store with code {item_code}")

    async def replace_item_store_async(
        self, item_code: str, new_document: ItemStoreMasterDocument
    ) -> ItemStoreMasterDocument:
        """
        Replace an existing store-specific item with a new document.

        Args:
            item_code: Unique identifier for the item to replace
            new_document: New store-specific item document to replace the existing one

        Returns:
            The replaced store-specific item document
        """
        filter = {"tenant_id": self.tenant_id, "store_code": self.store_code, "item_code": item_code}
        success = await self.replace_one_async(filter, new_document)
        if success:
            return new_document
        else:
            raise Exception(f"Failed to replace item store with code {item_code}")

    async def delete_item_store_async(self, item_code: str) -> None:
        """
        Delete a store-specific item from the database.

        Args:
            item_code: Unique identifier for the item to delete

        Returns:
            None
        """
        filter = {"tenant_id": self.tenant_id, "store_code": self.store_code, "item_code": item_code}
        await self.delete_async(filter)

    async def get_item_count_by_filter_async(self, query_filter: dict) -> int:
        """
        Get the count of store-specific items matching the specified filter.

        Args:
            query_filter: MongoDB query filter to count items

        Returns:
            Count of items matching the filter
        """
        query_filter["tenant_id"] = self.tenant_id
        query_filter["store_code"] = self.store_code
        if self.dbcollection is None:
            await self.initialize()
        return await self.dbcollection.count_documents(query_filter)

    def __get_shard_key(self, item_store_doc: ItemStoreMasterDocument) -> str:
        """
        Generate a shard key for the store-specific item document.

        Uses a composite key of tenant ID and store code for sharding.

        Args:
            item_store_doc: Store-specific item document for which to generate a shard key

        Returns:
            String representation of the composite shard key
        """
        keys = []
        keys.append(item_store_doc.tenant_id)
        keys.append(item_store_doc.store_code)
        return self.make_shard_key(keys)
