# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.config.settings import settings

from logging import getLogger

logger = getLogger(__name__)


class StaffMasterRepository(AbstractRepository[StaffMasterDocument]):
    """
    Repository for managing staff member master data in the database.

    This class provides specific implementation for CRUD operations on staff data,
    extending the generic functionality provided by AbstractRepository. It handles
    information about staff members (employees) including their authentication details,
    permissions, and roles.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str):
        """
        Initialize a new StaffMasterRepository instance.

        Args:
            db: MongoDB database instance
            tenant_id: Identifier for the tenant whose data this repository will manage
        """
        super().__init__(settings.DB_COLLECTION_NAME_STAFF_MASTER, StaffMasterDocument, db)
        self.tenant_id = tenant_id

    async def create_staff_async(self, document: StaffMasterDocument) -> StaffMasterDocument:
        """
        Create a new staff member record in the database.

        This method sets the tenant ID and generates a shard key before creating the document.

        Args:
            document: Staff member document to create

        Returns:
            The created staff member document
        """
        document.tenant_id = self.tenant_id
        document.shard_key = self.__get_shard_key(document)
        success = await self.create_async(document)
        if success:
            return document
        else:
            raise Exception("Failed to create staf")

    async def get_staff_by_id_async(self, staff_id: str) -> StaffMasterDocument:
        """
        Retrieve a staff member by their unique ID.

        Args:
            staff_id: Unique identifier for the staff member

        Returns:
            The matching staff member document, or None if not found
        """
        return await self.get_one_async(self.__make_query_filter(staff_id))

    async def get_staff_by_filter_async(
        self, query_filter: dict, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> list[StaffMasterDocument]:
        """
        Retrieve staff members matching the specified filter with pagination and sorting.

        This method automatically adds tenant filtering to ensure data isolation.

        Args:
            query_filter: MongoDB query filter to select staff members
            limit: Maximum number of staff members to return per page
            page: Page number (1-based) to retrieve
            sort: List of tuples containing field name and sort direction

        Returns:
            List of staff member documents matching the query parameters
        """
        query_filter["tenant_id"] = self.tenant_id
        logger.debug(f"query_filter: {query_filter} limit: {limit} page: {page} sort: {sort}")
        return await self.get_list_async_with_sort_and_paging(query_filter, limit, page, sort)

    async def update_staff_async(self, staff_id: str, update_data: dict) -> StaffMasterDocument:
        """
        Update specific fields of a staff member record.

        Args:
            staff_id: Unique identifier for the staff member to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            The updated staff member document
        """
        success = await self.update_one_async(self.__make_query_filter(staff_id), update_data)
        if success:
            return await self.get_staff_by_id_async(staff_id)
        else:
            raise Exception(f"Failed to update staff with id {staff_id}")

    async def replace_staff_async(self, staff_id: str, new_document: StaffMasterDocument) -> StaffMasterDocument:
        """
        Replace an existing staff member record with a new document.

        Args:
            staff_id: Unique identifier for the staff member to replace
            new_document: New staff member document to replace the existing one

        Returns:
            The replaced staff member document
        """
        success = await self.replace_one_async(self.__make_query_filter(staff_id), new_document)
        if success:
            return new_document
        else:
            raise Exception(f"Failed to replace staff with id {staff_id}")

    async def delete_staff_async(self, staff_id: str):
        """
        Delete a staff member record from the database.

        Args:
            staff_id: Unique identifier for the staff member to delete

        Returns:
            None
        """
        return await self.delete_async(self.__make_query_filter(staff_id))

    async def get_staff_count_async(self) -> int:
        """
        Get the count of all staff members for the current tenant.

        Returns:
            Count of staff members for the tenant
        """
        if self.dbcollection is None:
            await self.initialize()
        query_filter = {"tenant_id": self.tenant_id}
        return await self.dbcollection.count_documents(query_filter)

    def __make_query_filter(self, staff_id: str) -> dict:
        """
        Create a query filter for staff operations based on tenant and staff ID.

        This private method ensures that all queries are scoped to the correct tenant.

        Args:
            staff_id: Unique identifier for the staff member

        Returns:
            Dictionary containing the query filter parameters
        """
        return {"tenant_id": self.tenant_id, "id": staff_id}

    def __get_shard_key(self, document: StaffMasterDocument) -> str:
        """
        Generate a shard key for the staff member document.

        Currently uses only the tenant ID as the sharding key.

        Args:
            document: Staff member document for which to generate a shard key

        Returns:
            String representation of the shard key
        """
        keys = []
        keys.append(document.tenant_id)
        return self.make_shard_key(keys)
