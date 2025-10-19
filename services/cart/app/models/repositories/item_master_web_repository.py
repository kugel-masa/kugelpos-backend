# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.exceptions import RepositoryException, NotFoundException
from kugel_common.utils.http_client_helper import get_pooled_client
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.item_master_document import ItemMasterDocument
from app.config.settings import settings


from logging import getLogger

logger = getLogger(__name__)


class ItemMasterWebRepository:
    """
    Repository class for accessing item master data through web API.

    This class provides methods to retrieve item information from the master data service
    and caches retrieved items to avoid redundant API calls.
    """

    def __init__(
        self,
        tenant_id: str,
        store_code: str,
        terminal_info: TerminalInfoDocument,
        item_master_documents: list[ItemMasterDocument] = None,
    ):
        """
        Initialize the repository with tenant, store and terminal information.

        Args:
            tenant_id: The tenant identifier
            store_code: The store code
            terminal_info: Terminal information document
            item_master_documents: Optional list of pre-loaded item documents for caching
        """
        self.tenant_id = tenant_id
        self.store_code = store_code
        self.terminal_info = terminal_info
        self.item_master_documents = item_master_documents
        self.base_url = settings.BASE_URL_MASTER_DATA

    def set_item_master_documents(self, item_master_documents: list):
        """
        Set the cached item master documents.

        Args:
            item_master_documents: List of item master documents to cache
        """
        self.item_master_documents = item_master_documents

    # get item
    async def get_item_by_code_async(self, item_code: str) -> ItemMasterDocument:
        """
        Get an item by its code from cache or from the web API.

        First checks if the item exists in the cache, and if not, fetches it from the API.
        The fetched item is then added to the cache for future use.

        Args:
            item_code: The code of the item to retrieve

        Returns:
            ItemMasterDocument: The requested item

        Raises:
            NotFoundException: If the item could not be found
            RepositoryException: If there's an error communicating with the API
        """
        if self.item_master_documents is None:
            self.item_master_documents = []

        # first check item_code exist in the list of item_master_documents
        item = next((item for item in self.item_master_documents if item.item_code == item_code), None)
        if item is not None:
            logger.info(
                f"ItemMasterRepository.get_item_by_code: item_code->{item_code} in the list of item_master_documents"
            )
            return item

        # Use pooled client for connection reuse (eliminates 50-100ms overhead per request)
        client = await get_pooled_client("master-data")
        headers = {"X-API-KEY": self.terminal_info.api_key}
        params = {"terminal_id": self.terminal_info.terminal_id}
        endpoint = f"/tenants/{self.tenant_id}/stores/{self.store_code}/items/{item_code}/details"

        try:
            response_data = await client.get(endpoint, params=params, headers=headers)
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 404:
                message = f"item not found for id {item_code}"
                raise NotFoundException(
                    message=message,
                    collection_name="item web",
                    find_key=item_code,
                    logger=logger,
                    original_exception=e,
                )
            else:
                message = f"Request error for id {item_code}"
                raise RepositoryException(
                    message=message, collection_name="item web", logger=logger, original_exception=e
                )

        logger.debug(f"response: {response_data}")

        item = ItemMasterDocument(**response_data.get("data"))
        self.item_master_documents.append(item)
        return item
