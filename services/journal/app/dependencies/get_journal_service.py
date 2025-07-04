# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

"""
Dependency injection functions for journal API endpoints.

This module provides dependency injection helpers for creating and configuring
journal service instances with all necessary repositories and services.
"""

from fastapi import Path
from logging import getLogger

from kugel_common.database import database as db_helper

from app.services.journal_service import JournalService
from app.models.repositories.journal_repository import JournalRepository
from app.config.settings import settings

# Get logger instance
logger = getLogger(__name__)


async def get_journal_service(tenant_id: str = Path(...)) -> JournalService:
    """
    Dependency function to create and inject a JournalService instance.

    This function creates the necessary repository and injects it into the JournalService,
    providing access to the required data sources for journal operations.

    Args:
        tenant_id: The tenant identifier from the path parameter

    Returns:
        JournalService: Configured instance with required repositories
    """
    logger.debug(f"get_journal_service: tenant_id->{tenant_id}")

    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return JournalService(journal_repository=JournalRepository(db=db, tenant_id=tenant_id))
