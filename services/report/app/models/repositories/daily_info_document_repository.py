# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.exceptions import CannotCreateException, DuplicateKeyException

from app.config.settings import settings
from app.models.documents.daily_info_document import DailyInfoDocument

logger = getLogger(__name__)


class DailyInfoDocumentRepository(AbstractRepository[DailyInfoDocument]):
    """
    Repository for daily information document operations.

    This class provides methods for storing, retrieving, and updating
    daily information documents in the database. These documents track
    the verification status of terminal data for report generation.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str) -> None:
        """
        Initialize the daily information document repository.

        Args:
            db: AsyncIOMotorDatabase instance for database operations
            tenant_id: Identifier for the tenant
        """
        super().__init__(settings.DB_COLLECTION_NAME_DAILY_INFO, DailyInfoDocument, db)
        self.tenant_id = tenant_id

    async def create_daily_info_document(self, daily_info: DailyInfoDocument) -> DailyInfoDocument:
        """
        Create a new daily information document in the database.

        This method attempts to store a daily information document in the database.
        If a duplicate key error occurs, it will update the existing document instead.

        Args:
            daily_info: Daily information document to store

        Returns:
            The stored daily information document

        Raises:
            CannotCreateException: If the document cannot be created
        """
        logger.debug("DailyInfoDocumentRepository.create_daily_info_document: daily_info->{daily_info}")

        try:
            daily_info.shard_key = self.__get_shard_key(daily_info)
            logger.debug(f"DailyInfoDocumentRepository.create_daily_info_document: daily_info->{daily_info}")
            if not await self.create_async(daily_info):
                raise Exception()
            return daily_info
        except DuplicateKeyException as e:
            filter = {
                "tenant_id": daily_info.tenant_id,
                "store_code": daily_info.store_code,
                "terminal_no": daily_info.terminal_no,
                "business_date": daily_info.business_date,
                "open_counter": daily_info.open_counter,
            }
            logger.warning(f"DailyInfoDocument already exists. Updating daily_info: {daily_info} with filter: {filter}")
            await self.replace_one_async(filter, daily_info)
            return daily_info
        except Exception as e:
            message = f"Cannot create daily info document: {daily_info}"
            raise CannotCreateException(message, self.collection_name, daily_info, logger, e) from e

    async def get_daily_info_documents(
        self,
        store_code: str,
        business_date: str,
        open_counter: int = None,
        terminal_no: int = None,
        limit: int = 100,
        page: int = 1,
        sort: list[tuple[str, int]] = None,
    ) -> PaginatedResult[DailyInfoDocument]:
        """
        Retrieve daily information documents based on query parameters.

        This method allows for flexible querying of daily information documents
        based on store, terminal, date, and other filter criteria. Results are paginated.

        Args:
            store_code: Identifier for the store
            business_date: Business date to filter by
            open_counter: Optional counter for terminal open/close cycles
            terminal_no: Optional terminal number to filter by
            limit: Maximum number of results per page (default: 100)
            page: Page number (default: 1)
            sort: List of field name and direction tuples for sorting

        Returns:
            Paginated result containing matching daily information documents
        """
        filters = {"tenant_id": self.tenant_id, "store_code": store_code, "business_date": business_date}
        if open_counter:
            filters["open_counter"] = open_counter
        if terminal_no:
            filters["terminal_no"] = terminal_no

        return await self.get_paginated_list_async(filters, limit, page, sort)

    async def update_daily_info_document(self, filter: dict, update_data: dict) -> bool:
        """
        Update an existing daily information document.

        This method allows for partial updates of daily information documents
        based on the provided filter and update data.

        Args:
            filter: Dictionary of criteria to identify the document to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            True if the update was successful, False otherwise
        """
        logger.debug(
            f"DailyInfoDocumentRepository.update_daily_info_document: filter->{filter}, update_data->{update_data}"
        )
        return await self.update_one_async(filter, update_data)

    def __get_shard_key(self, daily_info: DailyInfoDocument) -> str:
        """
        Generate a shard key for database partitioning.

        Creates a composite shard key from tenant ID, store code,
        terminal number, and business date.

        Args:
            daily_info: Daily information document

        Returns:
            String representation of the shard key
        """
        keys = []
        keys.append(daily_info.tenant_id)
        keys.append(daily_info.store_code)
        keys.append(str(daily_info.terminal_no))
        keys.append(daily_info.business_date)
        return self.make_shard_key(keys)
