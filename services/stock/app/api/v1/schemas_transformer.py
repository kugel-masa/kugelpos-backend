# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import List
from datetime import datetime, timezone

from app.models.documents import StockDocument, StockUpdateDocument, StockSnapshotDocument, StockSnapshotItem
from app.api.v1.schemas import StockResponse, StockUpdateResponse, StockSnapshotResponse, StockSnapshotItemResponse


class StockTransformer:
    """Transform between document models and API schemas for stock"""

    @staticmethod
    def to_response(document: StockDocument) -> StockResponse:
        """Convert StockDocument to StockResponse"""
        return StockResponse(
            tenant_id=document.tenant_id,
            store_code=document.store_code,
            item_code=document.item_code,
            current_quantity=document.current_quantity,
            minimum_quantity=document.minimum_quantity,
            reorder_point=document.reorder_point,
            reorder_quantity=document.reorder_quantity,
            last_updated=document.updated_at or datetime.now(timezone.utc),
            last_transaction_id=document.last_transaction_id,
        )


class StockUpdateTransformer:
    """Transform between document models and API schemas for stock updates"""

    @staticmethod
    def to_response(document: StockUpdateDocument) -> StockUpdateResponse:
        """Convert StockUpdateDocument to StockUpdateResponse"""
        return StockUpdateResponse(
            tenant_id=document.tenant_id,
            store_code=document.store_code,
            item_code=document.item_code,
            update_type=document.update_type,
            quantity_change=document.quantity_change,
            before_quantity=document.before_quantity,
            after_quantity=document.after_quantity,
            reference_id=document.reference_id,
            timestamp=document.timestamp,
            operator_id=document.operator_id,
            note=document.note,
        )


class SnapshotTransformer:
    """Transform between document models and API schemas for snapshots"""

    @staticmethod
    def snapshot_item_to_response(item: StockSnapshotItem) -> StockSnapshotItemResponse:
        """Convert StockSnapshotItem to StockSnapshotItemResponse"""
        return StockSnapshotItemResponse(
            item_code=item.item_code,
            quantity=item.quantity,
            minimum_quantity=item.minimum_quantity,
            reorder_point=item.reorder_point,
            reorder_quantity=item.reorder_quantity,
        )

    @staticmethod
    def to_response(document: StockSnapshotDocument) -> StockSnapshotResponse:
        """Convert StockSnapshotDocument to StockSnapshotResponse"""
        return StockSnapshotResponse(
            tenant_id=document.tenant_id,
            store_code=document.store_code,
            total_items=document.total_items,
            total_quantity=document.total_quantity,
            stocks=[SnapshotTransformer.snapshot_item_to_response(item) for item in document.stocks],
            created_by=document.created_by,
            created_at=document.created_at,
            updated_at=document.updated_at,
            generate_date_time=document.generate_date_time,
        )
