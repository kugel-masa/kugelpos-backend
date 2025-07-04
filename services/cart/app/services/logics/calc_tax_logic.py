# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.enums import TaxType
from kugel_common.enums import RoundMethod
from app.models.documents.cart_document import CartDocument
from app.models.repositories.tax_master_repository import TaxMasterRepository
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, ROUND_CEILING
import math


async def calc_tax_async(cart: CartDocument, tax_master_repo: TaxMasterRepository) -> CartDocument:
    """
    Calculate tax amounts for all items in the cart.

    This function calculates tax amounts for all items in the cart based on their
    tax codes. It first determines the target amount for each tax code by grouping
    items with the same tax code, then calculates the tax amount for each group
    using the corresponding tax rates from the tax master.

    Args:
        cart: Cart document containing items to calculate taxes for
        tax_master_repo: Repository for accessing tax master information

    Returns:
        CartDocument: The updated cart document with calculated tax amounts
    """
    # Set target amounts for each tax code
    cart = await __set_target_amount_for_tax_code(cart)

    # Calculate tax amounts
    return await __calc_tax(tax_master_repo, cart)


async def __set_target_amount_for_tax_code(cart: CartDocument) -> CartDocument:
    """
    Set target amounts for tax calculation by tax code.

    Groups line items by tax code and calculates the target amount for each tax code.
    The target amount is the sum of line item amounts minus allocated discounts.

    Args:
        cart: Cart document containing line items

    Returns:
        CartDocument: Cart document with updated tax information including target amounts
    """
    # Clear existing tax information
    cart.taxes = []
    # Exclude cancelled line items
    filtered_line_items = [line_item for line_item in cart.line_items if not line_item.is_cancelled]
    taxes_dict = {}

    for line_item in filtered_line_items:
        if line_item.tax_code not in taxes_dict:
            # Create new tax entry for this tax code
            new_tax = CartDocument.Tax()
            new_tax.tax_no = len(cart.taxes) + 1
            new_tax.tax_code = line_item.tax_code
            new_tax.tax_amount = 0.0
            # Calculate target amount (line item amount minus allocated discounts)
            new_tax.target_amount = float(
                Decimal(line_item.amount)
                - sum([Decimal(discount.discount_amount) for discount in line_item.discounts_allocated])
            )
            new_tax.target_quantity = line_item.quantity
            cart.taxes.append(new_tax)
            taxes_dict[line_item.tax_code] = new_tax
        else:
            # Update existing tax entry
            tax = taxes_dict[line_item.tax_code]
            # Add to target amount (line item amount minus allocated discounts)
            tax.target_amount += float(
                Decimal(line_item.amount)
                - sum([Decimal(discount.discount_amount) for discount in line_item.discounts_allocated])
            )
            tax.target_quantity += line_item.quantity

    return cart


async def __calc_tax(tax_master_repo: TaxMasterRepository, cart: CartDocument) -> CartDocument:
    """
    Calculate tax amounts for each tax entry in the cart.

    Applies the appropriate tax calculation method based on the tax type (external,
    internal, or exempt) and performs rounding according to the tax master settings.

    Args:
        tax_master_repo: Repository for accessing tax master information
        cart: Cart document with tax entries including target amounts

    Returns:
        CartDocument: Cart document with updated tax amounts
    """
    # Calculate tax for each tax entry
    for tax in cart.taxes:
        # Get tax master information for this tax code
        tax_master = await tax_master_repo.get_tax_by_code(tax.tax_code)
        tax.tax_name = tax_master.tax_name

        # Calculate tax amount based on tax type
        match tax_master.tax_type:
            case TaxType.External.value:
                # External tax: Simple percentage of target amount
                tax.tax_amount = float(Decimal(tax.target_amount) * Decimal(tax_master.rate) / Decimal(100))
                tax.tax_type = TaxType.External.value
            case TaxType.Internal.value:
                # Internal tax: Extract tax amount from target amount (target already includes tax)
                tax.tax_amount = float(
                    Decimal(tax.target_amount)
                    / (Decimal(1) + Decimal(tax_master.rate) / Decimal(100))
                    * Decimal(tax_master.rate)
                    / Decimal(100)
                )
                tax.tax_type = TaxType.Internal.value
            case TaxType.Exempt.value:
                # Tax exempt: No tax
                tax.tax_amount = 0.0
                tax.tax_type = TaxType.Exempt.value

        # Apply rounding method
        tax.tax_amount = float(__round(tax_master.round_method, Decimal(tax.tax_amount), tax_master.round_digit))

    return cart


def __round(round_method: str, value: Decimal, round_digit: int) -> float:
    """
    Round a decimal value using the specified rounding method and precision.

    Applies one of three rounding methods (floor, round, ceiling) to the specified
    number of decimal places.

    Args:
        round_method: Rounding method to use (floor, round, ceiling)
        value: Decimal value to round
        round_digit: Number of decimal places to round to

    Returns:
        float: The rounded value as a float
    """
    quantize_str = "1." + "0" * round_digit
    match round_method:
        case RoundMethod.Floor.value:
            return float(value.quantize(Decimal(quantize_str), rounding=ROUND_FLOOR))
        case RoundMethod.Round.value:
            return float(value.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP))
        case RoundMethod.Ceil.value:
            return float(value.quantize(Decimal(quantize_str), rounding=ROUND_CEILING))
    return float(value)
