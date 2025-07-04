# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import List, Optional, Tuple
from datetime import datetime
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from kugel_common.utils.misc import get_app_time_str

from app.models.documents import StockSnapshotDocument, StockSnapshotItem
from app.models.repositories import StockRepository, StockSnapshotRepository
from app.config.settings import settings

logger = getLogger(__name__)


class SnapshotService:
    def __init__(self, database: AsyncIOMotorDatabase):
        self._database = database
        self._stock_repository = StockRepository(database)
        self._snapshot_repository = StockSnapshotRepository(database)

    async def create_snapshot_async(
        self, tenant_id: str, store_code: str, created_by: str = "system"
    ) -> StockSnapshotDocument:
        """Create a snapshot of current stock levels"""

        # Get all stocks for the store
        stocks = await self._stock_repository.find_by_store_async(
            tenant_id, store_code, skip=0, limit=10000  # Get all stocks
        )

        # Prepare snapshot items
        snapshot_items = []
        total_quantity = 0.0

        for stock in stocks:
            snapshot_item = StockSnapshotItem(
                item_code=stock.item_code,
                quantity=stock.current_quantity,
                minimum_quantity=stock.minimum_quantity,
                reorder_point=stock.reorder_point,
                reorder_quantity=stock.reorder_quantity,
            )
            snapshot_items.append(snapshot_item)
            total_quantity += stock.current_quantity

        # Create snapshot document
        snapshot = StockSnapshotDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            total_items=len(snapshot_items),
            total_quantity=total_quantity,
            stocks=snapshot_items,
            created_by=created_by,
            generate_date_time=get_app_time_str(),
        )

        # Save snapshot
        success = await self._snapshot_repository.create_async(snapshot)

        if not success:
            logger.error(f"Failed to create snapshot for store {store_code}")
            raise Exception("Failed to create snapshot")

        logger.info(f"Snapshot created for store {store_code} with {len(snapshot_items)} items")

        # Retrieve the created snapshot to get the ID
        # Since we just created it, get the most recent one
        created_snapshot = await self._snapshot_repository.get_latest_snapshot_async(tenant_id, store_code)

        if created_snapshot:
            return created_snapshot
        else:
            # If retrieval fails, return the original snapshot without ID
            logger.warning(f"Could not retrieve created snapshot for store {store_code}")
            return snapshot

    async def get_snapshots_async(
        self, tenant_id: str, store_code: str, skip: int = 0, limit: int = 20
    ) -> Tuple[List[StockSnapshotDocument], int]:
        """Get snapshots for a store with total count"""
        snapshots = await self._snapshot_repository.find_by_store_async(tenant_id, store_code, skip, limit)
        total_count = await self._snapshot_repository.count_by_store_async(tenant_id, store_code)
        return snapshots, total_count

    async def get_snapshot_by_id_async(self, snapshot_id: str) -> Optional[StockSnapshotDocument]:
        """Get a specific snapshot by ID"""
        return await self._snapshot_repository.get_by_id_async(snapshot_id)

    async def get_snapshots_by_date_range_async(
        self, tenant_id: str, store_code: str, start_date: datetime, end_date: datetime
    ) -> List[StockSnapshotDocument]:
        """Get snapshots within a date range"""
        return await self._snapshot_repository.find_by_date_range_async(tenant_id, store_code, start_date, end_date)

    async def cleanup_old_snapshots_async(self, tenant_id: str, store_code: str, retention_days: int = 90) -> int:
        """Delete snapshots older than retention days"""
        deleted_count = await self._snapshot_repository.delete_old_snapshots_async(
            tenant_id, store_code, retention_days
        )

        logger.info(f"Deleted {deleted_count} old snapshots for store {store_code}")

        return deleted_count

    async def get_snapshots_by_generate_date_time_async(
        self,
        tenant_id: str,
        store_code: str,
        start_date: Optional[str],
        end_date: Optional[str],
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[StockSnapshotDocument], int]:
        """Get snapshots by generate_date_time range with pagination"""
        return await self._snapshot_repository.find_by_generate_date_time_async(
            tenant_id, store_code, start_date, end_date, skip, limit
        )
