# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, Dict
import logging

from kugel_common.utils.http_client_helper import get_service_client, HttpClientError
from kugel_common.utils.service_auth import create_service_token
from kugel_common.utils.log_utils import mask_sensitive_data
from kugel_common.exceptions import ServiceException
from app.exceptions import CategoryMasterDataNotFoundException
from app.utils.master_data_pages import MASTER_DATA_PAGE_SIZE, has_next_page

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
        Retrieve every category of the tenant as a mapping of category code to description.

        Every page of the list is read, so a category past the first page is
        named too, and logically deleted categories are included (issue #324),
        so a past report keeps the name of a category deleted since (issue #326).

        Returns:
            Dict[str, str]: Mapping of category_code to description

        Raises:
            CategoryMasterDataNotFoundException: If category data cannot be retrieved
        """
        try:
            async with get_service_client("master-data") as client:
                service_token = create_service_token(self.tenant_id, "report")
                headers = {
                    "Authorization": f"Bearer {service_token}",
                    "X-Tenant-ID": self.tenant_id
                }
                # The Authorization value is the service token itself (issue #211).
                logger.debug(f"Request headers: {mask_sensitive_data(headers)}")

                url = f"{self.master_data_base_url}/tenants/{self.tenant_id}/categories"
                category_map: Dict[str, str] = {}
                page = 1
                while True:
                    # HttpClientHelper.get() returns the JSON data directly, not a response object
                    data = await client.get(
                        url,
                        params={"limit": MASTER_DATA_PAGE_SIZE, "page": page, "include_deleted": "true"},
                        headers=headers,
                    )
                    if not data.get("success"):
                        logger.error(f"Failed to get categories: {data.get('message')}")
                        raise CategoryMasterDataNotFoundException(
                            f"Failed to retrieve category master data: {data.get('message', 'Unknown error')}",
                            logger
                        )
                    categories = data.get("data") or []
                    for category in categories:
                        category_code = category.get("categoryCode")
                        if category_code:
                            category_map[category_code] = category.get("description") or category_code
                    if not has_next_page(data.get("metadata"), page, len(categories)):
                        break
                    page += 1

                logger.info(f"Fetched {len(category_map)} categories in {page} page(s)")
                return category_map

        except CategoryMasterDataNotFoundException:
            raise
        except HttpClientError as e:
            logger.error(f"HTTP client error while getting categories: {e}")
            raise CategoryMasterDataNotFoundException(
                "Failed to connect to master-data service",
                logger,
                e
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error while getting categories: {e}")
            raise CategoryMasterDataNotFoundException(
                "Unexpected error retrieving category data",
                logger,
                e
            ) from e