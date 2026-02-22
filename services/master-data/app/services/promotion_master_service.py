# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from datetime import datetime
from logging import getLogger
from typing import Optional

from kugel_common.exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    InvalidRequestDataException,
)
from app.models.documents.promotion_master_document import PromotionMasterDocument
from app.models.repositories.promotion_master_repository import (
    PromotionMasterRepository,
)

logger = getLogger(__name__)


class PromotionMasterService:
    """
    Service class for managing promotion master data operations.

    This service provides business logic for creating, retrieving, updating,
    and deleting promotion records in the master data database.
    """

    def __init__(self, promotion_master_repo: PromotionMasterRepository):
        """
        Initialize the PromotionMasterService with a repository.

        Args:
            promotion_master_repo: Repository for promotion master data operations
        """
        self.promotion_master_repo = promotion_master_repo

    async def create_promotion_async(
        self,
        promotion_code: str,
        promotion_type: str,
        name: str,
        start_datetime: datetime,
        end_datetime: datetime,
        description: Optional[str] = None,
        is_active: bool = True,
        detail: Optional[
            PromotionMasterDocument.CategoryPromoDetail
        ] = None,
    ) -> PromotionMasterDocument:
        """
        Create a new promotion in the database.

        Args:
            promotion_code: Unique identifier for the promotion
            promotion_type: Type of promotion (e.g., "category_discount")
            name: Display name of the promotion
            start_datetime: Start datetime of the promotion
            end_datetime: End datetime of the promotion
            description: Optional description of the promotion
            is_active: Whether the promotion is active
            detail: Type-specific promotion details

        Returns:
            Newly created PromotionMasterDocument

        Raises:
            DocumentAlreadyExistsException: If a promotion with the given code already exists
            InvalidRequestDataException: If validation fails
        """
        # Validate date range
        if end_datetime <= start_datetime:
            message = "end_datetime must be after start_datetime"
            raise InvalidRequestDataException(message, logger)

        # Validate detail for category_discount type
        if promotion_type == "category_discount":
            if detail is None:
                message = "detail is required for category_discount type"
                raise InvalidRequestDataException(message, logger)
            if (
                not detail.target_category_codes
                or len(detail.target_category_codes) == 0
            ):
                message = "target_category_codes must contain at least one category code"
                raise InvalidRequestDataException(message, logger)
            if (
                detail.discount_rate <= 0
                or detail.discount_rate > 100
            ):
                message = "discount_rate must be between 0 and 100"
                raise InvalidRequestDataException(message, logger)

        # Check if promotion exists
        existing = await self.promotion_master_repo.get_promotion_by_code_async(
            promotion_code
        )
        if existing is not None:
            message = f"promotion with code {promotion_code} already exists"
            raise DocumentAlreadyExistsException(message, logger)

        promotion_doc = PromotionMasterDocument()
        promotion_doc.promotion_code = promotion_code
        promotion_doc.promotion_type = promotion_type
        promotion_doc.name = name
        promotion_doc.description = description
        promotion_doc.start_datetime = start_datetime
        promotion_doc.end_datetime = end_datetime
        promotion_doc.is_active = is_active
        promotion_doc.detail = detail

        return await self.promotion_master_repo.create_promotion_async(promotion_doc)

    async def get_promotion_by_code_async(
        self, promotion_code: str
    ) -> PromotionMasterDocument:
        """
        Retrieve a promotion by its unique code.

        Args:
            promotion_code: Unique identifier for the promotion

        Returns:
            PromotionMasterDocument with the specified code

        Raises:
            DocumentNotFoundException: If no promotion with the given code exists
        """
        promotion = await self.promotion_master_repo.get_promotion_by_code_async(
            promotion_code
        )
        if promotion is None:
            message = f"promotion with code {promotion_code} not found"
            raise DocumentNotFoundException(message, logger)
        return promotion

    async def get_promotions_async(
        self,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
        promotion_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[PromotionMasterDocument]:
        """
        Retrieve promotions with pagination and sorting.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction
            promotion_type: Optional filter by promotion type
            is_active: Optional filter by active status

        Returns:
            List of PromotionMasterDocument objects
        """
        query_filter = {}
        if promotion_type is not None:
            query_filter["promotion_type"] = promotion_type
        if is_active is not None:
            query_filter["is_active"] = is_active

        return await self.promotion_master_repo.get_promotions_by_filter_async(
            query_filter, limit, page, sort
        )

    async def get_promotions_paginated_async(
        self,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
        promotion_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ):
        """
        Retrieve promotions with pagination metadata.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction
            promotion_type: Optional filter by promotion type
            is_active: Optional filter by active status

        Returns:
            PaginatedResult containing PromotionMasterDocument objects and metadata
        """
        query_filter = {}
        if promotion_type is not None:
            query_filter["promotion_type"] = promotion_type
        if is_active is not None:
            query_filter["is_active"] = is_active

        return await self.promotion_master_repo.get_promotions_by_filter_paginated_async(
            query_filter, limit, page, sort
        )

    async def get_active_promotions_async(
        self,
        store_code: Optional[str] = None,
        category_code: Optional[str] = None,
        promotion_type: Optional[str] = None,
    ) -> list[PromotionMasterDocument]:
        """
        Retrieve currently active promotions with optional filters.

        Args:
            store_code: Optional filter by store code
            category_code: Optional filter by category code
            promotion_type: Optional filter by promotion type

        Returns:
            List of active PromotionMasterDocument objects
        """
        if store_code and category_code:
            # Get promotions for both store and category
            store_promotions = (
                await self.promotion_master_repo.get_active_promotions_by_store_async(
                    store_code
                )
            )
            # Filter by category
            result = []
            for promo in store_promotions:
                if (
                    promo.detail
                    and category_code
                    in promo.detail.target_category_codes
                ):
                    if promotion_type is None or promo.promotion_type == promotion_type:
                        result.append(promo)
            return result
        elif store_code:
            promotions = (
                await self.promotion_master_repo.get_active_promotions_by_store_async(
                    store_code
                )
            )
            if promotion_type:
                return [p for p in promotions if p.promotion_type == promotion_type]
            return promotions
        elif category_code:
            promotions = await self.promotion_master_repo.get_active_promotions_by_category_async(
                category_code
            )
            if promotion_type:
                return [p for p in promotions if p.promotion_type == promotion_type]
            return promotions
        else:
            promotions = await self.promotion_master_repo.get_active_promotions_async()
            if promotion_type:
                return [p for p in promotions if p.promotion_type == promotion_type]
            return promotions

    async def update_promotion_async(
        self, promotion_code: str, update_data: dict
    ) -> PromotionMasterDocument:
        """
        Update an existing promotion with new data.

        Args:
            promotion_code: Unique identifier for the promotion to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated PromotionMasterDocument

        Raises:
            DocumentNotFoundException: If no promotion with the given code exists
            InvalidRequestDataException: If validation fails
        """
        # Check if promotion exists
        promotion = await self.promotion_master_repo.get_promotion_by_code_async(
            promotion_code
        )
        if promotion is None:
            message = f"promotion with code {promotion_code} not found"
            raise DocumentNotFoundException(message, logger)

        # Validate date range if both dates are provided
        start_dt = update_data.get("start_datetime", promotion.start_datetime)
        end_dt = update_data.get("end_datetime", promotion.end_datetime)
        if start_dt and end_dt and end_dt <= start_dt:
            message = "end_datetime must be after start_datetime"
            raise InvalidRequestDataException(message, logger)

        # Validate discount_rate if detail is updated
        if "detail" in update_data and update_data["detail"]:
            detail = update_data["detail"]
            if isinstance(detail, dict):
                rate = detail.get("discount_rate")
                if rate is not None and (rate <= 0 or rate > 100):
                    message = "discount_rate must be between 0 and 100"
                    raise InvalidRequestDataException(message, logger)

        return await self.promotion_master_repo.update_promotion_async(
            promotion_code, update_data
        )

    async def delete_promotion_async(self, promotion_code: str) -> None:
        """
        Logically delete a promotion from the database.

        Args:
            promotion_code: Unique identifier for the promotion to delete

        Raises:
            DocumentNotFoundException: If no promotion with the given code exists
        """
        # Check if promotion exists
        promotion = await self.promotion_master_repo.get_promotion_by_code_async(
            promotion_code
        )
        if promotion is None:
            message = f"promotion with code {promotion_code} not found"
            raise DocumentNotFoundException(message, logger)

        await self.promotion_master_repo.delete_promotion_async(promotion_code)
