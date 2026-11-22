# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from kugel_common.exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    InvalidRequestDataException,
)
from app.models.documents.payment_master_document import PaymentMasterDocument, PaymentVariant
from app.models.repositories.payment_master_repository import PaymentMasterRepository

logger = getLogger(__name__)


class PaymentMasterService:
    """
    Service class for managing payment method master data operations.

    This service provides business logic for creating, retrieving, updating,
    and deleting payment method records in the master data database.
    Payment methods define different ways customers can pay for transactions.
    """

    def __init__(self, payment_master_repository: PaymentMasterRepository):
        """
        Initialize the PaymentMasterService with a repository.

        Args:
            payment_master_repository: Repository for payment master data operations
        """
        logger.debug(f"PaymentMasterService: {payment_master_repository}")
        self.payment_master_repository = payment_master_repository

    async def create_payment_async(
        self,
        payment_code: str,
        description: str,
        limit_amount: float,
        can_refund: bool,
        can_deposit_over: bool,
        can_change: bool,
        is_active: bool,
    ) -> PaymentMasterDocument:
        """
        Create a new payment method in the database.

        Args:
            payment_code: Unique identifier for the payment method
            description: Description of the payment method
            limit_amount: Maximum amount allowed for this payment method
            can_refund: Whether this payment method can be refunded
            can_deposit_over: Whether this payment method allows deposits exceeding the transaction amount
            can_change: Whether this payment method can provide change
            is_active: Whether this payment method is currently active

        Returns:
            Newly created PaymentMasterDocument

        Raises:
            DocumentAlreadyExistsException: If a payment method with the given code already exists
        """

        # check if payment exists
        payment = await self.payment_master_repository.get_payment_by_code(payment_code)
        if payment is not None:
            message = f"payment with payment_code {payment_code} already exists. tenant_id: {payment.tenant_id}"
            raise DocumentAlreadyExistsException(message, logger)

        payment_doc = PaymentMasterDocument()
        payment_doc.payment_code = payment_code
        payment_doc.description = description
        payment_doc.limit_amount = limit_amount
        payment_doc.can_refund = can_refund
        payment_doc.can_deposit_over = can_deposit_over
        payment_doc.can_change = can_change
        payment_doc.is_active = is_active

        payment = await self.payment_master_repository.create_payment_async(payment_doc)
        return payment

    async def get_payment_by_code(self, payment_code: str) -> PaymentMasterDocument:
        """
        Retrieve a payment method by its unique code.

        Args:
            payment_code: Unique identifier for the payment method

        Returns:
            PaymentMasterDocument with the specified code, or None if not found
        """
        payment = await self.payment_master_repository.get_payment_by_code(payment_code)
        return payment

    async def get_all_payments(self, limit: int, page: int, sort: list[tuple[str, int]]) -> list[PaymentMasterDocument]:
        """
        Retrieve all payment methods with pagination and sorting.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction (1 for ascending, -1 for descending)

        Returns:
            List of PaymentMasterDocument objects
        """
        payments_all_in_tenant = await self.payment_master_repository.get_payment_by_filter_async({}, limit, page, sort)
        return payments_all_in_tenant

    async def get_all_payments_paginated(
        self, limit: int, page: int, sort: list[tuple[str, int]]
    ) -> tuple[list[PaymentMasterDocument], int]:
        """
        Retrieve all payment methods with pagination metadata.

        Args:
            limit: Maximum number of records to return
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction

        Returns:
            Tuple of (list of PaymentMasterDocument objects, total count)
        """
        payments_all_in_tenant = await self.payment_master_repository.get_payment_by_filter_async({}, limit, page, sort)
        total_count = await self.payment_master_repository.get_payment_count_by_filter_async({})
        return payments_all_in_tenant, total_count

    async def update_payment_async(self, payment_code: str, update_data: dict) -> PaymentMasterDocument:
        """
        Update an existing payment method with new data.

        Args:
            payment_code: Unique identifier for the payment method to update
            update_data: Dictionary containing the fields to update and their new values

        Returns:
            Updated PaymentMasterDocument

        Raises:
            InvalidRequestDataException: If the payment_code in the path and update data don't match
            DocumentNotFoundException: If no payment method with the given code exists
        """
        # check if payment_code in update_data quals payment_code
        if "payment_code" in update_data and payment_code != update_data.get("payment_code"):
            message = f"PaymentMasterService.update_payment_async: payment_code->{payment_code} in the path does not match with the payment_code->{update_data.get('payment_code')} in the data"
            raise InvalidRequestDataException(message, logger)

        # check if payment_code exists
        payment = await self.payment_master_repository.get_payment_by_code(payment_code)
        if payment is None:
            message = f"PaymentMasterService.update_payment_async: payment_code->{payment_code} not found"
            raise DocumentNotFoundException(message, logger)

        # update payment
        if "payment_code" in update_data:
            del update_data["payment_code"]
        payment = await self.payment_master_repository.update_payment_async(payment_code, update_data)
        return payment

    async def delete_payment_async(self, payment_code: str) -> None:
        """
        Delete a payment method from the database.

        Args:
            payment_code: Unique identifier for the payment method to delete

        Raises:
            DocumentNotFoundException: If no payment method with the given code exists
        """
        payment = await self.payment_master_repository.get_payment_by_code(payment_code)
        if payment is None:
            message = f"PaymentMasterService.delete_payment_async: payment_code->{payment_code} not found"
            raise DocumentNotFoundException(message, logger)
        await self.payment_master_repository.delete_payment_async(payment_code)
        return None

    async def add_variant_async(
        self, payment_code: str, variant_code: str, name: str, is_active: bool = True
    ) -> PaymentVariant:
        """
        Add a variant (sub-code) to a payment method (issue #311).

        Args:
            payment_code: Code of the payment method
            variant_code: Code of the new variant, unique within the payment method
            name: Name of the variant
            is_active: Whether the variant takes new payments

        Returns:
            The added variant

        Raises:
            DocumentNotFoundException: If no payment method with the given code exists
            DocumentAlreadyExistsException: If the payment method already has a variant with this code
        """
        variant = PaymentVariant(variant_code=variant_code, name=name, is_active=is_active)
        added = await self.payment_master_repository.add_variant_async(payment_code, variant)
        if not added:
            payment = await self.payment_master_repository.get_payment_by_code(payment_code)
            if payment is None:
                message = f"PaymentMasterService.add_variant_async: payment_code->{payment_code} not found"
                raise DocumentNotFoundException(message, logger)
            message = (
                f"PaymentMasterService.add_variant_async: variant_code->{variant_code} "
                f"already exists under payment_code->{payment_code}"
            )
            raise DocumentAlreadyExistsException(message, logger)
        return await self.get_variant_async(payment_code, variant_code)

    async def get_variants_async(self, payment_code: str) -> list[PaymentVariant]:
        """
        List a payment method's variants, stopped ones included, in variant code order.

        Raises:
            DocumentNotFoundException: If no payment method with the given code exists
        """
        payment = await self.payment_master_repository.get_payment_by_code(payment_code)
        if payment is None:
            message = f"PaymentMasterService.get_variants_async: payment_code->{payment_code} not found"
            raise DocumentNotFoundException(message, logger)
        return sorted(payment.variants, key=lambda v: v.variant_code or "")

    async def get_variant_async(self, payment_code: str, variant_code: str) -> PaymentVariant:
        """
        Get one variant of a payment method.

        Raises:
            DocumentNotFoundException: If the payment method or the variant does not exist
        """
        variants = await self.get_variants_async(payment_code)
        variant = next((v for v in variants if v.variant_code == variant_code), None)
        if variant is None:
            message = (
                f"PaymentMasterService.get_variant_async: variant_code->{variant_code} "
                f"not found under payment_code->{payment_code}"
            )
            raise DocumentNotFoundException(message, logger)
        return variant

    async def update_variant_async(
        self, payment_code: str, variant_code: str, name: str, is_active: bool
    ) -> PaymentVariant:
        """
        Change a variant's name and active flag. Its code cannot change.

        Raises:
            DocumentNotFoundException: If the payment method or the variant does not exist
        """
        updated = await self.payment_master_repository.update_variant_async(payment_code, variant_code, name, is_active)
        if not updated:
            payment = await self.payment_master_repository.get_payment_by_code(payment_code)
            if payment is None:
                message = f"PaymentMasterService.update_variant_async: payment_code->{payment_code} not found"
            else:
                message = (
                    f"PaymentMasterService.update_variant_async: variant_code->{variant_code} "
                    f"not found under payment_code->{payment_code}"
                )
            raise DocumentNotFoundException(message, logger)
        return await self.get_variant_async(payment_code, variant_code)
