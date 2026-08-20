# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.models.documents.stock_update_document import StockUpdateDocument
from app.config.settings import settings
from app.enums.update_type import UpdateType


class StockUpdateRepository(AbstractRepository[StockUpdateDocument]):
    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(settings.DB_COLLECTION_NAME_STOCK_UPDATE, StockUpdateDocument, database)

    async def find_by_item_async(
        self, tenant_id: str, store_code: str, item_code: str, skip: int = 0, limit: int = 100
    ) -> List[StockUpdateDocument]:
        """Find stock updates by item code"""
        if self.dbcollection is None:
            await self.initialize()

        cursor = (
            self.dbcollection.find({"tenant_id": tenant_id, "store_code": store_code, "item_code": item_code})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )

        documents = await cursor.to_list(length=limit if limit > 0 else None)
        return [StockUpdateDocument(**doc) for doc in documents]

    async def find_by_reference_async(self, reference_id: str) -> Optional[StockUpdateDocument]:
        """Find stock update by reference ID"""
        return await self.get_one_async({"reference_id": reference_id})

    async def find_by_transaction_async(
        self,
        tenant_id: str,
        store_code: str,
        terminal_no: int,
        transaction_no: int,
    ) -> List[StockUpdateDocument]:
        """Find ALL stock updates that came from a specific POS transaction
        (across line items / update types).

        Used for transaction-level idempotency in process_transaction_async:
        if any record exists for this transaction, the entire batch was
        already processed and we skip the redelivery.
        """
        if self.dbcollection is None:
            await self.initialize()

        cursor = self.dbcollection.find(
            {
                "tenant_id": tenant_id,
                "store_code": store_code,
                "terminal_no": terminal_no,
                "transaction_no": transaction_no,
            }
        )
        documents = await cursor.to_list(length=None)
        return [StockUpdateDocument(**doc) for doc in documents]

    async def find_by_cart_id_async(
        self,
        tenant_id: str,
        store_code: str,
        cart_id: str,
    ) -> List[StockUpdateDocument]:
        """Find ALL stock updates from a transaction identified by cart_id.

        Client-carried cart phase 2 (issue #156 / #152): a duplicate finalize
        (lost-ACK retry to any backend) carries the same cart_id. If any record
        exists for this cart_id the transaction was already processed, so the
        whole batch is skipped (apply once).
        """
        if self.dbcollection is None:
            await self.initialize()

        cursor = self.dbcollection.find(
            {
                "tenant_id": tenant_id,
                "store_code": store_code,
                "cart_id": cart_id,
            }
        )
        documents = await cursor.to_list(length=None)
        return [StockUpdateDocument(**doc) for doc in documents]

    async def find_by_date_range_async(
        self,
        tenant_id: str,
        store_code: str,
        start_date: datetime,
        end_date: datetime,
        update_type: Optional[UpdateType] = None,
    ) -> List[StockUpdateDocument]:
        """Find stock updates within date range"""
        filter_dict = {
            "tenant_id": tenant_id,
            "store_code": store_code,
            "timestamp": {"$gte": start_date, "$lte": end_date},
        }
        if update_type:
            filter_dict["update_type"] = update_type.value

        cursor = self.dbcollection.find(filter_dict).sort("timestamp", -1)
        documents = await cursor.to_list(length=None)
        return [StockUpdateDocument(**doc) for doc in documents]

    async def get_latest_update_async(
        self, tenant_id: str, store_code: str, item_code: str
    ) -> Optional[StockUpdateDocument]:
        """Get the latest update for an item"""
        if self.dbcollection is None:
            await self.initialize()

        cursor = (
            self.dbcollection.find({"tenant_id": tenant_id, "store_code": store_code, "item_code": item_code})
            .sort("timestamp", -1)
            .limit(1)
        )

        documents = await cursor.to_list(length=1)
        updates = [StockUpdateDocument(**doc) for doc in documents]
        return updates[0] if updates else None

    async def count_by_item_async(self, tenant_id: str, store_code: str, item_code: str) -> int:
        """Count stock updates by item code"""
        if self.dbcollection is None:
            await self.initialize()

        return await self.dbcollection.count_documents(
            {"tenant_id": tenant_id, "store_code": store_code, "item_code": item_code}
        )
