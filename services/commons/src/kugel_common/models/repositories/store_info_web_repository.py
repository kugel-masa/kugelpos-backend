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
Store Information Web Repository implementation

This module provides API client operations for retrieving store information
from the backend service. It implements a repository pattern that fetches
data over HTTP rather than from a direct database connection.
"""
from kugel_common.exceptions import NotFoundException, RepositoryException
from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.config.settings import settings
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.store_info_document import StoreInfoDocument

from logging import getLogger
logger = getLogger(__name__)

class StoreInfoWebRepository():
    """
    Repository class for fetching store information via web API
    
    This class provides methods to retrieve store information from a remote API endpoint.
    Unlike database repositories, this class communicates with external services
    over HTTP and transforms the JSON responses into domain models.
    """

    def __init__(
        self, 
        tenant_id: str, 
        terminal_info: TerminalInfoDocument
    ):
        """
        Initialize a new StoreInfoWebRepository instance
        
        Args:
            tenant_id: ID of the tenant to fetch store information for
            terminal_info: Terminal information used for authentication and context
        """
        self.tenant_id = tenant_id
        self.terminal_info = terminal_info 
        self.base_url = settings.BASE_URL_TERMINAL
    
    async def get_store_info_async(self) -> StoreInfoDocument:
        """
        Retrieve store information for the current terminal's store
        
        Makes an HTTP request to the terminal service API to fetch store details
        using the store code associated with the current terminal.
        
        Returns:
            StoreInfoDocument: The store information document
            
        Raises:
            NotFoundException: If the store information cannot be found
            RepositoryException: If there's an error communicating with the API
        """
        store_code = self.terminal_info.store_code
        async with get_service_client("terminal") as client:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params = {"terminal_id": self.terminal_info.terminal_id}
            endpoint = f"/tenants/{self.tenant_id}/stores/{store_code}"
            
            try:
                response_data = await client.get(endpoint, params=params, headers=headers)
            except Exception as e:
                if hasattr(e, 'status_code') and e.status_code == 404:
                    message = f"store info not found for store_code {store_code}"
                    raise NotFoundException(
                        message=message, 
                        collection_name="Store Info Web",
                        find_key=store_code, 
                        logger=logger, 
                        original_exception=e
                    )
                else:
                    message = f"Request error for store_code {store_code}"
                    raise RepositoryException(
                        message=message,
                        collection_name="Store Info Web",
                        logger=logger,
                        original_exception=e
                    )
                
            logger.debug(f"response: {response_data}")
            return StoreInfoDocument(**response_data.get("data"))


