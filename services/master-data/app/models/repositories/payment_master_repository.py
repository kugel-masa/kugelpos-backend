# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from app.models.documents.payment_master_document import PaymentMasterDocument
from app.config.settings import settings

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

    async def get_payment_by_code(self, payment_code: str) -> PaymentMasterDocument:
        """
        Retrieve a payment method by its unique code.

        Args:
            payment_code: Unique identifier for the payment method

        Returns:
            The matching payment method document, or None if not found
        """
        tenant_id = self.tenant_id
        filter = {"tenant_id": tenant_id, "payment_code": payment_code}
        return await self.get_one_async(filter)

    async def get_payment_by_filter_async(
        self, query_filter: dict, limit: int, page: int, sort: list[tuple[str, int]]
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
        query_filter["tenant_id"] = self.tenant_id
        logger.debug(f"query_filter: {query_filter} limit: {limit} page: {page} sort: {sort}")
        return await self.get_list_async_with_sort_and_paging(query_filter, limit, page, sort)

    async def update_payment_async(self, payment_code: str, update_data: dict) -> PaymentMasterDocument:
        """
        Update specific fields of a payment method.

        Args:
            payment_code: Unique identifier for the payment method to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            The updated payment method document
        """
        filter = {"tenant_id": self.tenant_id, "payment_code": payment_code}
        success = await self.update_one_async(filter, update_data)
        if success:
            return await self.get_payment_by_code(payment_code)
        else:
            raise Exception(f"Failed to update payment with code {payment_code}")

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

    async def delete_payment_async(self, payment_code: str) -> None:
        """
        Delete a payment method from the database.

        Args:
            payment_code: Unique identifier for the payment method to delete

        Returns:
            None
        """
        filter = {"tenant_id": self.tenant_id, "payment_code": payment_code}
        await self.delete_async(filter)

    async def get_payment_count_by_filter_async(self, query_filter: dict) -> int:
        """
        Get the count of payment methods matching the specified filter.

        Args:
            query_filter: MongoDB query filter to count payment methods

        Returns:
            Count of payment methods matching the filter
        """
        query_filter["tenant_id"] = self.tenant_id
        if self.dbcollection is None:
            await self.initialize()
        return await self.dbcollection.count_documents(query_filter)

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
