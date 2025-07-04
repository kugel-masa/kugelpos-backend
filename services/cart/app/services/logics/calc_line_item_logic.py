# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.enums import RoundMethod
from app.models.documents.cart_document import CartDocument
from app.config.settings import settings
from app.enums.discount_type import DiscountType
import math
from decimal import Decimal


async def calc_line_item_async(line_item: CartDocument.CartLineItem) -> CartDocument.CartLineItem:
    """
    Calculate the amount for a cart line item including discounts.

    This function calculates the final amount for a line item by applying all
    applicable discounts. It first processes percentage-based discounts and then
    amount-based discounts, finally calculating the total line item amount.

    The calculation order is important to ensure correct discount application:
    1. Clear existing discount amounts
    2. Calculate percentage-based discounts
    3. Calculate amount-based discounts
    4. Calculate the final line item amount with all discounts applied

    Args:
        line_item: The cart line item to calculate amounts for

    Returns:
        CartDocument.CartLineItem: The updated cart line item with calculated amounts
    """
    # Clear discount amounts
    for discount in line_item.discounts:
        discount.discount_amount = 0.0

    # Calculate discount amount for DiscountPercentage first
    for discount in line_item.discounts:
        if discount.discount_type == DiscountType.DiscountPercentage.value:
            # Calculate target amount after previous discounts
            target_amount = (
                Decimal(line_item.unit_price) * Decimal(line_item.quantity)
                - sum(Decimal(discount.discount_amount) for discount in line_item.discounts)
            ) / Decimal(line_item.quantity)
            # Apply percentage discount
            discount.discount_amount = (
                float(__round(target_amount * Decimal(discount.discount_value) / Decimal("100.0"))) * line_item.quantity
            )

    # Calculate discount amount for DiscountAmount
    for discount in line_item.discounts:
        if discount.discount_type == DiscountType.DiscountAmount.value:
            discount.discount_amount = discount.discount_value

    # Calculate final amount (unit price × quantity - all discounts)
    line_item.amount = float(
        Decimal(line_item.unit_price) * Decimal(line_item.quantity)
        - sum(Decimal(discount.discount_amount) for discount in line_item.discounts)
    )

    return line_item


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
            return float(value.to_integral_value(rounding="ROUND_FLOOR"))
        case RoundMethod.Round.value:
            return float(value.to_integral_value(rounding="ROUND_HALF_UP"))
        case RoundMethod.Ceil.value:
            return float(value.to_integral_value(rounding="ROUND_CEILING"))
    return float(value)
