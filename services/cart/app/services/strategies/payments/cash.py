# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any, Coroutine
from app.services.strategies.payments.abstract_payment import AbstractPayment
from logging import getLogger

logger = getLogger(__name__)


class PaymentByCash(AbstractPayment):
    """
    Cash payment strategy implementation.

    This class implements the payment strategy for cash transactions.
    Whether a deposit above the balance is taken and gives change, and how much
    cash a transaction may take, are set by the payment master
    (can_deposit_over, can_change, limit_amount); cash usually allows change.

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

    async def pay(self, cart_doc, payment_code, amount, detail=None, **kwargs):
        """
        Process a cash payment for the cart.

        Settles the payment as the payment master says: change for a deposit
        above the balance, the limit, and the remaining balance.

        Args:
            cart_doc: Cart document to process payment for
            payment_code: Code identifying the payment method (should match this strategy)
            amount: Cash payment amount
            detail: Optional payment details
            **kwargs: Further payment attributes from the caller; the payment's variant
                (variant_code, variant_name, builtin_description, issue #311) is passed
                on to settle_payment_async(), the rest is unused

        Returns:
            CartDocument: Updated cart document with cash payment applied
        """
        return await self.settle_payment_async(
            cart_doc,
            payment_code,
            amount,
            detail,
            variant_code=kwargs.get("variant_code"),
            variant_name=kwargs.get("variant_name"),
            builtin_description=kwargs.get("builtin_description"),
        )

    async def refund(self, cart_doc, payment_code, amount, detail=None, **kwargs):
        """
        Process a cash refund.

        Currently this method is a placeholder that simply logs the refund action.

        Args:
            cart_doc: Cart document to process refund for
            payment_code: Code identifying the payment method
            amount: Refund amount
            detail: Optional refund details
            **kwargs: Further refund attributes from the caller; this strategy uses none

        Returns:
            CartDocument: Updated cart document with refund information
        """
        print("Refunding by cash")
        return cart_doc
