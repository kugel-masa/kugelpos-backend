# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Transaction Log Web Repository Module

This module provides a repository class for retrieving transaction logs from the Cart service
via HTTP API calls. It is used to access transaction data that is stored in a different service.
"""

from kugel_common.exceptions import NotFoundException, RepositoryException
from kugel_common.utils.http_client_helper import get_service_client
from kugel_common.schemas.pagination import PaginatedResult, Metadata
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.config.settings import settings

from logging import getLogger

logger = getLogger(__name__)


class TranlogWebRepository:
    """
    Transaction Log Web Repository

    This repository class is responsible for retrieving transaction logs from the Cart service
    via HTTP API calls. Unlike local repositories that access MongoDB directly, this repository
    makes HTTP requests to another service's API.

    The repository uses the terminal's API key for authentication when making requests.
    """

    def __init__(self, tenant_id: str, terminal_info: TerminalInfoDocument):
        """
        Initialize the transaction log web repository

        Args:
            tenant_id: Tenant ID to associate with this repository
            terminal_info: Terminal information document containing API key and identification details
        """
        self.tenant_id = tenant_id
        self.terminal_info = terminal_info
        self.base_url = settings.BASE_URL_CART

    async def get_tran_log_list_async(
        self,
        business_date: str,
        open_counter: int,
        transaction_type: list[int] = None,
        limit: int = 0,
        page: int = 1,
        sort: list[tuple[str, int]] = None,
        include_cancelled: bool = False,
    ) -> PaginatedResult[BaseTransaction]:
        """
        Retrieve transaction logs from the Cart service with pagination

        This method fetches transaction logs for a specific terminal, business date, and
        open counter from the Cart service API. It supports filtering by transaction type
        and can include or exclude cancelled transactions.

        Args:
            business_date: Business date in YYYYMMDD format
            open_counter: Terminal open counter value
            transaction_type: Optional list of transaction type IDs to filter by
            limit: Maximum number of records to return per page (0 means no limit)
            page: Page number to return (1-based)
            sort: List of field name and direction tuples for sorting results
            include_cancelled: Whether to include cancelled transactions

        Returns:
            Paginated result containing transaction log records and metadata

        Raises:
            NotFoundException: If no transaction logs are found
            RepositoryException: If there is an error communicating with the Cart service
        """
        store_code = self.terminal_info.store_code
        terminal_no = self.terminal_info.terminal_no

        async with get_service_client("cart") as client:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params = {
                "terminal_id": self.terminal_info.terminal_id,
                "business_date": business_date,
                "open_counter": open_counter,
                "include_cancelled": include_cancelled,
                "limit": limit,
                "page": page,
            }
            if transaction_type:
                params["transaction_type"] = transaction_type
            if sort:
                sort_str = ",".join([f"{key}:{value}" for key, value in sort])
                params["sort"] = sort_str
            endpoint = f"/tenants/{self.tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions"

            logger.debug(f"TranlogWebRepository.get_tran_log_list_async: endpoint->{endpoint}, params->{params}")

            try:
                response_data = await client.get(endpoint, params=params, headers=headers)
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 404:
                    message = f"tranlog not found for terminal_id {self.terminal_info.terminal_id}"
                    raise NotFoundException(
                        message=message,
                        collection_name="Tranlog Web",
                        find_key=self.terminal_info.terminal_id,
                        logger=logger,
                        original_exception=e,
                    )
                else:
                    message = f"Request error for terminal_id {self.terminal_info.terminal_id}"
                    raise RepositoryException(
                        message=message, collection_name="Tranlog Web", logger=logger, original_exception=e
                    )

            logger.debug(f"response: {response_data}")
            paginated_result = PaginatedResult(
                data=[BaseTransaction(**tranlog) for tranlog in response_data.get("data")],
                metadata=Metadata(
                    limit=limit,
                    page=page,
                    total=response_data.get("metadata").get("total"),
                    sort=sort_str if "sort_str" in locals() else None,
                    filter={"terminal_id": self.terminal_info.terminal_id},
                ),
            )
            logger.debug(f"paginated_result: {paginated_result}")
            return paginated_result
