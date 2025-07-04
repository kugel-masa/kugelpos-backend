# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.models.documents.cart_document import CartDocument
from app.api.common.schemas_transformer import SchemasTransformer
from app.api.v1.schemas import Tran, Cart, TranLineItem, TranPayment, TrantTax


class SchemasTransformerV1(SchemasTransformer):
    """
    V1 API version of the schemas transformer.

    Extends the base SchemasTransformer to provide version-specific
    transformation logic for API v1 schema models.
    """

    def __init__(self):
        super().__init__()

    def transform_line_items(self, line_items: list[CartDocument.CartLineItem]) -> list[TranLineItem]:
        """
        Transform line items to v1 API schema models.

        Args:
            line_items: List of cart line items from the cart document

        Returns:
            List of v1 TranLineItem objects for API responses
        """
        return super().transform_line_items(line_items)

    def transform_payments(self, payments: list[CartDocument.Payment]) -> list[TranPayment]:
        """
        Transform payments to v1 API schema models.

        Args:
            payments: List of payment information from the cart document

        Returns:
            List of v1 TranPayment objects for API responses
        """
        return super().transform_payments(payments)

    def transform_taxes(self, taxes: list[CartDocument.Tax]) -> list[TrantTax]:
        """
        Transform taxes to v1 API schema models.

        This method extends the base tax transformation with additional
        v1-specific tax properties that aren't present in the base model.

        Args:
            taxes: List of tax information from the cart document

        Returns:
            List of v1 TrantTax objects for API responses with additional fields
        """
        return_tax = super().transform_taxes(taxes)

        # Add fields for V1 schema
        for tax in return_tax:
            tax_doc = self.__find_tax_by_no(taxes, tax.tax_no)
            tax = TrantTax(**tax.model_dump())  # Cast to CartTax from BaseCartTax
            tax.tax_code = tax_doc.tax_code
            tax.tax_target_amount = tax_doc.target_amount
            tax.tax_target_quantity = tax_doc.target_quantity

        return return_tax

    def transform_discounts(self, discounts):
        """
        Transform discounts to v1 API schema models.
        This method extends the base discount transformation to ensure
        compatibility with the v1 API schema.
        Args:
            discounts: List of discount information from the cart document
        Returns:
            List of v1 BaseDiscount objects for API responses
        """
        return super().transform_discounts(discounts)

    def transform_cart(self, cart_doc: CartDocument) -> Cart:
        """
        Transform a cart document to a v1 API cart schema.

        Args:
            cart_doc: Cart document from the database

        Returns:
            v1 Cart object for API response
        """
        return super().transform_cart(cart_doc)

    def trasform_tran(self, tranlog: BaseTransaction) -> Tran:
        """
        Transform a transaction document to a v1 API transaction schema.

        Args:
            tranlog: Transaction document from the database

        Returns:
            v1 Tran object for API response
        """
        return super().transform_tran(tranlog)

    def __find_tax_by_no(self, taxes: list[CartDocument.Tax], tax_no: int) -> CartDocument.Tax:
        """
        Helper method to find a tax entry by its tax number.

        Args:
            taxes: List of tax entries to search through
            tax_no: The tax number to search for

        Returns:
            The matching tax document or None if not found
        """
        for tax in taxes:
            if tax.tax_no == tax_no:
                return tax
        return None
