# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.documents.item_book_master_document import ItemBookMasterDocument
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import RepositoryException
from kugel_common.utils.misc import get_app_time
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
        super().__init__(settings.DB_COLLECTION_NAME_ITEM_BOOK_MASTER, ItemBookMasterDocument, db)
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

    # ------------------------------------------------------------------
    # Atomic writes to the nested structure (categories, tabs, buttons)
    #
    # Reading the whole book, changing it in memory and replacing it loses
    # whatever another request wrote between the read and the replace. These
    # methods change only the one element concerned, through $push, $pull or
    # a positional $set, so concurrent writes to different numbers or
    # positions do not overwrite each other.
    #
    # The preconditions (the parent exists, the number or position is free)
    # are part of the filter: an update whose arrayFilters match nothing
    # silently does nothing, so without them a write that did not happen
    # would look like one that did. Each method returns False when a
    # precondition no longer held at write time.
    # ------------------------------------------------------------------

    async def __apply_nested_update_async(
        self, item_book_id: str, conditions: list[dict], update: dict, array_filters: list[dict] = None
    ) -> bool:
        """
        Apply an atomic partial update to the nested structure of an item book.

        Args:
            item_book_id: Unique identifier for the item book to update
            conditions: Precondition clauses ANDed onto the tenant/item_book filter
            update: MongoDB update document ($push / $pull / $set)
            array_filters: Positional array filter identifiers used by the update

        Returns:
            True when a document matched every precondition and the update was applied,
            False when a precondition no longer held (a concurrent write changed it)
        """
        if self.dbcollection is None:
            await self.initialize()

        query_filter = self.__make_query_filter(item_book_id)
        if conditions:
            query_filter["$and"] = conditions

        # The replace path stamped updated_at; keep doing so.
        update.setdefault("$set", {})["updated_at"] = get_app_time()

        try:
            response = await self.dbcollection.update_one(
                query_filter, update, array_filters=array_filters, session=self.session
            )
        except Exception as e:
            message = f"Failed to update nested structure of item book: item_book_id->{item_book_id}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

        # matched_count, not modified_count: setting a value it already had
        # modifies nothing, and would read as a broken precondition.
        return response.matched_count == 1

    async def __empty_null_list_async(
        self, item_book_id: str, match: dict, path: str, array_filters: list[dict] = None
    ) -> None:
        """
        Turn a stored null child list into an empty one, so that $push can append to it.

        A book written before null lists were refused can still hold one. The
        model reads it as empty, but $push into a null field fails. The filter
        matches only when the list really is null, so otherwise nothing is written.

        Args:
            item_book_id: Unique identifier for the item book
            match: Filter clause requiring the parents of the list to exist, so that
                the positional path below always resolves
            path: Dotted path of the list, using the identifiers in array_filters
            array_filters: Filters naming the parent elements and requiring the list to be null
        """
        if self.dbcollection is None:
            await self.initialize()
        try:
            await self.dbcollection.update_one(
                {**self.__make_query_filter(item_book_id), **match},
                {"$set": {path: []}},
                array_filters=array_filters,
                session=self.session,
            )
        except Exception as e:
            message = f"Failed to normalise a null list in item book: item_book_id->{item_book_id}"
            raise RepositoryException(message, self.collection_name, logger, e) from e

    async def add_category_async(self, item_book_id: str, category: dict) -> bool:
        """Append a category, unless one with the same category_number already exists."""
        await self.__empty_null_list_async(item_book_id, {"categories": None}, "categories")
        return await self.__apply_nested_update_async(
            item_book_id,
            conditions=[{"categories.category_number": {"$ne": category["category_number"]}}],
            update={"$push": {"categories": category}},
        )

    async def set_category_fields_async(self, item_book_id: str, category_number: int, fields: dict) -> bool:
        """
        Set fields on one category in place.

        ``fields`` holds only the values the request gives, so a concurrent write
        inside the same category (a tab or a button) is not overwritten.
        """
        conditions = [{"categories.category_number": category_number}]
        destination_number = fields.get("category_number")
        if destination_number is not None and destination_number != category_number:
            conditions.append({"categories.category_number": {"$ne": destination_number}})
        return await self.__apply_nested_update_async(
            item_book_id,
            conditions=conditions,
            update={"$set": {f"categories.$[category].{name}": value for name, value in fields.items()}},
            array_filters=[{"category.category_number": category_number}],
        )

    async def delete_category_async(self, item_book_id: str, category_number: int) -> bool:
        """Remove one category by its number."""
        return await self.__apply_nested_update_async(
            item_book_id,
            conditions=[{"categories.category_number": category_number}],
            update={"$pull": {"categories": {"category_number": category_number}}},
        )

    async def add_tab_async(self, item_book_id: str, category_number: int, tab: dict) -> bool:
        """Append a tab to a category, unless one with the same tab_number already exists."""
        await self.__empty_null_list_async(
            item_book_id,
            {"categories.category_number": category_number},
            "categories.$[category].tabs",
            [{"category.category_number": category_number, "category.tabs": None}],
        )
        return await self.__apply_nested_update_async(
            item_book_id,
            conditions=[
                {
                    "categories": {
                        "$elemMatch": {
                            "category_number": category_number,
                            "tabs.tab_number": {"$ne": tab["tab_number"]},
                        }
                    }
                }
            ],
            update={"$push": {"categories.$[category].tabs": tab}},
            array_filters=[{"category.category_number": category_number}],
        )

    async def set_tab_fields_async(
        self, item_book_id: str, category_number: int, tab_number: int, fields: dict
    ) -> bool:
        """Set fields on one tab in place."""
        tab_conditions = [{"tabs.tab_number": tab_number}]
        destination_number = fields.get("tab_number")
        if destination_number is not None and destination_number != tab_number:
            tab_conditions.append({"tabs.tab_number": {"$ne": destination_number}})
        return await self.__apply_nested_update_async(
            item_book_id,
            conditions=[{"categories": {"$elemMatch": {"category_number": category_number, "$and": tab_conditions}}}],
            update={"$set": {f"categories.$[category].tabs.$[tab].{name}": value for name, value in fields.items()}},
            array_filters=[
                {"category.category_number": category_number},
                {"tab.tab_number": tab_number},
            ],
        )

    async def delete_tab_async(self, item_book_id: str, category_number: int, tab_number: int) -> bool:
        """Remove one tab from a category."""
        return await self.__apply_nested_update_async(
            item_book_id,
            conditions=[
                {"categories": {"$elemMatch": {"category_number": category_number, "tabs.tab_number": tab_number}}}
            ],
            update={"$pull": {"categories.$[category].tabs": {"tab_number": tab_number}}},
            array_filters=[{"category.category_number": category_number}],
        )

    async def add_button_async(self, item_book_id: str, category_number: int, tab_number: int, button: dict) -> bool:
        """
        Append a button to a tab, unless one already occupies the same position.

        Occupancy is a condition on the (pos_x, pos_y) pair: separate clauses per
        axis would also refuse a free position that only shares a row or a column
        with an existing button.
        """
        await self.__empty_null_list_async(
            item_book_id,
            {"categories": {"$elemMatch": {"category_number": category_number, "tabs.tab_number": tab_number}}},
            "categories.$[category].tabs.$[tab].buttons",
            [{"category.category_number": category_number}, {"tab.tab_number": tab_number, "tab.buttons": None}],
        )
        return await self.__apply_nested_update_async(
            item_book_id,
            conditions=[self.__tab_condition(category_number, tab_number, self.__free_position(button))],
            update={"$push": {"categories.$[category].tabs.$[tab].buttons": button}},
            array_filters=[
                {"category.category_number": category_number},
                {"tab.tab_number": tab_number},
            ],
        )

    async def set_button_fields_async(
        self, item_book_id: str, category_number: int, tab_number: int, pos_x: int, pos_y: int, fields: dict
    ) -> bool:
        """Set fields on one button in place."""
        button_conditions = [{"buttons": {"$elemMatch": {"pos_x": pos_x, "pos_y": pos_y}}}]
        destination_x = fields.get("pos_x", pos_x)
        destination_y = fields.get("pos_y", pos_y)
        if (destination_x, destination_y) != (pos_x, pos_y):
            button_conditions.append(self.__free_position({"pos_x": destination_x, "pos_y": destination_y}))
        return await self.__apply_nested_update_async(
            item_book_id,
            conditions=[self.__tab_condition(category_number, tab_number, *button_conditions)],
            update={
                "$set": {
                    f"categories.$[category].tabs.$[tab].buttons.$[button].{name}": value
                    for name, value in fields.items()
                }
            },
            array_filters=[
                {"category.category_number": category_number},
                {"tab.tab_number": tab_number},
                {"button.pos_x": pos_x, "button.pos_y": pos_y},
            ],
        )

    async def delete_button_async(
        self, item_book_id: str, category_number: int, tab_number: int, pos_x: int, pos_y: int
    ) -> bool:
        """Remove the single button at the given position."""
        return await self.__apply_nested_update_async(
            item_book_id,
            conditions=[
                self.__tab_condition(
                    category_number, tab_number, {"buttons": {"$elemMatch": {"pos_x": pos_x, "pos_y": pos_y}}}
                )
            ],
            update={"$pull": {"categories.$[category].tabs.$[tab].buttons": {"pos_x": pos_x, "pos_y": pos_y}}},
            array_filters=[
                {"category.category_number": category_number},
                {"tab.tab_number": tab_number},
            ],
        )

    def __tab_condition(self, category_number: int, tab_number: int, *tab_clauses: dict) -> dict:
        """Build a filter clause selecting one tab inside one category."""
        return {
            "categories": {
                "$elemMatch": {
                    "category_number": category_number,
                    "tabs": {"$elemMatch": {"tab_number": tab_number, "$and": list(tab_clauses)}},
                }
            }
        }

    def __free_position(self, button: dict) -> dict:
        """Build a filter clause asserting that no button occupies the given position."""
        return {"buttons": {"$not": {"$elemMatch": {"pos_x": button["pos_x"], "pos_y": button["pos_y"]}}}}

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
