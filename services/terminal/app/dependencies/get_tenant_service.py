# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
Dependency injection functions for tenant API endpoints.

This module provides dependency injection helpers for creating and configuring
tenant service instances with all necessary repositories.
"""

from fastapi import Depends, Query
from logging import getLogger

from kugel_common.database import database as db_helper
from kugel_common.security import (
    get_tenant_id_with_token,
    get_tenant_id_with_security_by_query_optional,
    oauth2_scheme,
    Security,
    api_key_header,
)

from app.config.settings import settings
from app.services.tenant_service import TenantService
from app.models.repositories.tenant_info_repository import TenantInfoRepository

# Get logger instance
logger = getLogger(__name__)


async def get_tenant_service_async(tenant_id: str) -> TenantService:
    """
    Factory function to create a TenantService instance with all required dependencies

    Args:
        tenant_id: The tenant ID to use for database and service operations

    Returns:
        Configured TenantService instance
    """
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    logger.debug(f"Getting tenant service for tenant {tenant_id}, db: {db}")
    tenant_info_repo = TenantInfoRepository(db=db, tenant_id=tenant_id)
    return TenantService(tenant_info_repo=tenant_info_repo, tenant_id=tenant_id)


# Helper function for query parameter parsing
def parse_sort_stores(sort: str = Query(default=None, description="?sort=field1:1,field2:-1")) -> list[tuple[str, int]]:
    """
    Parse the sort query parameter into a list of field name and sort direction tuples

    Format: field1:1,field2:-1 where 1 is ascending and -1 is descending

    Args:
        sort: The sort query parameter string

    Returns:
        List of tuples with field name and sort direction
    """
    sort_list = []
    if sort is None:
        sort_list = [("store_code", 1)]
    else:
        sort_list = [tuple(item.split(":")) for item in sort.split(",")]
        sort_list = [(field, int(order)) for field, order in sort_list]
    return sort_list


# Security dependency wrappers
async def get_tenant_id_with_token_wrapper(token: str = Depends(oauth2_scheme)):
    """
    Security dependency that extracts tenant ID from a JWT token
    Used for operations that only require OAuth2 token authentication
    """
    return await get_tenant_id_with_token(token, is_terminal_service=True)


async def get_tenant_id_with_security_by_query_optional_wrapper(
    terminal_id: str = Query(None), api_key: str = Security(api_key_header), token: str = Depends(oauth2_scheme)
):
    """
    Security dependency that validates authentication using either:
    - Terminal ID + API key combination, or
    - OAuth2 token
    Used for operations that can be performed with either authentication method
    """
    return await get_tenant_id_with_security_by_query_optional(terminal_id, api_key, token, is_terminal_service=True)
