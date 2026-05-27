# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Payment master repository on the shared cache base.

Tenant-scoped: payment methods are defined at tenant level (not per store),
so is_store_scoped=False forces the store position in the cache key to "_".
"""
from logging import getLogger

from kugel_common.exceptions import NotFoundException, RepositoryException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.cache_backend import AbstractCacheBackend
from kugel_common.utils.http_client_helper import get_pooled_client

from app.config.settings_cart import cart_settings
from app.models.documents.payment_master_document import PaymentMasterDocument
from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
)

logger = getLogger(__name__)


class PaymentMasterWebRepository(AbstractMasterDataRepository[PaymentMasterDocument]):
    cache_namespace = "payment_master"
    document_class = PaymentMasterDocument
    default_ttl_seconds = cart_settings.PAYMENT_MASTER_CACHE_TTL_SECONDS
    is_store_scoped = False

    def __init__(
        self,
        tenant_id: str,
        terminal_info: TerminalInfoDocument,
        cache_backend: AbstractCacheBackend,
    ):
        super().__init__(
            tenant_id=tenant_id,
            terminal_info=terminal_info,
            cache_backend=cache_backend,
            store_code=None,
        )

    async def get_payment_by_code_async(self, payment_code: str) -> PaymentMasterDocument:
        return await self.get_or_fetch_one(payment_code)

    async def _fetch_one(self, payment_code: str) -> PaymentMasterDocument:
        client = await get_pooled_client("master-data")
        jwt_token = getattr(self.terminal_info, "jwt_token", None)
        if jwt_token:
            headers = {"Authorization": f"Bearer {jwt_token}"}
            params = {}
        else:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params = {"terminal_id": self.terminal_info.terminal_id}
        endpoint = f"/tenants/{self.tenant_id}/payments/{payment_code}"

        try:
            response_data = await client.get(endpoint, params=params, headers=headers)
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 404:
                raise NotFoundException(
                    message=f"payment not found for id {payment_code}",
                    collection_name="payment web",
                    find_key=payment_code,
                    logger=logger,
                    original_exception=e,
                )
            raise RepositoryException(
                message=f"Request error for id {payment_code}",
                collection_name="payment web",
                logger=logger,
                original_exception=e,
            )

        return PaymentMasterDocument(**response_data.get("data"))
