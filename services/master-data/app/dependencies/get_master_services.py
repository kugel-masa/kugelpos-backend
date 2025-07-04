# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Service factory functions for master-data service.

This module provides dependency injection functions that create service instances
with their required repositories for each master data domain.
"""
from logging import getLogger

from kugel_common.database import database as db_helper

from app.config.settings import settings
from app.services.category_master_service import CategoryMasterService
from app.services.item_book_master_service import ItemBookMasterService
from app.services.item_common_master_service import ItemCommonMasterService
from app.services.item_store_master_service import ItemStoreMasterService
from app.services.payment_master_service import PaymentMasterService
from app.services.settings_master_service import SettingsMasterService
from app.services.staff_master_service import StaffMasterService
from app.services.tax_master_service import TaxMasterService

from app.models.repositories.category_master_repository import CategoryMasterRepository
from app.models.repositories.item_book_master_repository import ItemBookMasterRepository
from app.models.repositories.item_common_master_repository import ItemCommonMasterRepository
from app.models.repositories.item_store_master_repository import ItemStoreMasterRepository
from app.models.repositories.payment_master_repository import PaymentMasterRepository
from app.models.repositories.settings_master_repository import SettingsMasterRepository
from app.models.repositories.staff_master_repository import StaffMasterRepository
from app.models.repositories.tax_master_repository import TaxMasterRepository

logger = getLogger(__name__)


async def get_category_master_service_async(tenant_id: str) -> CategoryMasterService:
    """
    Dependency function to create and inject a CategoryMasterService instance.

    This function creates the necessary repository and injects it into the service,
    providing access to the tenant-specific database for category operations.

    Args:
        tenant_id: The tenant identifier used to select the appropriate database

    Returns:
        CategoryMasterService: Configured service instance for the specified tenant
    """
    logger.debug(f"get_category_master_service_async: tenant_id->{tenant_id}")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return CategoryMasterService(category_master_repo=CategoryMasterRepository(db, tenant_id))


async def get_item_book_service_async(tenant_id: str, store_code: str = None) -> ItemBookMasterService:
    """
    Dependency function to create and inject an ItemBookMasterService instance.

    This function creates the necessary repository and injects it into the service,
    providing access to the tenant-specific database for item book operations.

    Args:
        tenant_id: The tenant identifier used to select the appropriate database
        store_code: The store code for store-specific operations (optional)

    Returns:
        ItemBookMasterService: Configured service instance for the specified tenant
    """
    logger.debug(f"get_item_book_service_async: tenant_id->{tenant_id}")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")

    item_store_master_repo = None
    if store_code is not None:
        item_store_master_repo = ItemStoreMasterRepository(db, tenant_id, store_code)

    return ItemBookMasterService(
        item_book_master_repo=ItemBookMasterRepository(db, tenant_id),
        item_common_master_repo=ItemCommonMasterRepository(db, tenant_id),
        item_store_master_repo=item_store_master_repo,
    )


async def get_item_master_service_async(tenant_id: str) -> ItemCommonMasterService:
    """
    Dependency function to create and inject an ItemCommonMasterService instance.

    This function creates the necessary repository and injects it into the service,
    providing access to the tenant-specific database for item common operations.

    Args:
        tenant_id: The tenant identifier used to select the appropriate database

    Returns:
        ItemCommonMasterService: Configured service instance for the specified tenant
    """
    logger.debug(f"get_item_master_service_async: tenant_id->{tenant_id}")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return ItemCommonMasterService(item_common_master_repo=ItemCommonMasterRepository(db, tenant_id))


async def get_item_store_master_service_async(tenant_id: str, store_code: str) -> ItemStoreMasterService:
    """
    Dependency function to create and inject an ItemStoreMasterService instance.

    This function creates the necessary repository and injects it into the service,
    providing access to the tenant-specific database for item store operations.

    Args:
        tenant_id: The tenant identifier used to select the appropriate database
        store_code: The store code for store-specific operations

    Returns:
        ItemStoreMasterService: Configured service instance for the specified tenant
    """
    logger.debug(f"get_item_store_master_service_async: tenant_id->{tenant_id}")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return ItemStoreMasterService(
        item_store_master_repo=ItemStoreMasterRepository(db, tenant_id, store_code),
        item_common_master_repo=ItemCommonMasterRepository(db, tenant_id),
    )


async def get_payment_master_service_async(tenant_id: str) -> PaymentMasterService:
    """
    Dependency function to create and inject a PaymentMasterService instance.

    This function creates the necessary repository and injects it into the service,
    providing access to the tenant-specific database for payment operations.

    Args:
        tenant_id: The tenant identifier used to select the appropriate database

    Returns:
        PaymentMasterService: Configured service instance for the specified tenant
    """
    logger.debug(f"get_payment_master_service_async: tenant_id->{tenant_id}")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return PaymentMasterService(payment_master_repository=PaymentMasterRepository(db, tenant_id))


async def get_settings_master_service_async(tenant_id: str) -> SettingsMasterService:
    """
    Dependency function to create and inject a SettingsMasterService instance.

    This function creates the necessary repository and injects it into the service,
    providing access to the tenant-specific database for settings operations.

    Args:
        tenant_id: The tenant identifier used to select the appropriate database

    Returns:
        SettingsMasterService: Configured service instance for the specified tenant
    """
    logger.debug(f"get_settings_master_service_async: tenant_id->{tenant_id}")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return SettingsMasterService(settings_master_repo=SettingsMasterRepository(db, tenant_id))


async def get_staff_master_service_async(tenant_id: str) -> StaffMasterService:
    """
    Dependency function to create and inject a StaffMasterService instance.

    This function creates the necessary repository and injects it into the service,
    providing access to the tenant-specific database for staff operations.

    Args:
        tenant_id: The tenant identifier used to select the appropriate database

    Returns:
        StaffMasterService: Configured service instance for the specified tenant
    """
    logger.debug(f"get_staff_master_service_async: tenant_id->{tenant_id}")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return StaffMasterService(staff_master_repo=StaffMasterRepository(db, tenant_id))


async def get_tax_master_service_async(tenant_id: str) -> TaxMasterService:
    """
    Dependency function to create and inject a TaxMasterService instance.

    This function creates the necessary repository and injects it into the service,
    providing access to the tenant-specific database for tax operations.

    Args:
        tenant_id: The tenant identifier used to select the appropriate database

    Returns:
        TaxMasterService: Configured service instance for the specified tenant
    """
    logger.debug(f"get_tax_master_service_async: tenant_id->{tenant_id}")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return TaxMasterService(tax_master_repo=TaxMasterRepository(db, tenant_id))
