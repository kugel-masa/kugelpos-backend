# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from abc import ABC, abstractmethod
from app.models.documents.cart_document import CartDocument


class ICartService(ABC):
    """
    Interface for cart service implementations.

    This abstract class defines the contract that all cart service implementations
    must fulfill. It provides a common interface for retrieving cart information
    and ensures that all implementations provide basic cart functionality.

    Note that the actual cart service implementation includes many additional methods
    beyond this minimal interface. This interface ensures backward compatibility and
    provides a base level of functionality that all implementations must support.
    """

    @abstractmethod
    def get_current_cart(self) -> CartDocument:
        """
        Get the current cart document.

        Returns:
            CartDocument: The current cart document instance
        """
        pass
