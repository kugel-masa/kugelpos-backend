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
    # When the update is driven by a POS transaction (issue #98), these
    # carry the upstream transaction's full identity so a unique index can
    # detect duplicate processing at the DB layer. They are optional
    # because manual adjustments / migrations may have no transaction.
    terminal_no: Optional[int] = Field(None, description="Terminal number (only when driven by a POS transaction)")
    transaction_no: Optional[int] = Field(None, description="Transaction number (only when driven by a POS transaction)")
    # Client-carried cart phase 2 (issue #156 / #152): the transaction identity.
    # A duplicate finalize (lost-ACK retry to any backend) carries the same
    # cart_id, so stock movements dedupe on it (skip — apply once).
    cart_id: Optional[str] = Field(None, description="Cart/transaction identity (client-carried cart phase 2)")

    class Settings:
        name = "stock_updates"
        indexes = [
            {"keys": [("tenant_id", 1), ("store_code", 1), ("item_code", 1), ("timestamp", -1)]},
            {"keys": [("update_type", 1)]},
            {"keys": [("timestamp", -1)]},
            {"keys": [("reference_id", 1)]},
            # Unique on (tenant, store, cart_id, item, type): a duplicate
            # finalize carries the same cart_id, so the second stock movement
            # is blocked at the DB layer (issue #156). Partial filter limits it
            # to transaction-driven updates (cart_id present); manual
            # adjustments (cart_id NULL) are unaffected. transaction_no is the
            # per-open seq in phase 2 and no longer unique on its own.
            {
                "keys": [
                    ("tenant_id", 1),
                    ("store_code", 1),
                    ("cart_id", 1),
                    ("item_code", 1),
                    ("update_type", 1),
                ],
                "unique": True,
                "partialFilterExpression": {"cart_id": {"$type": "string"}},
            },
        ]
