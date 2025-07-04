# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.models.documents.stock_snapshot_document import StockSnapshotDocument
from app.config.settings import settings


class StockSnapshotRepository(AbstractRepository[StockSnapshotDocument]):
    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(settings.DB_COLLECTION_NAME_STOCK_SNAPSHOT, StockSnapshotDocument, database)

    async def find_by_store_async(
        self, tenant_id: str, store_code: str, skip: int = 0, limit: int = 20
    ) -> List[StockSnapshotDocument]:
        """Find snapshots by store"""
        if self.dbcollection is None:
            await self.initialize()

        cursor = (
            self.dbcollection.find({"tenant_id": tenant_id, "store_code": store_code})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        documents = await cursor.to_list(length=limit if limit > 0 else None)
        return [StockSnapshotDocument(**doc) for doc in documents]

    async def find_by_date_range_async(
        self, tenant_id: str, store_code: str, start_date: datetime, end_date: datetime
    ) -> List[StockSnapshotDocument]:
        """Find snapshots within date range using created_at for backward compatibility"""
        cursor = self.dbcollection.find(
            {"tenant_id": tenant_id, "store_code": store_code, "created_at": {"$gte": start_date, "$lte": end_date}}
        ).sort("created_at", -1)
        documents = await cursor.to_list(length=None)
        return [StockSnapshotDocument(**doc) for doc in documents]

    async def get_latest_snapshot_async(self, tenant_id: str, store_code: str) -> Optional[StockSnapshotDocument]:
        """Get the latest snapshot for a store"""
        # Use the parent class method with sorting
        snapshots = await self.get_list_async_with_sort_and_paging(
            filter={"tenant_id": tenant_id, "store_code": store_code}, limit=1, page=1, sort=[("created_at", -1)]
        )
        return snapshots[0] if snapshots else None

    async def delete_old_snapshots_async(self, tenant_id: str, store_code: str, retention_days: int = 90) -> int:
        """Delete snapshots older than retention days"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        result = await self.dbcollection.delete_many(
            {"tenant_id": tenant_id, "store_code": store_code, "created_at": {"$lt": cutoff_date}}
        )
        return result.deleted_count

    async def count_by_store_async(self, tenant_id: str, store_code: str) -> int:
        """Count snapshots by store"""
        if self.dbcollection is None:
            await self.initialize()

        return await self.dbcollection.count_documents({"tenant_id": tenant_id, "store_code": store_code})

    async def find_by_generate_date_time_async(
        self,
        tenant_id: str,
        store_code: str,
        start_date: Optional[str],
        end_date: Optional[str],
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[StockSnapshotDocument], int]:
        """Find snapshots by generate_date_time range with pagination"""
        if self.dbcollection is None:
            await self.initialize()

        # Build query - only consider records with generate_date_time
        query = {"tenant_id": tenant_id, "store_code": store_code, "generate_date_time": {"$ne": None}}

        # Add date range filters if provided
        if start_date:
            query["generate_date_time"]["$gte"] = start_date
        if end_date:
            query["generate_date_time"]["$lte"] = end_date

        # Get total count
        total_count = await self.dbcollection.count_documents(query)

        # Get paginated results sorted by generate_date_time
        cursor = self.dbcollection.find(query).sort("generate_date_time", -1).skip(skip).limit(limit)
        documents = await cursor.to_list(length=limit if limit > 0 else None)
        snapshots = [StockSnapshotDocument(**doc) for doc in documents]

        return snapshots, total_count

    async def ensure_ttl_index(self, retention_days: int):
        """Ensure TTL index exists on created_at field"""
        if self.dbcollection is None:
            await self.initialize()

        # Get existing indexes
        indexes = await self.dbcollection.list_indexes().to_list(None)

        # Check if TTL index already exists
        ttl_index_exists = False
        for index in indexes:
            if index.get("name") == "created_at_ttl":
                # Check if TTL value is different
                if index.get("expireAfterSeconds") != retention_days * 86400:
                    # Drop old index and recreate with new TTL
                    await self.dbcollection.drop_index("created_at_ttl")
                else:
                    ttl_index_exists = True
                break

        # Create TTL index if it doesn't exist
        if not ttl_index_exists:
            await self.dbcollection.create_index(
                "created_at", name="created_at_ttl", expireAfterSeconds=retention_days * 86400
            )
