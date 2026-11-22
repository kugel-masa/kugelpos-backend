# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from abc import ABC, abstractmethod
from typing import Optional
from logging import getLogger
from app.models.documents.cart_document import CartDocument
from app.models.documents.payment_master_document import PaymentMasterDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.repositories.payment_master_web_repository import PaymentMasterWebRepository
from kugel_common.exceptions import RepositoryException
from app.exceptions import (
    BalanceZeroException,
    BalanceMinusException,
    DepositOverException,
    PaymentLimitExceededException,
)

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
    async def pay(
        self, cart_doc: CartDocument, payment_code: str, amount: float, detail: str = None, **kwargs
    ) -> CartDocument:
        """
        Process a payment for the cart.

        This method must be implemented by concrete payment strategies to handle
        the specific payment method's processing rules.

        To settle the payment as its payment master says (deposit over the
        balance, change, limit), call settle_payment_async(). The lower-level
        helpers below apply none of the master's settings.

        The caller passes the payment's variant (issue #311) as the keyword
        arguments ``variant_code``, ``variant_name`` and ``builtin_description``,
        decided before any strategy is called. An implementation passes them on
        to settle_payment_async(), or refuses the payment if it cannot record
        them; the caller checks that the lines it added carry the variant.

        Callers may pass keyword arguments beyond these parameters to describe
        the payment further. Implementations must accept them. One that does not
        change what is settled may be ignored; one carrying a value the
        implementation cannot honour must refuse the payment, not be dropped.

        Args:
            cart_doc: Cart document to process payment for
            payment_code: Code identifying the payment method
            amount: Payment amount
            detail: Optional payment details (e.g., credit card info)
            **kwargs: Further payment attributes from the caller (see above)

        Returns:
            CartDocument: Updated cart document with payment applied

        Raises:
            Various exceptions: For payment validation errors
        """
        pass

    @abstractmethod
    async def refund(
        self, cart_doc: CartDocument, payment_code: str, amount: float, detail: str = None, **kwargs
    ) -> CartDocument:
        """
        Process a refund for the cart.

        This method must be implemented by concrete payment strategies to handle
        the specific payment method's refund rules.

        As with pay(), callers may pass further keyword arguments, under the
        same rule.

        Args:
            cart_doc: Cart document to process refund for
            payment_code: Code identifying the payment method
            amount: Refund amount
            detail: Optional refund details
            **kwargs: Further refund attributes from the caller (see pay())

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

    async def settle_payment_async(
        self,
        cart_doc: CartDocument,
        payment_code: str,
        amount: float,
        detail: str = None,
        *,
        variant_code: Optional[str] = None,
        variant_name: Optional[str] = None,
        builtin_description: Optional[str] = None,
    ) -> CartDocument:
        """
        Settle a payment on the cart as its payment master says.

        The master decides what happens to a deposit above the balance:

        - ``can_deposit_over`` false: the payment is refused (DepositOverException).
        - ``can_deposit_over`` true: the payment covers the balance. The excess
          becomes change when ``can_change`` is true; otherwise it stays on the
          line as deposit and no change is given.

        A positive ``limit_amount`` caps what the method covers in the cart, its
        lines together; zero or less means no limit.

        Args:
            cart_doc: Cart document to settle the payment on
            payment_code: Code identifying the payment method
            amount: Amount the customer hands over
            detail: Optional payment details
            variant_code: Variant the line is recorded with, or None (issue #311)
            variant_name: The variant's name, recorded as the line's description
            builtin_description: The payment method's name at the time of the sale

        Returns:
            CartDocument: The cart with the payment added and its balance updated

        Raises:
            BalanceZeroException: If the cart balance is less than 1
            DepositOverException: If the deposit exceeds the balance and the master refuses that
            PaymentLimitExceededException: If the payment takes the method past its limit
            NotFoundException: If the payment method is not found
        """
        pay_doc = await self._get_payment_master_async(cart_doc, payment_code, amount)
        payment = self._build_cart_payment(
            cart_doc,
            pay_doc,
            amount,
            detail,
            variant_code=variant_code,
            variant_name=variant_name,
            builtin_description=builtin_description,
        )

        balance = cart_doc.balance_amount
        change_amount = 0.0
        if payment.deposit_amount > balance:
            if not pay_doc.can_deposit_over:
                message = (
                    f"Deposit amount is more than balance: deposit_amount->{payment.deposit_amount}, "
                    f"balance->{balance}, payment_code->{payment_code}"
                )
                raise DepositOverException(message, logger)
            payment.amount = balance
            if pay_doc.can_change:
                change_amount = payment.deposit_amount - balance

        self.check_payment_limit(cart_doc, pay_doc, payment.amount)

        if change_amount > 0:
            cart_doc.sales.change_amount = change_amount
        self.update_cart_balance(cart_doc, payment.amount)
        cart_doc.payments.append(payment)
        return cart_doc

    def check_payment_limit(
        self, cart_doc: CartDocument, pay_doc: PaymentMasterDocument, payment_amount: float
    ) -> None:
        """
        Refuse a payment that takes its method past the master's limit_amount.

        The method's lines in the cart count together, or a limit could be passed
        by splitting the payment. Negative lines are not counted, so that they
        cannot make room under the limit.

        Args:
            cart_doc: Cart the payment is about to be added to
            pay_doc: Payment master of the method
            payment_amount: Amount the new payment covers

        Raises:
            PaymentLimitExceededException: If the method would cover more than its limit
        """
        limit = pay_doc.limit_amount
        if limit is None or limit <= 0:
            return
        covered = sum(
            max(p.amount or 0.0, 0.0) for p in cart_doc.payments if p.payment_code == pay_doc.payment_code
        )
        if covered + max(payment_amount, 0.0) > limit:
            message = (
                f"Payment exceeds the limit of its method: payment_code->{pay_doc.payment_code}, "
                f"covered->{covered}, payment->{payment_amount}, limit->{limit}"
            )
            raise PaymentLimitExceededException(message, logger)

    async def create_cart_payment_async(
        self, cart_doc: CartDocument, payment_code: str, amount: float, detail: str
    ) -> CartDocument.Payment:
        """
        Create a payment entry for the cart.

        This helper method creates a payment object with the specified details
        after validating that there's a sufficient balance to pay. It applies
        none of the master's settings; settle_payment_async() does.

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
        pay_doc = await self._get_payment_master_async(cart_doc, payment_code, amount)
        return self._build_cart_payment(cart_doc, pay_doc, amount, detail)

    async def _get_payment_master_async(
        self, cart_doc: CartDocument, payment_code: str, amount: float
    ) -> PaymentMasterDocument:
        """Check that there is a balance to pay, then read the method's payment master."""
        if cart_doc.balance_amount < 1:
            message = f"Balance is less than 1: balance->{cart_doc.balance_amount}, amount->{amount}"
            raise BalanceZeroException(message, logger)
        return await self.__get_payment_document_async(payment_code)

    @staticmethod
    def _build_cart_payment(
        cart_doc: CartDocument,
        pay_doc: PaymentMasterDocument,
        amount: float,
        detail: str,
        *,
        variant_code: Optional[str] = None,
        variant_name: Optional[str] = None,
        builtin_description: Optional[str] = None,
    ) -> CartDocument.Payment:
        """A payment line for the whole amount handed over; the caller settles its amount.

        A line recorded with a variant is named after the variant; the payment
        method's name is kept in ``builtin_description`` either way (issue #311).
        """
        payment = CartDocument.Payment()
        payment.payment_no = len(cart_doc.payments) + 1
        payment.payment_code = pay_doc.payment_code
        payment.description = variant_name or pay_doc.description
        payment.variant_code = variant_code
        payment.builtin_description = builtin_description or pay_doc.description
        payment.deposit_amount = amount
        payment.amount = amount
        payment.detail = detail
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
            NotFoundException: If the payment method is not found (raised by the repository)
            RepositoryException: If there's an error retrieving the information
        """
        try:
            return await self.payment_master_repo.get_payment_by_code_async(payment_code)
        except RepositoryException:
            # The repository already raises NotFoundException (404) for an unknown
            # code and RepositoryException for other failures. Re-wrapping them
            # turned "not found" into a repository failure, and the wrapper read a
            # base_url the repository no longer has, so every such case became a 500.
            raise
        except Exception as e:
            message = f"get_payment_document_async failed: payment_code->{payment_code}"
            raise RepositoryException(message, "payment web", logger, e) from e

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
