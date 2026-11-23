# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.exceptions import RepositoryException
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.utils.misc import get_app_time
from app.models.documents.payment_master_document import PaymentMasterDocument, PaymentVariant
from app.config.settings import settings
from app.models.repositories.logical_delete import alive, restore_async, soft_delete_async

logger = getLogger(__name__)


class PaymentMasterRepository(AbstractRepository[PaymentMasterDocument]):
    """
    Repository for managing payment method master data in the database.

    This class provides specific implementation for CRUD operations on payment method data,
    extending the generic functionality provided by AbstractRepository. It handles
    the configuration of different payment methods that can be used in the POS system,
    such as cash, credit card, or gift cards.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str):
        """
        Initialize a new PaymentMasterRepository instance.

        Args:
            db: MongoDB database instance
            tenant_id: Identifier for the tenant whose data this repository will manage
        """
        super().__init__(settings.DB_COLLECTION_NAME_PAYMENT_MASTER, PaymentMasterDocument, db)
        self.tenant_id = tenant_id

    async def create_payment_async(self, payment_doc: PaymentMasterDocument) -> PaymentMasterDocument:
        """
        Create a new payment method record in the database.

        This method sets the tenant ID and generates a shard key before creating the document.

        Args:
            payment_doc: Payment method document to create

        Returns:
            The created payment method document
        """
        payment_doc.tenant_id = self.tenant_id
        payment_doc.shard_key = self.__get_shard_key(payment_doc)
        success = await self.create_async(payment_doc)
        if success:
            return payment_doc
        else:
            raise Exception("Failed to create payment")

    async def get_payment_by_code(self, payment_code: str, include_deleted: bool = False) -> PaymentMasterDocument:
        """
        Retrieve a payment method by its unique code.

        Args:
            payment_code: Unique identifier for the payment method
            include_deleted: True to find a logically deleted payment method as well

        Returns:
            The matching payment method document, or None if not found
        """
        tenant_id = self.tenant_id
        filter = {"tenant_id": tenant_id, "payment_code": payment_code}
        return await self.get_one_async(alive(filter, include_deleted))

    async def get_payment_by_filter_async(
        self,
        query_filter: dict,
        limit: int,
        page: int,
        sort: list[tuple[str, int]],
        include_deleted: bool = False,
    ) -> list[PaymentMasterDocument]:
        """
        Retrieve payment methods matching the specified filter with pagination and sorting.

        This method automatically adds tenant filtering to ensure data isolation.

        Args:
            query_filter: MongoDB query filter to select payment methods
            limit: Maximum number of payment methods to return per page
            page: Page number (1-based) to retrieve
            sort: List of tuples containing field name and sort direction

        Returns:
            List of payment method documents matching the query parameters
        """
        query_filter = alive({**query_filter, "tenant_id": self.tenant_id}, include_deleted)
        logger.debug(f"query_filter: {query_filter} limit: {limit} page: {page} sort: {sort}")
        return await self.get_list_async_with_sort_and_paging(query_filter, limit, page, sort)

    async def update_payment_async(self, payment_code: str, update_data: dict) -> PaymentMasterDocument:
        """
        Update specific fields of a payment method.

        Args:
            payment_code: Unique identifier for the payment method to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            The updated payment method document, or None when no live payment
            method matched (missing, or deleted after the caller looked it up)
        """
        filter = alive({"tenant_id": self.tenant_id, "payment_code": payment_code})
        success = await self.update_one_async(filter, update_data)
        if not success:
            return None
        return await self.get_payment_by_code(payment_code)

    async def replace_payment_async(
        self, payment_code: str, new_document: PaymentMasterDocument
    ) -> PaymentMasterDocument:
        """
        Replace an existing payment method with a new document.

        Args:
            payment_code: Unique identifier for the payment method to replace
            new_document: New payment method document to replace the existing one

        Returns:
            The replaced payment method document
        """
        filter = {"tenant_id": self.tenant_id, "payment_code": payment_code}
        success = await self.replace_one_async(filter, new_document)
        if success:
            return new_document
        else:
            raise Exception(f"Failed to replace payment with code {payment_code}")

    async def delete_payment_async(self, payment_code: str, is_logical: bool = True) -> bool:
        """
        Delete a payment method from the database.

        Args:
            payment_code: Unique identifier for the payment method to delete

        Returns:
            None
        """
        filter = {"tenant_id": self.tenant_id, "payment_code": payment_code}
        if is_logical:
            return await soft_delete_async(self, filter)
        return await self.delete_async(filter)

    async def restore_payment_async(self, payment_doc: PaymentMasterDocument) -> bool:
        """
        Restore a logically deleted payment method with a new document (issue #324).

        Stamped as create stamps it. Returns False when no deleted payment method matched.
        """
        payment_doc.tenant_id = self.tenant_id
        payment_doc.shard_key = self.__get_shard_key(payment_doc)
        payment_doc.created_at = get_app_time()
        payment_doc.is_deleted = False
        return await restore_async(
            self, {"tenant_id": self.tenant_id, "payment_code": payment_doc.payment_code}, payment_doc
        )

    async def get_payment_count_by_filter_async(self, query_filter: dict, include_deleted: bool = False) -> int:
        """
        Get the count of payment methods matching the specified filter.

        Args:
            query_filter: MongoDB query filter to count payment methods

        Returns:
            Count of payment methods matching the filter
        """
        query_filter = alive({**query_filter, "tenant_id": self.tenant_id}, include_deleted)
        if self.dbcollection is None:
            await self.initialize()
        return await self.dbcollection.count_documents(query_filter)

    async def add_variant_async(self, payment_code: str, variant: PaymentVariant) -> bool:
        """
        Add a variant to a payment method, unless the method already has one with its code.

        The check and the write are one conditional update on one document, so two
        concurrent additions of the same code cannot both land.

        Args:
            payment_code: Code of the payment method the variant belongs to
            variant: The variant to add

        Returns:
            True when the variant was added; False when no payment method with this
            code exists or it already has a variant with this code
        """
        if self.dbcollection is None:
            await self.initialize()
        now = get_app_time()
        variant.created_at = now
        variant.updated_at = None
        # A deleted payment method takes no variants (issue #324)
        query_filter = alive(
            {
                "tenant_id": self.tenant_id,
                "payment_code": payment_code,
                "variants.variant_code": {"$ne": variant.variant_code},
            }
        )
        update = {"$push": {"variants": variant.model_dump()}, "$set": {"updated_at": now}}
        try:
            response = await self.dbcollection.update_one(query_filter, update, session=self.session)
        except Exception as e:
            message = (
                f"Failed to add a payment variant: payment_code->{payment_code}, variant_code->{variant.variant_code}"
            )
            raise RepositoryException(message, self.collection_name, logger, e) from e
        return response.matched_count == 1

    async def update_variant_async(self, payment_code: str, variant_code: str, name: str, is_active: bool) -> bool:
        """
        Change a variant's name and active flag.

        Args:
            payment_code: Code of the payment method the variant belongs to
            variant_code: Code of the variant to change
            name: New name of the variant
            is_active: New active flag of the variant

        Returns:
            True when the variant was found and changed; False when the payment
            method or the variant does not exist
        """
        if self.dbcollection is None:
            await self.initialize()
        now = get_app_time()
        query_filter = alive(
            {
                "tenant_id": self.tenant_id,
                "payment_code": payment_code,
                "variants.variant_code": variant_code,
            }
        )
        update = {
            "$set": {
                "variants.$.name": name,
                "variants.$.is_active": is_active,
                "variants.$.updated_at": now,
                "updated_at": now,
            }
        }
        try:
            response = await self.dbcollection.update_one(query_filter, update, session=self.session)
        except Exception as e:
            message = f"Failed to update a payment variant: payment_code->{payment_code}, variant_code->{variant_code}"
            raise RepositoryException(message, self.collection_name, logger, e) from e
        return response.matched_count == 1

    def __get_shard_key(self, payment_doc: PaymentMasterDocument) -> str:
        """
        Generate a shard key for the payment method document.

        Currently uses only the tenant ID as the sharding key.

        Args:
            payment_doc: Payment method document for which to generate a shard key

        Returns:
            String representation of the shard key
        """
        keys = []
        keys.append(payment_doc.tenant_id)
        return self.make_shard_key(keys)
