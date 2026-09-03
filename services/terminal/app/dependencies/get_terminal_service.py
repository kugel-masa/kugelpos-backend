# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
Dependency injection functions for terminal API endpoints.

This module provides dependency injection helpers for creating and configuring
terminal service instances with all necessary repositories and services.
"""

from fastapi import Depends, HTTPException, Path, Query, status
from logging import getLogger
from typing import Optional

from kugel_common.database import database as db_helper
from kugel_common.utils.log_utils import mask_loggable
from kugel_common.security import (
    get_tenant_id_with_security,
    get_tenant_id_with_security_by_query_optional,
    get_tenant_id_with_token,
    verify_pubsub_notification_auth,
    verify_terminal_token,
    get_current_user,
    get_terminal_info,
    Security,
    api_key_header,
    oauth2_scheme,
)
from kugel_common.models.repositories.staff_master_web_repository import StaffMasterWebRepository
from kugel_common.models.repositories.store_info_web_repository import StoreInfoWebRepository

from app.config.settings import settings
from app.services.terminal_service import TerminalService
from app.models.repositories.terminal_info_repository import TerminalInfoRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.tran_log_web_repository import TranlogWebRepository
from app.models.repositories.terminallog_delivery_status_repository import TerminallogDeliveryStatusRepository
from app.exceptions import NotFoundException

# Get logger instance
logger = getLogger(__name__)


async def get_terminal_service_async(
    tenant_id: str,
    terminal_id: Optional[str] = None,
) -> TerminalService:
    """
    Factory function to create a TerminalService instance with all required dependencies

    This function creates and initializes all necessary repository instances and configures
    them for the specified tenant and terminal.

    Args:
        tenant_id: The tenant ID to use for database and service operations
        terminal_id: Optional terminal ID to associate with the service

    Returns:
        Configured TerminalService instance
    """

    # db for tenant
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    # db for all tenants
    db_common = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_commons")

    logger.debug(f"Getting terminal service for tenant {tenant_id}, terminal {terminal_id}, db: {db}")
    terminal_info_repo = TerminalInfoRepository(db=db, tenant_id=tenant_id)
    try:
        if terminal_id is not None:
            terminal_info = await terminal_info_repo.get_terminal_info_by_id_async(terminal_id)
        else:
            terminal_info = None
    except NotFoundException:
        logger.info(f"Terminal {terminal_id} not found in tenant {tenant_id}. Creating new terminal info.")
        terminal_info = None

    staff_master_repo = StaffMasterWebRepository(tenant_id=tenant_id, terminal_info=terminal_info)
    store_info_repo = StoreInfoWebRepository(tenant_id=tenant_id, terminal_info=terminal_info)
    # The repository holds the whole terminal document - `api_key`, and the
    # staff's plaintext `pin` one level down (issue #211). Found by planting
    # sentinel credentials and running the stack: every static sweep had
    # missed it, because it is an ATTRIBUTE inside a call that spans lines,
    # and they all looked for a bare `{name}` on one line.
    logger.debug(
        f"staff_master_repo.tenant_id: {staff_master_repo.tenant_id}, "
        f"staff_master_repo.terminal_info: {mask_loggable(staff_master_repo.terminal_info)}"
    )
    cash_in_out_log_repo = CashInOutLogRepository(db=db, tenant_id=tenant_id)
    open_close_log_repo = OpenCloseLogRepository(db=db, tenant_id=tenant_id)
    tran_log_repo = TranlogWebRepository(tenant_id=tenant_id, terminal_info=terminal_info)
    terminal_log_delivery_status_repo = TerminallogDeliveryStatusRepository(
        db=db_common, terminal_info=terminal_info
    )  # use common db

    return TerminalService(
        terminal_info_repo=terminal_info_repo,
        staff_master_repo=staff_master_repo,
        store_info_repo=store_info_repo,
        cash_in_out_log_repo=cash_in_out_log_repo,
        open_close_log_repo=open_close_log_repo,
        terminal_id=terminal_id,
        tran_log_repo=tran_log_repo,
        terminal_log_delivery_status_repo=terminal_log_delivery_status_repo,
    )


# Helper function for query parameter parsing
def parse_sort(sort: str = Query(default=None, description="?sort=field1:1,field2:-1")) -> list[tuple[str, int]]:
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
        sort_list = [("terminal_id", 1)]
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


async def get_tenant_id_with_security_wrapper(
    terminal_id: str = Path, api_key: str = Security(api_key_header), token: str = Depends(oauth2_scheme)
):
    """
    Security dependency that validates terminal authentication using either:
    - Terminal ID + API key combination, or
    - OAuth2 token
    Used for terminal-specific operations
    """
    return await get_tenant_id_with_security(terminal_id, api_key, token, is_terminal_service=True)


async def get_tenant_id_with_security_by_query_optional_wrapper(
    terminal_id: Optional[str] = Query(None),
    api_key: str = Security(api_key_header),
    token: str = Depends(oauth2_scheme),
):
    """
    Security dependency similar to get_tenant_id_with_security_wrapper,
    but with terminal ID as an optional query parameter instead of a path parameter
    """
    return await get_tenant_id_with_security_by_query_optional(terminal_id, api_key, token, is_terminal_service=True)


async def get_auth_context_with_path_terminal(
    terminal_id: str = Path(...),
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
) -> dict:
    """
    Returns authentication context for endpoints that need to know the auth method
    in addition to the tenant_id (e.g. to gate `?include_api_key=true` on user JWT only).

    Mirrors the priority order of kugel_common.security.__get_tenant_id:
      1. Terminal JWT (token_type="terminal")
      2. User JWT (existing OAuth2 flow)
      3. X-API-KEY + terminal_id

    Returns:
        Dict with keys:
          - tenant_id: str
          - auth_type: one of {"user_jwt", "terminal_jwt", "api_key"}
          - subject: identifier of the authenticated principal (terminal_id or username)
    """
    if token:
        try:
            claims = verify_terminal_token(token)
            return {
                "tenant_id": claims.get("tenant_id"),
                "auth_type": "terminal_jwt",
                "subject": claims.get("terminal_id"),
            }
        except HTTPException:
            pass  # Not a terminal token, fall through to user JWT
        user = await get_current_user(token)
        return {
            "tenant_id": user.get("tenant_id"),
            "auth_type": "user_jwt",
            "subject": user.get("username") or user.get("user_id") or "unknown",
        }
    if terminal_id and api_key:
        terminal_info = await get_terminal_info(terminal_id, api_key, is_terminal_service=True)
        return {
            "tenant_id": terminal_info.tenant_id,
            "auth_type": "api_key",
            "subject": terminal_id,
        }
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized access : No token or API-KEY provided",
    )


async def get_tenant_id_for_pubsub_notification(
    terminal_id: str = Path(...), auth_info: dict = Depends(verify_pubsub_notification_auth)
):
    """
    Security dependency for pub/sub notification endpoints.
    Validates authentication using either service JWT token or PUBSUB_NOTIFY_API_KEY.

    Args:
        terminal_id: Terminal ID from path parameter
        auth_info: Authentication information from JWT or API key

    Returns:
        Tenant ID extracted from terminal ID
    """
    # Extract tenant_id from terminal_id (format: tenant_id-store_code-terminal_no)
    tenant_id = terminal_id.split("-")[0]
    return tenant_id
