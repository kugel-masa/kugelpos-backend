# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, List
from datetime import datetime
from pydantic import Field, ConfigDict

from app.enums.update_type import UpdateType
from app.api.common.schemas import *


# Request schemas
class StockUpdateRequest(BaseSchemaModel):
    """在庫更新リクエスト"""

    quantity_change: float = Field(..., description="Quantity change (positive for increase, negative for decrease)")
    update_type: UpdateType = Field(..., description="Type of stock update")
    reference_id: Optional[str] = Field(None, description="Reference ID (transaction, adjustment, etc.)")
    operator_id: Optional[str] = Field(None, description="User who performed the update")
    note: Optional[str] = Field(None, description="Additional notes")


class SetMinimumQuantityRequest(BaseSchemaModel):
    """最小在庫数設定リクエスト"""

    minimum_quantity: float = Field(..., ge=0, description="Minimum stock quantity for alerts")


class CreateSnapshotRequest(BaseSchemaModel):
    """スナップショット作成リクエスト"""

    created_by: str = Field("system", description="User or system that created the snapshot")


class SetReorderParametersRequest(BaseSchemaModel):
    """発注点・発注数量設定リクエスト"""

    reorder_point: float = Field(..., ge=0, description="Reorder point - quantity that triggers reorder")
    reorder_quantity: float = Field(..., ge=0, description="Quantity to order when reorder point is reached")


# Response schemas
class StockResponse(BaseSchemaModel):
    """在庫情報レスポンス"""

    tenant_id: str = Field(..., description="Tenant ID")
    store_code: str = Field(..., description="Store code")
    item_code: str = Field(..., description="Item code")
    current_quantity: float = Field(..., description="Current stock quantity")
    minimum_quantity: float = Field(..., description="Minimum stock quantity for alerts")
    reorder_point: float = Field(..., description="Reorder point - quantity that triggers reorder")
    reorder_quantity: float = Field(..., description="Quantity to order when reorder point is reached")
    last_updated: datetime = Field(..., description="Last update timestamp")
    last_transaction_id: Optional[str] = Field(None, description="Last transaction reference")


class StockUpdateResponse(BaseSchemaModel):
    """在庫更新履歴レスポンス"""

    tenant_id: str = Field(..., description="Tenant ID")
    store_code: str = Field(..., description="Store code")
    item_code: str = Field(..., description="Item code")
    update_type: UpdateType = Field(..., description="Type of stock update")
    quantity_change: float = Field(..., description="Quantity change")
    before_quantity: float = Field(..., description="Stock quantity before update")
    after_quantity: float = Field(..., description="Stock quantity after update")
    reference_id: Optional[str] = Field(None, description="Reference ID")
    timestamp: datetime = Field(..., description="Update timestamp")
    operator_id: Optional[str] = Field(None, description="User who performed the update")
    note: Optional[str] = Field(None, description="Additional notes")


class StockSnapshotItemResponse(BaseSchemaModel):
    """スナップショット内の在庫アイテム"""

    item_code: str = Field(..., description="Item code")
    quantity: float = Field(..., description="Stock quantity at snapshot time")
    minimum_quantity: float = Field(..., description="Minimum stock quantity")
    reorder_point: float = Field(..., description="Reorder point")
    reorder_quantity: float = Field(..., description="Reorder quantity")


class StockSnapshotResponse(BaseSchemaModel):
    """在庫スナップショットレスポンス"""

    tenant_id: str = Field(..., description="Tenant ID")
    store_code: str = Field(..., description="Store code")
    total_items: int = Field(..., description="Total number of items")
    total_quantity: float = Field(..., description="Total stock quantity")
    stocks: List[StockSnapshotItemResponse] = Field(..., description="Stock details by item")
    created_by: str = Field(..., description="User or system that created the snapshot")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    generate_date_time: Optional[str] = Field(None, description="Snapshot generation datetime in ISO format")


# PubSub message schemas
class TransactionLog(BaseSchemaModel):
    """トランザクションログ (from cart service)"""

    event_id: str = Field(..., description="Unique event ID for idempotency")
    tenant_id: str = Field(..., description="Tenant ID")
    store_code: str = Field(..., description="Store code")
    terminal_no: str = Field(..., description="Terminal number")
    transaction_no: str = Field(..., description="Transaction number")
    business_date: str = Field(..., description="Business date")
    transaction_time: datetime = Field(..., description="Transaction timestamp")
    items: List[dict] = Field(..., description="Transaction items")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_lower_camel,
        json_schema_extra={
            "example": {
                "eventId": "evt_12345",
                "tenantId": "tenant001",
                "storeCode": "store001",
                "terminalNo": "001",
                "transactionNo": "TRX001",
                "businessDate": "2024-01-01",
                "transactionTime": "2024-01-01T10:30:00Z",
                "items": [{"itemCode": "ITEM001", "quantity": 2, "unitPrice": 100.0, "amount": 200.0}],
            }
        },
    )


# Tenant management schemas
class TenantCreateRequest(BaseTenantCreateRequest):
    """
    Tenant creation request model for API version 1.

    Extends the base tenant creation request model with version-specific fields
    if needed. Currently inherits all functionality from BaseTenantCreateRequest.
    Used to initialize the stock service for a new tenant.
    """

    pass


class TenantCreateResponse(BaseTenantCreateResponse):
    """
    Tenant creation response model for API version 1.

    Extends the base tenant creation response model with version-specific fields
    if needed. Currently inherits all functionality from BaseTenantCreateResponse.
    Used to confirm the tenant was successfully created in the stock service.
    """

    pass
