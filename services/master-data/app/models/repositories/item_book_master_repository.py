# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.documents.item_book_master_document import ItemBookMasterDocument
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.config.settings import settings

from logging import getLogger

logger = getLogger(__name__)


class ItemBookMasterRepository(AbstractRepository[ItemBookMasterDocument]):
    """
    Repository for managing item book master data in the database.

    This class provides specific implementation for CRUD operations on item book data,
    extending the generic functionality provided by AbstractRepository. Item books
    define the hierarchical button layout used in the POS UI for product selection.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str):
        """
        Initialize a new ItemBookMasterRepository instance.

        Args:
            db: MongoDB database instance
            tenant_id: Identifier for the tenant whose data this repository will manage
        """
        super().__init__(settings.DB_COLLECTION_NAME_KEY_PRESET_MASTER, ItemBookMasterDocument, db)
        self.tenant_id = tenant_id

    async def create_item_book_async(self, document: ItemBookMasterDocument) -> ItemBookMasterDocument:
        """
        Create a new item book in the database.

        This method sets the tenant ID and generates a shard key before creating the document.

        Args:
            document: Item book document to create

        Returns:
            The created item book document
        """
        document.tenant_id = self.tenant_id
        document.shard_key = self.__get_shard_key(document)
        success = await self.create_async(document)
        if success:
            return document
        else:
            raise Exception("Failed to create item book")

    async def get_item_book_async(self, item_book_id: str) -> ItemBookMasterDocument:
        """
        Retrieve an item book by its unique ID.

        Args:
            item_book_id: Unique identifier for the item book

        Returns:
            The matching item book document, or None if not found
        """
        return await self.get_one_async(self.__make_query_filter(item_book_id))

    async def get_item_book_by_filter_async(
        self, query_filter: dict, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> list[ItemBookMasterDocument]:
        """
        Retrieve item books matching the specified filter with pagination and sorting.

        This method automatically adds tenant filtering to ensure data isolation.

        Args:
            query_filter: MongoDB query filter to select item books
            limit: Maximum number of item books to return per page
            page: Page number (1-based) to retrieve
            sort: List of tuples containing field name and sort direction

        Returns:
            List of item book documents matching the query parameters
        """
        query_filter["tenant_id"] = self.tenant_id
        logger.debug(f"query_filter: {query_filter} limit: {limit} page: {page} sort: {sort}")
        return await self.get_list_async_with_sort_and_paging(query_filter, limit, page, sort)

    async def update_item_book_async(self, item_book_id: str, update_data: dict) -> ItemBookMasterDocument:
        """
        Update specific fields of an item book.

        Args:
            item_book_id: Unique identifier for the item book to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            The updated item book document
        """
        success = await self.update_one_async(self.__make_query_filter(item_book_id), update_data)
        if success:
            return await self.get_item_book_async(item_book_id)
        else:
            raise Exception(f"Failed to update item book with id {item_book_id}")

    async def replace_item_book_async(
        self, item_book_id: str, new_document: ItemBookMasterDocument
    ) -> ItemBookMasterDocument:
        """
        Replace an existing item book with a new document.

        Args:
            item_book_id: Unique identifier for the item book to replace
            new_document: New item book document to replace the existing one

        Returns:
            The replaced item book document
        """
        success = await self.replace_one_async(self.__make_query_filter(item_book_id), new_document)
        if success:
            return new_document
        else:
            raise Exception(f"Failed to replace item book with id {item_book_id}")

    async def delete_item_book_async(self, item_book_id: str):
        """
        Delete an item book from the database.

        Args:
            item_book_id: Unique identifier for the item book to delete

        Returns:
            None
        """
        return await self.delete_async(self.__make_query_filter(item_book_id))

    async def get_item_book_count_by_filter_async(self, query_filter: dict) -> int:
        """
        Get the count of item books matching the specified filter.

        Args:
            query_filter: MongoDB query filter to count item books

        Returns:
            Count of item books matching the filter
        """
        query_filter["tenant_id"] = self.tenant_id
        if self.dbcollection is None:
            await self.initialize()
        return await self.dbcollection.count_documents(query_filter)

    def __make_query_filter(self, item_book_id: str) -> dict:
        """
        Create a query filter for item book operations based on tenant and item book ID.

        This private method ensures that all queries are scoped to the correct tenant.

        Args:
            item_book_id: Unique identifier for the item book

        Returns:
            Dictionary containing the query filter parameters
        """
        return {"tenant_id": self.tenant_id, "item_book_id": item_book_id}

    def __get_shard_key(self, document: ItemBookMasterDocument) -> str:
        """
        Generate a shard key for the item book document.

        Currently uses only the tenant ID as the sharding key.

        Args:
            document: Item book document for which to generate a shard key

        Returns:
            String representation of the shard key
        """
        keys = []
        keys.append(document.tenant_id)
        return "-".join(keys)
