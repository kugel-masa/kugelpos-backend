# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Type
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import CannotCreateException, DuplicateKeyException
from kugel_common.schemas.pagination import PaginatedResult, Metadata

from app.config.settings import settings
from app.models.documents.cash_in_out_log import CashInOutLog

logger = getLogger(__name__)


class CashInOutLogRepository(AbstractRepository[CashInOutLog]):
    """
    Cash In/Out Log Repository

    This repository class handles database operations for cash drawer transactions,
    including adding and retrieving records of cash additions and removals.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str) -> None:
        """
        Initialize the cash in/out log repository

        Args:
            db: MongoDB database connection
            tenant_id: Tenant ID to associate with this repository
        """
        super().__init__(settings.DB_COLLECTION_NAME_CASH_IN_OUT_LOG, CashInOutLog, db)
        self.tenant_id = tenant_id

    async def create_cash_in_out_log(self, cash_in_out_log: CashInOutLog) -> CashInOutLog:
        """
        Create a new cash in/out log document in the database

        Records a cash transaction (addition or removal) for a terminal's cash drawer.
        Handles potential duplicate transactions by updating existing records.

        Args:
            cash_in_out_log: Cash in/out log document to create

        Returns:
            The created or updated cash in/out log document

        Raises:
            CannotCreateException: If the document creation fails
        """
        logger.debug("CashInOutLogRepository.create_cash_in_out_log: cash_in_out_log->{cash_in_out_log}")

        try:
            cash_in_out_log.shard_key = self.__get_shard_key(cash_in_out_log)
            logger.debug(f"CashInOutLog.create_cash_in_out_log: cash_in_out_log->{cash_in_out_log}")
            if not await self.create_async(cash_in_out_log):
                raise Exception()
            return cash_in_out_log
        except DuplicateKeyException as e:
            filter = {
                "tenant_id": cash_in_out_log.tenant_id,
                "store_code": cash_in_out_log.store_code,
                "terminal_no": cash_in_out_log.terminal_no,
                "generate_date_time": cash_in_out_log.generate_date_time,
            }
            logger.warning(f"Cashlog already exists. Updating cashlog: {cash_in_out_log} with filter: {filter}")
            await self.replace_one_async(filter, cash_in_out_log)
            return cash_in_out_log
        except Exception as e:
            message = f"Cannot create cash in/out log: {cash_in_out_log}"
            raise CannotCreateException(message, self.collection_name, cash_in_out_log, logger, e) from e

    async def get_cash_in_out_logs(
        self, filter: dict, limit: int = 100, page: int = 1, sort: list[tuple[str, int]] = None
    ) -> PaginatedResult[CashInOutLog]:
        """
        Retrieve cash in/out logs from the database with pagination

        Allows searching for cash transactions with various filters and sorting options.

        Args:
            filter: Dictionary of query criteria for filtering records
            limit: Maximum number of records to return per page
            page: Page number to return (1-based)
            sort: List of field name and direction tuples for sorting results

        Returns:
            Paginated result containing cash in/out log records and metadata
        """
        logger.debug(
            f"CashInOutLogRepository.get_cash_in_out_logs: tenant_id->{self.tenant_id}, "
            f"filter->{filter}, limit->{limit}, page->{page}, sort->{sort}"
        )
        return await self.get_paginated_list_async(filter, limit, page, sort)

    def __get_shard_key(self, cash_in_out_log: CashInOutLog) -> str:
        """
        Generate a shard key for database sharding

        Creates a key that combines tenant, store, terminal, and business date
        to efficiently distribute records across database shards.

        Args:
            cash_in_out_log: Cash in/out log document

        Returns:
            Shard key string
        """
        keys = []
        keys.append(cash_in_out_log.tenant_id)
        keys.append(cash_in_out_log.store_code)
        keys.append(str(cash_in_out_log.terminal_no))
        keys.append(cash_in_out_log.business_date)
        return self.make_shard_key(keys)
