# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.utils.misc import get_app_time

from app.models.documents.cart_document import CartDocument
from app.api.common.schemas import (
    BaseTran,
    BaseTranLineItem,
    BaseTranPayment,
    BaseTranTax,
    BaseCart,
    BaseDiscount,
    BaseTranStaff,
    BaseTranStatus,
)

from logging import getLogger

logger = getLogger(__name__)


class SchemasTransformer:
    """
    Utility class that handles transformations between internal document models
    and API schema models.

    This class provides methods to convert database document objects into API response
    objects that follow the defined schema structure.
    """

    def __init__(self):
        pass

    def transform_discounts(self, discounts: list[CartDocument.DiscountInfo]) -> list[BaseDiscount]:
        """
        Transform discount information from internal document model to API schema model.

        Args:
            discounts: List of discount information from the cart document

        Returns:
            List of BaseDiscount objects for API responses
        """
        return_discounts: list[BaseDiscount] = []
        for discount in discounts:
            return_discount = BaseDiscount(
                discount_type=discount.discount_type,
                discount_value=discount.discount_value,
                discount_amount=discount.discount_amount,
                discount_detail=discount.detail,
            )
            return_discounts.append(return_discount)
        logger.debug(f"transform_discounts: discounts->{return_discounts}")
        return return_discounts

    def transform_line_items(self, line_items: list[CartDocument.CartLineItem]) -> list[BaseTranLineItem]:
        """
        Transform line items from internal document model to API schema model.

        Args:
            line_items: List of cart line items from the cart document

        Returns:
            List of BaseTranLineItem objects for API responses
        """
        return_line_items: list[BaseTranLineItem] = []
        for item in line_items:
            line_item = BaseTranLineItem(
                line_no=item.line_no,
                item_code=item.item_code,
                item_name=item.description,
                unit_price=item.unit_price,
                unit_price_original=item.unit_price_original,
                is_unit_price_changed=item.is_unit_price_changed,
                quantity=item.quantity,
                amount=item.amount,
                discounts=self.transform_discounts(item.discounts),
                image_urls=item.image_urls if hasattr(item, "image_urls") else [],
                is_cancelled=item.is_cancelled,
            )
            return_line_items.append(line_item)
        return return_line_items

    def transform_payments(self, payments: list[CartDocument.Payment]) -> list[BaseTranPayment]:
        """
        Transform payment information from internal document model to API schema model.

        Args:
            payments: List of payment information from the cart document

        Returns:
            List of BaseTranPayment objects for API responses
        """
        logger.debug(f"transform_payments: payments->{payments}")
        return_payments: list[BaseTranPayment] = []
        for payment in payments:
            return_payment = BaseTranPayment(
                payment_no=payment.payment_no,
                payment_code=payment.payment_code,
                payment_name=payment.description,
                payment_amount=payment.amount,
                payment_detail=payment.detail,
            )
            return_payments.append(return_payment)
        return return_payments

    def transform_taxes(self, taxes: list[CartDocument.Tax]) -> list[BaseTranTax]:
        """
        Transform tax information from internal document model to API schema model.

        Args:
            taxes: List of tax information from the cart document

        Returns:
            List of BaseTranTax objects for API responses
        """
        return_taxes: list[BaseTranTax] = []
        for tax in taxes:
            return_tax = BaseTranTax(
                tax_no=tax.tax_no,
                tax_code=tax.tax_code,
                tax_type=tax.tax_type,
                tax_name=tax.tax_name,
                tax_amount=tax.tax_amount,
                target_amount=tax.target_amount,
                target_quantity=tax.target_quantity,
            )
            return_taxes.append(return_tax)
        return return_taxes

    def transform_cart(self, cart_doc: CartDocument) -> BaseCart:
        """
        Transform a cart document to an API cart schema.

        Takes a CartDocument from the database and converts it into a BaseCart
        schema model suitable for API responses.

        Args:
            cart_doc: Cart document from the database

        Returns:
            BaseCart object for API response
        """
        return_cart = BaseCart(
            cartId=cart_doc.cart_id,
            tenant_id=cart_doc.tenant_id,
            store_code=cart_doc.store_code,
            store_name=cart_doc.store_name,
            terminal_no=cart_doc.terminal_no,
            total_amount=cart_doc.sales.total_amount,
            total_amount_with_tax=cart_doc.sales.total_amount_with_tax,
            total_discount_amount=cart_doc.sales.total_discount_amount,
            total_quantity=cart_doc.sales.total_quantity,
            subtotal_amount=cart_doc.sales.total_amount,
            deposit_amount=sum([payment.deposit_amount for payment in cart_doc.payments]),
            change_amount=cart_doc.sales.change_amount,
            stamp_duty_amount=cart_doc.sales.stamp_duty_amount,
            balance_amount=cart_doc.balance_amount,
            receipt_no=cart_doc.receipt_no,
            transaction_no=cart_doc.transaction_no,
            transaction_type=cart_doc.transaction_type,
            cart_status=cart_doc.status,
            line_items=self.transform_line_items(cart_doc.line_items),
            payments=self.transform_payments(cart_doc.payments),
            taxes=self.transform_taxes(cart_doc.taxes),
            subtotal_discounts=self.transform_discounts(cart_doc.subtotal_discounts),
            receipt_text=cart_doc.receipt_text,
            journal_text=cart_doc.journal_text,
            staff=BaseTranStaff(id=cart_doc.staff.id, name=cart_doc.staff.name),
        )
        return return_cart

    def transform_tran(self, tranlog: BaseTransaction) -> BaseTran:
        """
        Transform a transaction document to an API transaction schema.

        Takes a BaseTransaction from the database and converts it into a BaseTran
        schema model suitable for API responses.

        Args:
            tranlog: Transaction document from the database

        Returns:
            BaseTran object for API response
        """
        logger.debug(f"transform_tran: base_tran->{tranlog}")

        return_tran = BaseTran(
            tenant_id=tranlog.tenant_id,
            store_code=tranlog.store_code,
            store_name=tranlog.store_name,
            terminal_no=tranlog.terminal_no,
            total_amount=tranlog.sales.total_amount_with_tax,
            total_amount_with_tax=tranlog.sales.total_amount_with_tax,
            total_discount_amount=tranlog.sales.total_discount_amount,
            total_quantity=tranlog.sales.total_quantity,
            subtotal_amount=tranlog.sales.total_amount,
            deposit_amount=sum([payment.deposit_amount for payment in tranlog.payments]),
            change_amount=tranlog.sales.change_amount,
            stamp_duty_amount=tranlog.sales.stamp_duty_amount,
            receipt_no=tranlog.receipt_no,
            transaction_no=tranlog.transaction_no,
            transaction_type=tranlog.transaction_type,
            business_date=tranlog.business_date,
            generate_date_time=tranlog.generate_date_time,
            line_items=self.transform_line_items(tranlog.line_items),
            payments=self.transform_payments(tranlog.payments),
            taxes=self.transform_taxes(tranlog.taxes),
            subtotal_discounts=self.transform_discounts(tranlog.subtotal_discounts),
            receipt_text=tranlog.receipt_text,
            journal_text=tranlog.journal_text,
            staff=BaseTranStaff(id=tranlog.staff.id, name=tranlog.staff.name),
            status=BaseTranStatus(
                is_cancelled=tranlog.sales.is_cancelled,
                is_refunded=tranlog.is_refunded,
                is_voided=tranlog.is_voided,
            ),
        )
        return return_tran
