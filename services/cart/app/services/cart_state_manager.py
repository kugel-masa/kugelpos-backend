# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.states.abstract_state import AbstractState
from app.services.states.initial_state import InitialState
from app.services.states.idle_state import IdleState
from app.services.states.entering_item_state import EnteringItemState
from app.services.states.paying_state import PayingState
from app.services.states.completed_state import CompletedState
from app.services.states.cancelled_state import CancelledState
from logging import getLogger
import inspect

from app.services.cart_service_interface import ICartService
from app.enums.cart_status import CartStatus as st

logger = getLogger(__name__)


class CartStateManager:
    """
    Manages the state transitions of a cart.

    This class implements the State design pattern to manage different states
    of a shopping cart and controls which operations are permitted in each state.
    It prevents invalid operations based on the current state of the cart and
    ensures the cart follows a proper lifecycle.
    """

    def __init__(self):
        """
        Initialize the state manager with instances of all possible states.

        Creates instances of each state class and sets the initial state.
        """
        # Create each state instance
        self.initial_state = InitialState()
        self.idle_state = IdleState()
        self.entering_item_state = EnteringItemState()
        self.paying_state = PayingState()
        self.completed_state = CompletedState()
        self.cancelled_state = CancelledState()
        # Current state instance
        self.current_state = self.initial_state

    def set_state(self, state: str):
        """
        Set the current state of the cart.

        Changes the current state based on the provided state value string.

        Args:
            state: String representing the cart status/state

        Raises:
            ValueError: If an invalid state is provided
        """
        if state == st.Initial.value:
            self.current_state = self.initial_state
        elif state == st.Idle.value:
            self.current_state = self.idle_state
        elif state == st.EnteringItem.value:
            self.current_state = self.entering_item_state
        elif state == st.Paying.value:
            self.current_state = self.paying_state
        elif state == st.Completed.value:
            self.current_state = self.completed_state
        elif state == st.Cancelled.value:
            self.current_state = self.cancelled_state
        else:
            message = f"Invalid state: {state}"
            raise ValueError(message)

    def check_event_sequence(self, service: ICartService, event: str = None):
        """
        Check if the event is allowed in the current state.

        Delegates to the current state to determine if the event can be processed.
        If no event is provided, attempts to determine the event from the calling method.

        Args:
            service: The cart service instance
            event: Optional name of the event to check (method name)

        Raises:
            Various exceptions defined in state implementations if the event is not allowed
        """
        if event is None:
            # Get the caller function name
            event = inspect.currentframe().f_back.f_code.co_name
        logger.debug(f"Checking event: {event} in state: {self.current_state.__class__.__name__}")
        self.current_state.check_event_sequence(service, event)
