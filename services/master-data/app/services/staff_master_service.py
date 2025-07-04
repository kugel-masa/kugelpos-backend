# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from typing import Any

from kugel_common.exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    InvalidRequestDataException,
)
from app.models.documents.staff_master_document import StaffMasterDocument
from app.models.repositories.staff_master_repository import StaffMasterRepository

logger = getLogger(__name__)


class StaffMasterService:
    """
    Service class for managing staff member master data operations.

    This service provides business logic for creating, retrieving, updating,
    and deleting staff member records in the master data database.
    Staff records contain information about employees including their credentials and roles.
    """

    def __init__(self, staff_master_repo: StaffMasterRepository):
        """
        Initialize the StaffMasterService with a repository.

        Args:
            staff_master_repo: Repository for staff master data operations
        """
        self.staff_master_repo = staff_master_repo

    async def create_staff_async(self, staff_id: str, staff_name: str, pin: str, roles: list) -> StaffMasterDocument:
        """
        Create a new staff member record in the database.

        Args:
            staff_id: Unique identifier for the staff member
            staff_name: Name of the staff member
            pin: Personal identification number for authentication
            roles: List of roles assigned to this staff member

        Returns:
            Newly created StaffMasterDocument

        Raises:
            DocumentAlreadyExistsException: If a staff member with the given ID already exists
        """

        # check if staff exists
        staff = await self.staff_master_repo.get_staff_by_id_async(staff_id)
        if staff is not None:
            message = f"staff with id {staff_id} already exists. tenant_id: {staff.tenant_id}"
            raise DocumentAlreadyExistsException(message, logger)

        staff_doc = StaffMasterDocument()
        staff_doc.id = staff_id
        staff_doc.name = staff_name
        staff_doc.pin = pin
        staff_doc.roles = roles
        return await self.staff_master_repo.create_staff_async(staff_doc)

    async def get_staff_by_id_async(self, staff_id: str) -> StaffMasterDocument:
        """
        Retrieve a staff member by their unique ID.

        Args:
            staff_id: Unique identifier for the staff member

        Returns:
            StaffMasterDocument with the specified ID

        Raises:
            DocumentNotFoundException: If no staff member with the given ID exists
        """
        staff = await self.staff_master_repo.get_staff_by_id_async(staff_id)
        if staff is None:
            message = f"staff with id {staff_id} not found"
            raise DocumentNotFoundException(message, logger)
        return staff

    async def get_staff_all_async(self, limit: int, page: int, sort: list[tuple[str, int]]) -> list:
        """
        Retrieve all staff members with pagination and sorting.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)

        Returns:
            List of StaffMasterDocument objects
        """
        return await self.staff_master_repo.get_staff_by_filter_async({}, limit, page, sort)

    async def get_staff_all_paginated_async(
        self, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> tuple[list[StaffMasterDocument], int]:
        """
        Retrieve all staff members with pagination metadata.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction

        Returns:
            Tuple of (list of StaffMasterDocument objects, total count)
        """
        staff_list = await self.staff_master_repo.get_staff_by_filter_async({}, limit, page, sort)
        total_count = await self.staff_master_repo.get_staff_count_async()
        return staff_list, total_count

    async def update_staff_async(self, staff_id: str, update_data: dict) -> StaffMasterDocument:
        """
        Update an existing staff member's information.

        Args:
            staff_id: Unique identifier for the staff member to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated StaffMasterDocument

        Raises:
            InvalidRequestDataException: If the ID in update_data doesn't match staff_id
            DocumentNotFoundException: If no staff member with the given ID exists
        """

        # check if id in update_data equals staff_id
        if "id" in update_data and update_data["id"] != staff_id:
            message = f"id in update_data {update_data['id']} not equal to staff_id {staff_id}"
            raise InvalidRequestDataException(message, logger)

        # check if staff exists
        staff = await self.staff_master_repo.get_staff_by_id_async(staff_id)
        if staff is None:
            message = f"staff with id {staff_id} not found"
            raise DocumentNotFoundException(message, logger)

        # update staff
        # remove staff_id from update_data
        if "id" in update_data:
            del update_data["id"]
        return await self.staff_master_repo.update_staff_async(staff_id, update_data)

    async def delete_staff_async(self, staff_id: str) -> StaffMasterDocument:
        """
        Delete a staff member from the database.

        Args:
            staff_id: Unique identifier for the staff member to delete

        Returns:
            The deleted StaffMasterDocument

        Raises:
            DocumentNotFoundException: If no staff member with the given ID exists
        """
        staff = await self.staff_master_repo.get_staff_by_id_async(staff_id)
        logger.debug(f"staff: {staff}")
        if staff is None:
            message = f"staff with id {staff_id} not found"
            raise DocumentNotFoundException(message, logger)
        return await self.staff_master_repo.delete_staff_async(staff_id)
