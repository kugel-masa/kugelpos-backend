# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Type
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import CannotCreateException, DuplicateKeyException
from kugel_common.schemas.pagination import PaginatedResult, Metadata

from app.config.settings import settings
from app.models.documents.open_close_log import OpenCloseLog

logger = getLogger(__name__)


class OpenCloseLogRepository(AbstractRepository[OpenCloseLog]):
    """
    Open/Close Log Repository

    This repository class handles database operations for terminal opening and closing operations,
    including creating and retrieving records of terminal business sessions.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str) -> None:
        """
        Initialize the open/close log repository

        Args:
            db: MongoDB database connection
            tenant_id: Tenant ID to associate with this repository
        """
        super().__init__(settings.DB_COLLECTION_NAME_OPEN_CLOSE_LOG, OpenCloseLog, db)
        self.tenant_id = tenant_id

    async def create_open_close_log(self, open_close_log: OpenCloseLog) -> OpenCloseLog:
        """
        Create a new open/close log document in the database

        Records a terminal opening or closing operation, including the business date,
        terminal status, and summary information at the time of the operation.
        Handles potential duplicate records by updating existing entries.

        Args:
            open_close_log: Open/close log document to create

        Returns:
            The created or updated open/close log document

        Raises:
            CannotCreateException: If the document creation fails
        """
        logger.debug("OpenCloseLogRepository.create_open_close_log: open_close_log->{open_close_log}")

        try:
            open_close_log.shard_key = self.__get_shard_key(open_close_log)
            logger.debug(f"OpenCloseLog.create_open_close_log: open_close_log->{open_close_log}")
            if not await self.create_async(open_close_log):
                raise Exception()
            return open_close_log
        except DuplicateKeyException as e:
            filter = {
                "tenant_id": open_close_log.tenant_id,
                "store_code": open_close_log.store_code,
                "terminal_no": open_close_log.terminal_no,
                "business_date": open_close_log.business_date,
                "open_counter": open_close_log.open_counter,
                "operation": open_close_log.operation,
            }
            logger.warning(
                f"OpenCloseLog already exists. Updating open_close_log: {open_close_log} with filter: {filter}"
            )
            await self.replace_one_async(filter, open_close_log)
            return open_close_log
        except Exception as e:
            message = f"Cannot create open/close log: {open_close_log}"
            raise CannotCreateException(message, self.collection_name, open_close_log, logger, e) from e

    def __get_shard_key(self, open_close_log: OpenCloseLog) -> str:
        """
        Generate a shard key for database sharding

        Creates a key that combines tenant, store, terminal, and business date
        to efficiently distribute records across database shards.

        Args:
            open_close_log: Open/close log document

        Returns:
            Shard key string
        """
        keys = []
        keys.append(open_close_log.tenant_id)
        keys.append(open_close_log.store_code)
        keys.append(str(open_close_log.terminal_no))
        keys.append(open_close_log.business_date)
        return self.make_shard_key(keys)
