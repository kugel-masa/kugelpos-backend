# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from pydantic import BaseModel, ConfigDict, Field
from typing import TypeVar, Optional

from kugel_common.utils.misc import to_lower_camel


# Base Schema Model
class BaseSchemaModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)


T = TypeVar("T")


# for service
class BaseJournalSchema(BaseSchemaModel):
    tenant_id: str = Field(..., description="tenant id")
    store_code: str = Field(..., description="store code")
    terminal_no: int = Field(..., description="terminal no")
    journal_seq_no: Optional[int] = Field(-1, description="delete in future")
    transaction_no: Optional[int] = Field(None, description="transaction_no")
    transaction_type: int = Field(..., description="transaction type")
    business_date: str = Field(..., description="business date")
    open_counter: int = Field(..., description="open counter")
    business_counter: int = Field(..., description="business counter")
    generate_date_time: str = Field(..., description="generate date time")
    receipt_no: Optional[int] = Field(None, description="receipt no")
    amount: Optional[float] = Field(0.0, description="total_amount_with_tax")
    quantity: Optional[int] = Field(0, description="total_quantity")
    staff_id: Optional[str] = Field(None, description="staff id")
    user_id: Optional[str] = Field(None, description="user id")
    content: Optional[str] = Field("please refer to journal_text.", description="delete in future")
    journal_text: str = Field(..., description="journal text")
    receipt_text: str = Field(..., description="receipt text")


class BaseTenantCreateRequest(BaseSchemaModel):
    tenant_id: str


class BaseTenantCreateResponse(BaseSchemaModel):
    tenant_id: str


class BaseTranResponse(BaseSchemaModel):
    tenant_id: str
    store_code: str
    terminal_no: int
    transaction_no: int
