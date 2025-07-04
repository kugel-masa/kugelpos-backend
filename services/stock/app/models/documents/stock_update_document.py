# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from datetime import datetime
from pydantic import Field
from kugel_common.models.documents.abstract_document import AbstractDocument
from app.enums.update_type import UpdateType


class StockUpdateDocument(AbstractDocument):
    tenant_id: str = Field(..., description="Tenant ID")
    store_code: str = Field(..., description="Store code")
    item_code: str = Field(..., description="Item code")
    update_type: UpdateType = Field(..., description="Type of stock update")
    quantity_change: float = Field(..., description="Quantity change (positive for increase, negative for decrease)")
    before_quantity: float = Field(..., description="Stock quantity before update")
    after_quantity: float = Field(..., description="Stock quantity after update")
    reference_id: Optional[str] = Field(None, description="Reference ID (transaction, adjustment, etc.)")
    timestamp: datetime = Field(..., description="Update timestamp")
    operator_id: Optional[str] = Field(None, description="User who performed the update")
    note: Optional[str] = Field(None, description="Additional notes")

    class Settings:
        name = "stock_updates"
        indexes = [
            {"keys": [("tenant_id", 1), ("store_code", 1), ("item_code", 1), ("timestamp", -1)]},
            {"keys": [("update_type", 1)]},
            {"keys": [("timestamp", -1)]},
            {"keys": [("reference_id", 1)]},
        ]
