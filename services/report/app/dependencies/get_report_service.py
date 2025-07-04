# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
Dependency injection functions for report API endpoints.

This module provides dependency injection helpers for creating and configuring
report service instances with all necessary repositories and services.
"""

from fastapi import Depends, Path, Query, Security
from typing import Optional
from logging import getLogger

from kugel_common.database import database as db_helper
from kugel_common.security import api_key_header, oauth2_scheme

from app.services.report_service import ReportService
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository
from app.models.repositories.terminal_info_web_repository import TerminalInfoWebRepository
from app.config.settings import settings

# Get logger instance
logger = getLogger(__name__)


async def get_report_service(
    tenant_id: str = Path(...),
    store_code: str = Path(...),
    terminal_id: Optional[str] = Query(None),
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
) -> ReportService:
    """
    Dependency function to create and inject a ReportService instance.

    This function creates all necessary repositories and injects them into the ReportService,
    providing access to the required data sources for generating reports.

    Args:
        tenant_id: The tenant identifier from the path
        store_code: The store code from the path
        terminal_id: Optional terminal ID from the query parameters
        api_key: Optional API key from the security header
        token: Optional OAuth2 token

    Returns:
        ReportService: Configured instance with all required repositories
    """
    logger.debug(f"get_report_service: tenant_id->{tenant_id}, store_code->{store_code}")

    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    tran_repo = TranlogRepository(db=db, tenant_id=tenant_id)
    cash_repo = CashInOutLogRepository(db=db, tenant_id=tenant_id)
    open_close_repo = OpenCloseLogRepository(db=db, tenant_id=tenant_id)
    daily_info_repo = DailyInfoDocumentRepository(db=db, tenant_id=tenant_id)
    terminal_info_repo = TerminalInfoWebRepository(
        tenant_id=tenant_id, store_code=store_code, terminal_id=terminal_id, api_key=api_key, token=token
    )

    return ReportService(
        tran_repository=tran_repo,
        cash_in_out_log_repository=cash_repo,
        open_close_log_repository=open_close_repo,
        daily_info_repository=daily_info_repo,
        terminal_info_repository=terminal_info_repo,
    )
