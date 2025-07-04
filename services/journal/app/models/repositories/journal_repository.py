# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Type
from datetime import datetime
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import CannotCreateException, DocumentNotFoundException
from kugel_common.schemas.pagination import PaginatedResult
from app.models.documents.jornal_document import JournalDocument
from app.config.settings import settings

logger = getLogger(__name__)


class JournalRepository(AbstractRepository[JournalDocument]):
    """
    Repository for journal document operations.

    This class provides methods for storing and retrieving journal entries
    in the database. Journal entries serve as a permanent record of all
    POS operations, including transactions, cash operations, and terminal
    open/close events.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str):
        """
        Initialize the journal repository.

        Args:
            db: AsyncIOMotorDatabase instance for database operations
            tenant_id: Identifier for the tenant
        """
        super().__init__(settings.DB_COLLECTION_NAME_JOURNAL, JournalDocument, db)
        self.tenant_id = tenant_id

    async def create_journal_async(self, journal_doc: JournalDocument) -> JournalDocument:
        """
        Create a new journal entry in the database.

        This method attempts to store a journal document in the database
        with a generated shard key for distributed storage.

        Args:
            journal_doc: Journal document to store

        Returns:
            The stored journal document

        Raises:
            CannotCreateException: If the journal entry cannot be created
        """
        try:
            # check if the journal document is already created
            filter = {
                "tenant_id": journal_doc.tenant_id,
                "store_code": journal_doc.store_code,
                "terminal_no": journal_doc.terminal_no,
                "transaction_type": journal_doc.transaction_type,
                "generate_date_time": journal_doc.generate_date_time,
            }

            existing_doc = await self.get_one_async(filter=filter)
            if existing_doc:
                logger.warning(f"Journal already exists. journal_doc: {journal_doc}")
                return existing_doc

            # Create a new journal document
            journal_doc.shard_key = self.__get_shard_key(journal_doc)
            logger.debug(f"JournalRepository.create_journal_async: journal_doc->{journal_doc}")
            if not await self.create_async(journal_doc):
                raise Exception()
            return journal_doc
        except Exception as e:
            message = (
                "Failed to create journal: "
                f"tenant_id->{journal_doc.tenant_id} "
                f"store_code->{journal_doc.store_code} "
                f"terminal_no->{journal_doc.terminal_no} "
                f"transaction_no->{journal_doc.transaction_no} "
                f"transaction_type->{journal_doc.transaction_type}"
            )
            raise CannotCreateException(message, logger, e) from e

    async def get_journals_async(
        self,
        store_code: str,
        terminals: list[int] = None,
        transaction_types: list[int] = None,
        business_date_from: str = None,
        business_date_to: str = None,
        generate_date_time_from: str = None,
        generate_date_time_to: str = None,
        receipt_no_from: int = None,
        receipt_no_to: int = None,
        keywords: list[str] = None,
        limit: int = 100,
        page: int = 1,
        sort: list[tuple[str, int]] = None,
    ) -> list[JournalDocument]:
        """
        Retrieve journal entries based on multiple search criteria.

        This method provides a flexible search interface for journal entries,
        allowing filtering by terminal, transaction type, date ranges,
        receipt numbers, and even text content within the journal.
        Results can be paginated and sorted as needed.

        Args:
            store_code: Identifier for the store
            terminals: Optional list of terminal numbers to filter by
            transaction_types: Optional list of transaction types to filter by
            business_date_from: Optional start date for business date range
            business_date_to: Optional end date for business date range
            generate_date_time_from: Optional start datetime for journal creation
            generate_date_time_to: Optional end datetime for journal creation
            receipt_no_from: Optional start receipt number for range
            receipt_no_to: Optional end receipt number for range
            keywords: Optional list of keywords to search for in journal text
            limit: Maximum number of results per page (default: 100)
            page: Page number (default: 1)
            sort: List of field name and direction tuples for sorting

        Returns:
            List of journal documents matching the search criteria

        Raises:
            DocumentNotFoundException: If journals cannot be retrieved or no matches found
        """
        query = {"tenant_id": self.tenant_id, "store_code": store_code}

        if terminals:
            query["terminal_no"] = {"$in": terminals}
        if transaction_types:
            query["transaction_type"] = {"$in": transaction_types}
        if business_date_from and business_date_to:
            query["business_date"] = {
                "$gte": business_date_from,
                "$lte": business_date_to,
            }
        if generate_date_time_from and generate_date_time_to:
            query["generate_date_time"] = {
                "$gte": generate_date_time_from,
                "$lte": generate_date_time_to,
            }
        if receipt_no_from and receipt_no_to:
            query["receipt_no"] = {"$gte": receipt_no_from, "$lte": receipt_no_to}
        if keywords:
            query["journal_text"] = {"$regex": "|".join(keywords)}

        try:
            logger.debug(f"JournalRepository.get_journals_async: query->{query}, limit->{limit}, sort->{sort}")
            journals = await self.get_list_async_with_sort_and_paging(filter=query, limit=limit, page=page, sort=sort)
            logger.debug(f"JournalRepository.get_journals_async: journals->{journals}")
            return journals
        except Exception as e:
            message = (
                "Failed to get journals: "
                f"tenant_id->{self.tenant_id} "
                f"store_code->{store_code} "
                f"terminals->{terminals} "
                f"transaction_types->{transaction_types} "
                f"business_date_from->{business_date_from} "
                f"business_date_to->{business_date_to} "
                f"generate_date_time_from->{generate_date_time_from} "
                f"generate_date_time_to->{generate_date_time_to} "
                f"receipt_no_from->{receipt_no_from} "
                f"receipt_no_to->{receipt_no_to} "
                f"keywords->{keywords} "
                f"limit->{limit} "
                f"page->{page} "
                f"sort->{sort}"
            )
            raise DocumentNotFoundException(message, logger, e) from e

    async def get_journals_paginated_async(
        self,
        store_code: str,
        terminals: list[int] = None,
        transaction_types: list[int] = None,
        business_date_from: str = None,
        business_date_to: str = None,
        generate_date_time_from: str = None,
        generate_date_time_to: str = None,
        receipt_no_from: int = None,
        receipt_no_to: int = None,
        keywords: list[str] = None,
        limit: int = 100,
        page: int = 1,
        sort: list[tuple[str, int]] = None,
    ) -> PaginatedResult[JournalDocument]:
        """
        Retrieve journal entries with pagination metadata.

        This method provides the same search functionality as get_journals_async
        but returns results with pagination metadata including total count,
        current page, and other pagination information.

        Args:
            store_code: Identifier for the store
            terminals: Optional list of terminal numbers to filter by
            transaction_types: Optional list of transaction types to filter by
            business_date_from: Optional start date for business date range
            business_date_to: Optional end date for business date range
            generate_date_time_from: Optional start datetime for journal creation
            generate_date_time_to: Optional end datetime for journal creation
            receipt_no_from: Optional start receipt number for range
            receipt_no_to: Optional end receipt number for range
            keywords: Optional list of keywords to search for in journal text
            limit: Maximum number of results per page (default: 100)
            page: Page number (default: 1)
            sort: List of field name and direction tuples for sorting

        Returns:
            PaginatedResult containing journal documents and metadata

        Raises:
            DocumentNotFoundException: If journals cannot be retrieved
        """
        query = {"tenant_id": self.tenant_id, "store_code": store_code}

        if terminals:
            query["terminal_no"] = {"$in": terminals}
        if transaction_types:
            query["transaction_type"] = {"$in": transaction_types}
        if business_date_from and business_date_to:
            query["business_date"] = {
                "$gte": business_date_from,
                "$lte": business_date_to,
            }
        if generate_date_time_from and generate_date_time_to:
            query["generate_date_time"] = {
                "$gte": generate_date_time_from,
                "$lte": generate_date_time_to,
            }
        if receipt_no_from and receipt_no_to:
            query["receipt_no"] = {"$gte": receipt_no_from, "$lte": receipt_no_to}
        if keywords:
            query["journal_text"] = {"$regex": "|".join(keywords)}

        try:
            logger.debug(
                f"JournalRepository.get_journals_paginated_async: query->{query}, limit->{limit}, sort->{sort}"
            )
            return await self.get_paginated_list_async(filter=query, limit=limit, page=page, sort=sort)
        except Exception as e:
            message = (
                "Failed to get journals with pagination: "
                f"tenant_id->{self.tenant_id} "
                f"store_code->{store_code} "
                f"terminals->{terminals} "
                f"transaction_types->{transaction_types}"
            )
            raise DocumentNotFoundException(message, logger, e) from e

    def __get_shard_key(self, journal_doc: JournalDocument) -> str:
        """
        Generate a shard key for database partitioning.

        Creates a composite shard key from tenant ID, store code,
        terminal number, and business date for efficient data distribution
        and retrieval.

        Args:
            journal_doc: Journal document

        Returns:
            String representation of the shard key
        """
        key = []
        key.append(journal_doc.tenant_id)
        key.append(journal_doc.store_code)
        key.append(str(journal_doc.terminal_no))
        key.append(journal_doc.business_date)
        return self.make_shard_key(key)
