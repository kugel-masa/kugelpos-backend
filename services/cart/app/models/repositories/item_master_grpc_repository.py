# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""gRPC-backed item master repository, sitting on the shared cache base.

Shares the same cache namespace ("item_master") and document_class
(ItemMasterDocument) as ItemMasterWebRepository so the two transports
read/write the same cache entries (SC-007).
"""
from logging import getLogger

import grpc

from kugel_common.exceptions import NotFoundException, RepositoryException
from kugel_common.grpc import item_service_pb2
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.cache_backend import AbstractCacheBackend

from app.config.settings_cart import cart_settings
from app.models.documents.item_master_document import ItemMasterDocument
from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
)
from app.utils.grpc_channel_helper import get_master_data_grpc_stub

logger = getLogger(__name__)


class ItemMasterGrpcRepository(AbstractMasterDataRepository[ItemMasterDocument]):
    """Fetches item master records via gRPC; cache-equivalent to the Web variant."""

    # Same namespace and document class as ItemMasterWebRepository so cache
    # entries written by either transport are visible to the other.
    cache_namespace = "item_master"
    document_class = ItemMasterDocument
    default_ttl_seconds = cart_settings.ITEM_MASTER_CACHE_TTL_SECONDS
    is_store_scoped = True

    def __init__(
        self,
        tenant_id: str,
        store_code: str,
        terminal_info: TerminalInfoDocument,
        cache_backend: AbstractCacheBackend,
    ):
        super().__init__(
            tenant_id=tenant_id,
            terminal_info=terminal_info,
            cache_backend=cache_backend,
            store_code=store_code,
        )

    async def get_item_by_code_async(self, item_code: str) -> ItemMasterDocument:
        return await self.get_or_fetch_one(item_code)

    async def _fetch_one(self, item_code: str) -> ItemMasterDocument:
        try:
            stub = await get_master_data_grpc_stub(self.tenant_id, self.store_code)
            request = item_service_pb2.ItemDetailRequest(
                tenant_id=self.tenant_id,
                store_code=self.store_code,
                item_code=item_code,
                terminal_id=self.terminal_info.terminal_id,
            )
            response = await stub.GetItemDetail(
                request, timeout=cart_settings.GRPC_TIMEOUT
            )

            if not response.item_code:
                raise NotFoundException(
                    message=f"Item not found for code {item_code}",
                    collection_name="item grpc",
                    find_key=item_code,
                    logger=logger,
                )

            return ItemMasterDocument(
                tenant_id=self.tenant_id,
                store_code=self.store_code,
                item_code=response.item_code,
                description=response.item_name,
                unit_price=float(response.price),
                tax_code=response.tax_code,
                category_code=response.category_code,
                is_deleted=not response.is_active,
            )

        except NotFoundException:
            raise
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise NotFoundException(
                    message=f"Item not found for code {item_code}",
                    collection_name="item grpc",
                    find_key=item_code,
                    logger=logger,
                    original_exception=e,
                )
            raise RepositoryException(
                message=f"gRPC error for item {item_code}: {e.code()} - {e.details()}",
                collection_name="item grpc",
                logger=logger,
                original_exception=e,
            )
        except Exception as e:
            raise RepositoryException(
                message=f"Unexpected error fetching item {item_code}",
                collection_name="item grpc",
                logger=logger,
                original_exception=e,
            )
