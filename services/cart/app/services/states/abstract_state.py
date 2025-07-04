# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from abc import ABC, abstractmethod
from app.services.cart_service_interface import ICartService


class AbstractState(ABC):
    """
    Abstract base class for all cart state implementations.

    This class is part of the State design pattern implementation for the cart service.
    Each concrete state class must inherit from this class and implement the
    check_event_sequence method to define which events are allowed in that state.

    State classes control the flow of operations in the cart lifecycle by validating
    that operations are performed in the correct order and preventing invalid state
    transitions.
    """

    @abstractmethod
    def check_event_sequence(self, service: ICartService, event: str):
        """
        Check if the event is allowed in the current state.

        This method validates whether the requested event (operation) can be
        performed in the current cart state. If the event is not allowed,
        an appropriate exception should be raised.

        Args:
            service: The cart service instance
            event: Name of the event/operation to check

        Raises:
            Various exceptions: If the event is not allowed in the current state
        """
        pass
