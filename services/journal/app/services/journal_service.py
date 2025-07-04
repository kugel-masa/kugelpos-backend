# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from app.models.documents.jornal_document import JournalDocument
from app.models.repositories.journal_repository import JournalRepository
from app.exceptions import (
    JournalCreationException,
    JournalQueryException,
    JournalValidationException,
    JournalNotFoundException,
)

logger = getLogger(__name__)


class JournalService:
    """
    Service class for journal operations.

    This class provides business logic for journal-related operations,
    handling the creation and retrieval of journal entries. It serves as an
    intermediate layer between the API controllers and the journal repository.
    """

    def __init__(self, journal_repository: JournalRepository):
        """
        Initialize the journal service.

        Args:
            journal_repository: Repository instance for journal data operations
        """
        self.journal_repository = journal_repository

    async def receive_journal_async(self, journal: dict):
        """
        Create a new journal entry from dictionary data.

        This method validates and converts the input dictionary to a JournalDocument
        object and stores it in the database using the repository.

        Args:
            journal: Dictionary containing journal data

        Returns:
            Created JournalDocument instance

        Raises:
            JournalValidationException: If the journal data fails validation
            JournalCreationException: If there is an error during journal creation
        """
        try:
            journal_obj = JournalDocument(**journal)
            await self.journal_repository.create_journal_async(journal_obj)
            return journal_obj
        except ValueError as e:
            message = f"ジャーナルのバリデーションに失敗しました: {journal}"
            raise JournalValidationException(message, logger, e) from e
        except Exception as e:
            message = f"ジャーナルの作成に失敗しました: {journal}"
            raise JournalCreationException(message, logger, e) from e

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
            JournalNotFoundException: If no journals match the criteria
            JournalQueryException: If there is an error during journal retrieval
        """
        try:
            journals = await self.journal_repository.get_journals_async(
                store_code=store_code,
                terminals=terminals,
                transaction_types=transaction_types,
                business_date_from=business_date_from,
                business_date_to=business_date_to,
                generate_date_time_from=generate_date_time_from,
                generate_date_time_to=generate_date_time_to,
                receipt_no_from=receipt_no_from,
                receipt_no_to=receipt_no_to,
                keywords=keywords,
                limit=limit,
                page=page,
                sort=sort,
            )
            if not journals:
                message = (
                    "ジャーナルが見つかりません: "
                    f"store_code->{store_code}, "
                    f"terminals->{terminals}, "
                    f"transaction_types->{transaction_types}"
                )
                raise JournalNotFoundException(message, logger)
            return journals
        except JournalNotFoundException:
            # JournalNotFoundExceptionはそのまま上位に伝播させる
            raise
        except Exception as e:
            message = (
                "ジャーナルの検索に失敗しました: "
                f"store_code->{store_code}, "
                f"terminals->{terminals}, "
                f"transaction_types->{transaction_types}, "
                f"business_date_from->{business_date_from}, "
                f"business_date_to->{business_date_to}"
            )
            raise JournalQueryException(message, logger, e) from e

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
    ):
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
            JournalQueryException: If there is an error during journal retrieval
        """
        try:
            return await self.journal_repository.get_journals_paginated_async(
                store_code=store_code,
                terminals=terminals,
                transaction_types=transaction_types,
                business_date_from=business_date_from,
                business_date_to=business_date_to,
                generate_date_time_from=generate_date_time_from,
                generate_date_time_to=generate_date_time_to,
                receipt_no_from=receipt_no_from,
                receipt_no_to=receipt_no_to,
                keywords=keywords,
                limit=limit,
                page=page,
                sort=sort,
            )
        except Exception as e:
            message = (
                "ジャーナルの検索に失敗しました: "
                f"store_code->{store_code}, "
                f"terminals->{terminals}, "
                f"transaction_types->{transaction_types}"
            )
            raise JournalQueryException(message, logger, e) from e
