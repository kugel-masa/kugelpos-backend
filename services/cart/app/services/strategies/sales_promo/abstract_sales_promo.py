# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from abc import ABC, abstractmethod
from logging import getLogger

logger = getLogger(__name__)


class AbstractSalesPromo(ABC):
    """
    Abstract base class for sales promotion strategies.

    This class serves as an interface for different sales promotion implementations.
    Each promotion strategy must implement the apply method to define how
    the promotion is applied to a cart.
    """

    def __init__(self) -> None:
        """Initialize the sales promotion strategy."""
        pass

    @abstractmethod
    def apply(self, cart_doc, sales_promo_code, value):
        """
        Apply the sales promotion to a cart.

        Args:
            cart_doc: The cart document to apply the promotion to
            sales_promo_code: The promotion code identifying the type of promotion
            value: The promotion value (e.g., discount amount or percentage)

        Returns:
            Updated cart document with the promotion applied
        """
        pass

    def sales_promo_code(self) -> str:
        """
        Get the promotion code for this strategy.

        Returns:
            str: The promotion code string
        """
        return self.sales_promo_code
