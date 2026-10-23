# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Type
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.exceptions import CannotCreateException
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
            # Check if the transaction log already exists
            if await self.get_one_async(self.__identity_filter(tranlog)):
                logger.warning(f"Transaction already exists. transaction: {tranlog}")
                return tranlog

            # Create a new transaction log
            tranlog.shard_key = self.__get_shard_key(tranlog)
            logger.debug(f"TranlogRepository.create_tranlog_async: tranlog->{tranlog}")
            if not await self.create_async(tranlog):
                raise Exception()
            await self.__warn_on_numbering_reuse(tranlog)
            return tranlog

        # A duplicate key is not caught as "already stored" here, unlike report:
        # this insert runs inside the journal's transaction, and MongoDB aborts
        # the transaction on the error, so carrying on only fails the journal
        # insert that follows (issue #230). The caller aborts, then runs the
        # transaction again or checks with find_stored_async whether a
        # concurrent delivery stored it.
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

    async def find_stored_async(self, tranlog: BaseTransaction) -> BaseTransaction | None:
        """
        Find the stored transaction log that is the same transaction as ``tranlog``.

        Uses the identity create_tranlog_async deduplicates on.

        Args:
            tranlog: The transaction log to look for

        Returns:
            The stored transaction log, or None when there is none
        """
        return await self.get_one_async(self.__identity_filter(tranlog))

    @staticmethod
    def __identity_filter(tranlog: BaseTransaction) -> dict:
        # Client-carried cart phase 2 (issue #156 / #152): dedupe on cart_id
        # (the transaction identity) so a duplicate finalize converges to one
        # record (first-wins skip). Fall back to (business_counter,
        # transaction_no) for legacy records without cart_id — transaction_no
        # alone is the per-open seq and not unique across sessions.
        if tranlog.cart_id is not None:
            return {
                "tenant_id": tranlog.tenant_id,
                "store_code": tranlog.store_code,
                "cart_id": tranlog.cart_id,
            }
        return {
            "tenant_id": tranlog.tenant_id,
            "store_code": tranlog.store_code,
            "terminal_no": tranlog.terminal_no,
            "business_counter": tranlog.business_counter,
            "transaction_no": tranlog.transaction_no,
        }

    async def __warn_on_numbering_reuse(self, tranlog: BaseTransaction) -> None:
        """
        Log when two transactions with different cart_ids share one numbering (issue #230).

        Both are stored: a cart_id is the transaction's identity, so they are
        different sales. But the numbering is unique at the source, where cart
        refuses the second finalize, so a reuse here means the numbering went
        wrong somewhere: a restored or rebuilt cart database, a replaced
        terminal, or a second backend. The unique index used to reject the second
        sale instead; this keeps the signal without losing the sale.
        """
        if tranlog.cart_id is None:
            return
        try:
            others = await self.dbcollection.count_documents(
                {
                    "tenant_id": tranlog.tenant_id,
                    "store_code": tranlog.store_code,
                    "terminal_no": tranlog.terminal_no,
                    "business_counter": tranlog.business_counter,
                    "transaction_no": tranlog.transaction_no,
                    "cart_id": {"$ne": tranlog.cart_id},
                },
                limit=1,
                session=self.session,
            )
        except Exception as e:
            # A read for a warning must not fail the sale.
            logger.debug(f"Could not check the numbering for reuse: {e}")
            return
        if others:
            logger.warning(
                "Two transactions share one numbering: "
                f"tenant_id={tranlog.tenant_id} store_code={tranlog.store_code} "
                f"terminal_no={tranlog.terminal_no} business_counter={tranlog.business_counter} "
                f"transaction_no={tranlog.transaction_no} cart_id={tranlog.cart_id}. "
                "Both are stored as different sales by cart_id; the numbering is worth checking."
            )

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
