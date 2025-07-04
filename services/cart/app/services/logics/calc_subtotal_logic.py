# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

from kugel_common.enums import TaxType
from app.models.documents.cart_document import CartDocument
from app.models.repositories.tax_master_repository import TaxMasterRepository
from app.services.logics import calc_line_item_logic
from app.services.logics import calc_tax_logic


async def calc_subtotal_async(cart_doc: CartDocument, tax_master_repo: TaxMasterRepository) -> CartDocument:
    """
    Calculate all cart totals including line items, taxes, and sales information.

    This function orchestrates the complete subtotal calculation process:
    1. Recalculates each line item amount (including discounts)
    2. Calculates tax amounts
    3. Updates sales information fields from cart properties

    The function ensures all cart amounts are correctly calculated and
    synchronized across the cart document structure.

    Args:
        cart_doc: The cart document to calculate totals for
        tax_master_repo: Repository for accessing tax master information

    Returns:
        CartDocument: The cart document with all totals calculated and updated
    """
    # Step 1: Recalculate amount for each line item
    for line_item in cart_doc.line_items:
        if not line_item.is_cancelled:
            await calc_line_item_logic.calc_line_item_async(line_item)

    # Step 2: Calculate taxes (this modifies cart_doc.taxes)
    cart_doc = await calc_tax_logic.calc_tax_async(cart_doc, tax_master_repo)

    # Step 3: Update sales information from cart properties
    cart_doc = await update_sales_info_async(cart_doc)

    return cart_doc


async def update_sales_info_async(cart_doc: CartDocument) -> CartDocument:
    """
    Update the sales information fields from cart document properties.

    This function synchronizes the sales info fields with the calculated
    properties on the cart document. This is necessary for persistence
    and backward compatibility.

    Note: With issue #193, subtotal_amount and balance_amount are now
    computed properties and don't need to be explicitly set.

    Args:
        cart_doc: The cart document to update sales info for

    Returns:
        CartDocument: The cart document with updated sales information
    """
    # Update discount amount
    cart_doc.sales.total_discount_amount = sum([discount.discount_amount for discount in cart_doc.subtotal_discounts])
    line_item_discount_total = 0.0
    for line_item in cart_doc.line_items:
        if not line_item.is_cancelled:
            for discount in line_item.discounts:
                line_item_discount_total += discount.discount_amount
    cart_doc.sales.total_discount_amount += line_item_discount_total

    # Update subtotal amount (for backward compatibility)
    cart_doc.subtotal_amount = sum(
        [line_item.amount for line_item in cart_doc.line_items if not line_item.is_cancelled]
    )

    # Update total amount (subtotal minus discounts)
    cart_doc.sales.total_amount = cart_doc.subtotal_amount - sum(
        [discount.discount_amount for discount in cart_doc.subtotal_discounts]
    )

    # Update external tax amount
    cart_doc.sales.tax_amount = sum(
        [tax.tax_amount for tax in cart_doc.taxes if tax.tax_type == TaxType.External.value]
    )

    # Update total quantity
    cart_doc.sales.total_quantity = sum(
        [line_item.quantity for line_item in cart_doc.line_items if not line_item.is_cancelled]
    )

    # Update total amount including tax
    cart_doc.sales.total_amount_with_tax = cart_doc.sales.total_amount + cart_doc.sales.tax_amount

    # Update balance amount
    cart_doc.balance_amount = cart_doc.sales.total_amount_with_tax - sum(
        [payment.amount for payment in cart_doc.payments]
    )

    return cart_doc
