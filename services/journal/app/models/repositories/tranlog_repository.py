# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Type
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.exceptions import CannotCreateException, DuplicateKeyException
from kugel_common.models.documents.base_tranlog import BaseTransaction

from app.config.settings import settings
from app.exceptions import DocumentNotFoundException

logger = getLogger(__name__)


class TranlogRepository(AbstractRepository[BaseTransaction]):
    """
    Repository for transaction log operations.

    This class provides methods for storing, retrieving, and querying
    transaction logs in the database. It extends the AbstractRepository
    to implement specific functionality for transaction operations.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str):
        """
        Initialize the transaction log repository.

        Args:
            db: AsyncIOMotorDatabase instance for database operations
            tenant_id: Identifier for the tenant
        """
        super().__init__(settings.DB_COLLECTION_NAME_TRAN, BaseTransaction, db)
        self.tenant_id = tenant_id

    async def create_tranlog_async(self, tranlog: BaseTransaction) -> BaseTransaction:
        """
        Create a new transaction log in the database.

        This method attempts to store a transaction log document in the database.
        If a duplicate key error occurs, it will update the existing document instead.

        Args:
            tranlog: Transaction log document to store

        Returns:
            The stored transaction log document

        Raises:
            CannotCreateException: If the transaction log cannot be created
        """
        try:

            filter = {
                "tenant_id": tranlog.tenant_id,
                "store_code": tranlog.store_code,
                "terminal_no": tranlog.terminal_no,
                "transaction_no": tranlog.transaction_no,
            }

            # Check if the transaction log already exists
            if await self.get_one_async(filter):
                logger.warning(f"Transaction already exists. transaction: {tranlog}")
                return tranlog

            # Create a new transaction log
            tranlog.shard_key = self.__get_shard_key(tranlog)
            logger.debug(f"TranlogRepository.create_tranlog_async: tranlog->{tranlog}")
            if not await self.create_async(tranlog):
                raise Exception()
            return tranlog

        except Exception as e:
            message = (
                "Failed to create tranlog: "
                f"tenant_id->{tranlog.tenant_id} "
                f"store_code->{tranlog.store_code} "
                f"terminal_no->{tranlog.terminal_no} "
                f"transaction_no->{tranlog.transaction_no} "
                f"transaction_type->{tranlog.transaction_type}"
            )
            raise CannotCreateException(message, logger, e) from e

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
        Retrieve transaction logs based on query parameters.

        This method allows for flexible querying of transaction logs based on
        store, terminal, date, and other filter criteria. Results are paginated.

        Args:
            store_code: Identifier for the store
            terminal_no: Terminal number
            business_date: Optional date to filter by
            open_counter: Optional counter for terminal open/close cycles
            transaction_type: Optional list of transaction types to filter by
            receipt_no: Optional receipt number to filter by
            limit: Maximum number of results per page (default: 100)
            page: Page number (default: 1)
            sort: List of field name and direction tuples for sorting
            include_cancelled: Whether to include cancelled transactions (default: False)

        Returns:
            Paginated result containing matching transaction logs
        """
        query = {"tenant_id": self.tenant_id, "store_code": store_code, "terminal_no": terminal_no}
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
        Generate a shard key for database partitioning.

        Creates a composite shard key from tenant ID, store code,
        terminal number, and the date portion of the generation timestamp.

        Args:
            tranlog: Transaction log document

        Returns:
            String representation of the shard key
        """
        key = []
        key.append(tranlog.tenant_id)
        key.append(tranlog.store_code)
        key.append(str(tranlog.terminal_no))
        key.append(tranlog.generate_date_time.split("T")[0])  # format: YYYY-MM-DDTHH:MM:SSZ
        return self.make_shard_key(key)
