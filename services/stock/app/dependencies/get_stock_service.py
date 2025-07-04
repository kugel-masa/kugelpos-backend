# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.database import database as db_helper
from app.services.stock_service import StockService
from app.services.snapshot_service import SnapshotService
from app.config.settings import settings
from app.dependencies.get_alert_service import get_alert_service


async def get_db_from_tenant(tenant_id: str) -> AsyncIOMotorDatabase:
    """Get database from tenant ID"""
    return await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")


async def get_stock_service(request: Request, tenant_id: str) -> StockService:
    """Get stock service instance"""
    db = await get_db_from_tenant(tenant_id)
    alert_service = get_alert_service()
    return StockService(db, alert_service)


async def get_stock_service_from_request(request: Request) -> StockService:
    """Get stock service instance from request (for pubsub handlers)"""
    # Extract tenant_id from request body for pubsub messages
    req_json = await request.json()
    tenant_id = req_json.get("data", {}).get("tenant_id", "")
    if not tenant_id:
        from logging import getLogger

        logger = getLogger(__name__)
        logger.error(f"tenant_id is required. request: {req_json}")
        return None
    db = await get_db_from_tenant(tenant_id)
    alert_service = get_alert_service()
    return StockService(db, alert_service)


async def get_snapshot_service(request: Request, tenant_id: str) -> SnapshotService:
    """Get snapshot service instance"""
    db = await get_db_from_tenant(tenant_id)
    return SnapshotService(db)


async def get_snapshot_service_from_request(request: Request) -> SnapshotService:
    """Get snapshot service instance from request (for pubsub handlers)"""
    # Extract tenant_id from request body for pubsub messages
    req_json = await request.json()
    tenant_id = req_json.get("data", {}).get("tenant_id", "")
    if not tenant_id:
        from logging import getLogger

        logger = getLogger(__name__)
        logger.error(f"tenant_id is required. request: {req_json}")
        return None
    db = await get_db_from_tenant(tenant_id)
    return SnapshotService(db)
