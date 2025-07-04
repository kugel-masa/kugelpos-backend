# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import CannotCreateException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.config.settings import settings

logger = getLogger(__name__)


class TranlogRepository(AbstractRepository[BaseTransaction]):
    """
    Repository for managing transaction logs.

    This class provides methods to create, query, and retrieve transaction log records
    from the database. Transaction logs represent completed transactions in the system,
    providing a history of all sales and other transaction activities.
    """

    def __init__(self, db: AsyncIOMotorDatabase, terminal_info: TerminalInfoDocument):
        """
        Initialize the repository with database connection and terminal information.

        Args:
            db: Database connection object
            terminal_info: Terminal information document containing tenant, store, and terminal details
        """
        super().__init__(settings.DB_COLLECTION_NAME_TRAN_LOG, BaseTransaction, db)
        self.terminal_info = terminal_info

    async def create_tranlog_async(self, tranlog: BaseTransaction) -> BaseTransaction:
        """
        Create a new transaction log entry in the database.

        Sets the appropriate shard key before saving the transaction log to ensure
        proper data partitioning.

        Args:
            tranlog: Transaction log document to create

        Returns:
            BaseTransaction: The created transaction log document

        Raises:
            CannotCreateException: If the transaction log could not be created
        """
        try:
            tranlog.shard_key = self.__get_shard_key(tranlog)
            logger.debug(f"TranlogRepository.create_tranlog_async: tranlog->{tranlog}")
            if not await self.create_async(tranlog):
                raise Exception()
            return tranlog
        except Exception as e:
            message = (
                "Failed to create tranlog: "
                f"tenant_id->{self.terminal_info.tenant_id} "
                f"store_code->{self.terminal_info.store_code} "
                f"terminal_no->{self.terminal_info.terminal_no} "
                f"transaction_no->{tranlog.transaction_no} "
                f"transaction_type->{tranlog.transaction_type}"
            )
            raise CannotCreateException(message, logger, e) from e

    async def get_tranlog_by_transaction_no_async(
        self, store_code: str, terminal_no: int, transaction_no: int
    ) -> BaseTransaction:
        """
        Retrieve a specific transaction log by its transaction number.

        Args:
            store_code: Store code where the transaction occurred
            terminal_no: Terminal number where the transaction occurred
            transaction_no: Unique transaction number to retrieve

        Returns:
            BaseTransaction: The retrieved transaction log, or None if not found
        """
        query = {
            "tenant_id": self.terminal_info.tenant_id,
            "store_code": store_code,
            "terminal_no": terminal_no,
            "transaction_no": transaction_no,
        }
        logger.debug(f"TranlogRepository.get_tranlog_by_transaction_no_async: query->{query}")
        return await self.get_one_async(query)

    # get tranlog list by query parameters
    async def get_tranlog_list_by_query_async(
        self,
        store_code: str,
        terminal_no: int,
        business_date: str = None,
        open_counter: int = None,
        transaction_type: list[int] = None,
        receipt_no: int = None,
        limit: int = 100,
        page: int = 1,
        sort: list[tuple[str, int]] = None,
        include_cancelled: bool = False,
    ) -> PaginatedResult[BaseTransaction]:
        """
        Retrieve a paginated list of transaction logs matching the specified criteria.

        Args:
            store_code: Store code filter
            terminal_no: Terminal number filter
            business_date: Optional business date filter (format: YYYY-MM-DD)
            open_counter: Optional open counter number filter
            transaction_type: Optional list of transaction types to include
            receipt_no: Optional receipt number filter
            limit: Maximum number of records to return per page
            page: Page number to retrieve
            sort: List of field name and direction tuples for sorting
            include_cancelled: Whether to include cancelled transactions

        Returns:
            PaginatedResult[BaseTransaction]: Paginated list of matching transaction logs
        """
        query = {"tenant_id": self.terminal_info.tenant_id, "store_code": store_code, "terminal_no": terminal_no}
        if business_date:
            query["business_date"] = business_date
        if open_counter:
            query["open_counter"] = open_counter
        if transaction_type:
            query["transaction_type"] = {"$in": transaction_type}
        if receipt_no:
            query["receipt_no"] = receipt_no
        if not include_cancelled:
            query["sales.is_cancelled"] = False
        logger.debug(
            f"TranlogRepository.get_tranlog_list_by_query_async: query->{query} limit->{limit} page->{page} sort->{sort}"
        )
        return await self.get_paginated_list_async(filter=query, limit=limit, page=page, sort=sort)

    def __get_shard_key(self, tranlog: BaseTransaction) -> str:
        """
        Generate a shard key for partitioning transaction log data.

        Creates a shard key based on tenant ID, store code, terminal number, and
        the date portion of the generation timestamp.

        Args:
            tranlog: The transaction log document

        Returns:
            str: The generated shard key
        """
        key = []
        key.append(tranlog.tenant_id)
        key.append(tranlog.store_code)
        key.append(str(tranlog.terminal_no))
        key.append(tranlog.generate_date_time.split("T")[0])  # format: YYYY-MM-DDTHH:MM:SSZ
        return self.make_shard_key(key)
