# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from pydantic import Field
from kugel_common.models.documents.abstract_document import AbstractDocument


class StockDocument(AbstractDocument):
    """
    Document class representing current stock levels.

    This document stores the current quantity and minimum threshold
    for each item in a store.
    """

    tenant_id: str = Field(..., description="Tenant ID")
    store_code: str = Field(..., description="Store code")
    item_code: str = Field(..., description="Item code")
    current_quantity: float = Field(0.0, description="Current stock quantity")
    minimum_quantity: float = Field(0.0, description="Minimum stock quantity for alerts")
    reorder_point: float = Field(0.0, description="Reorder point - quantity that triggers reorder")
    reorder_quantity: float = Field(0.0, description="Quantity to order when reorder point is reached")
    last_transaction_id: Optional[str] = Field(None, description="Last transaction reference")
