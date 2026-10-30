# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Refuse a change that would leave a line item with a negative amount.

A fixed-amount discount is checked against the line amount only when it is
added, and is then kept as a fixed amount off the whole line. Lowering the
quantity or the unit price afterwards shrinks what it is taken from: 689 x 2
with 1,000 off (accepted, 1,378 >= 1,000) becomes 689 - 1,000 = -311 once the
quantity goes to 1.

The change is refused rather than the discount re-checked or cut down, so a
discount the cashier was already given is never silently altered.
"""

import logging

from app.exceptions import AmountLessThanDiscountException
from app.models.documents.cart_document import CartDocument

logger = logging.getLogger(__name__)


def assert_line_amounts_not_negative(cart_doc: CartDocument, *, context: str) -> None:
    """
    Raise if any line item that is not cancelled has a negative amount.

    Call it after the subtotal is recalculated. Before that, a percentage
    discount still carries the amount worked out from the previous quantity
    or price, and a legitimate change would be refused. Nothing is persisted
    until the cart is cached, so raising here leaves the cart as it was.

    Args:
        cart_doc: The cart, recalculated
        context: What the request was, for the log message

    Raises:
        AmountLessThanDiscountException: A line amount is negative (402002, the
            code a line discount larger than the line already gets)
    """
    for line_item in cart_doc.line_items:
        if line_item.is_cancelled:
            continue
        if (line_item.amount or 0) < 0:
            raise AmountLessThanDiscountException(
                f"The line amount would become negative, line_no: {line_item.line_no}, "
                f"amount: {line_item.amount}, {context}",
                logger,
            )
