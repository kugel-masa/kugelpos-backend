# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any, Coroutine
from app.services.strategies.payments.abstract_payment import AbstractPayment
from app.models.documents.cart_document import CartDocument
from logging import getLogger

logger = getLogger(__name__)


class PaymentByCash(AbstractPayment):
    """
    Cash payment strategy implementation.

    This class implements the payment strategy for cash transactions.
    Cash payments have specific rules for handling change when the
    deposit amount exceeds the remaining balance.

    Cash is typically the default payment method and is identified
    by the payment code "01" in the system.
    """

    def __init__(self, payment_code: str) -> None:
        """
        Initialize the cash payment strategy.

        Args:
            payment_code: The payment code that identifies this payment method
        """
        super().__init__()
        self.payment_code = payment_code

    async def pay(self, cart_doc, payment_code, amount, detail):
        """
        Process a cash payment for the cart.

        Handles cash payment processing including creating payment information,
        calculating change if the customer pays more than the balance,
        updating the remaining balance, and adding the payment to the cart.

        Args:
            cart_doc: Cart document to process payment for
            payment_code: Code identifying the payment method (should match this strategy)
            amount: Cash payment amount
            detail: Optional payment details

        Returns:
            CartDocument: Updated cart document with cash payment applied
        """
        # Create payment information
        payment: CartDocument.Payment = await self.create_cart_payment_async(cart_doc, payment_code, amount, detail)

        # Calculate change
        self.update_cart_change(cart_doc, payment)

        # Update remaining balance
        self.update_cart_balance(cart_doc, payment.amount)

        # Add payment information
        cart_doc.payments.append(payment)

        return cart_doc

    def refund(self, cart_doc, payment_code, amount, detail):
        """
        Process a cash refund.

        Currently this method is a placeholder that simply logs the refund action.

        Args:
            cart_doc: Cart document to process refund for
            payment_code: Code identifying the payment method
            amount: Refund amount
            detail: Optional refund details

        Returns:
            CartDocument: Updated cart document with refund information
        """
        print("Refunding by cash")
        return cart_doc
