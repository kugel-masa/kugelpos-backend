# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from enum import Enum


class CartServiceEvent(Enum):
    """
    Enumeration of cart service events.

    This enum defines all possible events that can be processed by the cart service.
    Each value corresponds to a method name in the CartService class.
    State classes use these event names to determine which events can be processed
    in each cart state.

    Note:
    When adding a new method to CartService class, you must also add a corresponding
    event here to enable state management for that operation.
    """

    CREATE_CART = "create_cart_async"  # Event for creating a new cart
    GET_CART = "get_cart_async"  # Event for retrieving cart information
    CANCEL_TRANSACTION = "cancel_transaction_async"  # Event for cancelling the entire transaction
    ADD_ITEM_TO_CART = "add_item_to_cart_async"  # Event for adding items to the cart
    ADD_DISCOUNT_TO_LINE_ITEM_IN_CART = (
        "add_discount_to_line_item_in_cart_async"  # Event for adding discount to a line item
    )
    CANCEL_LINE_ITEM_FROM_CART = "cancel_line_item_from_cart_async"  # Event for cancelling a specific line item
    UPDATE_LINE_ITEM_QUANTITY_IN_CART = (
        "update_line_item_quantity_in_cart_async"  # Event for updating quantity of a line item
    )
    UPDATE_LINE_ITEM_UNIT_PRICE_IN_CART = (
        "update_line_item_unit_price_in_cart_async"  # Event for updating unit price of a line item
    )
    SUBTOTAL = "subtotal_async"  # Event for calculating subtotal and preparing for payment
    ADD_DISCOUNT_TO_CART = "add_discount_to_cart_async"  # Event for adding discount to the entire cart
    ADD_PAYMENT_TO_CART = "add_payment_to_cart_async"  # Event for adding payment to the cart
    BILL = "bill_async"  # Event for finalizing the transaction
    RESUME_ITEM_ENTRY = "resume_item_entry_async"  # Event for resuming item entry from paying state
