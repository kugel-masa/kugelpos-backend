# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.exceptions import CannotCreateException, DuplicateKeyException
from app.models.documents.open_close_log import OpenCloseLog
from app.config.settings import settings

logger = getLogger(__name__)


class OpenCloseLogRepository(AbstractRepository[OpenCloseLog]):
    """
    Repository for open/close log operations.

    This class provides methods for storing and retrieving terminal
    open/close operation logs in the database. It extends the AbstractRepository
    to implement specific functionality for open/close operations.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str) -> None:
        """
        Initialize the open/close log repository.

        Args:
            db: AsyncIOMotorDatabase instance for database operations
            tenant_id: Identifier for the tenant
        """
        super().__init__(settings.DB_COLLECTION_NAME_OPEN_CLOSE_LOG, OpenCloseLog, db)
        self.tenant_id = tenant_id

    async def create_open_close_log(self, open_close_log: OpenCloseLog) -> OpenCloseLog:
        """
        Create a new open/close log in the database.

        This method attempts to store an open/close log document in the database.
        If a duplicate key error occurs, it will update the existing document instead.

        Args:
            open_close_log: Open/close log document to store

        Returns:
            The stored open/close log document

        Raises:
            CannotCreateException: If the open/close log cannot be created
        """
        logger.debug("OpenCloseLogRepository.create_open_close_log: open_close_log->{open_close_log}")

        try:
            # check if the log is already created
            filter = {
                "tenant_id": open_close_log.tenant_id,
                "store_code": open_close_log.store_code,
                "terminal_no": open_close_log.terminal_no,
                "business_date": open_close_log.business_date,
                "open_counter": open_close_log.open_counter,
                "operation": open_close_log.operation,
            }
            if await self.get_one_async(filter):
                logger.warning(f"OpenCloseLog already exists. open_close_log: {open_close_log}")
                return open_close_log

            # create new open_close_log
            open_close_log.shard_key = self.__get_shard_key(open_close_log)
            logger.debug(f"OpenCloseLog.create_open_close_log: open_close_log->{open_close_log}")
            if not await self.create_async(open_close_log):
                raise Exception()
            return open_close_log

        except Exception as e:
            message = f"Cannot create open/close log: {open_close_log}"
            raise CannotCreateException(message, self.collection_name, open_close_log, logger, e) from e

    async def get_open_close_logs(
        self,
        store_code: str,
        business_date: str,
        terminal_no: int = None,
        open_counter: int = None,
        operation: str = None,
        limit: int = 100,
        page: int = 1,
        sort: list[tuple[str, int]] = None,
    ) -> PaginatedResult[OpenCloseLog]:
        """
        Retrieve open/close logs based on query parameters.

        This method allows for flexible querying of open/close logs based on
        store, terminal, date, and other filter criteria. Results are paginated.

        Args:
            store_code: Identifier for the store
            business_date: Business date to filter by
            terminal_no: Optional terminal number to filter by
            open_counter: Optional counter for terminal open/close cycles
            operation: Optional operation type ('open' or 'close') to filter by
            limit: Maximum number of results per page (default: 100)
            page: Page number (default: 1)
            sort: List of field name and direction tuples for sorting

        Returns:
            Paginated result containing matching open/close logs
        """
        filters = {"tenant_id": self.tenant_id, "store_code": store_code, "business_date": business_date}
        if terminal_no:
            filters["terminal_no"] = terminal_no
        if open_counter:
            filters["open_counter"] = open_counter
        if operation:
            filters["operation"] = operation

        return await self.get_paginated_list_async(filters, limit, page, sort)

    def __get_shard_key(self, open_close_log: OpenCloseLog) -> str:
        """
        Generate a shard key for database partitioning.

        Creates a composite shard key from tenant ID, store code,
        terminal number, and business date.

        Args:
            open_close_log: Open/close log document

        Returns:
            String representation of the shard key
        """
        keys = []
        keys.append(open_close_log.tenant_id)
        keys.append(open_close_log.store_code)
        keys.append(str(open_close_log.terminal_no))
        keys.append(open_close_log.business_date)
        return self.make_shard_key(keys)
