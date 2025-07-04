# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.strategies.payments.abstract_payment import AbstractPayment
from app.models.documents.cart_document import CartDocument, CartDocument
from logging import getLogger

logger = getLogger(__name__)


class PaymentByCashless(AbstractPayment):
    """
    Cashless payment strategy implementation.

    This class implements the payment strategy for cashless transactions
    such as credit cards, debit cards, or digital payment methods.

    Cashless payments have specific validation rules, particularly that
    the payment amount cannot exceed the remaining balance (no change is given).

    This payment method is typically identified by the payment code "11" in the system.
    """

    def __init__(self, payment_code: str) -> None:
        """
        Initialize the cashless payment strategy.

        Args:
            payment_code: The payment code that identifies this payment method
        """
        super().__init__()
        self.payment_code = payment_code

    async def pay(self, cart_doc, payment_code, amount, detail):
        """
        Process a cashless payment for the cart.

        Handles cashless payment processing including creating payment information,
        validating that the payment amount doesn't exceed the balance,
        updating the remaining balance, and adding the payment to the cart.

        Args:
            cart_doc: Cart document to process payment for
            payment_code: Code identifying the payment method (should match this strategy)
            amount: Cashless payment amount
            detail: Optional payment details (e.g., card info, transaction ID)

        Returns:
            CartDocument: Updated cart document with cashless payment applied
        """
        # Create payment information
        payment: CartDocument.Payment = await self.create_cart_payment_async(cart_doc, payment_code, amount, detail)

        # Check that payment doesn't exceed balance (no change given for cashless)
        self.check_deposit_over(cart_doc, payment.deposit_amount)

        # Update remaining balance
        self.update_cart_balance(cart_doc, payment.amount)

        # Add payment information
        cart_doc.payments.append(payment)

        return cart_doc

    def refund(self, cart_doc, payment_code, amount, detail):
        """
        Process a cashless refund.

        Currently this method is a placeholder that simply logs the refund action.

        Args:
            cart_doc: Cart document to process refund for
            payment_code: Code identifying the payment method
            amount: Refund amount
            detail: Optional refund details

        Returns:
            CartDocument: Updated cart document with refund information
        """
        print("Refunding by credit")
        return cart_doc

    def payment_code(self) -> str:
        """
        Get the payment code for this cashless payment strategy.

        Returns:
            str: Payment code this strategy handles
        """
        return self.payment_code
