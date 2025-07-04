# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from abc import ABC, abstractmethod
from logging import getLogger
from app.models.documents.cart_document import CartDocument
from app.models.documents.payment_master_document import PaymentMasterDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.repositories.payment_master_web_repository import PaymentMasterWebRepository
from kugel_common.exceptions import NotFoundException, RepositoryException
from app.exceptions import BalanceZeroException, BalanceMinusException, DepositOverException

logger = getLogger(__name__)


class AbstractPayment(ABC):
    """
    Abstract base class for payment strategy implementations.

    This class is part of the Strategy design pattern implementation for payment
    processing. It defines the interface that all payment strategy classes must
    implement, along with common utility methods for payment processing.

    Payment strategies handle different payment methods (cash, credit card, etc.)
    with their specific validation and processing rules while sharing common
    payment-related functionality.
    """

    def __init__(self) -> None:
        """
        Initialize the payment strategy.
        """
        pass

    @abstractmethod
    async def pay(self, cart_doc: CartDocument, payment_code: str, amount: float, detail: str = None) -> CartDocument:
        """
        Process a payment for the cart.

        This method must be implemented by concrete payment strategies to handle
        the specific payment method's processing rules.

        Args:
            cart_doc: Cart document to process payment for
            payment_code: Code identifying the payment method
            amount: Payment amount
            detail: Optional payment details (e.g., credit card info)

        Returns:
            CartDocument: Updated cart document with payment applied

        Raises:
            Various exceptions: For payment validation errors
        """
        pass

    @abstractmethod
    async def refund(
        self, cart_doc: CartDocument, payment_code: str, amount: float, detail: str = None
    ) -> CartDocument:
        """
        Process a refund for the cart.

        This method must be implemented by concrete payment strategies to handle
        the specific payment method's refund rules.

        Args:
            cart_doc: Cart document to process refund for
            payment_code: Code identifying the payment method
            amount: Refund amount
            detail: Optional refund details

        Returns:
            CartDocument: Updated cart document with refund applied

        Raises:
            Various exceptions: For refund validation errors
        """
        pass

    async def payment_code(self) -> str:
        """
        Get the payment code for this payment strategy.

        Returns:
            str: Payment code this strategy handles
        """
        return self.payment_code

    def set_payment_master_repository(self, payment_master_repo: PaymentMasterWebRepository) -> None:
        """
        Set the payment master repository for this strategy.

        Args:
            payment_master_repo: Repository for accessing payment method information
        """
        self.payment_master_repo = payment_master_repo

    async def create_cart_payment_async(
        self, cart_doc: CartDocument, payment_code: str, amount: float, detail: str
    ) -> CartDocument.Payment:
        """
        Create a payment entry for the cart.

        This helper method creates a payment object with the specified details
        after validating that there's a sufficient balance to pay.

        Args:
            cart_doc: Cart document to create payment for
            payment_code: Code identifying the payment method
            amount: Payment amount
            detail: Optional payment details

        Returns:
            CartDocument.Payment: The created payment object

        Raises:
            BalanceZeroException: If the cart balance is less than 1
            NotFoundException: If the payment method is not found
            RepositoryException: If there's an error retrieving payment information
        """
        if cart_doc.balance_amount < 1:
            message = f"Balance is less than 1: balance->{cart_doc.balance_amount}, amount->{amount}"
            raise BalanceZeroException(message, logger)

        pay_doc = await self.__get_payment_document_async(payment_code)

        payment = CartDocument.Payment()
        payment.payment_no = len(cart_doc.payments) + 1
        payment.payment_code = pay_doc.payment_code
        payment.description = pay_doc.description
        payment.deposit_amount = amount
        payment.amount = amount
        payment.detail = detail
        # Notice: balance is not updated here. And you should update payment.amount at each payment plugin.

        logger.debug(f"payment: {payment}")

        return payment

    async def __get_payment_document_async(self, payment_code: str) -> PaymentMasterDocument:
        """
        Get the payment method document from the repository.

        Retrieves payment method details from the payment master repository
        based on the payment code.

        Args:
            payment_code: Code identifying the payment method

        Returns:
            PaymentMasterDocument: Payment method information

        Raises:
            NotFoundException: If the payment method is not found
            RepositoryException: If there's an error retrieving the information
        """
        try:
            pay_doc = await self.payment_master_repo.get_payment_by_code_async(payment_code)
            if pay_doc is None:
                message = f"PaymentMaster not found: payment_code->{payment_code}"
                raise NotFoundException(message, self.payment_master_repo.base_url, payment_code, logger)
            return pay_doc
        except Exception as e:
            message = f"get_payment_document_async failed: payment_code->{payment_code}"
            logger.error(message)
            raise RepositoryException(message, self.payment_master_repo.base_url, logger, e) from e

    def update_cart_balance(self, cart_doc: CartDocument, payment_amount: float) -> None:
        """
        Update the cart balance after a payment.

        Deducts the payment amount from the cart balance and validates that
        the resulting balance is not negative.

        Args:
            cart_doc: Cart document to update
            payment_amount: Amount to deduct from balance

        Raises:
            BalanceMinusException: If the resulting balance would be negative
        """
        cart_doc.balance_amount -= payment_amount
        if cart_doc.balance_amount < 0:
            message = f"Balance is less than 0: balance->{cart_doc.balance_amount}, payment->{payment_amount}"
            raise BalanceMinusException(message, logger)

    def check_deposit_over(self, cart_doc: CartDocument, deposit_amount: float) -> None:
        """
        Check if the deposit amount exceeds the remaining balance.

        For some payment methods, the deposit amount should not exceed the
        remaining balance. This method validates that rule.

        Args:
            cart_doc: Cart document to check
            deposit_amount: Deposit amount to validate

        Raises:
            DepositOverException: If the deposit amount exceeds the balance
        """
        if deposit_amount > cart_doc.balance_amount:
            message = f"Deposit amount is more than balance: deposit_amount->{deposit_amount}, balance->{cart_doc.balance_amount}"
            raise DepositOverException(message, logger)

    def update_cart_change(self, cart_doc: CartDocument, payment: CartDocument.Payment) -> None:
        """
        Update the cart change amount for payment methods that can give change.

        If the deposit amount exceeds the remaining balance, the difference is
        recorded as change and the payment amount is set to the balance.

        Args:
            cart_doc: Cart document to update
            payment: Payment information with deposit amount
        """
        change_amount = payment.deposit_amount - cart_doc.balance_amount
        if change_amount > 0:
            cart_doc.sales.change_amount = change_amount
            payment.amount = cart_doc.balance_amount
        else:
            payment.amount = payment.deposit_amount
