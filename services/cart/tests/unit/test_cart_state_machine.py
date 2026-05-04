# Copyright 2026 masa@kugel
"""Unit tests for the cart state machine.

Each `*_state.py` declares an allow-list of events. The state pattern's
contract is:
  - allowed events: `check_event_sequence` returns silently
  - any other event: raises `EventBadSequenceException`

This is THE rule that prevents callers from doing things like adding
items to a cart that's already been billed, or paying a cart that's
been cancelled. Bugs here corrupt the cart lifecycle silently — they
are very hard to catch via integration tests because each invalid
sequence requires walking the cart through prior valid states first.
"""
import pytest

from app.services.cart_service_event import CartServiceEvent as Ev
from app.services.states.cancelled_state import CancelledState
from app.services.states.completed_state import CompletedState
from app.services.states.entering_item_state import EnteringItemState
from app.services.states.idle_state import IdleState
from app.services.states.initial_state import InitialState
from app.services.states.paying_state import PayingState
from kugel_common.exceptions import EventBadSequenceException


ALL_EVENTS = [e.value for e in Ev]


# Allowed events per state — mirrors the source-of-truth in each state class.
ALLOWED_BY_STATE = {
    InitialState: {Ev.CREATE_CART.value},
    IdleState: {Ev.ADD_ITEM_TO_CART.value, Ev.GET_CART.value, Ev.CANCEL_TRANSACTION.value},
    EnteringItemState: {
        Ev.ADD_ITEM_TO_CART.value,
        Ev.ADD_DISCOUNT_TO_LINE_ITEM_IN_CART.value,
        Ev.ADD_PAYMENT_TO_CART.value,
        Ev.CANCEL_LINE_ITEM_FROM_CART.value,
        Ev.UPDATE_LINE_ITEM_QUANTITY_IN_CART.value,
        Ev.UPDATE_LINE_ITEM_UNIT_PRICE_IN_CART.value,
        Ev.CANCEL_TRANSACTION.value,
        Ev.SUBTOTAL.value,
        Ev.GET_CART.value,
    },
    PayingState: {
        Ev.ADD_DISCOUNT_TO_CART.value,
        Ev.ADD_PAYMENT_TO_CART.value,
        Ev.CANCEL_TRANSACTION.value,
        Ev.BILL.value,
        Ev.GET_CART.value,
        Ev.RESUME_ITEM_ENTRY.value,
    },
    CompletedState: {Ev.GET_CART.value},
    CancelledState: {Ev.GET_CART.value},
}


@pytest.mark.parametrize(
    "state_cls,allowed",
    list(ALLOWED_BY_STATE.items()),
    ids=lambda x: getattr(x, "__name__", str(x)),
)
class TestStateAllowsEvents:
    def test_each_allowed_event_passes(self, state_cls, allowed):
        """Every event in the state's allow-list must NOT raise."""
        state = state_cls()
        for event in allowed:
            state.check_event_sequence(service=None, event=event)  # No exception expected

    def test_disallowed_events_raise(self, state_cls, allowed):
        """Every event NOT in the allow-list must raise EventBadSequenceException."""
        state = state_cls()
        disallowed = set(ALL_EVENTS) - allowed
        for event in disallowed:
            with pytest.raises(EventBadSequenceException):
                state.check_event_sequence(service=None, event=event)


# ---------------------------------------------------------------------------
# Specific high-value transition rules — guard against regressions of bugs
# that would silently break the POS lifecycle.
# ---------------------------------------------------------------------------


def test_initial_state_only_accepts_create_cart():
    """Initial state MUST reject every event except CREATE_CART. Bug here
    would let callers, e.g., subtotal a cart that doesn't exist."""
    state = InitialState()
    state.check_event_sequence(None, Ev.CREATE_CART.value)
    for forbidden in (Ev.ADD_ITEM_TO_CART, Ev.SUBTOTAL, Ev.BILL, Ev.GET_CART):
        with pytest.raises(EventBadSequenceException):
            state.check_event_sequence(None, forbidden.value)


def test_completed_state_is_terminal_for_writes():
    """A completed cart must reject every write event. Bug here would
    let callers add items to a cart whose tranlog has already been
    published — corrupting both cart and downstream services."""
    state = CompletedState()
    state.check_event_sequence(None, Ev.GET_CART.value)
    for forbidden in (
        Ev.ADD_ITEM_TO_CART,
        Ev.ADD_DISCOUNT_TO_CART,
        Ev.ADD_DISCOUNT_TO_LINE_ITEM_IN_CART,
        Ev.ADD_PAYMENT_TO_CART,
        Ev.SUBTOTAL,
        Ev.BILL,
        Ev.CANCEL_TRANSACTION,
        Ev.RESUME_ITEM_ENTRY,
    ):
        with pytest.raises(EventBadSequenceException):
            state.check_event_sequence(None, forbidden.value)


def test_cancelled_state_is_terminal_for_writes():
    """Same contract as Completed — once cancelled, no further mutations."""
    state = CancelledState()
    state.check_event_sequence(None, Ev.GET_CART.value)
    for forbidden in (Ev.ADD_ITEM_TO_CART, Ev.SUBTOTAL, Ev.BILL, Ev.RESUME_ITEM_ENTRY):
        with pytest.raises(EventBadSequenceException):
            state.check_event_sequence(None, forbidden.value)


def test_paying_state_rejects_lineitem_modifications():
    """Once subtotal is computed, line-item mutations are forbidden —
    otherwise the displayed total would diverge from the actual sum."""
    state = PayingState()
    state.check_event_sequence(None, Ev.ADD_PAYMENT_TO_CART.value)
    state.check_event_sequence(None, Ev.RESUME_ITEM_ENTRY.value)  # legitimate path back
    for forbidden in (
        Ev.ADD_ITEM_TO_CART,
        Ev.UPDATE_LINE_ITEM_QUANTITY_IN_CART,
        Ev.UPDATE_LINE_ITEM_UNIT_PRICE_IN_CART,
        Ev.CANCEL_LINE_ITEM_FROM_CART,
        Ev.ADD_DISCOUNT_TO_LINE_ITEM_IN_CART,
    ):
        with pytest.raises(EventBadSequenceException):
            state.check_event_sequence(None, forbidden.value)


def test_idle_state_does_not_accept_subtotal():
    """An empty cart cannot proceed to payment — subtotal needs items."""
    state = IdleState()
    state.check_event_sequence(None, Ev.ADD_ITEM_TO_CART.value)
    with pytest.raises(EventBadSequenceException):
        state.check_event_sequence(None, Ev.SUBTOTAL.value)
    with pytest.raises(EventBadSequenceException):
        state.check_event_sequence(None, Ev.ADD_PAYMENT_TO_CART.value)
    with pytest.raises(EventBadSequenceException):
        state.check_event_sequence(None, Ev.BILL.value)


def test_entering_item_does_not_accept_bill_directly():
    """Cart must transition through SUBTOTAL → PAYING before BILL.
    Bug here would let unbilled-but-paid carts complete."""
    state = EnteringItemState()
    state.check_event_sequence(None, Ev.SUBTOTAL.value)  # legitimate next step
    with pytest.raises(EventBadSequenceException):
        state.check_event_sequence(None, Ev.BILL.value)
    with pytest.raises(EventBadSequenceException):
        state.check_event_sequence(None, Ev.ADD_DISCOUNT_TO_CART.value)
    with pytest.raises(EventBadSequenceException):
        state.check_event_sequence(None, Ev.RESUME_ITEM_ENTRY.value)
