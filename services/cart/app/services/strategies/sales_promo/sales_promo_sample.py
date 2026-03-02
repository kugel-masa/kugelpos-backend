# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.strategies.sales_promo.abstract_sales_promo import AbstractSalesPromo


class SalesPromoSample(AbstractSalesPromo):
    """
    Sample implementation of a sales promotion strategy.

    This class provides a simple demonstration implementation of the AbstractSalesPromo
    interface. In a real application, this would contain actual promotion logic
    such as percentage discounts, fixed amount discounts, buy-one-get-one offers, etc.
    """

    async def apply(self, cart_doc):
        """
        Apply the sample sales promotion to a cart.

        This sample implementation just prints information about the promotion
        being applied and returns the cart document unchanged. In a real
        implementation, this method would modify the cart by applying
        the specified promotion.

        Args:
            cart_doc: The cart document to apply the promotion to

        Returns:
            The cart document (unchanged in this sample implementation)
        """
        print("Applying sales promo sample.")
        return cart_doc
