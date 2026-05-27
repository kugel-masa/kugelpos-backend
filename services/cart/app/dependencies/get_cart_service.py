# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
Dependency injection functions for cart API endpoints.

This module provides dependency injection helpers for creating and configuring
cart service instances with all necessary repositories and services.
"""

from fastapi import Depends, Path, Request
from logging import getLogger

from kugel_common.database import database as db_helper
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.cache.cache_backend import AbstractCacheBackend
from app.dependencies.terminal_cache_dependency import get_terminal_info_with_jwt_or_cache
from app.services.cart_service import CartService
from app.services.tran_service import TranService
from app.config.settings import settings

# Get logger instance
logger = getLogger(__name__)


def _get_master_cache_backend(request: Request) -> AbstractCacheBackend:
    """Retrieve the singleton master-data cache backend bound at app startup."""
    return request.app.state.master_cache_backend


async def get_cart_service_async(
    request: Request,
    terminal_info: TerminalInfoDocument = Depends(get_terminal_info_with_jwt_or_cache),
) -> CartService:
    """
    Dependency injection helper for cart service without cart_id.
    Creates and returns a configured cart service instance for API endpoints.

    Args:
        request: FastAPI request (used to access the master-data cache backend)
        terminal_info: Terminal information obtained from API key authentication

    Returns:
        Configured CartService instance
    """
    return await __get_cart_service_async(
        terminal_info=terminal_info,
        cart_id=None,
        cache_backend=_get_master_cache_backend(request),
    )


async def get_cart_service_with_cart_id_async(
    request: Request,
    terminal_info: TerminalInfoDocument = Depends(get_terminal_info_with_jwt_or_cache),
    cart_id: str = Path(...),
) -> CartService:
    """
    Dependency injection helper for cart service with cart_id.
    Creates and returns a configured cart service instance with the specified cart ID.

    Args:
        request: FastAPI request (used to access the master-data cache backend)
        terminal_info: Terminal information obtained from API key authentication
        cart_id: Cart identifier passed in the URL path

    Returns:
        Configured CartService instance with the specified cart ID
    """
    return await __get_cart_service_async(
        terminal_info=terminal_info,
        cart_id=cart_id,
        cache_backend=_get_master_cache_backend(request),
    )


async def __get_cart_service_async(
    terminal_info: TerminalInfoDocument,
    cart_id: str = None,
    cache_backend: AbstractCacheBackend = None,
) -> CartService:
    """
    Internal helper function to create a properly configured cart service.
    Initializes all necessary repositories and services.

    Args:
        terminal_info: Terminal information for the request
        cart_id: Optional cart identifier

    Returns:
        Fully configured CartService instance
    """
    from app.models.repositories.cart_repository import CartRepository
    from app.models.repositories.terminal_counter_repository import (
        TerminalCounterRepository,
    )
    from app.models.repositories.tax_master_repository import TaxMasterRepository
    from app.models.repositories.tranlog_repository import TranlogRepository
    from app.models.repositories.tranlog_delivery_status_repository import (
        TranlogDeliveryStatusRepository,
    )
    from app.models.repositories.transaction_status_repository import (
        TransactionStatusRepository,
    )

    from app.models.repositories.item_master_repository_factory import (
        create_item_master_repository,
    )
    from app.models.repositories.payment_master_web_repository import (
        PaymentMasterWebRepository,
    )
    from app.models.repositories.settings_master_web_repository import (
        SettingsMasterWebRepository,
    )
    from kugel_common.models.repositories.store_info_web_repository import (
        StoreInfoWebRepository,
    )

    logger.debug(f"terminal_info: {terminal_info}")

    # db for tenant
    tenant_id = terminal_info.tenant_id
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    # db for all tenant
    db_common = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_commons")  # ← 修正

    cart_repo = CartRepository(db=db, terminal_info=terminal_info)
    terminal_counter_repo = TerminalCounterRepository(db=db, terminal_info=terminal_info)
    await terminal_counter_repo.initialize()
    tax_master_repo = TaxMasterRepository(db=db, terminal_info=terminal_info)
    tranlog_repo = TranlogRepository(db=db, terminal_info=terminal_info)
    await tranlog_repo.initialize()
    tranlog_delivery_status_repo = TranlogDeliveryStatusRepository(
        db=db_common, terminal_info=terminal_info  # use common db
    )
    await tranlog_delivery_status_repo.initialize()
    transaction_status_repo = TransactionStatusRepository(db=db, terminal_info=terminal_info)
    await transaction_status_repo.initialize()
    item_master_repo = create_item_master_repository(
        tenant_id=tenant_id,
        store_code=terminal_info.store_code,
        terminal_info=terminal_info,
        cache_backend=cache_backend,
    )
    payment_master_repo = PaymentMasterWebRepository(
        tenant_id=tenant_id,
        terminal_info=terminal_info,
        cache_backend=cache_backend,
    )
    settings_master_repo = SettingsMasterWebRepository(
        tenant_id=tenant_id,
        terminal_info=terminal_info,
        cache_backend=cache_backend,
        store_code=terminal_info.store_code,
        terminal_no=terminal_info.terminal_no,
    )
    store_info_repo = StoreInfoWebRepository(tenant_id=tenant_id, terminal_info=terminal_info)

    tran_service = TranService(
        terminal_info=terminal_info,
        terminal_counter_repo=terminal_counter_repo,
        tranlog_repo=tranlog_repo,
        tranlog_delivery_status_repo=tranlog_delivery_status_repo,
        settings_master_repo=settings_master_repo,
        payment_master_repo=payment_master_repo,
        transaction_status_repo=transaction_status_repo,
    )

    return CartService(
        terminal_info=terminal_info,
        cart_repo=cart_repo,
        terminal_counter_repo=terminal_counter_repo,
        settings_master_repo=settings_master_repo,
        store_info_repo=store_info_repo,
        tax_master_repo=tax_master_repo,
        item_master_repo=item_master_repo,
        payment_master_repo=payment_master_repo,
        tran_service=tran_service,
        cart_id=cart_id,
        master_cache_backend=cache_backend,
    )
