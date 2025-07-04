# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
import secrets

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import (
    AlreadyExistException,
    CannotCreateException,
    NotFoundException,
    UpdateNotWorkException,
    CannotDeleteException,
)
from kugel_common.utils.misc import get_app_time
from kugel_common.schemas.pagination import PaginatedResult

from app.config.settings import settings
from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.enums.function_mode import FunctionMode
from app.enums.terminal_status import TerminalStatus

logger = getLogger(__name__)


# Helper functions for terminal ID and API key generation
def make_terminal_id(tenant_id: str, store_code: str, terminal_no: int):
    """
    Create a terminal ID by combining tenant ID, store code and terminal number

    Args:
        tenant_id: The tenant identifier
        store_code: The store code
        terminal_no: The terminal number within the store

    Returns:
        A formatted terminal ID string in the format "tenant_id-store_code-terminal_no"
    """
    return f"{tenant_id}-{store_code}-{terminal_no}"


def make_api_key():
    """
    Generate a secure API key for terminal authentication

    This creates a URL-safe token that can be used for terminal API authentication

    Returns:
        A secure random API key string
    """
    return secrets.token_urlsafe(32)


class TerminalInfoRepository(AbstractRepository[TerminalInfoDocument]):
    """
    Repository for Terminal Information

    Handles database operations for terminal information including CRUD operations
    and specialized terminal-related data access methods.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str) -> None:
        """
        Initialize the terminal info repository

        Args:
            db: MongoDB database connection
            tenant_id: Tenant ID to associate with this repository
        """
        super().__init__(settings.DB_COLLECTION_NAME_TERMINAL_INFO, TerminalInfoDocument, db)
        self.tenant_id = tenant_id

    async def create_terminal_info(
        self, store_code: str, terminal_no: int, description: str = None, tags: list[str] = None
    ) -> TerminalInfoDocument:
        """
        Create a new terminal information document in the database

        This method creates a new terminal with initial default values for
        function mode, status, counters, etc.

        Args:
            store_code: Store code where the terminal is located
            terminal_no: Terminal number within the store
            description: Optional description of the terminal
            tags: Optional list of tags for categorization

        Returns:
            The created terminal information document

        Raises:
            AlreadyExistException: If a terminal with the same ID already exists
            CannotCreateException: If the terminal creation fails
        """
        logger.debug(
            f"TerminalInfoRepository.create_terminal_info: tenant_id->{self.tenant_id}, "
            f"store_code->{store_code}, terminal_no->{terminal_no}, description->{description}"
        )
        terminal_id = make_terminal_id(tenant_id=self.tenant_id, store_code=store_code, terminal_no=terminal_no)

        try:
            result = await self.get_terminal_info_by_id_async(terminal_id)
            if result is not None:
                message = f"Terminal info already exists: {terminal_id}"
                raise AlreadyExistException(message, self.collection_name, terminal_id, logger)
        except NotFoundException:
            pass
        except Exception as e:
            raise e

        terminal_info = TerminalInfoDocument()
        terminal_info.tenant_id = self.tenant_id
        terminal_info.store_code = store_code
        terminal_info.terminal_no = terminal_no
        terminal_info.description = description
        terminal_info.function_mode = FunctionMode.MainMenu.value
        terminal_info.status = TerminalStatus.Idle.value
        terminal_info.business_date = None
        terminal_info.open_counter = 0
        terminal_info.business_counter = 0
        terminal_info.staff = None
        terminal_info.terminal_id = terminal_id
        terminal_info.shard_key = self.__make_shard_key(terminal_info)
        terminal_info.api_key = make_api_key()
        terminal_info.tags = tags

        resutl = await self.create_async(terminal_info)
        if not resutl:
            message = f"Cannot create terminal info: {terminal_info}"
            raise CannotCreateException(message, self.collection_name, terminal_info, logger)

        self.terminal_info = terminal_info

        return terminal_info

    async def get_terminal_info_list_async(
        self,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
        store_code: str = None,
    ) -> list[TerminalInfoDocument]:
        """
        Get a paginated list of terminal information documents

        Retrieves terminals for the current tenant, optionally filtered by store code

        Args:
            limit: Maximum number of results to return per page
            page: Page number to return (1-based)
            sort: List of tuples containing field name and sort direction (1 for asc, -1 for desc)
            store_code: Optional store code to filter terminals by

        Returns:
            Paginated list of terminal information documents
        """
        search_dict = {"tenant_id": self.tenant_id}
        if store_code is not None:
            search_dict["store_code"] = store_code
        logger.debug(f"search_dict: {search_dict} limit: {limit} page: {page} sort: {sort}")
        terminal_info_list = await self.get_list_async_with_sort_and_paging(search_dict, limit, page, sort)
        return terminal_info_list

    async def get_terminal_info_list_paginated_async(
        self,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
        store_code: str = None,
    ) -> PaginatedResult[TerminalInfoDocument]:
        """
        Get a paginated list of terminal information documents with metadata

        Retrieves terminals for the current tenant with pagination metadata,
        optionally filtered by store code

        Args:
            limit: Maximum number of results to return per page
            page: Page number to return (1-based)
            sort: List of tuples containing field name and sort direction (1 for asc, -1 for desc)
            store_code: Optional store code to filter terminals by

        Returns:
            PaginatedResult containing terminal information documents and metadata
        """
        search_dict = {"tenant_id": self.tenant_id}
        if store_code is not None:
            search_dict["store_code"] = store_code
        logger.debug(f"search_dict: {search_dict} limit: {limit} page: {page} sort: {sort}")
        return await self.get_paginated_list_async(search_dict, limit, page, sort)

    async def get_terminal_info_by_id_async(self, terminal_id: str) -> TerminalInfoDocument:
        """
        Get a terminal information document by its terminal ID

        Args:
            terminal_id: The terminal ID to look up

        Returns:
            Terminal information document

        Raises:
            NotFoundException: If the terminal is not found
        """
        search_dict = {"terminal_id": terminal_id}
        terminal_info = await self.get_one_async(search_dict)
        if terminal_info is None:
            message = f"Terminal info not found: terminal_id->{terminal_id}: tenant_id->{self.tenant_id}"
            raise NotFoundException(message, self.collection_name, terminal_id, logger)
        return terminal_info

    async def update_terminal_info_async(self, terminal_id: str, terminal_update_info: dict) -> bool:
        """
        Update specific fields of a terminal information document

        Args:
            terminal_id: The terminal ID to update
            terminal_update_info: Dictionary of fields to update

        Returns:
            True if update was successful

        Raises:
            UpdateNotWorkException: If the update operation fails
        """
        search_dict = {"terminal_id": terminal_id}
        result = await self.update_one_async(search_dict, terminal_update_info)
        if not result:
            message = f"Cannot update terminal info: {terminal_id}"
            raise UpdateNotWorkException(message, self.collection_name, terminal_id, logger)
        return result

    async def replace_terminal_info_async(self, terminal_id: str, terminal_info: TerminalInfoDocument) -> bool:
        """
        Replace an entire terminal information document

        This replaces the entire document rather than just updating specific fields

        Args:
            terminal_id: The terminal ID to replace
            terminal_info: New terminal information document

        Returns:
            True if replacement was successful

        Raises:
            UpdateNotWorkException: If the replace operation fails
        """
        search_dict = {"terminal_id": terminal_id}
        result = await self.replace_one_async(search_dict, terminal_info)
        if not result:
            message = f"Cannot replace terminal info: {terminal_id}"
            raise UpdateNotWorkException(message, self.collection_name, terminal_id, logger)
        return result

    async def delete_terminal_info_async(self, terminal_id: str) -> bool:
        """
        Delete a terminal information document

        Args:
            terminal_id: The terminal ID to delete

        Returns:
            True if deletion was successful

        Raises:
            CannotDeleteException: If the delete operation fails
        """
        search_dict = {"terminal_id": terminal_id}
        result = await self.delete_async(search_dict)
        if not result:
            message = f"Cannot delete terminal info: {terminal_id}"
            raise CannotDeleteException(message, self.collection_name, terminal_id, logger)
        return result

    def __make_shard_key(self, terminal_info: TerminalInfoDocument):
        """
        Create a shard key for database sharding

        Combines tenant ID, store code, and terminal number to create a shard key
        for efficient database distribution

        Args:
            terminal_info: Terminal information document

        Returns:
            Shard key string
        """
        keys = []
        keys.append(terminal_info.tenant_id)
        keys.append(terminal_info.store_code)
        keys.append(str(terminal_info.terminal_no))
        return self.make_shard_key(keys)
