# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, Dict, List
import logging

from kugel_common.utils.http_client_helper import get_service_client, HttpClientError
from kugel_common.utils.service_auth import create_service_token
from kugel_common.exceptions import ServiceException
from app.exceptions.report_exceptions import ItemMasterDataNotFoundException

logger = logging.getLogger(__name__)


class ItemMasterWebRepository:
    """
    Repository for retrieving item master data from the master-data service via HTTP.
    
    This repository communicates with the master-data service to fetch item information
    for enriching reports with proper item names and category associations.
    """

    def __init__(self, tenant_id: str, master_data_base_url: str):
        """
        Initialize the ItemMasterWebRepository.

        Args:
            tenant_id: The tenant identifier
            master_data_base_url: Base URL for the master-data service
        """
        self.tenant_id = tenant_id
        self.master_data_base_url = master_data_base_url

    async def get_items(self, item_codes: Optional[List[str]] = None) -> Dict[str, Dict[str, str]]:
        """
        Retrieve items for the tenant as a mapping of item code to item details.

        Args:
            item_codes: Optional list of specific item codes to retrieve.
                       If None, retrieves all items.

        Returns:
            Dict[str, Dict[str, str]]: Mapping of item_code to dict containing:
                - name: Item name
                - category_code: Category code for the item

        Raises:
            ItemMasterDataNotFoundException: If item data cannot be retrieved
        """
        try:
            async with get_service_client("master-data") as client:
                service_token = create_service_token(self.tenant_id, "report")
                headers = {
                    "Authorization": f"Bearer {service_token}",
                    "X-Tenant-ID": self.tenant_id
                }
                
                url = f"{self.master_data_base_url}/tenants/{self.tenant_id}/items"
                
                # Add item codes as query parameters if specified
                params = {}
                if item_codes:
                    params["item_codes"] = ",".join(item_codes)
                
                # HttpClientHelper.get() returns the JSON data directly, not a response object
                data = await client.get(url, headers=headers, params=params)
                
                # Check if the response was successful
                if data.get("success") and data.get("data"):
                    # Extract item code to item details mapping
                    item_map = {}
                    for item in data["data"]:
                        item_map[item["itemCode"]] = {
                            "name": item.get("itemName", item["itemCode"]),
                            "category_code": item.get("categoryCode", "")
                        }
                    return item_map
                else:
                    logger.error(f"Failed to get items: {data}")
                    raise ItemMasterDataNotFoundException(
                        f"Failed to retrieve item master data: {data.get('message', 'Unknown error')}",
                        logger
                    )
                    
        except HttpClientError as e:
            logger.error(f"HTTP client error while getting items: {e}")
            raise ItemMasterDataNotFoundException(
                f"Failed to connect to master-data service: {str(e)}",
                logger,
                e
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error while getting items: {e}")
            raise ItemMasterDataNotFoundException(
                f"Unexpected error retrieving item data: {str(e)}",
                logger,
                e
            ) from e