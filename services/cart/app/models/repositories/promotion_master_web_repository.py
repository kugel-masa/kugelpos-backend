# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Promotion master repository on the shared cache base.

Store-scoped: promotions apply per-store. The store_code is supplied at the
method-call level (not constructor) so the cache key is built from
store_code_override; see R-009 for the rationale.
"""
from logging import getLogger

from kugel_common.exceptions import RepositoryException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.cache_backend import AbstractCacheBackend
from kugel_common.utils.http_client_helper import get_pooled_client

from app.config.settings_cart import cart_settings
from app.models.documents.promotion_master_document import PromotionMasterDocument
from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
)

logger = getLogger(__name__)


class PromotionMasterWebRepository(AbstractMasterDataRepository[PromotionMasterDocument]):
    cache_namespace = "promotion_master"
    document_class = PromotionMasterDocument
    default_ttl_seconds = cart_settings.PROMOTION_MASTER_CACHE_TTL_SECONDS
    is_store_scoped = True

    def __init__(
        self,
        tenant_id: str,
        terminal_info: TerminalInfoDocument,
        cache_backend: AbstractCacheBackend | None,
    ):
        # store_code lives on the call (and on terminal_info as a fallback for
        # the business "use my terminal's store when omitted" convention);
        # the base class does NOT consult terminal_info itself, so we leave
        # self.store_code as None and pass store_code_override explicitly below.
        super().__init__(
            tenant_id=tenant_id,
            terminal_info=terminal_info,
            cache_backend=cache_backend,
            store_code=None,
        )

    async def get_active_promotions_by_store_async(
        self, store_code: str | None = None
    ) -> list[PromotionMasterDocument]:
        # Business convention: when the caller omits store_code, fall back to
        # the terminal's home store. This logic is local to the subclass; the
        # base class only sees a resolved effective_store via the override.
        effective_store = store_code or self.terminal_info.store_code
        return await self.get_or_fetch_list(
            logical_key="active",
            store_code_override=effective_store,
            fetcher=lambda: self._fetch_active(effective_store),
        )

    async def _fetch_one(self, logical_key: str) -> PromotionMasterDocument:
        raise NotImplementedError(
            "PromotionMasterWebRepository only supports list lookups."
        )

    async def _fetch_active(self, store_code: str) -> list[PromotionMasterDocument]:
        client = await get_pooled_client("master-data")
        jwt_token = getattr(self.terminal_info, "jwt_token", None)
        if jwt_token:
            headers = {"Authorization": f"Bearer {jwt_token}"}
            params = {"storeCode": store_code}
        else:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params = {
                "storeCode": store_code,
                "terminal_id": self.terminal_info.terminal_id,
            }
        endpoint = f"/tenants/{self.tenant_id}/promotions/active"

        try:
            response_data = await client.get(endpoint, params=params, headers=headers)
        except Exception as e:
            raise RepositoryException(
                message=f"Failed to get active promotions for store {store_code}",
                collection_name="promotion web",
                logger=logger,
                original_exception=e,
            )

        promotions: list[PromotionMasterDocument] = []
        for promo_data in response_data.get("data", []):
            try:
                promotions.append(PromotionMasterDocument.from_api_response(promo_data))
            except Exception as e:
                # Resilient against partial corruption in upstream data; an
                # individual bad row should not abort the entire response.
                logger.warning(
                    f"Failed to parse promotion data: {promo_data}, error: {e}"
                )
                continue
        return promotions
