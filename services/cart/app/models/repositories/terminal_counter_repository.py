# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from motor.motor_asyncio import AsyncIOMotorDatabase
from logging import getLogger
import sys
from pymongo import ReturnDocument

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import CannotCreateException, UpdateNotWorkException, CannotDeleteException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.terminal_counter_document import TerminalCounterDocument
from app.config.settings import settings

logger = getLogger(__name__)


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

        This method uses MongoDB's atomic find_one_and_update operation to prevent
        race conditions. No Python-level locking is required as the operation is
        atomic at the database level.

        Args:
            countType: Type of counter to increment (e.g., "receipt", "transaction")
            start_value: Value to start from if counter doesn't exist
            end_value: Maximum value before resetting to start_value

        Returns:
            int: The new counter value after incrementing
        """
        logger.debug(f"numbering_count: countType->{countType}, start_value->{start_value}, end_value->{end_value}")

        tenant_id = self.terminal_info.tenant_id
        store_code = self.terminal_info.store_code
        terminal_no = self.terminal_info.terminal_no
        terminal_id = make_terminal_id(tenant_id=tenant_id, store_code=store_code, terminal_no=terminal_no)

        target_field = f"count_dic.{countType}"

        # Set initial value for new counters
        initial_value = start_value - 1 if start_value > 1 else 0

        # Atomically increment counter using MongoDB's find_one_and_update
        result = await self.dbcollection.find_one_and_update(
            filter={"terminal_id": terminal_id},
            update={
                "$inc": {target_field: 1},  # Atomic increment
                "$setOnInsert": {
                    "terminal_id": terminal_id,
                    "shard_key": terminal_id,
                    target_field: initial_value
                }
            },
            upsert=True,  # Create document if it doesn't exist
            return_document=ReturnDocument.AFTER,  # Return updated value
            projection={target_field: 1, "_id": 0}
        )

        if result is None or "count_dic" not in result or countType not in result["count_dic"]:
            message = f"Failed to increment counter for countType={countType}, terminal_id={terminal_id}"
            logger.error(message)
            raise UpdateNotWorkException(message, self.collection_name, terminal_id, logger)

        new_count = result["count_dic"][countType]

        # Handle rollover if counter exceeds end_value
        if new_count > end_value:
            logger.debug(f"Counter {countType} exceeded end_value ({end_value}), rolling over to {start_value}")
            await self.dbcollection.update_one(
                {"terminal_id": terminal_id},
                {"$set": {target_field: start_value}}
            )
            new_count = start_value

        return new_count
