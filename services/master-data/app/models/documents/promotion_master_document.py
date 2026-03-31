# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from datetime import datetime
from pydantic import field_validator

from app.models.documents.abstract_document import AbstractDocument


class PromotionMasterDocument(AbstractDocument):
    """
    Document class representing a promotion in the master data system.

    This class defines the structure for promotion information which is used to apply
    discounts to items based on various criteria. The promotion system is designed to be
    extensible, supporting different promotion types through the promotion_type field.
    The detail field stores type-specific configuration as a plain dict, with validation
    handled by the service layer based on promotion_type.
    """

    tenant_id: Optional[str] = None
    promotion_code: Optional[str] = None
    promotion_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    is_active: bool = True
    is_deleted: bool = False
    detail: Optional[dict] = None

    @field_validator("end_datetime")
    @classmethod
    def validate_end_datetime(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_datetime")
        if start and v and v <= start:
            raise ValueError("end_datetime must be after start_datetime")
        return v
