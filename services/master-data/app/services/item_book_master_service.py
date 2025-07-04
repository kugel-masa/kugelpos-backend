# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from typing import Any
import uuid, datetime

from kugel_common.exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    InvalidRequestDataException,
)
from app.models.documents.item_book_master_document import (
    ItemBookMasterDocument,
    ItemBookCategory,
    ItemBookTab,
    ItemBookButton,
)
from app.models.repositories.item_book_master_repository import ItemBookMasterRepository
from app.models.repositories.item_common_master_repository import ItemCommonMasterRepository
from app.models.repositories.item_store_master_repository import ItemStoreMasterRepository

logger = getLogger(__name__)


class ItemBookMasterService:
    """
    Service class for managing item book master data operations.

    This service provides business logic for creating, retrieving, updating, and deleting
    item books and their hierarchical structure (categories, tabs, buttons).
    An item book represents a collection of items organized into categories and tabs
    for display and selection in the POS interface.
    """

    def __init__(
        self,
        item_book_master_repo: ItemBookMasterRepository,
        item_common_master_repo: ItemCommonMasterRepository,
        item_store_master_repo: ItemStoreMasterRepository,
    ):
        """
        Initialize the ItemBookMasterService with required repositories.

        Args:
            item_book_master_repo: Repository for item book master operations
            item_common_master_repo: Repository for accessing common item data
            item_store_master_repo: Repository for accessing store-specific item data
        """
        self.item_book_master_repo = item_book_master_repo
        self.item_common_master_repo = item_common_master_repo
        self.item_store_master_repo = item_store_master_repo

    async def create_item_book_async(self, title: str, categories: list[dict]) -> ItemBookMasterDocument:
        """
        Create a new item book with the specified title and categories.

        Args:
            title: The title of the item book
            categories: List of category dictionaries to include in the item book

        Returns:
            Newly created ItemBookMasterDocument
        """
        logger.debug(f"Create item book request received for title: {title}")

        item_book_doc = ItemBookMasterDocument()
        item_book_doc.item_book_id = await self.__generate_item_book_id()
        item_book_doc.title = title
        item_book_doc.categories = [ItemBookCategory(**category) for category in categories]
        return await self.item_book_master_repo.create_item_book_async(item_book_doc)

    async def __generate_item_book_id(self) -> str:
        """
        Generate a unique item book ID based on current date and sequence number.

        Returns:
            A unique item book ID in the format YYYYMMDD-NNNN
        """
        current_date = datetime.datetime.now().strftime("%Y%m%d")
        seq = 0
        while True:
            seq += 1
            item_book_id = f"{current_date}-{seq:04d}"
            item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
            if item_book is None:
                return item_book_id

    async def get_item_book_by_id_async(self, item_book_id: str) -> ItemBookMasterDocument:
        """
        Retrieve an item book by its unique ID.

        Args:
            item_book_id: The unique identifier of the item book

        Returns:
            The requested ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If no item book with the given ID exists
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)
        return item_book

    async def get_item_book_detail_by_id_async(self, item_book_id: str) -> ItemBookMasterDocument:
        """
        Retrieve an item book with detailed item information by its unique ID.

        This method enriches the standard item book data with additional details like
        unit prices and descriptions from the item common and store master data.

        Args:
            item_book_id: The unique identifier of the item book

        Returns:
            The requested ItemBookMasterDocument with enriched button data

        Raises:
            DocumentNotFoundException: If no item book with the given ID exists
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        # set unit_price to buttons
        for category in item_book.categories:
            for tab in category.tabs:
                for button in tab.buttons:

                    # get item common price & description
                    item_common = await self.item_common_master_repo.get_item_by_code_async(
                        button.item_code, is_logical_deleted=False, use_cache=False
                    )
                    if not item_common:
                        logger.warning(f"Item with item_code {button.item_code} not found")
                        button.description = "not found"
                        continue
                    else:
                        button.description = item_common.description
                        button.unit_price = item_common.unit_price

                    # get item store price
                    item_store = await self.item_store_master_repo.get_item_store_by_code(button.item_code)
                    if item_store:
                        button.unit_price = item_store.store_price  # override price

        return item_book

    async def get_item_book_all_async(self, limit: int, page: int, sort: list[tuple[str, int]]) -> list:
        """
        Retrieve all item books with pagination and sorting.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)

        Returns:
            List of ItemBookMasterDocument objects
        """
        item_books = await self.item_book_master_repo.get_item_book_by_filter_async({}, limit, page, sort)
        return item_books

    async def get_item_book_all_paginated_async(
        self, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> tuple[list[ItemBookMasterDocument], int]:
        """
        Retrieve all item books with pagination metadata.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction

        Returns:
            Tuple of (list of ItemBookMasterDocument objects, total count)
        """
        item_books = await self.item_book_master_repo.get_item_book_by_filter_async({}, limit, page, sort)
        total_count = await self.item_book_master_repo.get_item_book_count_by_filter_async({})
        return item_books, total_count

    async def update_item_book_async(self, item_book_id: str, update_data: dict) -> ItemBookMasterDocument:
        """
        Update an existing item book with new data.

        Args:
            item_book_id: The unique identifier of the item book to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If no item book with the given ID exists
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)
        return await self.item_book_master_repo.update_item_book_async(item_book_id, update_data)

    async def delete_item_book_async(self, item_book_id: str) -> None:
        """
        Delete an item book from the database.

        Args:
            item_book_id: The unique identifier of the item book to delete

        Raises:
            DocumentNotFoundException: If no item book with the given ID exists
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)
        await self.item_book_master_repo.delete_item_book_async(item_book_id)

    async def add_category_to_item_book_async(self, item_book_id: str, category: dict) -> ItemBookMasterDocument:
        """
        Add a new category to an existing item book.

        Args:
            item_book_id: The unique identifier of the target item book
            category: Dictionary containing the category data to add

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If the item book is not found
            DocumentAlreadyExistsException: If a category with the same number already exists
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        target_category = next(
            (
                item_book_category
                for item_book_category in item_book.categories
                if item_book_category.category_number == category["category_number"]
            ),
            None,
        )
        if target_category is not None:
            message = f"category with category_number {category['category_number']} already exists in item_book"
            raise DocumentAlreadyExistsException(message, logger)

        item_book.categories.append(ItemBookCategory(**category))
        return await self.item_book_master_repo.replace_item_book_async(item_book_id, item_book)

    async def update_category_in_item_book_async(
        self, item_book_id: str, category_number: int, update_data: dict
    ) -> ItemBookMasterDocument:
        """
        Update a category within an item book.

        Args:
            item_book_id: The unique identifier of the item book
            category_number: The number identifying the category to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If the item book or category is not found
            InvalidRequestDataException: If attempting to move to a category number that already exists
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        target_category = next(
            (
                item_book_category
                for item_book_category in item_book.categories
                if item_book_category.category_number == category_number
            ),
            None,
        )
        if target_category is None:
            message = f"category with category_number {category_number} not found in item_book"
            raise DocumentNotFoundException(message, logger)

        if category_number != update_data.get("category_number"):
            # case move category_number to new category_number
            destination_category = next(
                (
                    item_book_category
                    for item_book_category in item_book.categories
                    if item_book_category.category_number == update_data.get("category_number")
                ),
                None,
            )
            if destination_category is not None:
                message = (
                    f"category with category_number {update_data.get('category_number')} already exists in item_book"
                )
                raise InvalidRequestDataException(message, logger)

        # update category
        target_category.category_number = (
            update_data.get("category_number")
            if update_data.get("category_number")
            else target_category.category_number
        )
        target_category.title = update_data.get("title") if update_data.get("title") else target_category.title
        target_category.color = update_data.get("color") if update_data.get("color") else target_category.color
        target_category.tabs = (
            [ItemBookTab(**tab) for tab in update_data.get("tabs")] if update_data.get("tabs") else target_category.tabs
        )
        return await self.item_book_master_repo.replace_item_book_async(item_book_id, item_book)

    async def delete_category_from_item_book_async(
        self, item_book_id: str, category_number: int
    ) -> ItemBookMasterDocument:
        """
        Delete a category from an item book.

        Args:
            item_book_id: The unique identifier of the item book
            category_number: The number identifying the category to delete

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If the item book or category is not found
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        target_category = next(
            (
                item_book_category
                for item_book_category in item_book.categories
                if item_book_category.category_number == category_number
            ),
            None,
        )
        if target_category is None:
            message = f"category with category_number {category_number} not found in item_book"
            raise DocumentNotFoundException(message, logger)

        item_book.categories = [
            item_book_category
            for item_book_category in item_book.categories
            if item_book_category.category_number != category_number
        ]
        return await self.item_book_master_repo.replace_item_book_async(item_book_id, item_book)

    async def add_tab_to_category_in_item_book_async(
        self, item_book_id: str, category_number: int, tab: dict
    ) -> ItemBookMasterDocument:
        """
        Add a new tab to a category within an item book.

        Args:
            item_book_id: The unique identifier of the item book
            category_number: The number identifying the target category
            tab: Dictionary containing the tab data to add

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If the item book or category is not found
            DocumentAlreadyExistsException: If a tab with the same number already exists
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        target_category = next(
            (
                item_book_category
                for item_book_category in item_book.categories
                if item_book_category.category_number == category_number
            ),
            None,
        )
        if target_category is None:
            message = f"category with category_number {category_number} not found in item_book"
            raise DocumentNotFoundException(message, logger)

        target_tab = next(
            (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab["tab_number"]),
            None,
        )
        if target_tab is not None:
            message = f"tab with tab_number {tab['tab_number']} already exists in category"
            raise DocumentAlreadyExistsException(message, logger)

        target_category.tabs.append(ItemBookTab(**tab))
        return await self.item_book_master_repo.replace_item_book_async(item_book_id, item_book)

    async def update_tab_in_category_in_item_book_async(
        self, item_book_id: str, category_number: int, tab_number: int, update_data: dict
    ) -> ItemBookMasterDocument:
        """
        Update a tab within a category in an item book.

        Args:
            item_book_id: The unique identifier of the item book
            category_number: The number identifying the category
            tab_number: The number identifying the tab to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If the item book, category, or tab is not found
            InvalidRequestDataException: If attempting to move to a tab number that already exists
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        target_category = next(
            (
                item_book_category
                for item_book_category in item_book.categories
                if item_book_category.category_number == category_number
            ),
            None,
        )
        if target_category is None:
            message = f"category with category_number {category_number} not found in item_book"
            raise DocumentNotFoundException(message, logger)

        target_tab = next(
            (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number), None
        )
        if target_tab is None:
            message = f"tab with tab_number {tab_number} not found in category"
            raise DocumentNotFoundException(message, logger)

        if tab_number != update_data.get("tab_number"):
            # case move tab_number to new tab_number
            destination_tab = next(
                (
                    item_book_tab
                    for item_book_tab in target_category.tabs
                    if item_book_tab.tab_number == update_data.get("tab_number")
                ),
                None,
            )
            if destination_tab is not None:
                message = f"tab with tab_number {update_data.get('tab_number')} already exists in category"
                raise InvalidRequestDataException(message, logger)

        target_tab.tab_number = (
            update_data.get("tab_number") if update_data.get("tab_number") else target_tab.tab_number
        )
        target_tab.title = update_data.get("title") if update_data.get("title") else target_tab.title
        target_tab.color = update_data.get("color") if update_data.get("color") else target_tab.color
        target_tab.buttons = (
            [ItemBookButton(**button) for button in update_data.get("buttons")]
            if update_data.get("buttons")
            else target_tab.buttons
        )

        return await self.item_book_master_repo.replace_item_book_async(item_book_id, item_book)

    async def delete_tab_from_category_in_item_book_async(
        self, item_book_id: str, category_number: int, tab_number: int
    ) -> ItemBookMasterDocument:
        """
        Delete a tab from a category in an item book.

        Args:
            item_book_id: The unique identifier of the item book
            category_number: The number identifying the category
            tab_number: The number identifying the tab to delete

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If the item book, category, or tab is not found
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        target_category = next(
            (
                item_book_category
                for item_book_category in item_book.categories
                if item_book_category.category_number == category_number
            ),
            None,
        )
        if target_category is None:
            message = f"category with category_number {category_number} not found in item_book"
            raise DocumentNotFoundException(message, logger)

        target_tab = next(
            (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number), None
        )
        if target_tab is None:
            message = f"tab with tab_number {tab_number} not found in category"
            raise DocumentNotFoundException(message, logger)

        target_category.tabs = [
            item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number != tab_number
        ]

        return await self.item_book_master_repo.replace_item_book_async(item_book_id, item_book)

    async def add_button_to_tab_in_category_in_item_book_async(
        self, item_book_id: str, category_number: int, tab_number: int, button: dict
    ) -> ItemBookMasterDocument:
        """
        Add a new button to a tab within a category in an item book.

        Args:
            item_book_id: The unique identifier of the item book
            category_number: The number identifying the category
            tab_number: The number identifying the tab
            button: Dictionary containing the button data to add

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If the item book, category, or tab is not found
            DocumentAlreadyExistsException: If a button at the same position already exists
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        target_category = next(
            (
                item_book_category
                for item_book_category in item_book.categories
                if item_book_category.category_number == category_number
            ),
            None,
        )
        if target_category is None:
            message = f"category with category_number {category_number} not found in item_book"
            raise DocumentNotFoundException(message, logger)

        target_tab = next(
            (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number), None
        )
        if target_tab is None:
            message = f"tab with tab_number {tab_number} not found in category"
            raise DocumentNotFoundException(message, logger)

        target_button = next(
            (
                item_book_button
                for item_book_button in target_tab.buttons
                if item_book_button.pos_x == button["pos_x"] and item_book_button.pos_y == button["pos_y"]
            ),
            None,
        )
        if target_button is not None:
            message = f"button with pos_x {button['pos_x']} and pos_y {button['pos_y']} already exists in tab"
            raise DocumentAlreadyExistsException(message, logger)

        target_tab.buttons.append(ItemBookButton(**button))

        return await self.item_book_master_repo.replace_item_book_async(item_book_id, item_book)

    async def update_button_in_tab_in_category_in_item_book_async(
        self, item_book_id: str, category_number: int, tab_number: int, pos_x: int, pos_y: int, update_data: dict
    ) -> ItemBookMasterDocument:
        """
        Update a button within a tab in a category in an item book.

        Args:
            item_book_id: The unique identifier of the item book
            category_number: The number identifying the category
            tab_number: The number identifying the tab
            pos_x: The x-coordinate position of the button to update
            pos_y: The y-coordinate position of the button to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If the item book, category, tab, or button is not found
            InvalidRequestDataException: If attempting to move to a position that already has a button
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        target_category = next(
            (
                item_book_category
                for item_book_category in item_book.categories
                if item_book_category.category_number == category_number
            ),
            None,
        )
        if target_category is None:
            message = f"category with category_number {category_number} not found in item_book"
            raise DocumentNotFoundException(message, logger)

        target_tab = next(
            (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number), None
        )
        if target_tab is None:
            message = f"tab with tab_number {tab_number} not found in category"
            raise DocumentNotFoundException(message, logger)

        target_button = next(
            (
                item_book_button
                for item_book_button in target_tab.buttons
                if item_book_button.pos_x == pos_x and item_book_button.pos_y == pos_y
            ),
            None,
        )
        if target_button is None:
            message = f"button with pos_x {pos_x} and pos_y {pos_y} not found in tab"
            raise DocumentNotFoundException(message, logger)

        if pos_x != update_data.get("pos_x") or pos_y != update_data.get("pos_y"):
            # case move button to new position
            destination_button = next(
                (
                    item_book_button
                    for item_book_button in target_tab.buttons
                    if item_book_button.pos_x == update_data.get("pos_x")
                    and item_book_button.pos_y == update_data.get("pos_y")
                ),
                None,
            )
            if destination_button is not None:
                message = f"button with pos_x {update_data.get('pos_x')} and pos_y {update_data.get('pos_y')} already exists in tab"
                raise InvalidRequestDataException(message, logger)

        target_button.pos_x = update_data.get("pos_x") if update_data.get("pos_x") else target_button.pos_x
        target_button.pos_y = update_data.get("pos_y") if update_data.get("pos_y") else target_button.pos_y
        target_button.size = update_data.get("size") if update_data.get("size") else target_button.size
        target_button.image_url = (
            update_data.get("image_url") if update_data.get("image_url") else target_button.image_url
        )
        target_button.color_text = (
            update_data.get("color_text") if update_data.get("color_text") else target_button.color_text
        )
        target_button.item_code = (
            update_data.get("item_code") if update_data.get("item_code") else target_button.item_code
        )

        return await self.item_book_master_repo.replace_item_book_async(item_book_id, item_book)

    async def delete_button_from_tab_in_category_in_item_book_async(
        self, item_book_id: str, category_number: int, tab_number: int, pos_x: int, pos_y: int
    ) -> ItemBookMasterDocument:
        """
        Delete a button from a tab in a category in an item book.

        Args:
            item_book_id: The unique identifier of the item book
            category_number: The number identifying the category
            tab_number: The number identifying the tab
            pos_x: The x-coordinate position of the button to delete
            pos_y: The y-coordinate position of the button to delete

        Returns:
            Updated ItemBookMasterDocument

        Raises:
            DocumentNotFoundException: If the item book, category, tab, or button is not found
        """
        item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
        if item_book is None:
            message = f"item book with item_book_id {item_book_id} not found"
            raise DocumentNotFoundException(message, logger)

        target_category = next(
            (
                item_book_category
                for item_book_category in item_book.categories
                if item_book_category.category_number == category_number
            ),
            None,
        )
        if target_category is None:
            message = f"category with category_number {category_number} not found in item_book"
            raise DocumentNotFoundException(message, logger)

        target_tab = next(
            (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number), None
        )
        if target_tab is None:
            message = f"tab with tab_number {tab_number} not found in category"
            raise DocumentNotFoundException(message, logger)

        target_button = next(
            (
                item_book_button
                for item_book_button in target_tab.buttons
                if item_book_button.pos_x == pos_x and item_book_button.pos_y == pos_y
            ),
            None,
        )
        if target_button is None:
            message = f"button with pos_x {pos_x} and pos_y {pos_y} not found in tab"
            raise DocumentNotFoundException(message, logger)

        target_tab.buttons = [
            item_book_button
            for item_book_button in target_tab.buttons
            if item_book_button.pos_x != pos_x and item_book_button.pos_y != pos_y
        ]

        return await self.item_book_master_repo.replace_item_book_async(item_book_id, item_book)
