# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.states.abstract_state import AbstractState
from app.services.cart_service_event import CartServiceEvent as ev
from kugel_common.exceptions import EventBadSequenceException
from logging import getLogger

logger = getLogger(__name__)


class CancelledState(AbstractState):
    """
    Cancelled state implementation for the cart state machine.

    This state represents a cart transaction that has been cancelled.
    Similar to the completed state, this is also a terminal state where
    the cart is read-only and no modifications are allowed.

    This state can be reached from any active state (Idle, EnteringItem, Paying)
    when the cancel_transaction event occurs.
    """

    def __init__(self):
        """
        Initialize the cancelled state.
        """
        pass

    def check_event_sequence(self, service, event):
        """
        Check if the event is allowed in the cancelled state.

        In the cancelled state, only retrieval of cart information is allowed.
        No modifications to the cart are permitted as the transaction has been
        cancelled.

        Args:
            service: The cart service instance
            event: Name of the event/operation to check

        Raises:
            EventBadSequenceException: If the event is not allowed in this state
        """
        allowed_events = [ev.GET_CART.value]

        if event not in allowed_events:
            message = f"Invalid event: {event} for state: CancelledState"
            raise EventBadSequenceException(message, logger)
