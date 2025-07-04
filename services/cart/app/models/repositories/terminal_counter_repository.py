# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from motor.motor_asyncio import AsyncIOMotorDatabase
from logging import getLogger
import sys
import threading

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import CannotCreateException, UpdateNotWorkException, CannotDeleteException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.terminal_counter_document import TerminalCounterDocument
from app.config.settings import settings

logger = getLogger(__name__)

lock = threading.Lock()


def make_terminal_id(tenant_id: str, store_code: str, terminal_no: int) -> str:
    """
    Generate a unique terminal identifier by combining tenant, store, and terminal number.

    Args:
        tenant_id: The tenant identifier
        store_code: The store code
        terminal_no: The terminal number

    Returns:
        str: A unique terminal identifier in the format "{tenant_id}-{store_code}-{terminal_no}"
    """
    return f"{tenant_id}-{store_code}-{terminal_no}"


class TerminalCounterRepository(AbstractRepository[TerminalCounterDocument]):
    """
    Repository for managing terminal-specific counters.

    This class provides methods to create, retrieve, update, and manage numeric
    counters associated with a terminal, such as receipt numbers, transaction numbers,
    or other sequence generators.
    """

    def __init__(self, db: AsyncIOMotorDatabase, terminal_info: TerminalInfoDocument):
        """
        Initialize the repository with database connection and terminal information.

        Args:
            db: Database connection object
            terminal_info: Terminal information document containing tenant, store, and terminal details
        """
        super().__init__(settings.DB_COLLECTION_NAME_TERMINAL_COUTER, TerminalCounterDocument, db)
        self.terminal_info = terminal_info

    async def numbering_count(self, countType: str, start_value: int = 1, end_value: int = sys.maxsize) -> int:
        """
        Generate or increment a counter of the specified type for the current terminal.

        This method is thread-safe using a lock to prevent race conditions when
        multiple requests are incrementing the same counter.

        Args:
            countType: Type of counter to increment (e.g., "receipt", "transaction")
            start_value: Value to start from if counter doesn't exist
            end_value: Maximum value before resetting to start_value

        Returns:
            int: The new counter value after incrementing
        """
        # lock the method
        with lock:
            logger.debug(f"numbering_count: countType->{countType}, start_value->{start_value}, end_value->{end_value}")
            return await self.__numbering_count_async(countType, start_value, end_value)

    async def __numbering_count_async(self, countType: str, start_value: int, end_value: int) -> int:
        """
        Internal implementation of the counter increment logic.

        Retrieves the counter document, increments the specified counter, and updates
        the document in the database.

        Args:
            countType: Type of counter to increment
            start_value: Value to start from if counter doesn't exist
            end_value: Maximum value before resetting to start_value

        Returns:
            int: The new counter value after incrementing
        """
        tenant_id = self.terminal_info.tenant_id
        store_code = self.terminal_info.store_code
        terminal_no = self.terminal_info.terminal_no

        # first get the counter document for the terminal
        terminal_id = make_terminal_id(tenant_id=tenant_id, store_code=store_code, terminal_no=terminal_no)
        counter = await self.__get_counter_async(terminal_id)

        # if counter does not exist, create one
        if counter is None:
            counter = await self.__create_counter_async(terminal_id)

        # increment the counter in range [start_value, end_value]
        if countType in counter.count_dic:
            current_value = counter.count_dic[countType]
            if current_value < end_value:
                counter.count_dic[countType] += 1
            else:
                counter.count_dic[countType] = start_value
        else:
            counter.count_dic[countType] = start_value

        # update the counter document
        target_field = f"count_dic.{countType}"
        new_values = {target_field: counter.count_dic[countType]}
        await self.__update_counter_async(terminal_id, new_values)

        # return the counter value
        return counter.count_dic[countType]

    async def __create_counter_async(self, terminal_id: str):
        """
        Create a new counter document for the specified terminal ID.

        Args:
            terminal_id: Unique identifier for the terminal

        Returns:
            TerminalCounterDocument: The newly created counter document

        Raises:
            CannotCreateException: If the document could not be created in the database
        """
        counter = TerminalCounterDocument(terminal_id=terminal_id)
        counter.shard_key = terminal_id

        result = await self.create_async(counter)
        if not result:
            message = "Failed to create counter"
            raise CannotCreateException(message, self.collection_name, counter, logger)
        return counter

    async def __get_counter_async(self, terminal_id: str) -> TerminalCounterDocument:
        """
        Retrieve the counter document for a specific terminal ID.

        Args:
            terminal_id: Unique identifier for the terminal

        Returns:
            TerminalCounterDocument: The retrieved counter document, or None if not found
        """
        search_dict = {"terminal_id": terminal_id}
        doc = await self.get_one_async(search_dict)
        if doc is None:
            return None
        return doc

    async def __replace_counter_async(self, counter: TerminalCounterDocument) -> bool:
        """
        Replace an entire counter document in the database.

        Args:
            counter: The counter document to replace the existing one with

        Returns:
            bool: True if the replacement was successful

        Raises:
            UpdateNotWorkException: If the document could not be replaced
        """
        result = await self.replace_one_async({"terminal_id": counter.terminal_id}, counter)
        if not result:
            message = "document not replaced"
            raise UpdateNotWorkException(message, self.collection_name, counter.terminal_id, logger)
        return True

    async def __update_counter_async(self, terminal_id: str, new_values: dict) -> bool:
        """
        Update specific fields in a counter document.

        Args:
            terminal_id: Unique identifier for the terminal
            new_values: Dictionary of fields to update with their new values

        Returns:
            bool: True if the update was successful

        Raises:
            UpdateNotWorkException: If the document could not be updated
        """
        result = await self.update_one_async({"terminal_id": terminal_id}, new_values)
        if not result:
            message = "document not updated"
            raise UpdateNotWorkException(message, self.collection_name, terminal_id, logger)
        return True

    async def __delete_counter_async(self, terminal_id: str) -> bool:
        """
        Delete a counter document from the database.

        Args:
            terminal_id: Unique identifier for the terminal whose counter should be deleted

        Returns:
            bool: True if the deletion was successful

        Raises:
            CannotDeleteException: If the document could not be deleted
        """
        search_dict = {"terminal_id": terminal_id}
        result = await self.delete_async(search_dict)
        if not result:
            message = "document not deleted"
            raise CannotDeleteException(message, self.collection_name, terminal_id, logger)
        return True
