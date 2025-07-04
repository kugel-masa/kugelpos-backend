# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Tenant Information Repository Module

This module provides repository level functionality for tenant information management,
handling database operations for tenants and their associated stores. It implements
CRUD operations for tenant data and additional functionality for store management
within tenants.
"""

from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import (
    CannotCreateException,
    NotFoundException,
    UpdateNotWorkException,
    CannotDeleteException,
    AlreadyExistException,
)
from kugel_common.utils.misc import get_app_time

from app.config.settings import settings
from app.models.documents.tenant_info_document import TenantInfoDocument, StoreInfo

logger = getLogger(__name__)


class TenantInfoRepository(AbstractRepository[TenantInfoDocument]):
    """
    Tenant Information Repository

    This repository is responsible for handling database operations for tenant information
    and store management. It provides methods for creating, retrieving, updating,
    and deleting tenant records as well as managing store information within tenants.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str) -> None:
        """
        Initialize the tenant information repository

        Args:
            db: MongoDB database connection
            tenant_id: Tenant ID to associate with this repository
        """
        super().__init__(settings.DB_COLLECTION_NAME_TENANT_INFO, TenantInfoDocument, db)
        self.tenant_id = tenant_id

    async def create_tenant_info_async(
        self, tenant_name: str, stores: list[StoreInfo] = None, tags: list[str] = None
    ) -> TenantInfoDocument:
        """
        Create a new tenant information document in the database

        Args:
            tenant_name: Name of the tenant
            stores: Optional list of stores for the tenant (typically empty at creation)
            tags: Optional list of tags for categorizing the tenant

        Returns:
            The created tenant information document

        Raises:
            CannotCreateException: If the tenant creation fails
        """
        tenant_doc = TenantInfoDocument()
        tenant_doc.tenant_id = self.tenant_id
        tenant_doc.tenant_name = tenant_name
        tenant_doc.stores = stores
        tenant_doc.tags = tags
        tenant_doc.shard_key = self.__make_shard_key(tenant_info=tenant_doc)

        result = await self.create_async(tenant_doc)
        if not result:
            message = f"Cannot create tenant info: tenant_id->{self.tenant_id}"
            raise CannotCreateException(message, self.collection_name, tenant_doc.model_dump(), logger)
        return tenant_doc

    async def get_tenant_info_async(self) -> TenantInfoDocument:
        """
        Retrieve tenant information from the database

        Returns:
            The tenant information document

        Raises:
            NotFoundException: If the tenant is not found
        """
        search_dict = {"tenant_id": self.tenant_id}
        tenant_doc = await self.get_one_async(search_dict)
        if tenant_doc is None:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise NotFoundException(message, self.collection_name, search_dict, logger)
        return tenant_doc

    async def update_tenant_info_async(self, tenant_name: str, tags: list[str] = None) -> TenantInfoDocument:
        """
        Update tenant information in the database

        Args:
            tenant_name: New name for the tenant
            tags: Optional new list of tags for the tenant

        Returns:
            The updated tenant information document

        Raises:
            NotFoundException: If the tenant is not found
            UpdateNotWorkException: If the update operation fails
        """
        search_dict = {"tenant_id": self.tenant_id}
        tenant_doc = await self.get_one_async(search_dict)
        if tenant_doc is None:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise NotFoundException(message, self.collection_name, search_dict, logger)

        tenant_doc.tenant_name = tenant_name
        tenant_doc.tags = tags
        result = await self.replace_one_async(search_dict, tenant_doc)
        if not result:
            message = f"Cannot update tenant info: tenant name->{tenant_name}, tenant_id->{self.tenant_id}"
            raise UpdateNotWorkException(message, self.collection_name, search_dict, logger)
        return tenant_doc

    async def delete_tenant_info_async(self) -> bool:
        """
        Delete a tenant from the database

        Returns:
            True if deletion was successful

        Raises:
            CannotDeleteException: If the delete operation fails
        """
        search_dict = {"tenant_id": self.tenant_id}
        result = await self.delete_async(search_dict)
        if not result:
            message = f"Cannot delete tenant info: tenant_id->{self.tenant_id}"
            raise CannotDeleteException(message, self.collection_name, search_dict, logger)
        return result

    async def add_store_async(self, new_store: StoreInfo) -> TenantInfoDocument:
        """
        Add a new store to a tenant

        Args:
            new_store: Store information object to add

        Returns:
            The updated tenant information document containing the new store

        Raises:
            NotFoundException: If the tenant is not found
            AlreadyExistException: If a store with the same code already exists
            UpdateNotWorkException: If the store addition fails
        """
        search_dict = {"tenant_id": self.tenant_id}
        tenant_doc = await self.get_one_async(search_dict)
        if tenant_doc is None:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise NotFoundException(message, self.collection_name, search_dict, logger)

        for store in tenant_doc.stores:
            if store.store_code == new_store.store_code:
                message = f"Store already exists. store_code->{new_store.store_code}, tenant_id->{self.tenant_id}"
                raise AlreadyExistException(message, self.collection_name, search_dict, logger)

        new_store.created_at = get_app_time()
        tenant_doc.stores.append(new_store)
        result = await self.replace_one_async(search_dict, tenant_doc)
        if not result:
            message = f"Cannot add store: store info->{new_store}, tenant_id->{self.tenant_id}"
            raise UpdateNotWorkException(message, self.collection_name, search_dict, logger)
        return tenant_doc

    async def get_stores_async(self, limit: int, page: int, sort: list[tuple[str, int]]) -> list[StoreInfo]:
        """
        Get a list of stores for the tenant with sorting options

        Args:
            limit: Maximum number of results to return per page
            page: Page number to return
            sort: List of tuples containing field name and sort direction (1 for asc, -1 for desc)

        Returns:
            List of store information objects

        Raises:
            NotFoundException: If the tenant is not found
        """
        search_dict = {"tenant_id": self.tenant_id}
        logger.debug(f"search_dict: {search_dict} limit: {limit}, page: {page}, sort: {sort}")
        tenant_doc = await self.get_one_async(search_dict)
        if tenant_doc is None:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise NotFoundException(message, self.collection_name, search_dict, logger)

        if sort:
            for field, order in reversed(sort):
                reverse = order == -1
                tenant_doc.stores.sort(key=lambda x: getattr(x, field), reverse=reverse)

        return tenant_doc.stores

    async def get_store_async(self, store_code: str) -> StoreInfo:
        """
        Get information for a specific store

        Args:
            store_code: Code of the store to retrieve

        Returns:
            Store information object, or None if the store is not found

        Raises:
            NotFoundException: If the tenant is not found
        """
        search_dict = {"tenant_id": self.tenant_id}
        tenant_doc = await self.get_one_async(search_dict)
        if tenant_doc is None:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise NotFoundException(message, self.collection_name, search_dict, logger)

        for store in tenant_doc.stores:
            if store.store_code == store_code:
                return store
        return None

    async def update_store_async(self, store_code: str, update_dict: dict) -> TenantInfoDocument:
        """
        Update information for a specific store

        Args:
            store_code: Code of the store to update
            update_dict: Dictionary containing the fields to update and their new values

        Returns:
            The updated store information object

        Raises:
            NotFoundException: If the tenant is not found
            UpdateNotWorkException: If the store update fails
        """
        logger.debug(f"store_code: {store_code}, update_dict: {update_dict}")

        search_dict = {"tenant_id": self.tenant_id}
        tenant_doc = await self.get_one_async(search_dict)
        if tenant_doc is None:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise NotFoundException(message, self.collection_name, search_dict, logger)

        for store in tenant_doc.stores:
            if store.store_code == store_code:
                if update_dict.get("store_name"):
                    store.store_name = update_dict.get("store_name")
                if update_dict.get("status"):
                    store.status = update_dict.get("status")
                if update_dict.get("business_date"):
                    store.business_date = update_dict.get("business_date")
                if update_dict.get("tags"):
                    store.tags = update_dict.get("tags")
                store.updated_at = get_app_time()
                return_store = store
                break

        result = await self.replace_one_async(search_dict, tenant_doc)
        if not result:
            message = f"Cannot update store: store info->{update_dict}, tenant_id->{self.tenant_id}"
            raise UpdateNotWorkException(message, self.collection_name, search_dict, logger)
        return return_store

    async def delete_store_async(self, store_code: str) -> bool:
        """
        Delete a store from the tenant

        Args:
            store_code: Code of the store to delete

        Returns:
            True if deletion was successful

        Raises:
            NotFoundException: If the tenant is not found
            CannotDeleteException: If the store deletion fails
        """
        search_dict = {"tenant_id": self.tenant_id}
        tenant_doc = await self.get_one_async(search_dict)
        if tenant_doc is None:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise NotFoundException(message, self.collection_name, search_dict, logger)

        tenant_doc.stores = [store for store in tenant_doc.stores if store.store_code != store_code]
        result = await self.replace_one_async(search_dict, tenant_doc)
        if not result:
            message = f"Cannot delete store: store code->{store_code}, tenant_id->{self.tenant_id}"
            raise CannotDeleteException(message, self.collection_name, search_dict, logger)
        return result

    def __make_shard_key(self, tenant_info: TenantInfoDocument) -> str:
        """
        Create a shard key for database sharding

        Args:
            tenant_info: Tenant information document

        Returns:
            Shard key string for database partitioning
        """
        keys = []
        keys.append(tenant_info.tenant_id)
        return self.make_shard_key(keys)
