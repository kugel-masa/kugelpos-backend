# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.states.abstract_state import AbstractState
from app.services.cart_service_event import CartServiceEvent as ev
from kugel_common.exceptions import EventBadSequenceException
from logging import getLogger

logger = getLogger(__name__)


class CompletedState(AbstractState):
    """
    Completed state implementation for the cart state machine.

    This state represents a cart that has completed the transaction process.
    The transaction has been finalized, receipts generated, and payments processed.
    In this state, the cart is effectively read-only, with only query operations allowed.

    This state follows the Paying state after the bill operation is performed.
    This is a terminal state, meaning no further state transitions are possible.
    """

    def __init__(self):
        """
        Initialize the completed state.
        """
        pass

    def check_event_sequence(self, service, event):
        """
        Check if the event is allowed in the completed state.

        In the completed state, only retrieval of cart information is allowed.
        No modifications to the cart are permitted as the transaction has been
        finalized.

        Args:
            service: The cart service instance
            event: Name of the event/operation to check

        Raises:
            EventBadSequenceException: If the event is not allowed in this state
        """
        allowed_events = [ev.GET_CART.value]

        if event not in allowed_events:
            message = f"Invalid event: {event} for state: CompletedState"
            raise EventBadSequenceException(message, logger)
