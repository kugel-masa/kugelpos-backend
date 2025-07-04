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
Staff Master Web Repository implementation

This module provides API client operations for retrieving staff information
from the backend service. It implements a repository pattern that fetches
data over HTTP rather than from a direct database connection.
"""
from kugel_common.config.settings import settings
from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.exceptions import NotFoundException, RepositoryException
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument

from logging import getLogger
logger = getLogger(__name__)

class StaffMasterWebRepository():
    """
    Repository class for fetching staff information via web API
    
    This class provides methods to retrieve staff information from a remote API endpoint.
    Unlike database repositories, this class communicates with external services
    over HTTP and transforms the JSON responses into domain models.
    """

    def __init__(
        self, 
        tenant_id: str, 
        terminal_info: TerminalInfoDocument
    ):
        """
        Initialize a new StaffMasterWebRepository instance
        
        Args:
            tenant_id: ID of the tenant to fetch staff information for
            terminal_info: Terminal information used for authentication and context
        """
        self.tenant_id = tenant_id
        self.terminal_info = terminal_info 
        self.base_url = settings.BASE_URL_MASTER_DATA
    
    async def get_staff_by_id_async(self, id: str) -> StaffMasterDocument:
        """
        Retrieve staff information by staff ID
        
        Makes an HTTP request to the master data service API to fetch staff details
        for the specified staff ID.
        
        Args:
            id: Staff ID to look up
            
        Returns:
            StaffMasterDocument: The staff information document
            
        Raises:
            NotFoundException: If the staff information cannot be found
            RepositoryException: If there's an error communicating with the API
        """
        async with get_service_client("master-data") as client:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params = {"terminal_id": self.terminal_info.terminal_id}
            endpoint = f"/tenants/{self.tenant_id}/staff/{id}"
            
            logger.debug(f"endpoint: {endpoint}, params: {params}, headers: {headers}")
            
            try:
                response_data = await client.get(endpoint, params=params, headers=headers)
            except Exception as e:
                if hasattr(e, 'status_code') and e.status_code == 404:
                    message = f"staff not found for id {id}"
                    raise NotFoundException(
                        message=message, 
                        collection_name="staff web", 
                        find_key=id, 
                        logger=logger, 
                        original_exception=e
                    )
                else:
                    message = f"Request error for id {id}"
                    raise RepositoryException(
                        message=message,
                        collection_name="staff web",
                        logger=logger,
                        original_exception=e
                    )
                
            logger.debug(f"response: {response_data}")
            return StaffMasterDocument(**response_data.get("data"))


