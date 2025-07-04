# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.states.abstract_state import AbstractState
from app.services.cart_service_event import CartServiceEvent as ev
from kugel_common.exceptions import EventBadSequenceException
from logging import getLogger

logger = getLogger(__name__)


class EnteringItemState(AbstractState):
    """
    Entering Item state implementation for the cart state machine.

    This state represents a cart that contains items and is in the process of
    building the order. In this state, many operations are available including
    adding more items, applying discounts, modifying items, and preparing for payment.

    This state follows the Idle state after the first item is added to the cart.
    From this state, the cart can progress to the Paying state via the subtotal operation.
    """

    def __init__(self):
        """
        Initialize the entering item state.
        """
        pass

    def check_event_sequence(self, service, event):
        """
        Check if the event is allowed in the entering item state.

        This state allows many operations including item management, discount application,
        and preparing for payment. It is the most feature-rich state in terms of allowed
        operations.

        Args:
            service: The cart service instance
            event: Name of the event/operation to check

        Raises:
            EventBadSequenceException: If the event is not allowed in this state
        """
        allowed_events = [
            ev.ADD_ITEM_TO_CART.value,
            ev.ADD_DISCOUNT_TO_LINE_ITEM_IN_CART.value,
            ev.ADD_PAYMENT_TO_CART.value,
            ev.CANCEL_LINE_ITEM_FROM_CART.value,
            ev.UPDATE_LINE_ITEM_QUANTITY_IN_CART.value,
            ev.UPDATE_LINE_ITEM_UNIT_PRICE_IN_CART.value,
            ev.CANCEL_TRANSACTION.value,
            ev.SUBTOTAL.value,
            ev.GET_CART.value,
        ]

        if event not in allowed_events:
            message = f"Invalid event: {event} for state: EnteringItemState"
            raise EventBadSequenceException(message, logger)
