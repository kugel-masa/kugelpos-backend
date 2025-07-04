# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.states.abstract_state import AbstractState
from app.services.cart_service_event import CartServiceEvent as ev
from kugel_common.exceptions import EventBadSequenceException
from logging import getLogger

logger = getLogger(__name__)


class IdleState(AbstractState):
    """
    Idle state implementation for the cart state machine.

    This state represents a cart that has been created but has no items yet.
    From this state, the cart can either have items added to it (transitioning to
    EnteringItem state), be queried, or be cancelled.

    This is the state that follows successful cart creation from the Initial state.
    """

    def __init__(self):
        """
        Initialize the idle state.
        """
        pass

    def check_event_sequence(self, service, event):
        """
        Check if the event is allowed in the idle state.

        In the idle state, only adding items to cart, getting cart information,
        or cancelling the transaction are allowed operations.

        Args:
            service: The cart service instance
            event: Name of the event/operation to check

        Raises:
            EventBadSequenceException: If the event is not allowed in this state
        """
        allowed_events = [ev.ADD_ITEM_TO_CART.value, ev.GET_CART.value, ev.CANCEL_TRANSACTION.value]

        if event not in allowed_events:
            message = f"Invalid event: {event} for state: IdleState"
            raise EventBadSequenceException(message, logger)
