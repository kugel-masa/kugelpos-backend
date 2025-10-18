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
gRPC-based Item Master Repository

Provides item master data retrieval via gRPC protocol.
Maintains compatibility with HTTP-based repository interface.
"""

import grpc
from datetime import datetime
from kugel_common.grpc import item_service_pb2, item_service_pb2_grpc
from kugel_common.utils.grpc_client_helper import GrpcClientHelper
from kugel_common.exceptions import RepositoryException, NotFoundException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.item_master_document import ItemMasterDocument
from app.config.settings_cart import cart_settings
from logging import getLogger

logger = getLogger(__name__)


class ItemMasterGrpcRepository:
    """gRPC-based repository for item master data"""

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
        self.grpc_helper = GrpcClientHelper(
            target=cart_settings.MASTER_DATA_GRPC_URL,
            options=[
                ('grpc.max_send_message_length', 10 * 1024 * 1024),
                ('grpc.max_receive_message_length', 10 * 1024 * 1024),
            ]
        )

    def set_item_master_documents(self, item_master_documents: list):
        """
        Set the cached item master documents.

        Args:
            item_master_documents: List of item master documents to cache
        """
        self.item_master_documents = item_master_documents

    async def get_item_by_code_async(self, item_code: str) -> ItemMasterDocument:
        """
        Get an item by its code from cache or via gRPC.

        First checks if the item exists in the cache, and if not, fetches it via gRPC.
        The fetched item is then added to the cache for future use.

        Args:
            item_code: The code of the item to retrieve

        Returns:
            ItemMasterDocument: The requested item

        Raises:
            NotFoundException: If the item could not be found
            RepositoryException: If there's an error communicating via gRPC
        """
        if self.item_master_documents is None:
            self.item_master_documents = []

        # First check if item exists in cache
        item = next((item for item in self.item_master_documents if item.item_code == item_code), None)
        if item is not None:
            logger.info(
                f"ItemMasterGrpcRepository.get_item_by_code: item_code->{item_code} in cache"
            )
            return item

        # Fetch via gRPC
        try:
            channel = await self.grpc_helper.get_channel()
            stub = item_service_pb2_grpc.ItemServiceStub(channel)

            request = item_service_pb2.ItemDetailRequest(
                tenant_id=self.tenant_id,
                store_code=self.store_code,
                item_code=item_code,
                terminal_id=self.terminal_info.terminal_id
            )

            response = await stub.GetItemDetail(
                request,
                timeout=cart_settings.GRPC_TIMEOUT
            )

            if not response.item_code:
                message = f"Item not found for code {item_code}"
                raise NotFoundException(
                    message=message,
                    collection_name="item grpc",
                    find_key=item_code,
                    logger=logger,
                )

            # Convert gRPC response to ItemMasterDocument
            item = ItemMasterDocument(
                tenant_id=self.tenant_id,
                store_code=self.store_code,
                item_code=response.item_code,
                description=response.item_name,
                unit_price=float(response.price),
                tax_code=response.tax_code,  # Use tax_code field instead of tax_rate
                category_code=response.category_code,
                is_deleted=not response.is_active,
            )

            # Add to cache
            self.item_master_documents.append(item)
            logger.info(f"ItemMasterGrpcRepository.get_item_by_code: fetched item_code->{item_code} via gRPC")
            return item

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                message = f"Item not found for code {item_code}"
                raise NotFoundException(
                    message=message,
                    collection_name="item grpc",
                    find_key=item_code,
                    logger=logger,
                    original_exception=e,
                )
            else:
                message = f"gRPC error for item {item_code}: {e.code()} - {e.details()}"
                raise RepositoryException(
                    message=message,
                    collection_name="item grpc",
                    logger=logger,
                    original_exception=e,
                )
        except Exception as e:
            message = f"Unexpected error fetching item {item_code}"
            raise RepositoryException(
                message=message,
                collection_name="item grpc",
                logger=logger,
                original_exception=e,
            )
