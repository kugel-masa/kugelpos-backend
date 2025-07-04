# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.exceptions import RepositoryException
from app.models.documents.settings_master_document import SettingsMasterDocument
from app.config.settings import settings

logger = getLogger(__name__)


class SettingsMasterWebRepository:
    """
    Repository class for accessing settings master data through web API.

    This class provides methods to retrieve system settings from the master data service
    and caches retrieved settings to avoid redundant API calls.
    """

    def __init__(
        self,
        tenant_id: str,
        store_code: str = None,
        terminal_no: int = None,
        terminal_info: TerminalInfoDocument = None,
        settings_master_documents: list[SettingsMasterDocument] = None,
    ):
        """
        Initialize the repository with tenant, store, and terminal information.

        Args:
            tenant_id: The tenant identifier
            store_code: Optional store code filter
            terminal_no: Optional terminal number filter
            terminal_info: Terminal information document
            settings_master_documents: Optional list of pre-loaded settings documents for caching
        """
        self.tenant_id = tenant_id
        self.store_code = store_code
        self.terminal_no = terminal_no
        self.terminal_info = terminal_info
        self.settings_master_documents = settings_master_documents
        self.base_url = settings.BASE_URL_MASTER_DATA

    def set_settings_master_documents(self, settings_master_documents: list):
        """
        Set the cached settings master documents.

        Args:
            settings_master_documents: List of settings master documents to cache
        """
        self.settings_master_documents = settings_master_documents

    # get all settings
    async def get_all_settings_async(self) -> list[SettingsMasterDocument]:
        """
        Retrieve all settings for the specified tenant, store, and terminal.

        Fetches all settings from the master data service that match the tenant, store,
        and terminal criteria provided during initialization.

        Returns:
            list[SettingsMasterDocument]: A list of all matching settings

        Raises:
            RepositoryException: If there's an error communicating with the API
        """
        async with get_service_client("master-data") as client:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params = {
                "store_code": self.store_code,
                "terminal_no": self.terminal_no,
                "terminal_id": self.terminal_info.terminal_id,
            }
            endpoint = f"/tenants/{self.tenant_id}/settings"

            try:
                response_data = await client.get(endpoint, params=params, headers=headers)
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 404:
                    message = f"settings not found: {e.status_code}"
                    logger.info(message)
                    response_data = {"success": False, "data": None}
                else:
                    message = f"Request error: {e}"
                    raise RepositoryException(message, logger)

            logger.debug(f"response: {response_data}")

            if response_data.get("success") and response_data.get("data"):
                self.settings_master_documents = [
                    SettingsMasterDocument(**setting) for setting in response_data.get("data")
                ]
            else:
                self.settings_master_documents = []
            return self.settings_master_documents

    # get settings value by name
    async def get_settings_value_by_name_async(self, name: str) -> SettingsMasterDocument:
        """
        Get a specific setting by its name from cache or from the web API.

        First checks if the setting exists in the cache, and if not, fetches it from the API.
        The fetched setting is then added to the cache for future use.

        Args:
            name: The name of the setting to retrieve

        Returns:
            SettingsMasterDocument: The requested setting document, or None if not found

        Raises:
            RepositoryException: If there's an error communicating with the API
        """
        if self.settings_master_documents is None:
            self.settings_master_documents = []

        # first check name exist in the list of settings_master_documents
        setting_doc = next((setting for setting in self.settings_master_documents if setting.name == name), None)
        if setting_doc is not None:
            return setting_doc

        async with get_service_client("master-data") as client:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params = {
                "store_code": self.store_code,
                "terminal_no": self.terminal_no,
                "terminal_id": self.terminal_info.terminal_id,
            }
            endpoint = f"/tenants/{self.tenant_id}/settings/{name}/value"

            try:
                response_data = await client.get(endpoint, params=params, headers=headers)
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 404:
                    message = f"setting not found for name {name}: {e.status_code}"
                    return None
                    # raise NotFoundException(message, name, logger)
                else:
                    message = f"Request error for name {name}: {e}"
                    raise RepositoryException(message, logger)

            logger.debug(f"response: {response_data}")
            return_doc = SettingsMasterDocument(name=name, value=response_data.get("data").get("value"))
            self.settings_master_documents.append(return_doc)
            return return_doc
