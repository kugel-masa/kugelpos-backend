# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""HTTP-backed item master repository, sitting on the shared cache base."""
from logging import getLogger

from kugel_common.exceptions import NotFoundException, RepositoryException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.cache_backend import AbstractCacheBackend
from kugel_common.utils.http_client_helper import get_pooled_client

from app.config.settings_cart import cart_settings
from app.models.documents.item_master_document import ItemMasterDocument
from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
)

logger = getLogger(__name__)


class ItemMasterWebRepository(AbstractMasterDataRepository[ItemMasterDocument]):
    """Fetches item master records from the master-data HTTP service.

    Caching, key construction, TTL, and invalidation are delegated to
    AbstractMasterDataRepository. This class only knows how to call the
    upstream service and how to convert its response into an
    ItemMasterDocument.
    """

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
        """Fetch a single item; transparently cached by the base class."""
        return await self.get_or_fetch_one(item_code)

    async def _fetch_one(self, item_code: str) -> ItemMasterDocument:
        client = await get_pooled_client("master-data")
        jwt_token = getattr(self.terminal_info, "jwt_token", None)
        if jwt_token:
            headers = {"Authorization": f"Bearer {jwt_token}"}
            params = {}
        else:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params = {"terminal_id": self.terminal_info.terminal_id}
        endpoint = (
            f"/tenants/{self.tenant_id}/stores/{self.store_code}"
            f"/items/{item_code}/details"
        )

        try:
            response_data = await client.get(endpoint, params=params, headers=headers)
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 404:
                raise NotFoundException(
                    message=f"item not found for id {item_code}",
                    collection_name="item web",
                    find_key=item_code,
                    logger=logger,
                    original_exception=e,
                )
            raise RepositoryException(
                message=f"Request error for id {item_code}",
                collection_name="item web",
                logger=logger,
                original_exception=e,
            )

        return ItemMasterDocument(**response_data.get("data"))
