# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Request Log Repository implementation

This module provides database operations for storing and retrieving API request logs.
It implements the repository pattern for the RequestLog document model.
"""
from typing import Type
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.documents.request_log_document import RequestLog
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import CannotCreateException
from kugel_common.config.settings import settings

logger = getLogger(__name__)

class RequestLogRepository(AbstractRepository[RequestLog]):
    """
    Repository class for API request logging
    
    Extends the AbstractRepository to provide specialized operations for working with
    RequestLog documents. This repository is responsible for persisting API request
    and response information to the database for auditing and debugging purposes.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize a new RequestLogRepository instance
        
        Args:
            db: MongoDB database connection instance
        """
        super().__init__(settings.DB_COLLECTION_NAME_REQUEST_LOG, RequestLog, db)

    async def create_request_log_async(self, request_log: RequestLog) -> RequestLog:
        """
        Create a new request log entry in the database
        
        Generates a shard key based on request information and persists the
        request log document to the database.
        
        Args:
            request_log: The RequestLog document to persist
            
        Returns:
            RequestLog: The created request log document
            
        Raises:
            CannotCreateException: If the request log cannot be created
        """
        try:
            request_log.shard_key=self.__get_shard_key(request_log)
            logger.debug(f"RequestLogRepository.create_request_log_async: request_log->{request_log}")
            if not await self.create_async(request_log):
                raise Exception()
            return request_log
        except Exception as e:
            message = (
                f"Failed to create request log: {request_log}"
            )
            raise CannotCreateException(message, logger, e) from e

    def __get_shard_key(self, request_log: RequestLog) -> str:
        """
        Generate a shard key for the request log document
        
        Creates a composite key from tenant ID, store code, terminal number,
        username, and request date to ensure proper data distribution across shards.
        
        Args:
            request_log: The RequestLog document to generate a key for
            
        Returns:
            str: The generated shard key
        """
        key =[]
        if request_log.terminal_info is not None:
            tenant_id = request_log.terminal_info.tenant_id
        else:
            tenant_id = request_log.user_info.tenant_id

        key.append(tenant_id)
        key.append(request_log.terminal_info.store_code if request_log.terminal_info is not None else "NO STORE CODE")
        key.append(str(request_log.terminal_info.terminal_no) if request_log.terminal_info is not None else "NO TERMINAL")
        key.append(request_log.user_info.username if request_log.user_info is not None else "NO USER")
        key.append(request_log.request_info.accept_time.split("T")[0])
        return self.make_shard_key(key)