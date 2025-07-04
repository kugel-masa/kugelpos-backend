# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from kugel_common.exceptions import (
    DocumentAlreadyExistsException,
    DocumentNotFoundException,
    InvalidRequestDataException,
)
from app.models.documents.settings_master_document import SettingsMasterDocument, SettingsValue
from app.models.repositories.settings_master_repository import SettingsMasterRepository
from app.utils.json_settings import ensure_json_format, process_setting_values

logger = getLogger(__name__)


class SettingsMasterService:
    """
    Service class for managing system settings master data operations.

    This service provides business logic for creating, retrieving, updating,
    and deleting system settings in the master data database.
    Settings can be configured at different levels (global, store, terminal).
    """

    def __init__(self, settings_master_repo: SettingsMasterRepository):
        """
        Initialize the SettingsMasterService with a repository.

        Args:
            settings_master_repo: Repository for settings master data operations
        """
        self.settings_master_repo = settings_master_repo

    async def create_settings_async(self, name: str, default_value: str, values: list[dict]) -> SettingsMasterDocument:
        """
        Create a new system setting in the database.

        Args:
            name: Unique identifier for the setting
            default_value: The default value to use when no specific value is found
            values: List of dictionaries containing specific setting values for different scopes

        Returns:
            Newly created SettingsMasterDocument

        Raises:
            DocumentAlreadyExistsException: If a setting with the given name already exists
        """

        # check if exists
        settings = await self.settings_master_repo.get_settings_by_name_async(name)
        if settings is not None:
            message = f"settings with name {name} already exists. tenant_id: {settings.tenant_id}"
            raise DocumentAlreadyExistsException(message, logger)

        settings_doc = SettingsMasterDocument()
        settings_doc.name = name
        # Ensure default value is in JSON format if it's JSON data
        settings_doc.default_value = ensure_json_format(default_value)
        # Process values to ensure JSON formatting
        processed_values = process_setting_values(values)
        settings_doc.values = [SettingsValue(**value) for value in processed_values]
        return await self.settings_master_repo.create_settings_async(settings_doc)

    async def get_settings_by_name_async(self, name: str) -> SettingsMasterDocument:
        """
        Retrieve a settings document by its name.

        Args:
            name: Unique name of the setting to retrieve

        Returns:
            SettingsMasterDocument with the specified name, or None if not found
        """
        return await self.settings_master_repo.get_settings_by_name_async(name)

    async def get_settings_value_by_name_async(
        self,
        name: str,
        store_code: str,
        terminal_no: int,
    ) -> str:
        """
        Retrieve the appropriate value for a setting based on hierarchical scope.

        This method implements a priority-based lookup for settings:
        1. Store and terminal specific setting
        2. Store specific setting (any terminal)
        3. Global setting
        4. Default value

        Args:
            name: Name of the setting to retrieve
            store_code: Store code to look up store-specific settings
            terminal_no: Terminal number to look up terminal-specific settings

        Returns:
            The appropriate setting value as a string

        Raises:
            DocumentNotFoundException: If no setting with the given name exists
        """

        # get the settings document
        setting_doc = await self.settings_master_repo.get_settings_by_name_async(name)
        logger.debug(f"setting_doc: {setting_doc}")
        if setting_doc is None:
            message = f"settings with name {name} not found"
            raise DocumentNotFoundException(message, logger)

        # get the value from the settings in the order of priority
        priority = [
            {"store_code": store_code, "terminal_no": terminal_no},
            {"store_code": store_code, "terminal_no": None},
            {"store_code": None, "terminal_no": None},
        ]

        value_list = [value.model_dump() for value in setting_doc.values]
        for p in priority:
            for value_dict in value_list:
                if all(value_dict[key] == p[key] for key in p):
                    return value_dict["value"]

        # if no settings value is found, return the default value
        return setting_doc.default_value

    async def get_settings_all_async(self, limit: int, page: int, sort: list[tuple[str, int]]) -> list:
        """
        Retrieve all system settings with pagination and sorting.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)

        Returns:
            List of SettingsMasterDocument objects
        """
        return await self.settings_master_repo.get_settings_all_async(limit, page, sort)

    async def get_settings_all_paginated_async(
        self, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> tuple[list[SettingsMasterDocument], int]:
        """
        Retrieve all system settings with pagination metadata.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction

        Returns:
            Tuple of (list of SettingsMasterDocument objects, total count)
        """
        settings_list = await self.settings_master_repo.get_settings_all_async(limit, page, sort)
        total_count = await self.settings_master_repo.get_settings_count_async()
        return settings_list, total_count

    async def update_settings_async(self, name: str, update_data: dict) -> SettingsMasterDocument:
        """
        Update an existing system setting with new data.

        Args:
            name: Unique name of the setting to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated SettingsMasterDocument

        Raises:
            InvalidRequestDataException: If the name in update_data doesn't match the name parameter
            DocumentNotFoundException: If no setting with the given name exists
        """

        # check if name in update_data equals name
        if "name" in update_data and update_data["name"] != name:
            message = f"name in update_data {update_data['name']} not equal to name {name}"
            raise InvalidRequestDataException(message, logger)

        # check if settings exists
        settings = await self.settings_master_repo.get_settings_by_name_async(name)
        if settings is None:
            message = f"settings with name {name} not found"
            raise DocumentNotFoundException(message, logger)

        # update settings
        # remove name from update_data
        if "name" in update_data:
            del update_data["name"]

        # Process default_value if present
        if "default_value" in update_data and isinstance(update_data["default_value"], str):
            update_data["default_value"] = ensure_json_format(update_data["default_value"])

        # Process values if present
        if "values" in update_data and isinstance(update_data["values"], list):
            update_data["values"] = process_setting_values(update_data["values"])

        return await self.settings_master_repo.update_settings_async(name, update_data)

    async def delete_settings_async(self, name: str) -> None:
        """
        Delete a system setting from the database.

        Args:
            name: Unique name of the setting to delete

        Raises:
            DocumentNotFoundException: If no setting with the given name exists
        """
        settings = await self.settings_master_repo.get_settings_by_name_async(name)
        if settings is None:
            message = f"settings with name {name} not found"
            raise DocumentNotFoundException(message, logger)
        return await self.settings_master_repo.delete_settings_async(name)
