# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from typing import Any
import uuid, datetime

from kugel_common.exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    DuplicateKeyException,
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

# How often a nested write re-reads the book when a concurrent write broke the
# precondition it had validated. Writes to different numbers or positions get
# through on the first attempt; only two requests claiming the same number or
# position come back, and the re-read then refuses the loser as a duplicate.
NESTED_WRITE_ATTEMPTS = 3


class ItemBookMasterService:
    """
    Service class for managing item book master data operations.

    This service provides business logic for creating, retrieving, updating, and deleting
    item books and their hierarchical structure (categories, tabs, buttons).
    An item book represents a collection of items organized into categories and tabs
    for display and selection in the POS interface.
    """

    ITEM_BOOK_ID_ATTEMPTS = 20

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
        item_book_doc.title = title
        item_book_doc.categories = [ItemBookCategory(**category) for category in categories]
        # The id is the first free number of the day, so two books created at the
        # same moment can pick the same one; the unique index refuses the second,
        # which then takes the next free number.
        for attempt in range(1, self.ITEM_BOOK_ID_ATTEMPTS + 1):
            item_book_doc.item_book_id = await self.__generate_item_book_id()
            try:
                return await self.item_book_master_repo.create_item_book_async(item_book_doc)
            except DuplicateKeyException:
                if attempt == self.ITEM_BOOK_ID_ATTEMPTS:
                    raise
                logger.info(f"Item book id {item_book_doc.item_book_id} was taken meanwhile; retrying")

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
                        # Not in the item master: no price and no name, rather than
                        # the string "not found" (a price of 0 would read as a free item).
                        logger.warning(f"Item with item_code {button.item_code} not found")
                        button.description = None
                        button.unit_price = None
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

    async def __apply_nested_write_async(self, item_book_id: str, write) -> ItemBookMasterDocument:
        """
        Run one nested write (category / tab / button) against a freshly read item book.

        ``write`` validates the request against the document it is handed and then
        performs the change through an atomic repository operation, returning False
        when the precondition it validated no longer held at write time. Only in
        that case do we read again and re-validate — the re-read is what turns a
        lost race into the error the request deserves (already exists / not found).

        These writes used to read the whole book, change it and replace it, so
        whatever another request wrote in between was lost. Validation still runs
        against the document as read, so the errors and their messages are unchanged.

        Args:
            item_book_id: The unique identifier of the item book to write to
            write: Async callable taking the item book and returning whether it was written

        Returns:
            The item book as stored after the write

        Raises:
            DocumentNotFoundException: If the item book is not found
        """
        for _ in range(NESTED_WRITE_ATTEMPTS):
            item_book = await self.item_book_master_repo.get_item_book_async(item_book_id)
            if item_book is None:
                message = f"item book with item_book_id {item_book_id} not found"
                raise DocumentNotFoundException(message, logger)

            if await write(item_book):
                written = await self.item_book_master_repo.get_item_book_async(item_book_id)
                if written is None:
                    message = f"item book with item_book_id {item_book_id} not found"
                    raise DocumentNotFoundException(message, logger)
                return written

        # Reached only when every re-read validated and the precondition broke again
        # each time right before the write. Same outcome (500) as a replace that failed.
        raise Exception(f"Failed to update item book with id {item_book_id}")

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
        async def write(item_book: ItemBookMasterDocument) -> bool:
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

            return await self.item_book_master_repo.add_category_async(
                item_book_id, ItemBookCategory(**category).model_dump()
            )

        return await self.__apply_nested_write_async(item_book_id, write)

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
        async def write(item_book: ItemBookMasterDocument) -> bool:
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
                        f"category with category_number {update_data.get('category_number')} "
                        "already exists in item_book"
                    )
                    raise InvalidRequestDataException(message, logger)

            # Write only the fields the request gives. Writing the rest back from the
            # document as read would undo a concurrent update to the same category.
            fields = {}
            if update_data.get("category_number"):
                fields["category_number"] = update_data.get("category_number")
            if update_data.get("title"):
                fields["title"] = update_data.get("title")
            if update_data.get("color"):
                fields["color"] = update_data.get("color")
            if update_data.get("tabs"):
                fields["tabs"] = [ItemBookTab(**tab).model_dump() for tab in update_data.get("tabs")]
            if not fields:
                return True

            return await self.item_book_master_repo.set_category_fields_async(
                item_book_id, category_number, fields
            )

        return await self.__apply_nested_write_async(item_book_id, write)

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
        async def write(item_book: ItemBookMasterDocument) -> bool:
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

            return await self.item_book_master_repo.delete_category_async(item_book_id, category_number)

        return await self.__apply_nested_write_async(item_book_id, write)

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
        async def write(item_book: ItemBookMasterDocument) -> bool:
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
                (
                    item_book_tab
                    for item_book_tab in target_category.tabs
                    if item_book_tab.tab_number == tab["tab_number"]
                ),
                None,
            )
            if target_tab is not None:
                message = f"tab with tab_number {tab['tab_number']} already exists in category"
                raise DocumentAlreadyExistsException(message, logger)

            return await self.item_book_master_repo.add_tab_async(
                item_book_id, category_number, ItemBookTab(**tab).model_dump()
            )

        return await self.__apply_nested_write_async(item_book_id, write)

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
        async def write(item_book: ItemBookMasterDocument) -> bool:
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
                (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number),
                None,
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

            # Write only the fields the request gives (see update_category).
            fields = {}
            if update_data.get("tab_number"):
                fields["tab_number"] = update_data.get("tab_number")
            if update_data.get("title"):
                fields["title"] = update_data.get("title")
            if update_data.get("color"):
                fields["color"] = update_data.get("color")
            if update_data.get("buttons"):
                fields["buttons"] = [ItemBookButton(**button).model_dump() for button in update_data.get("buttons")]
            if not fields:
                return True

            return await self.item_book_master_repo.set_tab_fields_async(
                item_book_id, category_number, tab_number, fields
            )

        return await self.__apply_nested_write_async(item_book_id, write)

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
        async def write(item_book: ItemBookMasterDocument) -> bool:
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
                (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number),
                None,
            )
            if target_tab is None:
                message = f"tab with tab_number {tab_number} not found in category"
                raise DocumentNotFoundException(message, logger)

            return await self.item_book_master_repo.delete_tab_async(item_book_id, category_number, tab_number)

        return await self.__apply_nested_write_async(item_book_id, write)

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
        async def write(item_book: ItemBookMasterDocument) -> bool:
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
                (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number),
                None,
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

            return await self.item_book_master_repo.add_button_async(
                item_book_id, category_number, tab_number, ItemBookButton(**button).model_dump()
            )

        return await self.__apply_nested_write_async(item_book_id, write)

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
        async def write(item_book: ItemBookMasterDocument) -> bool:
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
                (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number),
                None,
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
                    message = (
                        f"button with pos_x {update_data.get('pos_x')} and "
                        f"pos_y {update_data.get('pos_y')} already exists in tab"
                    )
                    raise InvalidRequestDataException(message, logger)

            # Coordinates count from 0, so 0 is a position, not "not given": a truthiness
            # test kept a button out of the first row and column. Write only the fields
            # the request gives (see update_category).
            fields = {}
            if update_data.get("pos_x") is not None:
                fields["pos_x"] = update_data.get("pos_x")
            if update_data.get("pos_y") is not None:
                fields["pos_y"] = update_data.get("pos_y")
            if update_data.get("size"):
                fields["size"] = update_data.get("size")
            if update_data.get("image_url"):
                fields["image_url"] = update_data.get("image_url")
            if update_data.get("color_text"):
                fields["color_text"] = update_data.get("color_text")
            if update_data.get("item_code"):
                fields["item_code"] = update_data.get("item_code")
            if not fields:
                return True

            return await self.item_book_master_repo.set_button_fields_async(
                item_book_id, category_number, tab_number, pos_x, pos_y, fields
            )

        return await self.__apply_nested_write_async(item_book_id, write)

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
        async def write(item_book: ItemBookMasterDocument) -> bool:
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
                (item_book_tab for item_book_tab in target_category.tabs if item_book_tab.tab_number == tab_number),
                None,
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

            # Remove only the button at (pos_x, pos_y). A condition per axis would also
            # take every button sharing its row or its column.
            return await self.item_book_master_repo.delete_button_async(
                item_book_id, category_number, tab_number, pos_x, pos_y
            )

        return await self.__apply_nested_write_async(item_book_id, write)
