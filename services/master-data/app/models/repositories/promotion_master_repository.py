# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.documents.promotion_master_document import PromotionMasterDocument
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.config.settings import settings
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.utils.misc import get_app_time

from logging import getLogger

logger = getLogger(__name__)


class PromotionMasterRepository(AbstractRepository[PromotionMasterDocument]):
    """
    Repository for managing promotion master data in the database.

    This class provides specific implementation for CRUD operations on promotion master data,
    extending the generic functionality provided by AbstractRepository. It handles
    tenant-specific data access and includes methods tailored for promotion operations.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str):
        """
        Initialize a new PromotionMasterRepository instance.

        Args:
            db: MongoDB database instance
            tenant_id: Identifier for the tenant whose data this repository will manage
        """
        super().__init__(
            settings.DB_COLLECTION_NAME_PROMOTION_MASTER, PromotionMasterDocument, db
        )
        self.tenant_id = tenant_id

    async def create_promotion_async(
        self, document: PromotionMasterDocument
    ) -> PromotionMasterDocument:
        """
        Create a new promotion in the database.

        This method sets the tenant ID and generates a shard key before creating the document.

        Args:
            document: Promotion document to create

        Returns:
            The created promotion document
        """
        document.tenant_id = self.tenant_id
        document.shard_key = self.__get_shard_key(document)
        success = await self.create_async(document)
        if success:
            return document
        else:
            raise Exception("Failed to create promotion")

    async def get_promotion_by_code_async(
        self, promotion_code: str
    ) -> PromotionMasterDocument:
        """
        Retrieve a promotion by its unique code.

        Args:
            promotion_code: Unique identifier for the promotion

        Returns:
            The matching promotion document, or None if not found
        """
        return await self.get_one_async(self.__make_query_filter(promotion_code))

    async def get_promotions_by_filter_async(
        self, query_filter: dict, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> list[PromotionMasterDocument]:
        """
        Retrieve promotions matching the specified filter with pagination and sorting.

        This method automatically adds tenant filtering to ensure data isolation.

        Args:
            query_filter: MongoDB query filter to select promotions
            limit: Maximum number of promotions to return per page
            page: Page number (1-based) to retrieve
            sort: List of tuples containing field name and sort direction

        Returns:
            List of promotion documents matching the query parameters
        """
        query_filter["tenant_id"] = self.tenant_id
        query_filter["is_deleted"] = False
        logger.debug(
            f"query_filter: {query_filter} limit: {limit} page: {page} sort: {sort}"
        )
        return await self.get_list_async_with_sort_and_paging(
            query_filter, limit, page, sort
        )

    async def get_promotions_by_filter_paginated_async(
        self, query_filter: dict, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> PaginatedResult[PromotionMasterDocument]:
        """
        Retrieve promotions matching the specified filter with pagination metadata.

        This method automatically adds tenant filtering to ensure data isolation and
        returns both the data and pagination metadata.

        Args:
            query_filter: MongoDB query filter to select promotions
            limit: Maximum number of promotions to return per page
            page: Page number (1-based) to retrieve
            sort: List of tuples containing field name and sort direction

        Returns:
            PaginatedResult containing promotion documents and metadata
        """
        query_filter["tenant_id"] = self.tenant_id
        query_filter["is_deleted"] = False
        logger.debug(
            f"query_filter: {query_filter} limit: {limit} page: {page} sort: {sort}"
        )
        return await self.get_paginated_list_async(query_filter, limit, page, sort)

    async def get_active_promotions_async(
        self, current_time: datetime = None
    ) -> list[PromotionMasterDocument]:
        """
        Retrieve all currently active promotions.

        Active promotions are those that are:
        - is_active = True
        - is_deleted = False
        - start_datetime <= current_time <= end_datetime

        Args:
            current_time: The time to check against (defaults to current app time)

        Returns:
            List of active promotion documents
        """
        if current_time is None:
            current_time = get_app_time()

        query_filter = {
            "tenant_id": self.tenant_id,
            "is_active": True,
            "is_deleted": False,
            "start_datetime": {"$lte": current_time},
            "end_datetime": {"$gte": current_time},
        }
        return await self.get_list_async(query_filter)

    async def get_active_promotions_by_category_async(
        self, category_code: str, current_time: datetime = None
    ) -> list[PromotionMasterDocument]:
        """
        Retrieve active promotions that apply to a specific category.

        Args:
            category_code: The category code to filter by
            current_time: The time to check against (defaults to current app time)

        Returns:
            List of active promotion documents for the specified category
        """
        if current_time is None:
            current_time = get_app_time()

        query_filter = {
            "tenant_id": self.tenant_id,
            "is_active": True,
            "is_deleted": False,
            "start_datetime": {"$lte": current_time},
            "end_datetime": {"$gte": current_time},
            "promotion_type": "category_discount",
            "category_promo_detail.target_category_codes": category_code,
        }
        return await self.get_list_async(query_filter)

    async def get_active_promotions_by_store_async(
        self, store_code: str, current_time: datetime = None
    ) -> list[PromotionMasterDocument]:
        """
        Retrieve active promotions that apply to a specific store.

        This method returns promotions that either:
        - Have the store_code in target_store_codes, OR
        - Have an empty target_store_codes list (applies to all stores)

        Args:
            store_code: The store code to filter by
            current_time: The time to check against (defaults to current app time)

        Returns:
            List of active promotion documents for the specified store
        """
        if current_time is None:
            current_time = get_app_time()

        query_filter = {
            "tenant_id": self.tenant_id,
            "is_active": True,
            "is_deleted": False,
            "start_datetime": {"$lte": current_time},
            "end_datetime": {"$gte": current_time},
            "$or": [
                {"category_promo_detail.target_store_codes": {"$size": 0}},
                {"category_promo_detail.target_store_codes": store_code},
            ],
        }
        return await self.get_list_async(query_filter)

    async def update_promotion_async(
        self, promotion_code: str, update_data: dict
    ) -> PromotionMasterDocument:
        """
        Update specific fields of a promotion.

        Args:
            promotion_code: Unique identifier for the promotion to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            The updated promotion document
        """
        success = await self.update_one_async(
            self.__make_query_filter(promotion_code), update_data
        )
        if success:
            return await self.get_promotion_by_code_async(promotion_code)
        else:
            raise Exception(f"Failed to update promotion with code {promotion_code}")

    async def delete_promotion_async(self, promotion_code: str) -> bool:
        """
        Logically delete a promotion from the database.

        This method performs a soft delete by setting is_deleted = True.

        Args:
            promotion_code: Unique identifier for the promotion to delete

        Returns:
            True if deletion was successful
        """
        update_data = {"is_deleted": True, "updated_at": get_app_time()}
        success = await self.update_one_async(
            self.__make_query_filter(promotion_code), update_data
        )
        return success

    def __make_query_filter(self, promotion_code: str) -> dict:
        """
        Create a query filter for promotion operations based on tenant and promotion code.

        This private method ensures that all queries are scoped to the correct tenant.

        Args:
            promotion_code: Unique identifier for the promotion

        Returns:
            Dictionary containing the query filter parameters
        """
        return {
            "tenant_id": self.tenant_id,
            "promotion_code": promotion_code,
            "is_deleted": False,
        }

    def __get_shard_key(self, document: PromotionMasterDocument) -> str:
        """
        Generate a shard key for the promotion document.

        Currently uses only the tenant ID as the sharding key.

        Args:
            document: Promotion document for which to generate a shard key

        Returns:
            String representation of the shard key
        """
        keys = []
        keys.append(document.tenant_id)
        return "-".join(keys)
