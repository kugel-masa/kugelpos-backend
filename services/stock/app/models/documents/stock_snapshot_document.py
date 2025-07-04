# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import List, Optional
from datetime import datetime
from pydantic import Field
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.base_document_model import BaseDocumentModel


class StockSnapshotItem(BaseDocumentModel):
    item_code: str = Field(..., description="Item code")
    quantity: float = Field(..., description="Stock quantity at snapshot time")
    minimum_quantity: float = Field(..., description="Minimum stock quantity")
    reorder_point: float = Field(0.0, description="Reorder point")
    reorder_quantity: float = Field(0.0, description="Reorder quantity")


class StockSnapshotDocument(AbstractDocument):
    tenant_id: str = Field(..., description="Tenant ID")
    store_code: str = Field(..., description="Store code")
    total_items: int = Field(..., description="Total number of items")
    total_quantity: float = Field(..., description="Total stock quantity")
    stocks: List[StockSnapshotItem] = Field(default_factory=list, description="Stock details by item")
    created_by: str = Field(..., description="User or system that created the snapshot")
    generate_date_time: Optional[str] = Field(None, description="Snapshot generation datetime in ISO format")

    class Settings:
        name = "stock_snapshots"
        indexes = [
            {"keys": [("tenant_id", 1), ("store_code", 1), ("created_at", -1)]},
            {"keys": [("tenant_id", 1), ("store_code", 1), ("generate_date_time", -1)]},
        ]
