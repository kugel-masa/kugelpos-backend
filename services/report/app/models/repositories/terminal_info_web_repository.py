# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language gove/api/rning permissions and  # limitations under the License.
from fastapi import Depends

from kugel_common.exceptions import RepositoryException, NotFoundException
from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.config.settings import settings

from logging import getLogger

logger = getLogger(__name__)


class TerminalInfoWebRepository:
    """
    Repository for retrieving terminal information via web API.

    This class handles communication with the terminal service to fetch
    information about terminals in a store. It uses HTTP requests to
    retrieve terminal data from a remote service.
    """

    def __init__(
        self, tenant_id: str, store_code: str, terminal_id: str = None, api_key: str = None, token: str = None
    ):
        """
        Initialize the terminal information web repository.

        Args:
            tenant_id: Identifier for the tenant
            store_code: Identifier for the store
            terminal_id: Optional identifier for a specific terminal
            api_key: Optional API key for authentication
            token: Optional bearer token for authentication
        """
        self.tenant_id = tenant_id
        self.store_code = store_code
        self.base_url = settings.BASE_URL_TERMINAL
        self.terminal_id = terminal_id
        self.api_key = api_key
        self.token = token

    async def get_terminal_info_list_async(self) -> list[TerminalInfoDocument]:
        """
        Retrieve a list of all terminals for a store.

        This method fetches information about all terminals associated with
        the store specified during repository initialization.

        Returns:
            List of terminal information documents

        Raises:
            NotFoundException: If terminals for the store cannot be found
            RepositoryException: If a communication error occurs
        """
        async with get_service_client("terminal") as client:
            headers = {}
            params = {"store_code": self.store_code, "limit": 0, "page": 1, "sort": "terminal_no:1"}
            if self.api_key is not None and self.terminal_id is not None:
                headers["X-API-KEY"] = self.api_key
                params["terminal_id"] = self.terminal_id
            elif self.token is not None:
                headers["Authorization"] = f"Bearer {self.token}"

            endpoint = "/terminals"
            logger.debug(f"endpoint: {endpoint}, params: {params}, headers: {headers}")

            try:
                response_data = await client.get(endpoint, params=params, headers=headers)
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 404:
                    message = f"Terminal not found for store code {self.store_code}"
                    raise NotFoundException(
                        message=message,
                        collection_name="terminal web",
                        find_key=self.store_code,
                        logger=logger,
                        original_exception=e,
                    )
                else:
                    message = f"Request error for store code {self.store_code}"
                    raise RepositoryException(
                        message=message, collection_name="terminal web", logger=logger, original_exception=e
                    )

            logger.debug(f"response: {response_data}")
            return [TerminalInfoDocument(**terminal) for terminal in response_data.get("data")]

    async def get_terminal_info_async(self, terminal_no: str) -> TerminalInfoDocument:
        """
        Retrieve information for a specific terminal.

        This method fetches information about a specific terminal identified by
        its terminal number within the store specified during repository initialization.

        Args:
            terminal_no: Terminal number to retrieve

        Returns:
            Terminal information document

        Raises:
            NotFoundException: If the terminal cannot be found
            RepositoryException: If a communication error occurs
        """
        async with get_service_client("terminal") as client:
            headers = {}
            params = {"store_code": self.store_code}

            if self.api_key is not None:
                headers["X-API-KEY"] = self.api_key
            elif self.token is not None:
                headers["Authorization"] = f"Bearer {self.token}"

            terminal_id = f"{self.tenant_id}-{self.store_code}-{terminal_no}"
            endpoint = f"/terminals/{terminal_id}"

            try:
                response_data = await client.get(endpoint, params=params, headers=headers)
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 404:
                    message = f"Terminal not found for id {terminal_id}"
                    raise NotFoundException(
                        message=message,
                        collection_name="terminal web",
                        find_key=terminal_id,
                        logger=logger,
                        original_exception=e,
                    )
                else:
                    message = f"Request error for id {terminal_id}"
                    raise RepositoryException(
                        message=message, collection_name="terminal web", logger=logger, original_exception=e
                    )

            logger.debug(f"response: {response_data}")

            return TerminalInfoDocument(**response_data.get("data"))
