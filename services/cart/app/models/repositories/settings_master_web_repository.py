# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Settings master repository on the shared cache base.

Scoping is dynamic: one instance can represent either tenant-level settings
(store_code=None at construction) or store-level settings (store_code given),
so is_store_scoped is computed as a property rather than a ClassVar. See R-002.
"""
from logging import getLogger
from typing import Optional

from kugel_common.exceptions import NotFoundException, RepositoryException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.cache_backend import AbstractCacheBackend
from kugel_common.utils.http_client_helper import get_pooled_client

from app.config.settings_cart import cart_settings
from app.models.documents.settings_master_document import SettingsMasterDocument
from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
)

logger = getLogger(__name__)


class SettingsMasterWebRepository(AbstractMasterDataRepository[SettingsMasterDocument]):
    cache_namespace = "settings_master"
    document_class = SettingsMasterDocument
    default_ttl_seconds = cart_settings.SETTINGS_MASTER_CACHE_TTL_SECONDS

    def __init__(
        self,
        tenant_id: str,
        terminal_info: TerminalInfoDocument,
        cache_backend: AbstractCacheBackend,
        store_code: Optional[str] = None,
        terminal_no: Optional[int] = None,
    ):
        super().__init__(
            tenant_id=tenant_id,
            terminal_info=terminal_info,
            cache_backend=cache_backend,
            store_code=store_code,
        )
        self.terminal_no = terminal_no
        # Per-instance snapshot of settings observed during this cart's lifetime;
        # cart_service seeds this on cart resume so previously-referenced
        # settings resolve without going through master-data again.
        self._session_docs_by_name: dict[str, SettingsMasterDocument] = {}

    def set_settings_master_documents(self, documents: list[SettingsMasterDocument] | None) -> None:
        """Replace the session snapshot. Called by cart_service on cart resume."""
        self._session_docs_by_name = {d.name: d for d in (documents or [])}

    @property
    def settings_master_documents(self) -> list[SettingsMasterDocument]:
        return list(self._session_docs_by_name.values())

    @property
    def is_store_scoped(self) -> bool:  # type: ignore[override]
        # Dynamic scoping: tenant-wide when store_code is absent, store-wide otherwise.
        return self.store_code is not None

    async def get_all_settings_async(self) -> list[SettingsMasterDocument]:
        return await self.get_or_fetch_list("__all__")

    async def get_settings_value_by_name_async(self, name: str) -> Optional[SettingsMasterDocument]:
        if name in self._session_docs_by_name:
            return self._session_docs_by_name[name]
        try:
            doc = await self.get_or_fetch_one(name)
        except NotFoundException:
            # Existing API contract: 404 is signalled as None rather than as
            # an exception (different from how other repos handle missing keys).
            return None
        self._session_docs_by_name[name] = doc
        return doc

    # ------------------------------------------------------------------ private

    async def _fetch_one(self, name: str) -> SettingsMasterDocument:
        client = await get_pooled_client("master-data")
        headers, params = self._build_auth(extra_params=True)
        endpoint = f"/tenants/{self.tenant_id}/settings/{name}/value"

        try:
            response_data = await client.get(endpoint, params=params, headers=headers)
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 404:
                raise NotFoundException(
                    message=f"setting not found for name {name}",
                    collection_name="settings web",
                    find_key=name,
                    logger=logger,
                    original_exception=e,
                )
            raise RepositoryException(
                message=f"Request error for name {name}",
                collection_name="settings web",
                logger=logger,
                original_exception=e,
            )

        # /settings/{name}/value returns {"data": {"value": ...}}; SettingsMasterDocument
        # has no "value" field, so we map the response into default_value to
        # preserve the existing get_setting_value() fallback behaviour.
        api_value = (response_data.get("data") or {}).get("value")
        return SettingsMasterDocument(name=name, default_value=api_value)

    async def _fetch_list(self, _logical_key: str) -> list[SettingsMasterDocument]:
        client = await get_pooled_client("master-data")
        headers, params = self._build_auth(extra_params=True)
        endpoint = f"/tenants/{self.tenant_id}/settings"

        try:
            response_data = await client.get(endpoint, params=params, headers=headers)
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 404:
                # Legacy behaviour: 404 yields an empty list, not an exception.
                return []
            raise RepositoryException(
                message="Request error fetching all settings",
                collection_name="settings web",
                logger=logger,
                original_exception=e,
            )

        if response_data.get("success") and response_data.get("data"):
            return [SettingsMasterDocument(**setting) for setting in response_data["data"]]
        return []

    def _build_auth(self, *, extra_params: bool) -> tuple[dict, dict]:
        jwt_token = getattr(self.terminal_info, "jwt_token", None)
        params = {
            "store_code": self.store_code,
            "terminal_no": self.terminal_no,
        }
        if jwt_token:
            headers = {"Authorization": f"Bearer {jwt_token}"}
        else:
            headers = {"X-API-KEY": self.terminal_info.api_key}
            params["terminal_id"] = self.terminal_info.terminal_id
        return headers, params
