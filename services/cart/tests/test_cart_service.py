"""
Unit tests for CartService.
All external dependencies (repos, tran_service, strategies) are mocked.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cart_service import CartService
from app.models.documents.cart_document import CartDocument
from app.enums.cart_status import CartStatus
from app.enums.terminal_status import TerminalStatus
from app.exceptions import (
    TerminalStatusException,
    SignInOutException,
    CartCannotCreateException,
    CartCannotSaveException,
    CartNotFoundException,
    ItemNotFoundException,
    BalanceZeroException,
    BalanceGreaterThanZeroException,
    StrategyPluginException,
)
from kugel_common.exceptions import EventBadSequenceException, NotFoundException


def _make_terminal_info(status="Opened", staff=True, tenant_id="t1", store_code="S001", terminal_no=1, terminal_id="t1-S001-1"):
    """Create a mock terminal info document."""
    ti = MagicMock()
    ti.status = status
    ti.staff = MagicMock() if staff else None
    ti.staff_id = "staff1" if staff else None
    ti.tenant_id = tenant_id
    ti.store_code = store_code
    ti.terminal_no = terminal_no
    ti.terminal_id = terminal_id
    if staff:
        ti.staff.id = "staff1"
        ti.staff.name = "Staff One"
    ti.business_date = "2025-01-01"
    ti.business_counter = 1
    ti.open_counter = 1
    return ti


def _make_cart_doc(status="Idle", cart_id="cart-001", balance=1000.0, line_items=None):
    """Create a CartDocument with sensible defaults."""
    cart = CartDocument()
    cart.cart_id = cart_id
    cart.status = status
    cart.balance_amount = balance
    cart.line_items = line_items or []
    cart.payments = []
    cart.sales = MagicMock()
    cart.sales.total_amount_with_tax = balance
    cart.sales.is_cancelled = False
    cart.masters = MagicMock()
    cart.masters.settings = []
    cart.masters.items = []
    cart.masters.taxes = []
    cart.taxes = []
    cart.subtotal_discounts = []
    cart.transaction_type = 1
    cart.store_name = "Test Store"
    cart.business_date = "2025-01-01"
    cart.user = MagicMock()
    return cart


def _build_service(terminal_info=None, cart_doc=None):
    """
    Build a CartService with fully mocked dependencies.
    Patches CartStrategyManager at construction time and installs a persistent
    patch on calc_subtotal_logic so it stays active during test execution.
    """
    if terminal_info is None:
        terminal_info = _make_terminal_info()

    cart_repo = MagicMock()
    terminal_counter_repo = MagicMock()
    settings_master_repo = MagicMock()
    tax_master_repo = MagicMock()
    item_master_repo = MagicMock()
    payment_master_repo = MagicMock()
    store_info_repo = MagicMock()
    tran_service = MagicMock()

    # Setup item_master_repo defaults
    item_master_repo.item_master_documents = []
    item_master_repo.set_item_master_documents = MagicMock()
    item_master_repo.get_item_by_code_async = AsyncMock()
    settings_master_repo.set_settings_master_documents = MagicMock()
    tax_master_repo.set_tax_master_documents = MagicMock()
    tax_master_repo.tax_master_documents = []

    # If a cart_doc is provided, set up cache retrieval
    if cart_doc is not None:
        cart_repo.get_cached_cart_async = AsyncMock(return_value=cart_doc)
    cart_repo.cache_cart_async = AsyncMock()
    cart_repo.create_cart_async = AsyncMock()
    cart_repo.delete_cart_async = AsyncMock()

    # Mock store info
    store_info = MagicMock()
    store_info.store_name = "Test Store"
    store_info_repo.get_store_info_async = AsyncMock(return_value=store_info)

    settings_master_repo.get_all_settings_async = AsyncMock(return_value=[])
    tax_master_repo.load_all_taxes = AsyncMock(return_value=[])
    tran_service.create_tranlog_async = AsyncMock(return_value=MagicMock())

    # Install persistent patch on calc_subtotal_logic (stays active for test execution)
    patcher = patch(
        "app.services.cart_service.calc_subtotal_logic"
    )
    mock_subtotal_logic = patcher.start()
    mock_subtotal_logic.calc_subtotal_async = AsyncMock(side_effect=lambda cart, repo: cart)

    # Patch CartStrategyManager to avoid file I/O
    with patch("app.services.cart_service.CartStrategyManager") as MockStrategyMgr:
        mock_strategy_instance = MagicMock()
        mock_strategy_instance.load_strategies.return_value = []
        MockStrategyMgr.return_value = mock_strategy_instance

        svc = CartService(
            terminal_info=terminal_info,
            cart_repo=cart_repo,
            terminal_counter_repo=terminal_counter_repo,
            settings_master_repo=settings_master_repo,
            tax_master_repo=tax_master_repo,
            item_master_repo=item_master_repo,
            payment_master_repo=payment_master_repo,
            store_info_repo=store_info_repo,
            tran_service=tran_service,
            cart_id="cart-001",
        )

    # Store the patcher so tests can stop it if needed; also auto-stop via finalizer
    svc._subtotal_patcher = patcher

    return svc


class TestCartServiceCreateCart:
    """Tests for create_cart_async."""

    @pytest.mark.asyncio
    async def test_create_cart_success(self):
        """Successfully create a cart when terminal is opened and staff signed in."""
        svc = _build_service()
        new_cart = _make_cart_doc(status="Initial", cart_id="new-cart-123")
        svc.cart_repo.create_cart_async = AsyncMock(return_value=new_cart)

        result = await svc.create_cart_async(
            terminal_id="t1-S001-1",
            transaction_type=1,
            user_id="user1",
            user_name="User One",
        )
        assert result == "new-cart-123"
        svc.cart_repo.create_cart_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_cart_terminal_not_opened(self):
        """Should raise TerminalStatusException when terminal is not opened."""
        ti = _make_terminal_info(status=TerminalStatus.Closed.value)
        svc = _build_service(terminal_info=ti)

        with pytest.raises(TerminalStatusException):
            await svc.create_cart_async("t1", 1, "u1", "User")

    @pytest.mark.asyncio
    async def test_create_cart_no_staff(self):
        """Should raise SignInOutException when no staff is signed in."""
        ti = _make_terminal_info(staff=False)
        svc = _build_service(terminal_info=ti)

        with pytest.raises(SignInOutException):
            await svc.create_cart_async("t1", 1, "u1", "User")

    @pytest.mark.asyncio
    async def test_create_cart_repo_failure(self):
        """Should raise CartCannotCreateException when repo fails."""
        svc = _build_service()
        svc.cart_repo.create_cart_async = AsyncMock(return_value=None)

        with pytest.raises(CartCannotCreateException):
            await svc.create_cart_async("t1", 1, "u1", "User")


class TestCartServiceGetCart:
    """Tests for get_cart_async."""

    @pytest.mark.asyncio
    async def test_get_cart_success(self):
        """Successfully retrieve cart from cache."""
        cart = _make_cart_doc()
        svc = _build_service(cart_doc=cart)

        result = await svc.get_cart_async()
        assert result.cart_id == "cart-001"

    @pytest.mark.asyncio
    async def test_get_cart_cache_miss(self):
        """Should raise CartNotFoundException when cache lookup fails."""
        svc = _build_service()
        svc.cart_repo.get_cached_cart_async = AsyncMock(side_effect=Exception("not found"))
        # Patch send_fatal_error_notification to avoid actual calls
        with patch("app.services.cart_service.send_fatal_error_notification", new_callable=AsyncMock):
            with pytest.raises(CartNotFoundException):
                await svc.get_cart_async()


class TestCartServiceAddItem:
    """Tests for add_item_to_cart_async."""

    @pytest.mark.asyncio
    async def test_add_item_success(self):
        """Successfully add an item to the cart."""
        cart = _make_cart_doc(status="Idle")
        svc = _build_service(cart_doc=cart)
        # Set state to Idle so add_item is allowed
        svc.state_manager.set_state(CartStatus.Idle.value)

        mock_item = MagicMock()
        mock_item.item_code = "ITEM001"
        mock_item.category_code = "CAT01"
        mock_item.description = "Test Item"
        mock_item.description_short = "TI"
        mock_item.store_price = 500.0
        mock_item.unit_price = 500.0
        mock_item.tax_code = "T01"
        mock_item.is_discount_restricted = False
        svc.item_master_repo.get_item_by_code_async = AsyncMock(return_value=mock_item)

        add_list = [{"item_code": "ITEM001", "unit_price": None, "quantity": 2}]
        result = await svc.add_item_to_cart_async(add_list)
        assert len(result.line_items) == 1
        assert result.line_items[0].item_code == "ITEM001"
        assert result.line_items[0].quantity == 2

    @pytest.mark.asyncio
    async def test_add_item_not_found(self):
        """Should raise ItemNotFoundException when item code is not in master."""
        cart = _make_cart_doc(status="Idle")
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.Idle.value)
        svc.item_master_repo.get_item_by_code_async = AsyncMock(
            side_effect=NotFoundException("not found", "item_master", "BAD")
        )

        with pytest.raises(ItemNotFoundException):
            await svc.add_item_to_cart_async([{"item_code": "BAD", "unit_price": 100, "quantity": 1}])


class TestCartServiceCancelLineItem:
    """Tests for cancel_line_item_from_cart_async."""

    @pytest.mark.asyncio
    async def test_cancel_line_item_success(self):
        """Successfully cancel a line item."""
        line_item = MagicMock()
        line_item.is_cancelled = False
        cart = _make_cart_doc(status="EnteringItem", line_items=[line_item])
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.EnteringItem.value)

        result = await svc.cancel_line_item_from_cart_async(line_no=1)
        assert result.line_items[0].is_cancelled is True


class TestCartServiceSubtotal:
    """Tests for subtotal_async."""

    @pytest.mark.asyncio
    async def test_subtotal_success(self):
        """Successfully calculate subtotal and move to Paying state."""
        cart = _make_cart_doc(status="EnteringItem")
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.EnteringItem.value)

        result = await svc.subtotal_async()
        assert result is not None
        # Verify cache was called with Paying status
        svc.cart_repo.cache_cart_async.assert_awaited_once()


class TestCartServiceAddDiscountToLineItem:
    """Tests for add_discount_to_line_item_in_cart_async."""

    @pytest.mark.asyncio
    async def test_add_discount_to_line_item_success(self):
        """Successfully add a discount to a line item."""
        line_item = MagicMock()
        cart = _make_cart_doc(status="EnteringItem", line_items=[line_item])
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.EnteringItem.value)

        with patch("app.services.cart_service.add_discount_to_cart_logic") as mock_logic:
            mock_logic.add_discount_to_line_item_async = AsyncMock()
            result = await svc.add_discount_to_line_item_in_cart_async(
                line_no=1, add_discount_list=[{"type": "percent", "value": 10}]
            )
            assert result is not None


class TestCartServiceAddDiscountToCart:
    """Tests for add_discount_to_cart_async."""

    @pytest.mark.asyncio
    async def test_add_discount_to_cart_success(self):
        """Successfully add a discount to the cart."""
        cart = _make_cart_doc(status="Paying")
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.Paying.value)

        with patch("app.services.cart_service.add_discount_to_cart_logic") as mock_logic:
            mock_logic.add_discount_to_cart_async = AsyncMock()
            result = await svc.add_discount_to_cart_async(
                add_discount_list=[{"type": "amount", "value": 100}]
            )
            assert result is not None


class TestCartServicePayment:
    """Tests for add_payment_to_cart_async."""

    @pytest.mark.asyncio
    async def test_add_payment_success(self):
        """Successfully add a payment."""
        cart = _make_cart_doc(status="Paying", balance=1000.0)
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.Paying.value)

        mock_pay_strategy = MagicMock()
        mock_pay_strategy.payment_code = "01"
        mock_pay_strategy.pay = AsyncMock(return_value=cart)
        svc.payment_strategies = [mock_pay_strategy]

        result = await svc.add_payment_to_cart_async(
            [{"payment_code": "01", "amount": 1000, "detail": None}]
        )
        assert result is not None
        mock_pay_strategy.pay.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_payment_balance_zero(self):
        """Should raise BalanceZeroException when balance is already 0."""
        cart = _make_cart_doc(status="Paying", balance=0.0)
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.Paying.value)
        svc.payment_strategies = []

        with pytest.raises(BalanceZeroException):
            await svc.add_payment_to_cart_async(
                [{"payment_code": "01", "amount": 100, "detail": None}]
            )

    @pytest.mark.asyncio
    async def test_add_payment_strategy_not_found(self):
        """Should raise StrategyPluginException when payment code has no strategy."""
        cart = _make_cart_doc(status="Paying", balance=1000.0)
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.Paying.value)
        svc.payment_strategies = []  # No strategies loaded

        with pytest.raises(StrategyPluginException):
            await svc.add_payment_to_cart_async(
                [{"payment_code": "99", "amount": 1000, "detail": None}]
            )


class TestCartServiceBill:
    """Tests for bill_async."""

    @pytest.mark.asyncio
    async def test_bill_success(self):
        """Successfully finalize a transaction."""
        cart = _make_cart_doc(status="Paying", balance=0.0)
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.Paying.value)

        result = await svc.bill_async()
        assert result is not None
        svc.tran_service.create_tranlog_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bill_balance_greater_than_zero(self):
        """Should raise BalanceGreaterThanZeroException when balance > 0."""
        cart = _make_cart_doc(status="Paying", balance=500.0)
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.Paying.value)

        with pytest.raises(BalanceGreaterThanZeroException):
            await svc.bill_async()


class TestCartServiceCancelTransaction:
    """Tests for cancel_transaction_async."""

    @pytest.mark.asyncio
    async def test_cancel_transaction_success(self):
        """Successfully cancel a transaction."""
        cart = _make_cart_doc(status="Idle")
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.Idle.value)

        result = await svc.cancel_transaction_async()
        assert result.sales.is_cancelled is True
        svc.tran_service.create_tranlog_async.assert_awaited_once()


class TestCartServiceResumeItemEntry:
    """Tests for resume_item_entry_async."""

    @pytest.mark.asyncio
    async def test_resume_item_entry_success(self):
        """Successfully resume item entry from paying state."""
        cart = _make_cart_doc(status="Paying")
        cart.payments = [MagicMock(), MagicMock()]
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.Paying.value)

        result = await svc.resume_item_entry_async()
        assert result.payments == []


class TestCartServiceUpdateLineItem:
    """Tests for update_line_item_quantity and update_line_item_unit_price."""

    @pytest.mark.asyncio
    async def test_update_quantity_success(self):
        """Successfully update line item quantity."""
        line_item = MagicMock()
        line_item.quantity = 1
        cart = _make_cart_doc(status="EnteringItem", line_items=[line_item])
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.EnteringItem.value)

        result = await svc.update_line_item_quantity_in_cart_async(line_no=1, quantity=5)
        assert result.line_items[0].quantity == 5

    @pytest.mark.asyncio
    async def test_update_unit_price_success(self):
        """Successfully update line item unit price."""
        line_item = MagicMock()
        line_item.unit_price = 100.0
        line_item.is_unit_price_changed = False
        cart = _make_cart_doc(status="EnteringItem", line_items=[line_item])
        svc = _build_service(cart_doc=cart)
        svc.state_manager.set_state(CartStatus.EnteringItem.value)

        result = await svc.update_line_item_unit_price_in_cart_async(line_no=1, unit_price=150.0)
        assert result.line_items[0].unit_price == 150.0
        assert result.line_items[0].is_unit_price_changed is True
        assert result.line_items[0].unit_price_original == 100.0


class TestCartServiceCacheFailure:
    """Tests for cache save/get failures."""

    @pytest.mark.asyncio
    async def test_cache_save_failure_raises_exception(self):
        """Should raise CartCannotSaveException when cache save fails."""
        svc = _build_service()
        new_cart = _make_cart_doc(status="Initial", cart_id="new-cart")
        svc.cart_repo.create_cart_async = AsyncMock(return_value=new_cart)
        svc.cart_repo.cache_cart_async = AsyncMock(side_effect=Exception("cache error"))

        with patch("app.services.cart_service.send_fatal_error_notification", new_callable=AsyncMock):
            with pytest.raises(CartCannotSaveException):
                await svc.create_cart_async("t1", 1, "u1", "User")


class TestCartServiceGetCurrentCart:
    """Tests for get_current_cart."""

    def test_get_current_cart_returns_none_initially(self):
        """current_cart should be None before any cart is loaded."""
        svc = _build_service()
        assert svc.get_current_cart() is None

    def test_get_current_cart_after_set(self):
        """current_cart should return the set cart."""
        svc = _build_service()
        mock_cart = MagicMock()
        svc.current_cart = mock_cart
        assert svc.get_current_cart() is mock_cart


class TestCartServiceApplySalesPromotions:
    """Tests for _apply_sales_promotions_async."""

    @pytest.mark.asyncio
    async def test_apply_promotions_matching_phase(self):
        """Should apply promotions matching the phase."""
        cart = _make_cart_doc()
        svc = _build_service(cart_doc=cart)

        mock_promo = MagicMock()
        mock_promo.execution_phase = "line_item"
        mock_promo.apply = AsyncMock(return_value=cart)
        svc.sales_promo_strategies = [mock_promo]

        result = await svc._apply_sales_promotions_async(cart, phase="line_item")
        mock_promo.apply.assert_awaited_once_with(cart)
        assert result is cart

    @pytest.mark.asyncio
    async def test_apply_promotions_skips_non_matching_phase(self):
        """Should skip promotions not matching the phase."""
        cart = _make_cart_doc()
        svc = _build_service(cart_doc=cart)

        mock_promo = MagicMock()
        mock_promo.execution_phase = "subtotal"
        mock_promo.apply = AsyncMock()
        svc.sales_promo_strategies = [mock_promo]

        await svc._apply_sales_promotions_async(cart, phase="line_item")
        mock_promo.apply.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_apply_promotions_continues_on_error(self):
        """Should continue processing even if a promotion raises an exception."""
        cart = _make_cart_doc()
        svc = _build_service(cart_doc=cart)

        bad_promo = MagicMock()
        bad_promo.execution_phase = "line_item"
        bad_promo.apply = AsyncMock(side_effect=Exception("promo error"))

        good_promo = MagicMock()
        good_promo.execution_phase = "line_item"
        good_promo.apply = AsyncMock(return_value=cart)

        svc.sales_promo_strategies = [bad_promo, good_promo]

        result = await svc._apply_sales_promotions_async(cart, phase="line_item")
        good_promo.apply.assert_awaited_once()
        assert result is cart
