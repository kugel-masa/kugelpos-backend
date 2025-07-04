# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.services.states.abstract_state import AbstractState
from app.services.cart_service_event import CartServiceEvent as ev
from kugel_common.exceptions import EventBadSequenceException
from logging import getLogger

logger = getLogger(__name__)


class PayingState(AbstractState):
    """
    Paying state implementation for the cart state machine.

    This state represents a cart that has completed item entry and is in the process
    of payment. In this state, discounts can be applied to the cart subtotal, payments
    can be processed, and the transaction can be completed (billed) or cancelled.

    This state follows the EnteringItem state after the subtotal operation is performed.
    From this state, the cart can progress to the Completed state via the bill operation
    or to the Cancelled state via cancel_transaction.
    """

    def __init__(self):
        """
        Initialize the paying state.
        """
        pass

    def check_event_sequence(self, service, event):
        """
        Check if the event is allowed in the paying state.

        This state allows operations related to payment processing, including
        applying cart-level discounts, adding payments, getting cart information,
        completing the transaction (billing), or cancelling the transaction.

        Args:
            service: The cart service instance
            event: Name of the event/operation to check

        Raises:
            EventBadSequenceException: If the event is not allowed in this state
        """
        allowed_events = [
            ev.ADD_DISCOUNT_TO_CART.value,
            ev.ADD_PAYMENT_TO_CART.value,
            ev.CANCEL_TRANSACTION.value,
            ev.BILL.value,
            ev.GET_CART.value,
            ev.RESUME_ITEM_ENTRY.value,
        ]

        if event not in allowed_events:
            message = f"Invalid event: {event} for state: PayingState"
            raise EventBadSequenceException(message, logger)
