# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Tenant Service Module

This module provides the service layer for tenant and store management operations.
It encapsulates the business logic for creating, retrieving, updating, and deleting
tenants and stores in the Terminal service.
"""

from logging import getLogger

from app.models.repositories.tenant_info_repository import TenantInfoRepository
from app.models.documents.tenant_info_document import TenantInfoDocument, StoreInfo
from app.enums.store_status import StoreStatus
from app.exceptions import (
    NotFoundException,
    DuplicateKeyException,
    TenantAlreadyExistsException,
    TenantCreateException,
    TenantNotFoundException,
    TenantUpdateException,
    TenantDeleteException,
    StoreAlreadyExistsException,
    StoreNotFoundException,
)

logger = getLogger(__name__)


class TenantService:
    """
    Tenant Service Class

    This service provides methods for tenant and store management operations.
    It acts as an intermediary between the API layer and the repository layer,
    handling business logic and error handling.
    """

    def __init__(self, tenant_info_repo: TenantInfoRepository, tenant_id: str) -> None:
        """
        Initialize a TenantService instance

        Args:
            tenant_info_repo: Repository for tenant information
            tenant_id: ID of the tenant being managed by this service
        """
        self.tenant_info_repo = tenant_info_repo
        self.tenant_id = tenant_id

    async def create_tenant_async(
        self, tenant_name: str, stores: list[StoreInfo], tags: list[str]
    ) -> TenantInfoDocument:
        """
        Create a new tenant in the system

        Args:
            tenant_name: Name of the tenant
            stores: List of stores for the tenant (typically empty at creation)
            tags: List of tags for categorizing the tenant

        Returns:
            TenantInfoDocument: The created tenant information

        Raises:
            TenantAlreadyExistsException: If a tenant with the same ID already exists
            TenantCreateException: If tenant creation fails for any other reason
        """
        try:
            return await self.tenant_info_repo.create_tenant_info_async(tenant_name, stores, tags)
        except DuplicateKeyException as e:
            message = f"Tenant already exists. tenant_id->{self.tenant_id}"
            raise TenantAlreadyExistsException(message, logger) from e
        except Exception as e:
            message = f"Cannot create tenant info: tenant_id->{self.tenant_id}"
            raise TenantCreateException(message, logger) from e

    async def get_tenant_async(self) -> TenantInfoDocument:
        """
        Retrieve tenant information

        Returns:
            TenantInfoDocument: The tenant information

        Raises:
            TenantNotFoundException: If the tenant is not found
        """
        try:
            return await self.tenant_info_repo.get_tenant_info_async()
        except Exception as e:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise TenantNotFoundException(message=message, logger=logger, original_exception=e) from e

    async def update_tenant_async(self, tenant_name: str, tags: list[str]) -> TenantInfoDocument:
        """
        Update tenant information

        Args:
            tenant_name: New name for the tenant
            tags: New list of tags for the tenant

        Returns:
            TenantInfoDocument: The updated tenant information

        Raises:
            TenantUpdateException: If the update operation fails
        """
        try:
            return await self.tenant_info_repo.update_tenant_info_async(tenant_name=tenant_name, tags=tags)
        except Exception as e:
            message = f"Cannot update tenant info: tenant_id->{self.tenant_id}"
            raise TenantUpdateException(message=message, logger=logger, original_exception=e) from e

    async def delete_tenant_async(self) -> bool:
        """
        Delete a tenant from the system

        Returns:
            bool: True if the deletion was successful

        Raises:
            TenantDeleteException: If the delete operation fails
        """
        try:
            return await self.tenant_info_repo.delete_tenant_info_async()
        except Exception as e:
            message = f"Cannot delete tenant info: tenant_id->{self.tenant_id}"
            raise TenantDeleteException(message=message, logger=logger, original_exception=e) from e

    async def add_store_async(
        self,
        store_code: str,
        store_name: str,
        status: str = StoreStatus.Idle.value,
        business_date: str = None,
        tags: list[str] = [],
    ) -> TenantInfoDocument:
        """
        Add a new store to the tenant

        Args:
            store_code: Unique code for the store
            store_name: Name of the store
            status: Initial status of the store (default: Idle)
            business_date: Business date for the store (optional)
            tags: List of tags for categorizing the store

        Returns:
            TenantInfoDocument: The updated tenant information containing the new store

        Raises:
            TenantNotFoundException: If the tenant is not found
            StoreAlreadyExistsException: If a store with the same code already exists
            TenantUpdateException: If the store addition fails for any other reason
        """
        store = StoreInfo()
        store.store_code = store_code
        store.store_name = store_name
        store.status = status
        store.business_date = business_date
        store.tags = tags

        try:
            return await self.tenant_info_repo.add_store_async(new_store=store)
        except NotFoundException as e:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise TenantNotFoundException(message=message, logger=logger, original_exception=e) from e
        except DuplicateKeyException as e:
            message = f"Store already exists. store_code->{store.store_code}, tenant_id->{self.tenant_id}"
            raise StoreAlreadyExistsException(message=message, logger=logger) from e
        except Exception as e:
            message = f"Cannot add store info: tenant_id->{self.tenant_id}"
            raise TenantUpdateException(message=message, logger=logger, original_exception=e) from e

    async def get_stores_async(self, limit: int, page: int, sort: list[tuple[str, int]]) -> list[StoreInfo]:
        """
        Get a paginated list of stores for the tenant

        Args:
            limit: Maximum number of results to return
            page: Page number to return
            sort: List of tuples containing field name and sort direction (1 for asc, -1 for desc)

        Returns:
            list[StoreInfo]: List of store information

        Raises:
            TenantNotFoundException: If the tenant is not found
            SystemError: If the operation fails for any other reason
        """
        try:
            return await self.tenant_info_repo.get_stores_async(limit, page, sort)
        except NotFoundException as e:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise TenantNotFoundException(message=message, logger=logger, original_exception=e) from e
        except Exception as e:
            message = f"Cannot get stores info: tenant_id->{self.tenant_id}"
            raise SystemError(message=message, logger=logger, original_exception=e) from e

    async def get_store_async(self, store_code: str) -> StoreInfo:
        """
        Get information for a specific store

        Args:
            store_code: Code of the store to retrieve

        Returns:
            StoreInfo: The store information

        Raises:
            TenantNotFoundException: If the tenant is not found
            StoreNotFoundException: If the store is not found
        """
        try:
            store = await self.tenant_info_repo.get_store_async(store_code=store_code)
            if store is None:
                message = f"Store Not found. store_code->{store_code}, tenant_id->{self.tenant_id}"
                raise StoreNotFoundException(message=message, logger=logger)
            return store
        except NotFoundException as e:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise TenantNotFoundException(message=message, logger=logger, original_exception=e) from e
        except Exception as e:
            raise e

    async def update_store_async(self, store_code: str, update_dict: dict) -> StoreInfo:
        """
        Update information for a specific store

        Args:
            store_code: Code of the store to update
            update_dict: Dictionary containing the fields to update and their new values

        Returns:
            StoreInfo: The updated store information

        Raises:
            TenantNotFoundException: If the tenant is not found
            TenantUpdateException: If the update operation fails
        """
        try:
            return await self.tenant_info_repo.update_store_async(store_code=store_code, update_dict=update_dict)
        except NotFoundException as e:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise TenantNotFoundException(message=message, logger=logger, original_exception=e) from e
        except Exception as e:
            message = f"Cannot update store info: tenant_id->{self.tenant_id}"
            raise TenantUpdateException(message=message, logger=logger, original_exception=e) from e

    async def delete_store_async(self, store_code: str) -> bool:
        """
        Delete a store from the tenant

        Args:
            store_code: Code of the store to delete

        Returns:
            bool: True if the deletion was successful

        Raises:
            TenantNotFoundException: If the tenant is not found
            TenantDeleteException: If the delete operation fails
        """
        try:
            return await self.tenant_info_repo.delete_store_async(store_code=store_code)
        except NotFoundException as e:
            message = f"Tenant Info Not found. tenant_id->{self.tenant_id}"
            raise TenantNotFoundException(message=message, logger=logger, original_exception=e) from e
        except Exception as e:
            message = f"Cannot delete store info: tenant_id->{self.tenant_id}"
            raise TenantDeleteException(message=message, logger=logger, original_exception=e) from e
