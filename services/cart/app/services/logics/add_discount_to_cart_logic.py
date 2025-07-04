# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

logger = getLogger(__name__)

from typing import Any
import math
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, ROUND_CEILING

from kugel_common.exceptions import ServiceException
from app.exceptions import (
    AmountLessThanDiscountException,
    BalanceLessThanDiscountException,
    DiscountAllocationException,
    DiscountRestrictionException,
)
from kugel_common.enums import RoundMethod
from app.models.documents.cart_document import CartDocument
from app.enums.discount_type import DiscountType
from app.config.settings import settings


async def add_discount_to_line_item_async(line_item: CartDocument.CartLineItem, discounts: list[dict[str, Any]]):
    """
    Add discounts to a line item in the cart.

    This function applies discounts to a specific line item. It first checks if
    discounts are allowed for the item, clears any existing discounts, and then
    adds the new discount information.

    Args:
        line_item: The line item to apply discounts to
        discounts: A list of discount dictionaries, each containing:
            - discount_type: Type of discount (amount or percentage)
            - discount_value: Value of discount
            - discount_detail: Additional information about the discount

    Raises:
        DiscountRestrictionException: If the line item does not allow discounts
        AmountLessThanDiscountException: If the discount amount exceeds the item amount
        ServiceException: If the discount type or value is invalid
    """
    # Check if discount is restricted
    if line_item.is_discount_restricted:
        message = f"Discount is restricted, line_no: {line_item.line_no}"
        raise DiscountRestrictionException(message, logger)

    # Clear existing discount information
    line_item.discounts = []

    # Add discounts
    for discount in discounts:
        # Validate discount
        discount_type = discount["discount_type"]
        discount_value = discount["discount_value"]
        discount_detail = discount["discount_detail"]
        if discount_type == DiscountType.DiscountAmount.value:
            if line_item.amount < discount_value:
                message = f"The amount is less than the discount value, line_no: {line_item.line_no}, amount: {line_item.amount}, discount_value: {discount_value}"
                raise AmountLessThanDiscountException(message, logger)
        elif discount_type == DiscountType.DiscountPercentage.value:
            if discount_value > 100 or discount_value < 0:
                message = f"Invalid discount percentage: {discount_value}"
                raise ServiceException(message, logger)
        else:
            message = f"Invalid discount type discount: {discount}"
            raise ServiceException(message, logger)

        # Add discount information
        line_item.discounts.append(
            CartDocument.DiscountInfo(
                seq_no=len(line_item.discounts) + 1,
                discount_type=discount_type,
                discount_value=discount_value,
                detail=discount_detail,
            )
        )

    logger.debug(f"AddDiscount-> line_item:{line_item}")
    return


async def add_discount_to_cart_async(cart_doc: CartDocument, add_discount_list: list[dict[str, Any]]):
    """
    Add discounts to the entire cart (subtotal).

    This function applies discounts to the cart subtotal. It clears existing discounts,
    adds new discount information, calculates the discount amounts, and then
    allocates those discounts proportionally across eligible line items.

    Args:
        cart_doc: The cart document to apply discounts to
        add_discount_list: A list of discount dictionaries, each containing:
            - discount_type: Type of discount (amount or percentage)
            - discount_value: Value of discount
            - discount_detail: Additional information about the discount

    Raises:
        BalanceLessThanDiscountException: If the discount amount exceeds the cart balance
        ServiceException: If the discount type is invalid
        DiscountAllocationException: If the discount allocation fails
    """
    # Clear existing discount information
    cart_doc.subtotal_discounts = []

    # Add discounts to cart
    for add_discount in add_discount_list:
        logger.debug(f"AddDiscount-> type: {add_discount['discount_type']}, value: {add_discount['discount_value']}")
        discount_type = add_discount["discount_type"]
        discount_value = add_discount["discount_value"]
        discount_detail = add_discount["discount_detail"]
        discount_amount: float = 0.0

        # Calculate discount amount
        if discount_type == DiscountType.DiscountAmount.value:
            if cart_doc.balance_amount < discount_value:
                message = f"The balance is less than the discount value, cart_id: {cart_doc.cart_id}, balance: {cart_doc.balance_amount}, discount_value: {discount_value}"
                raise BalanceLessThanDiscountException(message, logger)
            discount_amount = discount_value
        elif discount_type == DiscountType.DiscountPercentage.value:
            target_amout = sum(
                [
                    line_item.amount
                    for line_item in cart_doc.line_items
                    if not line_item.is_cancelled and not line_item.is_discount_restricted
                ]
            )
            discount_amount = float(__round(Decimal(target_amout) * Decimal(discount_value) / Decimal(100)))
        else:
            message = f"Invalid discount type discount: {add_discount}"
            raise ServiceException(message, logger)

        # Add discount information
        cart_doc.subtotal_discounts.append(
            CartDocument.DiscountInfo(
                seq_no=len(cart_doc.subtotal_discounts) + 1,
                discount_type=discount_type,
                discount_value=discount_value,
                discount_amount=discount_amount,
                detail=discount_detail,
            )
        )

    # Allocate subtotal discounts to line items proportionally
    for discount in cart_doc.subtotal_discounts:
        for line_item in cart_doc.line_items:
            line_item.discounts_allocated = []  # Initialize
            if not line_item.is_cancelled and not line_item.is_discount_restricted:
                # Allocate discount amount proportionally by line item amount
                target_discount_amount = Decimal(discount.discount_amount)
                line_item_amout = Decimal(line_item.amount)
                sub_total_amount = Decimal(cart_doc.subtotal_amount)
                discount_amount_allocated = __round(target_discount_amount * line_item_amout / sub_total_amount)

                line_item.discounts_allocated.append(
                    CartDocument.DiscountInfo(
                        seq_no=discount.seq_no,
                        discount_type=discount.discount_type,
                        discount_value=discount.discount_value,
                        discount_amount=discount_amount_allocated,
                        detail=discount.detail,
                    )
                )

        # Add any remaining discount amount to the line item with the highest amount
        # Calculate total allocated discount amount
        discount_amount_allocated_total = sum(
            [
                sum([discount.discount_amount for discount in line_item.discounts_allocated])
                for line_item in cart_doc.line_items
            ]
        )
        diff = discount.discount_amount - discount_amount_allocated_total
        if diff > 0:
            # Sort line items by amount in descending order and add remaining amount
            sorted_line_items = sorted(cart_doc.line_items, key=lambda x: x.amount, reverse=True)
            while diff > 0:
                for line_item in sorted_line_items:
                    if not line_item.is_cancelled:
                        if diff >= line_item.quantity:
                            add_value = line_item.quantity
                        elif diff < line_item.quantity:
                            add_value = diff
                        line_item.discounts_allocated[0].discount_amount += add_value
                        diff -= add_value
                        if diff == 0:
                            break
                if diff > 0:
                    message = f"Failed to add discount, diff: {diff}"
                    raise DiscountAllocationException(message, logger)
                break
    return


def __round(value: Decimal) -> float:
    """
    Round a decimal value according to the configured rounding method.

    Uses the rounding method specified in settings to round the given decimal value.

    Args:
        value: The decimal value to round

    Returns:
        float: The rounded value as a float
    """
    match settings.ROUND_METHOD_FOR_DISCOUNT:
        case RoundMethod.Floor.value:
            return float(value.to_integral_value(rounding=ROUND_FLOOR))
        case RoundMethod.Round.value:
            return float(value.to_integral_value(rounding=ROUND_HALF_UP))
        case RoundMethod.Ceil.value:
            return float(value.to_integral_value(rounding=ROUND_CEILING))
    return float(value)
