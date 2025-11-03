# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, Dict
import logging

from kugel_common.utils.http_client_helper import get_service_client, HttpClientError
from kugel_common.utils.service_auth import create_service_token
from kugel_common.exceptions import ServiceException
from app.exceptions import CategoryMasterDataNotFoundException

logger = logging.getLogger(__name__)


class CategoryMasterWebRepository:
    """
    Repository for retrieving category master data from the master-data service via HTTP.
    
    This repository communicates with the master-data service to fetch category information
    for enriching reports with proper category names.
    """

    def __init__(self, tenant_id: str, master_data_base_url: str):
        """
        Initialize the CategoryMasterWebRepository.

        Args:
            tenant_id: The tenant identifier
            master_data_base_url: Base URL for the master-data service
        """
        self.tenant_id = tenant_id
        self.master_data_base_url = master_data_base_url

    async def get_categories(self) -> Dict[str, str]:
        """
        Retrieve all categories for the tenant as a mapping of category code to description.

        Returns:
            Dict[str, str]: Mapping of category_code to description

        Raises:
            CategoryMasterDataNotFoundException: If category data cannot be retrieved
        """
        try:
            logger.info(f"Getting categories from master-data service for tenant {self.tenant_id}")
            logger.info(f"Master data base URL: {self.master_data_base_url}")
            
            async with get_service_client("master-data") as client:
                service_token = create_service_token(self.tenant_id, "report")
                headers = {
                    "Authorization": f"Bearer {service_token}",
                    "X-Tenant-ID": self.tenant_id
                }
                logger.debug(f"Request headers: {headers}")
                
                url = f"{self.master_data_base_url}/tenants/{self.tenant_id}/categories"
                logger.info(f"Requesting categories from URL: {url}")
                # HttpClientHelper.get() returns the JSON data directly, not a response object
                data = await client.get(url, headers=headers)
                
                logger.info(f"Received response from master-data service: success={data.get('success')}, data count={len(data.get('data', []))}")
                logger.debug(f"Full response data: {data}")
                
                # Check if the response was successful
                if data.get("success") and data.get("data"):
                    # Extract category code to description mapping
                    category_map = {}
                    for category in data["data"]:
                        logger.debug(f"Processing category: {category}")
                        category_code = category.get("categoryCode")
                        description = category.get("description")
                        logger.debug(f"Category mapping: {category_code} -> {description}")
                        category_map[category_code] = description if description else category_code
                    
                    logger.info(f"Final category mapping: {category_map}")
                    return category_map
                else:
                    logger.error(f"Failed to get categories: {data}")
                    raise CategoryMasterDataNotFoundException(
                        f"Failed to retrieve category master data: {data.get('message', 'Unknown error')}",
                        logger
                    )
                    
        except HttpClientError as e:
            logger.error(f"HTTP client error while getting categories: {e}")
            raise CategoryMasterDataNotFoundException(
                f"Failed to connect to master-data service: {str(e)}",
                logger,
                e
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error while getting categories: {e}")
            raise CategoryMasterDataNotFoundException(
                f"Unexpected error retrieving category data: {str(e)}",
                logger,
                e
            ) from e