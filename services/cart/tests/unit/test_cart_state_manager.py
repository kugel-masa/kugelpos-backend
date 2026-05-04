"""
Unit tests for CartStateManager and state classes.
Tests state transitions and event validation for each cart state.
"""
import pytest
from unittest.mock import MagicMock

from app.services.cart_state_manager import CartStateManager
from app.services.states.initial_state import InitialState
from app.services.states.idle_state import IdleState
from app.services.states.entering_item_state import EnteringItemState
from app.services.states.paying_state import PayingState
from app.services.states.completed_state import CompletedState
from app.services.states.cancelled_state import CancelledState
from app.enums.cart_status import CartStatus
from app.services.cart_service_event import CartServiceEvent as ev
from kugel_common.exceptions import EventBadSequenceException


class TestCartStateManager:
    """Tests for CartStateManager."""

    def setup_method(self):
        self.manager = CartStateManager()
        self.mock_service = MagicMock()

    # --- set_state tests ---

    def test_initial_state_is_default(self):
        """Default state should be InitialState."""
        assert isinstance(self.manager.current_state, InitialState)

    @pytest.mark.parametrize(
        "status_value, expected_type",
        [
            (CartStatus.Initial.value, InitialState),
            (CartStatus.Idle.value, IdleState),
            (CartStatus.EnteringItem.value, EnteringItemState),
            (CartStatus.Paying.value, PayingState),
            (CartStatus.Completed.value, CompletedState),
            (CartStatus.Cancelled.value, CancelledState),
        ],
    )
    def test_set_state_transitions(self, status_value, expected_type):
        """set_state should set the correct state object for each status."""
        self.manager.set_state(status_value)
        assert isinstance(self.manager.current_state, expected_type)

    def test_set_state_invalid_raises_value_error(self):
        """set_state with invalid status should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid state"):
            self.manager.set_state("NonExistentState")

    # --- check_event_sequence delegation ---

    def test_check_event_sequence_delegates_to_current_state(self):
        """check_event_sequence should delegate to current state's check."""
        self.manager.current_state = MagicMock()
        self.manager.check_event_sequence(self.mock_service, event="create_cart_async")
        self.manager.current_state.check_event_sequence.assert_called_once_with(
            self.mock_service, "create_cart_async"
        )

    def test_check_event_sequence_auto_detects_caller_name(self):
        """When event is None, it should use the caller function name."""
        # We test by calling from a method with a known name
        self.manager.current_state = MagicMock()
        self.manager.check_event_sequence(self.mock_service)
        # The event should be the name of this test method
        call_args = self.manager.current_state.check_event_sequence.call_args
        assert call_args[0][1] == "test_check_event_sequence_auto_detects_caller_name"


class TestInitialState:
    """Tests for InitialState event validation."""

    def setup_method(self):
        self.state = InitialState()
        self.mock_service = MagicMock()

    def test_create_cart_allowed(self):
        """create_cart_async should be allowed in InitialState."""
        self.state.check_event_sequence(self.mock_service, ev.CREATE_CART.value)

    @pytest.mark.parametrize(
        "event",
        [
            ev.GET_CART.value,
            ev.ADD_ITEM_TO_CART.value,
            ev.SUBTOTAL.value,
            ev.BILL.value,
            ev.CANCEL_TRANSACTION.value,
        ],
    )
    def test_disallowed_events_raise_exception(self, event):
        """Non-create events should raise EventBadSequenceException in InitialState."""
        with pytest.raises(EventBadSequenceException):
            self.state.check_event_sequence(self.mock_service, event)


class TestIdleState:
    """Tests for IdleState event validation."""

    def setup_method(self):
        self.state = IdleState()
        self.mock_service = MagicMock()

    @pytest.mark.parametrize(
        "event",
        [ev.ADD_ITEM_TO_CART.value, ev.GET_CART.value, ev.CANCEL_TRANSACTION.value],
    )
    def test_allowed_events(self, event):
        """add_item, get_cart, cancel_transaction should be allowed in IdleState."""
        self.state.check_event_sequence(self.mock_service, event)

    @pytest.mark.parametrize(
        "event",
        [ev.CREATE_CART.value, ev.SUBTOTAL.value, ev.BILL.value, ev.ADD_PAYMENT_TO_CART.value],
    )
    def test_disallowed_events_raise_exception(self, event):
        """Events not in idle's allowed list should raise EventBadSequenceException."""
        with pytest.raises(EventBadSequenceException):
            self.state.check_event_sequence(self.mock_service, event)


class TestEnteringItemState:
    """Tests for EnteringItemState event validation."""

    def setup_method(self):
        self.state = EnteringItemState()
        self.mock_service = MagicMock()

    @pytest.mark.parametrize(
        "event",
        [
            ev.ADD_ITEM_TO_CART.value,
            ev.ADD_DISCOUNT_TO_LINE_ITEM_IN_CART.value,
            ev.ADD_PAYMENT_TO_CART.value,
            ev.CANCEL_LINE_ITEM_FROM_CART.value,
            ev.UPDATE_LINE_ITEM_QUANTITY_IN_CART.value,
            ev.UPDATE_LINE_ITEM_UNIT_PRICE_IN_CART.value,
            ev.CANCEL_TRANSACTION.value,
            ev.SUBTOTAL.value,
            ev.GET_CART.value,
        ],
    )
    def test_allowed_events(self, event):
        """All item-entry related events should be allowed in EnteringItemState."""
        self.state.check_event_sequence(self.mock_service, event)

    @pytest.mark.parametrize(
        "event",
        [ev.CREATE_CART.value, ev.BILL.value, ev.ADD_DISCOUNT_TO_CART.value],
    )
    def test_disallowed_events_raise_exception(self, event):
        """create_cart, bill, add_discount_to_cart should not be allowed in EnteringItemState."""
        with pytest.raises(EventBadSequenceException):
            self.state.check_event_sequence(self.mock_service, event)


class TestPayingState:
    """Tests for PayingState event validation."""

    def setup_method(self):
        self.state = PayingState()
        self.mock_service = MagicMock()

    @pytest.mark.parametrize(
        "event",
        [
            ev.ADD_DISCOUNT_TO_CART.value,
            ev.ADD_PAYMENT_TO_CART.value,
            ev.CANCEL_TRANSACTION.value,
            ev.BILL.value,
            ev.GET_CART.value,
            ev.RESUME_ITEM_ENTRY.value,
        ],
    )
    def test_allowed_events(self, event):
        """Payment-related events should be allowed in PayingState."""
        self.state.check_event_sequence(self.mock_service, event)

    @pytest.mark.parametrize(
        "event",
        [ev.CREATE_CART.value, ev.ADD_ITEM_TO_CART.value, ev.SUBTOTAL.value],
    )
    def test_disallowed_events_raise_exception(self, event):
        """Item entry events should not be allowed in PayingState."""
        with pytest.raises(EventBadSequenceException):
            self.state.check_event_sequence(self.mock_service, event)


class TestCompletedState:
    """Tests for CompletedState event validation."""

    def setup_method(self):
        self.state = CompletedState()
        self.mock_service = MagicMock()

    def test_get_cart_allowed(self):
        """get_cart_async should be allowed in CompletedState."""
        self.state.check_event_sequence(self.mock_service, ev.GET_CART.value)

    @pytest.mark.parametrize(
        "event",
        [
            ev.CREATE_CART.value,
            ev.ADD_ITEM_TO_CART.value,
            ev.BILL.value,
            ev.CANCEL_TRANSACTION.value,
            ev.ADD_PAYMENT_TO_CART.value,
        ],
    )
    def test_disallowed_events_raise_exception(self, event):
        """All events except get_cart should raise in CompletedState."""
        with pytest.raises(EventBadSequenceException):
            self.state.check_event_sequence(self.mock_service, event)


class TestCancelledState:
    """Tests for CancelledState event validation."""

    def setup_method(self):
        self.state = CancelledState()
        self.mock_service = MagicMock()

    def test_get_cart_allowed(self):
        """get_cart_async should be allowed in CancelledState."""
        self.state.check_event_sequence(self.mock_service, ev.GET_CART.value)

    @pytest.mark.parametrize(
        "event",
        [
            ev.CREATE_CART.value,
            ev.ADD_ITEM_TO_CART.value,
            ev.BILL.value,
            ev.CANCEL_TRANSACTION.value,
            ev.ADD_PAYMENT_TO_CART.value,
        ],
    )
    def test_disallowed_events_raise_exception(self, event):
        """All events except get_cart should raise in CancelledState."""
        with pytest.raises(EventBadSequenceException):
            self.state.check_event_sequence(self.mock_service, event)
