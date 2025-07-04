# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.states.abstract_state import AbstractState
from app.services.cart_service_event import CartServiceEvent as ev
from kugel_common.exceptions import EventBadSequenceException
from logging import getLogger

logger = getLogger(__name__)


class InitialState(AbstractState):
    """
    Initial state implementation for the cart state machine.

    This state represents the starting point in the cart lifecycle. In this state,
    the cart has not been created yet, and only the create_cart operation is allowed.

    This is the first state in the cart state machine. After successful cart creation,
    the state will transition to the Idle state.
    """

    def __init__(self):
        """
        Initialize the initial state.
        """
        pass

    def check_event_sequence(self, service, event):
        """
        Check if the event is allowed in the initial state.

        In the initial state, only the CREATE_CART event is allowed.

        Args:
            service: The cart service instance
            event: Name of the event/operation to check

        Raises:
            EventBadSequenceException: If the event is not allowed in this state
        """
        allowed_events = [ev.CREATE_CART.value]

        if event not in allowed_events:
            message = f"Invalid event: {event} for state: InitialState"
            raise EventBadSequenceException(message, logger)
