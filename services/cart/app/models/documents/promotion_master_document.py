# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from datetime import datetime
from typing import Optional
from pydantic import ConfigDict

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.utils.misc import to_lower_camel


class PromotionMasterDocument(AbstractDocument):
    """
    Document model representing promotion master data for cart service.

    This class defines the generic structure for promotion information retrieved
    from master-data. The detail field stores type-specific promotion configuration
    as a raw dict, which is parsed by individual promotion plugins.
    """

    tenant_id: Optional[str] = None
    promotion_code: Optional[str] = None
    promotion_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    is_active: bool = True
    detail: Optional[dict] = None

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)

    @classmethod
    def from_api_response(cls, data: dict) -> "PromotionMasterDocument":
        """
        Create a PromotionMasterDocument from API response data.

        Handles the camelCase to snake_case conversion for the response data.

        Args:
            data: The API response data dictionary (in camelCase)

        Returns:
            PromotionMasterDocument: The created document instance
        """
        # Parse datetime fields
        start_dt = None
        end_dt = None
        if data.get("startDatetime"):
            start_dt = datetime.fromisoformat(data["startDatetime"].replace("Z", "+00:00"))
        if data.get("endDatetime"):
            end_dt = datetime.fromisoformat(data["endDatetime"].replace("Z", "+00:00"))

        return cls(
            tenant_id=data.get("tenantId"),
            promotion_code=data.get("promotionCode"),
            promotion_type=data.get("promotionType"),
            name=data.get("name"),
            description=data.get("description"),
            start_datetime=start_dt,
            end_datetime=end_dt,
            is_active=data.get("isActive", True),
            detail=data.get("detail"),
        )
