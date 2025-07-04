# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.utils.misc import get_app_time
from app.models.documents.stock_document import StockDocument
from app.config.settings import settings


class StockRepository(AbstractRepository[StockDocument]):
    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(settings.DB_COLLECTION_NAME_STOCK, StockDocument, database)

    async def find_by_item_async(self, tenant_id: str, store_code: str, item_code: str) -> Optional[StockDocument]:
        """Find stock by tenant, store and item code"""
        return await self.get_one_async({"tenant_id": tenant_id, "store_code": store_code, "item_code": item_code})

    async def find_by_store_async(
        self, tenant_id: str, store_code: str, skip: int = 0, limit: int = 100
    ) -> List[StockDocument]:
        """Find all stocks for a store"""
        if self.dbcollection is None:
            await self.initialize()

        cursor = (
            self.dbcollection.find({"tenant_id": tenant_id, "store_code": store_code})
            .sort("item_code", 1)
            .skip(skip)
            .limit(limit)
        )

        documents = await cursor.to_list(length=limit if limit > 0 else None)
        return [StockDocument(**doc) for doc in documents]

    async def find_low_stock_async(self, tenant_id: str, store_code: str) -> List[StockDocument]:
        """Find items with stock below minimum quantity"""
        if self.dbcollection is None:
            await self.initialize()

        cursor = self.dbcollection.find(
            {
                "tenant_id": tenant_id,
                "store_code": store_code,
                "$expr": {"$lt": ["$current_quantity", "$minimum_quantity"]},
            }
        )
        documents = await cursor.to_list(length=None)
        return [StockDocument(**doc) for doc in documents]

    async def update_quantity_async(
        self, tenant_id: str, store_code: str, item_code: str, new_quantity: float, transaction_id: Optional[str] = None
    ) -> bool:
        """Update stock quantity"""
        update_data = {"current_quantity": new_quantity, "last_transaction_id": transaction_id}
        return await self.update_one_async(
            {"tenant_id": tenant_id, "store_code": store_code, "item_code": item_code}, update_data
        )

    async def update_quantity_atomic_async(
        self,
        tenant_id: str,
        store_code: str,
        item_code: str,
        quantity_change: float,
        transaction_id: Optional[str] = None,
    ) -> Optional[StockDocument]:
        """Atomically update stock quantity using findAndModify to prevent race conditions"""
        if self.dbcollection is None:
            await self.initialize()

        now = get_app_time()

        # Use findAndModify with upsert for atomic update
        result = await self.dbcollection.find_one_and_update(
            filter={"tenant_id": tenant_id, "store_code": store_code, "item_code": item_code},
            update={
                "$inc": {"current_quantity": quantity_change},
                "$set": {"last_transaction_id": transaction_id, "updated_at": now},
                "$setOnInsert": {
                    "tenant_id": tenant_id,
                    "store_code": store_code,
                    "item_code": item_code,
                    "minimum_quantity": 0.0,
                    "reorder_point": 0.0,
                    "reorder_quantity": 0.0,
                    "created_at": now,
                },
            },
            upsert=True,  # Create document if it doesn't exist
            return_document=True,  # Return the document after update
        )

        if result:
            return StockDocument(**result)
        return None

    async def count_by_store_async(self, tenant_id: str, store_code: str) -> int:
        """Count all stocks for a store"""
        if self.dbcollection is None:
            await self.initialize()

        return await self.dbcollection.count_documents({"tenant_id": tenant_id, "store_code": store_code})

    async def find_reorder_alerts_async(self, tenant_id: str, store_code: str) -> List[StockDocument]:
        """Find items with stock below reorder point"""
        if self.dbcollection is None:
            await self.initialize()

        cursor = self.dbcollection.find(
            {
                "tenant_id": tenant_id,
                "store_code": store_code,
                "$expr": {
                    "$and": [
                        {"$gt": ["$reorder_point", 0]},  # Only check if reorder point is set
                        {"$lte": ["$current_quantity", "$reorder_point"]},
                    ]
                },
            }
        )
        documents = await cursor.to_list(length=None)
        return [StockDocument(**doc) for doc in documents]

    async def update_reorder_parameters_async(
        self, tenant_id: str, store_code: str, item_code: str, reorder_point: float, reorder_quantity: float
    ) -> bool:
        """Update reorder point and quantity for an item"""
        update_data = {"reorder_point": reorder_point, "reorder_quantity": reorder_quantity}
        return await self.update_one_async(
            {"tenant_id": tenant_id, "store_code": store_code, "item_code": item_code}, update_data
        )
