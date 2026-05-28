# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""
Item Master Repository Factory

Provides runtime selection between HTTP and gRPC implementations.
Both implementations share the same cache namespace and document class
so cache entries are interchangeable across the two transports.
"""
import logging

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.cache_backend import AbstractCacheBackend

from app.config.settings_cart import cart_settings
from app.models.documents.item_master_document import ItemMasterDocument
from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
)
from app.models.repositories.item_master_grpc_repository import ItemMasterGrpcRepository
from app.models.repositories.item_master_web_repository import ItemMasterWebRepository

logger = logging.getLogger(__name__)


def create_item_master_repository(
    tenant_id: str,
    store_code: str,
    terminal_info: TerminalInfoDocument,
    cache_backend: AbstractCacheBackend | None,
) -> AbstractMasterDataRepository[ItemMasterDocument]:
    """Return the configured item master repository (HTTP or gRPC).

    The selection is controlled by cart_settings.USE_GRPC; the returned
    instance is interchangeable from the caller's perspective.
    """
    if cart_settings.USE_GRPC:
        logger.info("Using gRPC client for master-data communication")
        return ItemMasterGrpcRepository(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_info=terminal_info,
            cache_backend=cache_backend,
        )
    logger.info("Using HTTP client for master-data communication")
    return ItemMasterWebRepository(
        tenant_id=tenant_id,
        store_code=store_code,
        terminal_info=terminal_info,
        cache_backend=cache_backend,
    )
