# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from datetime import datetime
from typing import Optional
from pydantic import ConfigDict, Field

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.utils.misc import to_lower_camel


class PromotionMasterDocument(AbstractDocument):
    """
    Document model representing promotion master data for cart service.

    This class defines the structure for promotion information retrieved from master-data
    and used to apply category-based discounts to cart items.
    """

    class CategoryPromoDetail(BaseDocumentModel):
        """
        Nested class containing category promotion specific details.

        Defines the targeting and discount rate for category-based promotions.
        """

        target_store_codes: Optional[list[str]] = Field(
            default_factory=list,
            description="List of store codes where the promotion applies. Empty list means all stores.",
        )
        target_category_codes: list[str] = Field(
            default_factory=list,
            description="List of category codes that qualify for the promotion discount.",
        )
        discount_rate: float = Field(
            default=0.0,
            description="Discount percentage to apply (0-100).",
        )

        model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)

    tenant_id: Optional[str] = None
    promotion_code: Optional[str] = None
    promotion_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    is_active: bool = True
    category_promo_detail: Optional[CategoryPromoDetail] = None

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
        # Parse category promo detail if present
        category_detail_data = data.get("categoryPromoDetail")
        category_detail = None
        if category_detail_data:
            category_detail = cls.CategoryPromoDetail(
                target_store_codes=category_detail_data.get("targetStoreCodes", []),
                target_category_codes=category_detail_data.get("targetCategoryCodes", []),
                discount_rate=category_detail_data.get("discountRate", 0.0),
            )

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
            category_promo_detail=category_detail,
        )
