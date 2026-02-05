# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.http_client_helper import get_pooled_client
from kugel_common.exceptions import RepositoryException
from app.models.documents.promotion_master_document import PromotionMasterDocument
from app.config.settings import settings


from logging import getLogger

logger = getLogger(__name__)


class PromotionMasterWebRepository:
    """
    Repository class for accessing promotion master data through web API.

    This class provides methods to retrieve active promotion information from the master data service
    for applying category-based discounts to cart items.
    """

    def __init__(
        self,
        tenant_id: str,
        terminal_info: TerminalInfoDocument,
    ):
        """
        Initialize the repository with tenant and terminal information.

        Args:
            tenant_id: The tenant identifier
            terminal_info: Terminal information document containing API key and store code
        """
        self.tenant_id = tenant_id
        self.terminal_info = terminal_info
        self.base_url = settings.BASE_URL_MASTER_DATA
        self._cached_promotions: list[PromotionMasterDocument] = None

    async def get_active_promotions_by_store_async(
        self, store_code: str = None
    ) -> list[PromotionMasterDocument]:
        """
        Get active promotions filtered by store code.

        Retrieves all currently active promotions that apply to the specified store.
        If store_code is None, uses the terminal's store_code.

        Args:
            store_code: The store code to filter promotions for (optional)

        Returns:
            list[PromotionMasterDocument]: List of active promotions for the store

        Raises:
            RepositoryException: If there's an error communicating with the API
        """
        if store_code is None:
            store_code = self.terminal_info.store_code

        # Return cached promotions if available
        if self._cached_promotions is not None:
            return self._cached_promotions

        client = await get_pooled_client("master-data")
        headers = {"X-API-KEY": self.terminal_info.api_key}
        params = {"storeCode": store_code}
        endpoint = f"/tenants/{self.tenant_id}/promotions/active"

        try:
            response_data = await client.get(endpoint, params=params, headers=headers)
        except Exception as e:
            message = f"Failed to get active promotions for store {store_code}: {e}"
            raise RepositoryException(message, logger)

        logger.debug(f"response: {response_data}")
        data = response_data.get("data", [])

        # Convert response data to PromotionMasterDocument list
        promotions = []
        for promo_data in data:
            try:
                promotion = PromotionMasterDocument.from_api_response(promo_data)
                promotions.append(promotion)
            except Exception as e:
                logger.warning(f"Failed to parse promotion data: {promo_data}, error: {e}")
                continue

        # Cache the promotions
        self._cached_promotions = promotions

        return promotions

    def clear_cache(self):
        """Clear the cached promotions."""
        self._cached_promotions = None
