# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.exceptions import RepositoryException
from app.models.documents.settings_master_document import *
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.config.settings import settings

logger = getLogger(__name__)


class SettingsMasterRepository(AbstractRepository[SettingsMasterDocument]):
    """
    Repository for managing system settings master data in the database.

    This class provides specific implementation for CRUD operations on system settings data,
    extending the generic functionality provided by AbstractRepository. It handles
    hierarchical configuration settings that can be scoped at global, store,
    and terminal levels.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str):
        """
        Initialize a new SettingsMasterRepository instance.

        Args:
            db: MongoDB database instance
            tenant_id: Identifier for the tenant whose data this repository will manage
        """
        super().__init__(settings.DB_COLLECTION_NAME_SETTINGS_MASTER, SettingsMasterDocument, db)
        self.tenant_id = tenant_id

    async def create_settings_async(self, document: SettingsMasterDocument) -> SettingsMasterDocument:
        """
        Create a new settings record in the database.

        This method sets the tenant ID and generates a shard key before creating the document.

        Args:
            document: Settings document to create

        Returns:
            The created settings document
        """
        document.tenant_id = self.tenant_id
        document.shard_key = self.__get_shard_key(document)
        success = await self.create_async(document)
        if success:
            return document
        else:
            raise Exception("Failed to create settings")

    async def get_settings_all_async(
        self, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> list[SettingsMasterDocument]:
        """
        Retrieve all settings for the current tenant with pagination and sorting.

        Args:
            limit: Maximum number of settings to return per page
            page: Page number (1-based) to retrieve
            sort: List of tuples containing field name and sort direction

        Returns:
            List of settings documents for the tenant
        """
        query_filter = {"tenant_id": self.tenant_id}
        logger.debug(f"query_filter: {query_filter} limit: {limit} page: {page} sort: {sort}")
        return await self.get_list_async_with_sort_and_paging(query_filter, limit, page, sort)

    async def get_settings_by_name_async(self, name: str) -> SettingsMasterDocument:
        """
        Retrieve a specific setting by its name.

        Args:
            name: Unique name identifier for the setting

        Returns:
            The matching settings document, or None if not found
        """
        query_filter = {"tenant_id": self.tenant_id, "name": name}
        return await self.get_one_async(query_filter)

    async def update_settings_async(self, name: str, update_data: dict) -> SettingsMasterDocument:
        """
        Update specific fields of a settings record.

        Args:
            name: Unique name identifier for the setting to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            The updated settings document
        """
        query_filter = {"tenant_id": self.tenant_id, "name": name}
        success = await self.update_one_async(query_filter, update_data)
        if success:
            return await self.get_settings_by_name_async(name)
        else:
            raise Exception(f"Failed to update settings with name {name}")

    async def delete_settings_async(self, name: str) -> None:
        """
        Delete a settings record from the database.

        Args:
            name: Unique name identifier for the setting to delete

        Returns:
            None
        """
        query_filter = {"tenant_id": self.tenant_id, "name": name}
        return await self.delete_async(query_filter)

    async def get_settings_count_async(self) -> int:
        """
        Get the count of all settings for the current tenant.

        Returns:
            Count of settings for the tenant
        """
        query_filter = {"tenant_id": self.tenant_id}
        if self.dbcollection is None:
            await self.initialize()
        return await self.dbcollection.count_documents(query_filter)

    def __get_shard_key(self, document: SettingsMasterDocument) -> str:
        """
        Generate a shard key for the settings document.

        Currently uses only the tenant ID as the sharding key.

        Args:
            document: Settings document for which to generate a shard key

        Returns:
            String representation of the shard key
        """
        keys = []
        keys.append(document.tenant_id)
        return self.make_shard_key(keys)
