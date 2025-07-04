# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.strategies.sales_promo.abstract_sales_promo import AbstractSalesPromo


class SalesPromoSample(AbstractSalesPromo):
    """
    Sample implementation of a sales promotion strategy.

    This class provides a simple demonstration implementation of the AbstractSalesPromo
    interface. In a real application, this would contain actual promotion logic
    such as percentage discounts, fixed amount discounts, buy-one-get-one offers, etc.
    """

    def __init__(self, sales_promo_code: str) -> None:
        """
        Initialize the sales promotion sample with a specific promotion code.

        Args:
            sales_promo_code: The code that identifies this promotion type
        """
        super().__init__()
        self.sales_promo_code = sales_promo_code

    def apply(self, cart_doc, sales_promo_code, value):
        """
        Apply the sample sales promotion to a cart.

        This sample implementation just prints information about the promotion
        being applied and returns the cart document unchanged. In a real
        implementation, this method would modify the cart by applying
        the specified promotion.

        Args:
            cart_doc: The cart document to apply the promotion to
            sales_promo_code: The promotion code identifying the type of promotion
            value: The promotion value (e.g., discount amount or percentage)

        Returns:
            The cart document (unchanged in this sample implementation)
        """
        print(f"Applying sales promo sample. sales_promo_code: {sales_promo_code}, value: {value}")
        return cart_doc
