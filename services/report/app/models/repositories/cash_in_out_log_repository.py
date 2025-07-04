# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.exceptions import CannotCreateException, DuplicateKeyException

from app.config.settings import settings
from app.models.documents.cash_in_out_log import CashInOutLog

logger = getLogger(__name__)


class CashInOutLogRepository(AbstractRepository[CashInOutLog]):
    """
    Repository for cash in/out log operations.

    This class provides methods for storing and retrieving cash drawer operation
    logs in the database. It handles data related to adding or removing cash
    from terminal drawers.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str) -> None:
        """
        Initialize the cash in/out log repository.

        Args:
            db: AsyncIOMotorDatabase instance for database operations
            tenant_id: Identifier for the tenant
        """
        super().__init__(settings.DB_COLLECTION_NAME_CASH_IN_OUT_LOG, CashInOutLog, db)
        self.tenant_id = tenant_id

    async def create_cash_in_out_log(self, cash_in_out_log: CashInOutLog) -> CashInOutLog:
        """
        Create a new cash in/out log in the database.

        This method attempts to store a cash in/out log document in the database.
        If a duplicate key error occurs, it will update the existing document instead.

        Args:
            cash_in_out_log: Cash in/out log document to store

        Returns:
            The stored cash in/out log document

        Raises:
            CannotCreateException: If the cash in/out log cannot be created
        """
        logger.debug("CashInOutLogRepository.create_cash_in_out_log: cash_in_out_log->{cash_in_out_log}")

        try:
            # Check if the log is already created
            filter = {
                "tenant_id": cash_in_out_log.tenant_id,
                "store_code": cash_in_out_log.store_code,
                "terminal_no": cash_in_out_log.terminal_no,
                "business_date": cash_in_out_log.business_date,
                "open_counter": cash_in_out_log.open_counter,
                "generate_date_time": cash_in_out_log.generate_date_time,
            }
            if await self.get_one_async(filter):
                logger.warning(f"Cashlog already exists. transaction: {cash_in_out_log}")
                return cash_in_out_log

            # create new cash in/out log
            cash_in_out_log.shard_key = self.__get_shard_key(cash_in_out_log)
            logger.debug(f"CashInOutLog.create_cash_in_out_log: cash_in_out_log->{cash_in_out_log}")
            if not await self.create_async(cash_in_out_log):
                raise Exception()
            return cash_in_out_log

        except Exception as e:
            message = f"Cannot create cash in/out log: {cash_in_out_log}"
            raise CannotCreateException(message, self.collection_name, cash_in_out_log, logger, e) from e

    async def get_cash_in_out_logs(
        self, filter: dict, limit: int = 100, page: int = 1, sort: list[tuple[str, int]] = None
    ) -> PaginatedResult[CashInOutLog]:
        """
        Retrieve cash in/out logs based on query parameters.

        This method allows for flexible querying of cash in/out logs based on
        the provided filter criteria. Results are paginated.

        Args:
            filter: Dictionary of filter criteria
            limit: Maximum number of results per page (default: 100)
            page: Page number (default: 1)
            sort: List of field name and direction tuples for sorting

        Returns:
            Paginated result containing matching cash in/out logs
        """
        logger.debug(
            f"CashInOutLogRepository.get_cash_in_out_logs: tenant_id->{self.tenant_id}, "
            f"filter->{filter}, limit->{limit}, page->{page}, sort->{sort}"
        )
        return await self.get_paginated_list_async(filter, limit, page, sort)

    def __get_shard_key(self, cash_in_out_log: CashInOutLog) -> str:
        """
        Generate a shard key for database partitioning.

        Creates a composite shard key from tenant ID, store code,
        terminal number, and business date.

        Args:
            cash_in_out_log: Cash in/out log document

        Returns:
            String representation of the shard key
        """
        keys = []
        keys.append(cash_in_out_log.tenant_id)
        keys.append(cash_in_out_log.store_code)
        keys.append(str(cash_in_out_log.terminal_no))
        keys.append(cash_in_out_log.business_date)
        return self.make_shard_key(keys)
