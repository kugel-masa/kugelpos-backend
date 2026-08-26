# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any, Union
from logging import getLogger

# Get logger instance
logger = getLogger(__name__)

from app.config.settings import settings
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.repositories.store_info_web_repository import StoreInfoWebRepository
from kugel_common.utils.slack_notifier import send_warning_notification, send_fatal_error_notification
from kugel_common.enums import TaxType

from app.exceptions import (
    ServiceException,
    CartCannotCreateException,
    CartCannotSaveException,
    CartNotFoundException,
    NotFoundException,
    ItemNotFoundException,
    StrategyPluginException,
    BalanceZeroException,
    BalanceMinusException,
    DepositOverException,
    BalanceGreaterThanZeroException,
    TerminalStatusException,
    SignInOutException,
    SnapshotInvalidException,
    CartPathMismatchException,
    SnapshotScopeViolationException,
    SnapshotTerminalStateException,
    SnapshotCartIdMismatchException,
    CartSizeBudgetExceededException,
)
from app.models.repositories.cart_repository import CartRepository
from app.models.repositories.cart_restore_log_repository import CartRestoreLogRepository
from app.models.repositories.terminal_counter_repository import (
    TerminalCounterRepository,
)
from app.models.repositories.tax_master_repository import TaxMasterRepository
from app.models.repositories.item_master_web_repository import ItemMasterWebRepository
from app.models.repositories.item_master_grpc_repository import ItemMasterGrpcRepository
from app.models.repositories.payment_master_web_repository import (
    PaymentMasterWebRepository,
)
from app.models.repositories.settings_master_web_repository import (
    SettingsMasterWebRepository,
)
from app.models.repositories.promotion_master_web_repository import (
    PromotionMasterWebRepository,
)
from app.models.documents.cart_document import CartDocument
from app.enums.terminal_status import TerminalStatus
from app.services import snapshot_service
from app.services.cart_service_interface import ICartService
from app.services.cart_state_manager import CartStateManager
from app.services.cart_strategy_manager import CartStrategyManager
from app.services.logics import calc_tax_logic
from app.services.logics import add_discount_to_cart_logic
from app.services.logics import calc_line_item_logic
from app.services.logics import calc_subtotal_logic
from app.services.strategies.payments.abstract_payment import AbstractPayment
from app.services.strategies.sales_promo.abstract_sales_promo import AbstractSalesPromo
from app.services.tran_service import TranService
from app.enums.cart_status import CartStatus
from app.utils.settings import get_setting_value


# Define CartService class
class CartService(ICartService):
    """
    Cart Service implementation class that manages shopping cart operations.

    This class handles all operations related to shopping carts including:
    - Creating and retrieving carts
    - Adding/modifying/removing items
    - Calculating subtotals and taxes
    - Processing payments
    - Completing transactions

    Notice:
        <*** very important ***>
        You need to add CartServiceEvent to the CartService class in cart_service_event.py
        when you add a new method to the CartService class.
    """

    # Constructor
    def __init__(
        self,
        terminal_info: TerminalInfoDocument,
        cart_repo: CartRepository,
        terminal_counter_repo: TerminalCounterRepository,
        settings_master_repo: SettingsMasterWebRepository,
        tax_master_repo: TaxMasterRepository,
        item_master_repo: Union[ItemMasterWebRepository, ItemMasterGrpcRepository],
        payment_master_repo: PaymentMasterWebRepository,
        store_info_repo: StoreInfoWebRepository,
        tran_service: TranService,
        cart_id: str = None,
        master_cache_backend=None,
        cart_restore_log_repo: CartRestoreLogRepository = None,
    ) -> None:
        """
        Initialize the CartService with necessary repositories and configurations.

        Args:
            terminal_info: Information about the current terminal
            cart_repo: Repository for cart operations
            terminal_counter_repo: Repository for terminal counter operations
            settings_master_repo: Repository for settings master data
            tax_master_repo: Repository for tax master data
            item_master_repo: Repository for item master data
            payment_master_repo: Repository for payment master data
            store_info_repo: Repository for store information
            tran_service: Transaction service for creating transaction logs
            cart_id: Optional ID of an existing cart to operate on
        """
        self.terminal_info = terminal_info
        self.cart_repo = cart_repo
        self.terminal_counter_repo = terminal_counter_repo
        self.settings_master_repo = settings_master_repo
        self.tax_master_repo = tax_master_repo
        self.item_master_repo = item_master_repo
        self.payment_master_repo = payment_master_repo
        self.store_info_repo = store_info_repo
        self.tran_service = tran_service
        self.cart_restore_log_repo = cart_restore_log_repo

        self.cart_id = cart_id
        self.current_cart = None

        # Client-carried cart phase 2 (issue #156). When armed via
        # prepare_stateless_from_snapshot, the service serves the reconstructed
        # cart and skips server-side cache reads/writes (FR-004).
        self._stateless = False
        self._snapshot_cart = None

        self.state_manager = CartStateManager()
        self.strategy_manager = CartStrategyManager()

        # Promotion master repository for fetching promotions at cart creation.
        # The shared cache backend is injected via the DI layer.
        self.promotion_master_repo = PromotionMasterWebRepository(
            tenant_id=self.terminal_info.tenant_id,
            terminal_info=self.terminal_info,
            cache_backend=master_cache_backend,
        )

        try:
            # Load sales promotion strategy plugins
            self.sales_promo_strategies: list[AbstractSalesPromo] = self.strategy_manager.load_strategies(
                "sales_promo_strategies"
            )
            # Configure each plugin with shared infrastructure
            for strategy in self.sales_promo_strategies:
                strategy.configure(
                    tenant_id=self.terminal_info.tenant_id,
                    terminal_info=self.terminal_info,
                )
            logger.debug(f"sales_promo_strategies: {self.sales_promo_strategies}")

            # Load payment strategy plugins and set payment master repository
            self.payment_strategies: list[AbstractPayment] = self.strategy_manager.load_strategies("payment_strategies")
            for payment_strategy in self.payment_strategies:
                payment_strategy.set_payment_master_repository(self.payment_master_repo)
            logger.debug(f"payment_strategies: {self.payment_strategies}")

        except Exception as e:
            message = f"Failed to load strategies: {e}"
            raise StrategyPluginException(message, logger) from e

    # Get current cart information
    def get_current_cart(self) -> CartDocument:
        """
        Get the current cart document.

        Returns:
            CartDocument: The current cart document instance
        """
        return self.current_cart

    #
    # Create a new cart and return the cart ID
    #
    def __cart_is_carried(self, carry_snapshot: bool) -> bool:
        """
        Whether this cart will be carried, and so must not be cached.

        The client says so at creation. In REQUIRED mode it does not have to:
        every mutating request from then on has to carry a snapshot, so a cached
        copy could never be read and writing one is pure waste.
        """
        if settings.CART_REQUEST_SNAPSHOT_MODE.upper() == "REQUIRED":
            return True
        return bool(carry_snapshot)

    @property
    def is_carried(self) -> bool:
        """
        Whether the client holds this cart rather than the server (issue #192).

        True both for a request that arrived carrying a snapshot and for the
        creation of a cart declared as carried, which is what the API layer needs
        to know: in either case nothing was written to the cache, so a response
        without a snapshot would leave the client with no cart at all.
        """
        return self._stateless

    async def create_cart_async(
        self,
        terminal_id: str,
        transaction_type: int,
        user_id: str,
        user_name: str,
        carry_snapshot: bool = False,
    ) -> str:
        """
        Create a new cart for a transaction.

        Creates a new cart with initial state and references to the required master data.

        Args:
            terminal_id: Unique identifier for the terminal
            transaction_type: Type of transaction (e.g., sale, return)
            user_id: ID of the user creating the cart
            user_name: Name of the user creating the cart

        Returns:
            str: The newly created cart ID

        Raises:
            TerminalStatusException: If the terminal is not in the opened state
            SignInOutException: If no staff is signed into the terminal
            CartCannotSaveException: If the cart cannot be saved
        """
        logger.debug(f"create_cart_async: terminal_id->{terminal_id}, user_id->{user_id}, user_name->{user_name}")

        # Check if the terminal is opened
        if self.terminal_info.status != TerminalStatus.Opened.value:
            message = f"Terminal is not opened. status: {self.terminal_info.status}"
            raise TerminalStatusException(message, logger)

        # Check if staff is signed in
        if self.terminal_info.staff is None:
            message = "Terminal is not signed in"
            raise SignInOutException(message, logger)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Get temporary receipt number
        reciept_no = -1

        # Get temporary transaction number
        transaction_no = -1

        # Get store name
        store_info = await self.store_info_repo.get_store_info_async()
        store_name = store_info.store_name

        # Create list to hold settings master data
        settings_master = await self.settings_master_repo.get_all_settings_async()
        # Get tax master information for this cart
        tax_master = await self.tax_master_repo.load_all_taxes()
        # Create list to hold item master information
        item_master = []

        # Get active promotions for this store
        try:
            promotion_master = await self.promotion_master_repo.get_active_promotions_by_store_async()
        except Exception as e:
            message = f"Failed to get promotion master data: {e}"
            raise CartCannotCreateException(message, logger, e) from e

        # Create new cart
        try:
            cart = await self.cart_repo.create_cart_async(
                transaction_type=transaction_type,
                user_id=user_id,
                user_name=user_name,
                store_name=store_name,
                receipt_no=reciept_no,
                transaction_no=transaction_no,
                settings_master=settings_master,
                tax_master=tax_master,
                item_master=item_master,
                promotion_master=promotion_master,
            )
            if cart is None:
                raise Exception("failed to create cart, cart is None")
        except Exception as e:
            message = f"Failed to create cart, transaction_type: {transaction_type}, user_id: {user_id}, user_name: {user_name}"
            raise CartCannotCreateException(message, logger, e) from e

        # A cart the client will carry is never written to the cache - not even
        # here (issue #192). Creation is the one request that always wrote,
        # because it has nothing to carry yet and the server could not know
        # whether the client would; that copy then sat there while the carried
        # requests moved the cart on, and a single snapshot-less request
        # continued from it, dropping everything in between and answering with a
        # correctly signed snapshot of a cart missing it.
        #
        # Not writing makes the mixture impossible rather than detectable: there
        # is no stale copy to continue from, so such a request finds no cart at
        # all (404, error 401002). Setting `_stateless` here is what the rest of
        # the service already keys off - __cache_cart_async pins the document
        # instead of writing it, and __get_cached_cart_async serves the pinned
        # one - so the response is still built from the cart just created.
        cart.carry_snapshot = self.__cart_is_carried(carry_snapshot)
        self._stateless = cart.carry_snapshot
        await self.__cache_cart_async(cart_doc=cart, cart_status=CartStatus.Idle, isNew=True)

        # Store cart ID
        self.cart_id = cart.cart_id

        # Return cart ID
        return cart.cart_id

    # Retrieve cart by cart_id
    async def get_cart_async(self) -> CartDocument:
        """
        Retrieve the current cart document.

        Gets the cart document from cache without modifying its status.

        Returns:
            CartDocument: The retrieved cart document

        Note:
            This method does not update the cart status
        """
        # Get cart information from cache
        return_cart = await self.__get_cached_cart_async(self.cart_id)
        logger.debug(f"get_cart_async: return_cart->{return_cart} status->{return_cart.status}")

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        return return_cart

    # Cancel a transaction for a cart
    async def cancel_transaction_async(
        self,
        seq: int = None,
        receipt_no: int = None,
        transaction_datetime: str = None,
        receipt_counter: int = None,
    ) -> CartDocument:
        """
        Cancel the current transaction.

        Marks the cart as cancelled and creates a transaction log entry.

        A cancellation is a finalize: it writes a transaction log and prints a
        receipt, so it consumes a number like any other transaction the terminal
        produces (issue #170). On the stateless path the terminal therefore
        stamps the same finalize context it stamps at bill; without it the
        transaction would be numbered from the server-side counters, whose
        transaction_no shares the (business_counter, transaction_no) key space
        with the carried per-open seq and can collide with a sale in the same
        open session.

        Args:
            seq: Client-carried transaction sequence (issue #156).
            receipt_no: Client-carried receipt number - the number the terminal
                printed on the cancellation receipt.
            transaction_datetime: Client-stamped transaction time (issue #156).
            receipt_counter: Client-carried running receipt counter (issue #166).

        Returns:
            CartDocument: The updated cart document with cancelled status
        """
        # A carried context without a snapshot has no signature behind it: the
        # numbers would be whatever the caller typed. Same rule as bill.
        if transaction_datetime is not None and not self._stateless:
            message = (
                f"Finalize context supplied without a signed snapshot, cart_id: {self.cart_id}. "
                "Carried numbering requires the stateless (snapshot) path."
            )
            raise SnapshotInvalidException(message, logger)

        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Process cancellation
        cart_doc.sales.is_cancelled = True

        if transaction_datetime is not None and self._stateless:
            cart_doc.seq = seq
            cart_doc.receipt_no = receipt_no
            cart_doc.receipt_counter = receipt_counter
            cart_doc.transaction_datetime = transaction_datetime
        else:
            # No carried context: the numbers come from the server-side series
            # (issue #170 gave cancel a carried path; issue #168 is about the two
            # series coexisting while DUAL mode is on).
            await self.__audit_numbering_fallback_async(self.cart_id, "cancel")

        # Create transaction log
        tranlog = await self.tran_service.create_tranlog_async(cart_doc)
        logger.debug(f"CancelTransaction-> tranlog: {tranlog}")

        # Remove cart from cache (transaction data is already saved in MongoDB)
        await self.__remove_cached_cart_async(self.cart_id)

        # Update cart status in memory for response
        cart_doc.status = CartStatus.Cancelled.value

        return cart_doc

    # Add items to the cart
    async def add_item_to_cart_async(self, add_item_list: list[dict[str, any]]) -> CartDocument:
        """
        Add one or more items to the cart.

        Retrieves item details from the item master and adds them to the cart.

        Args:
            add_item_list: List of items to add, each containing item_code, unit_price, and quantity

        Returns:
            CartDocument: The updated cart document with new items

        Raises:
            ItemNotFoundException: If an item code is not found in the item master
        """
        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Add items to cart
        for add_item in add_item_list:
            try:
                # Get item master information
                item = await self.item_master_repo.get_item_by_code_async(add_item["item_code"])
            except NotFoundException as e:
                message = f"Item not found: item_code->{add_item['item_code']}"
                raise ItemNotFoundException(message, logger, e) from e

            logger.info(f"item: {item}")
            cart_item = CartDocument.CartLineItem()
            cart_item.line_no = len(cart_doc.line_items) + 1
            cart_item.item_code = item.item_code
            cart_item.category_code = item.category_code
            cart_item.description = item.description
            cart_item.description_short = item.description_short
            unit_price = add_item["unit_price"]
            # Use store price or unit price from item master if no price is specified
            if not unit_price:
                if item.store_price:
                    unit_price = item.store_price
                else:
                    unit_price = item.unit_price
            cart_item.unit_price = unit_price
            cart_item.quantity = add_item["quantity"]
            # cart_item.amount = cart_item.unit_price * cart_item.quantity
            cart_item.tax_code = item.tax_code
            cart_item.is_discount_restricted = item.is_discount_restricted
            logger.debug(f"cart_item: {cart_item}")
            cart_doc.line_items.append(cart_item)

        # Calculate subtotal (promotions are re-evaluated inside __subtotal_async)
        cart_doc = await self.__subtotal_async(cart_doc)

        # Checked before anything is committed, so a refusal leaves the cart
        # exactly as it was and the basket stays workable (issue #200).
        self.__check_snapshot_size_budget(cart_doc)

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.EnteringItem)

        return cart_doc

    def __check_snapshot_size_budget(self, cart_doc: CartDocument) -> None:
        """
        Refuse a cart that would outgrow the snapshot the client has to send back.

        Applied to the paths that take a list from the request and append it:
        adding line items, and adding discounts to a line or to the subtotal.
        Nothing bounds how long those lists are or how often they are sent, and
        they accumulate across requests.

        Deliberately NOT applied to paying, billing, cancelling a line, or
        changing a quantity or price. Those are how a cart is brought to a
        close or made smaller, and refusing them is the deadlock this guard
        exists to prevent - a basket that can be neither completed nor
        cancelled. It also keeps a cart that is somehow already over budget
        (opened before this guard, or after the ceiling was lowered) finishable
        rather than stranded.

        What keeps those paths from growing without bound instead: a payment is
        refused once the balance reaches zero (BalanceZeroException), so the
        number of them is bounded by the amount owed; cancelling and updating
        change a line in place rather than adding one.

        The server issues the snapshot and the client presents it on the next
        mutating request, so MAX_REQUEST_BODY_BYTES bounds it - while the cart
        itself had no bound. Past that point the terminal holds an envelope it
        cannot return: every following request is answered 413, and under
        CART_REQUEST_SNAPSHOT_MODE=REQUIRED the cart can be neither completed nor
        cancelled (issue #200).

        Args:
            cart_doc: The cart as it would stand after the addition

        Raises:
            CartSizeBudgetExceededException: The snapshot would pass the budget.
        """
        size = snapshot_service.measure_envelope_bytes(cart_doc, self.terminal_info)
        if size is None:
            # No signing key, so no snapshot is issued and nothing has to carry
            # the cart back. The request-body ceiling still applies on its own.
            return
        budget = snapshot_service.snapshot_size_refuse_bytes()
        if size > budget:
            raise CartSizeBudgetExceededException(
                f"Cart {cart_doc.cart_id} would produce a {size} byte snapshot, over the {budget} byte budget "
                f"({len(cart_doc.line_items)} line items); the client could not send it back",
                logger,
            )

    async def _apply_sales_promotions_async(self, cart_doc: CartDocument, phase: str = "line_item") -> CartDocument:
        """
        Apply sales promotion strategies matching the specified execution phase.

        Iterates through all loaded sales promotion strategies and applies those
        whose execution_phase matches the given phase parameter.

        Args:
            cart_doc: The cart document to apply promotions to
            phase: Execution phase to filter plugins ('line_item' or 'subtotal')

        Returns:
            CartDocument: The cart document with promotions applied
        """
        promotions = cart_doc.masters.promotions if cart_doc.masters else []
        for sales_promo_strategy in self.sales_promo_strategies:
            if sales_promo_strategy.execution_phase != phase:
                continue
            try:
                cart_doc = await sales_promo_strategy.apply(cart_doc, promotions=promotions)
            except Exception as e:
                logger.warning(f"Failed to apply sales promotion strategy: {e}")
                continue
        return cart_doc

    # Cancel a line item in the cart
    async def cancel_line_item_from_cart_async(self, line_no: int) -> CartDocument:
        """
        Cancel (remove) a line item from the cart.

        Marks the specified line item as cancelled and recalculates totals.

        Args:
            line_no: Line number of the item to cancel

        Returns:
            CartDocument: The updated cart document with the item cancelled
        """
        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Cancel target line item
        line_item = cart_doc.line_items[line_no - 1]
        line_item.is_cancelled = True

        # Calculate subtotal
        cart_doc = await self.__subtotal_async(cart_doc)

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.NoUpdate)

        return cart_doc

    # Update line item quantity
    async def update_line_item_quantity_in_cart_async(self, line_no: int, quantity: int) -> CartDocument:
        """
        Update the quantity of a line item in the cart.

        Changes the quantity of the specified line item and recalculates totals.

        Args:
            line_no: Line number of the item to update
            quantity: New quantity value

        Returns:
            CartDocument: The updated cart document with modified quantity
        """
        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Update target line item
        line_item = cart_doc.line_items[line_no - 1]
        line_item.quantity = quantity
        # line_item.amount = line_item.unit_price * line_item.quantity

        # Calculate subtotal
        cart_doc = await self.__subtotal_async(cart_doc)

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.NoUpdate)

        return cart_doc

    # Update line item unit price
    async def update_line_item_unit_price_in_cart_async(self, line_no: int, unit_price: float) -> CartDocument:
        """
        Update the unit price of a line item in the cart.

        Changes the unit price of the specified line item, preserving the original price,
        and recalculates totals.

        Args:
            line_no: Line number of the item to update
            unit_price: New unit price value

        Returns:
            CartDocument: The updated cart document with modified unit price
        """
        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Update target line item
        line_item = cart_doc.line_items[line_no - 1]
        if not line_item.is_unit_price_changed:
            line_item.is_unit_price_changed = True
            line_item.unit_price_original = line_item.unit_price
        line_item.unit_price = unit_price
        # line_item.amount = line_item.unit_price * line_item.quantity

        # Calculate subtotal
        cart_doc = await self.__subtotal_async(cart_doc)

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.NoUpdate)

        return cart_doc

    # Add discount to a line item
    async def add_discount_to_line_item_in_cart_async(
        self, line_no: int, add_discount_list: list[dict[str, any]]
    ) -> CartDocument:
        """
        Add discounts to a specific line item in the cart.

        Applies the specified discounts to a line item and recalculates totals.

        Args:
            line_no: Line number of the item to discount
            add_discount_list: List of discounts to apply

        Returns:
            CartDocument: The updated cart document with discounts applied
        """
        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Add discounts to the target line item
        line_item = cart_doc.line_items[line_no - 1]
        await add_discount_to_cart_logic.add_discount_to_line_item_async(line_item, add_discount_list)

        # Calculate subtotal
        cart_doc = await self.__subtotal_async(cart_doc)

        # Same budget as the line-item path: a discount list is taken from the
        # request and appended, with nothing bounding its length or how many
        # times it is sent (issue #200).
        self.__check_snapshot_size_budget(cart_doc)

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.NoUpdate)

        logger.debug(f"add_discount_to_line_item_in_cart_async: cart->{cart_doc}")

        return cart_doc

    # Calculate subtotal and change cart status to payment waiting
    async def subtotal_async(self) -> CartDocument:
        """
        Calculate subtotal and prepare the cart for payment.

        Performs final calculations and changes the cart status to indicate
        it's ready for payment processing.

        Returns:
            CartDocument: The updated cart document with calculated totals and payment status
        """
        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Calculate subtotal
        cart_doc = await self.__subtotal_async(cart_doc)

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.Paying)

        return cart_doc

    async def __subtotal_async(self, cart_doc: CartDocument) -> CartDocument:
        """
        Internal helper method to apply promotions and calculate all cart totals.

        Uses a two-phase promotion model:
        1. Line-item phase: promotions that operate on individual items (e.g., category discounts)
        2. Subtotal phase: promotions that require the subtotal amount (e.g., threshold discounts)

        The subtotal phase only runs if any plugins are registered for it.

        Args:
            cart_doc: The cart document to calculate totals for

        Returns:
            CartDocument: The cart document with updated totals
        """
        # Phase 1: line-item level promotions (e.g., category discounts)
        cart_doc = await self._apply_sales_promotions_async(cart_doc, phase="line_item")
        cart_doc = await calc_subtotal_logic.calc_subtotal_async(cart_doc, self.tax_master_repo)

        # Phase 2: subtotal level promotions (e.g., subtotal threshold discounts)
        # Only run if any plugins are registered for the subtotal phase
        if any(s.execution_phase == "subtotal" for s in self.sales_promo_strategies):
            cart_doc = await self._apply_sales_promotions_async(cart_doc, phase="subtotal")
            cart_doc = await calc_subtotal_logic.calc_subtotal_async(cart_doc, self.tax_master_repo)

        return cart_doc

    # Add discount to the cart subtotal
    async def add_discount_to_cart_async(self, add_discount_list: list[dict[str, any]]) -> CartDocument:
        """
        Add discounts to the cart subtotal.

        Applies discounts to the entire cart (not specific line items) and recalculates totals.

        Args:
            add_discount_list: List of discounts to apply to the cart

        Returns:
            CartDocument: The updated cart document with discounts applied
        """
        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Add discounts to cart
        await add_discount_to_cart_logic.add_discount_to_cart_async(cart_doc, add_discount_list)

        # Calculate subtotal
        cart_doc = await self.__subtotal_async(cart_doc)

        # Same budget as the line-item path: a discount list is taken from the
        # request and appended, with nothing bounding its length or how many
        # times it is sent (issue #200).
        self.__check_snapshot_size_budget(cart_doc)

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.NoUpdate)

        return cart_doc

    # Add payments to the cart
    async def add_payment_to_cart_async(self, add_payment_list: list[dict[str, any]]) -> CartDocument:
        """
        Add payments to the cart.

        Processes payments using the appropriate payment strategy plugins.

        Args:
            add_payment_list: List of payments to apply, each containing payment_code and amount

        Returns:
            CartDocument: The updated cart document with payments applied

        Raises:
            BalanceZeroException: If the cart balance is already zero
            StrategyPluginException: If a payment strategy plugin cannot be found
            ServiceException: If payment processing fails
        """
        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Add payments to cart
        for add_payment in add_payment_list:
            # Check balance
            if cart_doc.balance_amount == 0:
                message = f"The balance is equal to 0, cart_id: {self.cart_id}, balance: {cart_doc.balance_amount}, payments: {add_payment_list}, add_payment: {add_payment}"
                raise BalanceZeroException(message, logger)

            # Get payment plugin
            pay_strategy: AbstractPayment = next(
                (
                    pay_strategy
                    for pay_strategy in self.payment_strategies
                    if pay_strategy.payment_code == add_payment["payment_code"]
                ),
                None,
            )
            if pay_strategy is None:
                message = f"Payment strategy not found, payment_code: {add_payment['payment_code']}"
                raise StrategyPluginException(message, logger)

            logger.debug(f"AddPayment-> pay_strategy: {pay_strategy}")

            # Delegate payment to payment plugin
            try:
                cart_doc = await pay_strategy.pay(
                    cart_doc, add_payment["payment_code"], add_payment["amount"], add_payment["detail"]
                )
            except (BalanceZeroException, BalanceMinusException, DepositOverException) as e:
                # Re-raise business logic exceptions as-is
                raise e
            except Exception as e:
                message = f"Failed to pay, payment_code: {add_payment['payment_code']}, amount: {add_payment['amount']}"
                raise ServiceException(message, logger, e) from e

        # Calculate subtotal
        cart_doc = await self.__subtotal_async(cart_doc)
        logger.debug(f"AddPayment-> payments: {cart_doc.payments}")

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.NoUpdate)

        return cart_doc

    # Complete the transaction
    async def bill_async(
        self,
        seq: int = None,
        receipt_no: int = None,
        transaction_datetime: str = None,
        receipt_counter: int = None,
    ) -> CartDocument:
        """
        Complete the transaction and finalize the cart.

        Verifies that the balance is zero, creates a transaction log entry,
        and marks the cart as completed.

        Args:
            seq: Client-carried transaction sequence (issue #156). On the
                stateless path the terminal supplies the finalize context so
                the transaction number/receipt/time are deterministic across
                retries; create_tranlog uses them instead of server counters.
            receipt_no: Client-carried receipt number (issue #156). The number
                the terminal printed.
            receipt_counter: Client-carried running receipt counter (issue #166),
                from which the printed number is derived. None for pre-#166
                terminals, whose receipt_no is then recorded as sent.
            transaction_datetime: Client-stamped transaction time (issue #156).
                Its presence is the signal that turns on carried numbering.

        Returns:
            CartDocument: The final cart document with completed status

        Raises:
            BalanceGreaterThanZeroException: If the cart balance is not zero
        """
        logger.debug(f"Bill-> cart_id: {self.cart_id}")

        # A client-carried finalize context is only valid on the stateless
        # (signed-snapshot) path (issue #156 / bug_006). On the cache-authoritative
        # path the server assigns the transaction/receipt numbers, so honoring a
        # client-supplied context would let a phase-1 client forge the numbering.
        # Reject it loudly rather than silently ignoring it.
        if transaction_datetime is not None and not self._stateless:
            message = (
                f"Finalize context supplied without a signed snapshot, cart_id: {self.cart_id}. "
                "Carried numbering requires the stateless (snapshot) path."
            )
            raise SnapshotInvalidException(message, logger)

        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)
        logger.debug(f"Bill-> cart_doc: {cart_doc}")

        # Carry the client-stamped finalize context onto the cart so
        # create_tranlog stamps the tranlog deterministically (issue #156).
        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Calculate subtotal (as a precaution)
        cart_doc = await self.__subtotal_async(cart_doc)

        # Verify balance is zero
        if cart_doc.balance_amount > 0:
            message = f"The balance is greater than 0, cart_id: {self.cart_id}, balance: {cart_doc.balance_amount}"
            raise BalanceGreaterThanZeroException(message, logger)

        logger.debug(f"Bill-> balance: {cart_doc.balance_amount}")

        # Carry the client-stamped finalize context onto the cart (after
        # subtotal, which may rebuild cart_doc) so create_tranlog stamps the
        # tranlog deterministically (issue #156). transaction_datetime present
        # turns on carried numbering — only ever on the stateless path (the
        # non-stateless case is rejected at the top of this method, bug_006).
        if transaction_datetime is not None and self._stateless:
            cart_doc.seq = seq
            cart_doc.receipt_no = receipt_no
            cart_doc.receipt_counter = receipt_counter
            cart_doc.transaction_datetime = transaction_datetime
        else:
            await self.__audit_numbering_fallback_async(self.cart_id, "bill")

        # Create transaction log
        tranlog = await self.tran_service.create_tranlog_async(cart_doc)
        logger.debug(f"Bill-> tranlog: {tranlog}")

        # Remove cart from cache (transaction data is already saved in MongoDB)
        await self.__remove_cached_cart_async(self.cart_id)

        # Update cart status in memory for response
        cart_doc.status = CartStatus.Completed.value

        return cart_doc

    async def resume_item_entry_async(self) -> CartDocument:
        """
        Resume item entry from paying state.

        Allows the cart to transition back from Paying state to EnteringItem state,
        clearing any existing payment information and recalculating the balance.

        Returns:
            CartDocument: The updated cart document with EnteringItem status

        Raises:
            EventBadSequenceException: If the cart is not in Paying state
        """
        logger.debug(f"ResumeItemEntry-> cart_id: {self.cart_id}")

        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Clear payment information
        cart_doc.payments = []

        # Recalculate subtotal to update balance
        cart_doc = await self.__subtotal_async(cart_doc)

        logger.debug(f"ResumeItemEntry-> cleared payments, new balance: {cart_doc.balance_amount}")

        # Save to cache with EnteringItem status
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.EnteringItem)

        return cart_doc

    async def prepare_stateless_from_snapshot(self, envelope: dict, api_path: str = None) -> None:
        """
        Arm the per-request stateless path from a carried snapshot (issue #156).

        Verifies and reconstructs the cart from the presented snapshot envelope,
        then pins it so subsequent cart reads return the reconstructed cart and
        cache writes are skipped — the operation never depends on server-side
        cache (FR-004). Verifies signature, tenant/store scope, and that the
        snapshot is an in-flight (non-finalized) cart. Rejections raise the
        snapshot exceptions and are recorded in the audit trail (FR-007).

        Args:
            envelope: Snapshot envelope as a snake_case dict (the peeled
                request.scope["cart_snapshot"]).
        """
        audit_meta = snapshot_service.extract_audit_meta(envelope)
        try:
            # Same operability guard as restore / cart creation.
            if self.terminal_info.status != TerminalStatus.Opened.value:
                raise TerminalStatusException(f"Terminal is not opened. status: {self.terminal_info.status}", logger)
            if self.terminal_info.staff is None:
                raise SignInOutException("Terminal is not signed in", logger)

            # Verify signature/version/kid and rebuild the cart document.
            snapshot_cart = snapshot_service.verify_envelope(envelope)

            # Scope check: same tenant AND store (FR-005 / FR-012).
            if (
                envelope.get("tenant_id") != self.terminal_info.tenant_id
                or envelope.get("store_code") != self.terminal_info.store_code
            ):
                raise SnapshotScopeViolationException(
                    f"Snapshot scope mismatch: snapshot={envelope.get('tenant_id')}/{envelope.get('store_code')} "
                    f"auth={self.terminal_info.tenant_id}/{self.terminal_info.store_code}",
                    logger,
                )

            # A cart opened for the cache path must not be carried (issue #192).
            # Its copy is in the cache, and this request would not update it -
            # so the next snapshot-less request would continue from a cart
            # missing everything done here, and answer with a correctly signed
            # snapshot of it. Refusing is the whole guard: the way the cart was
            # opened is in the signed document, so no cache read is needed to
            # know it. `None` is a cart created before the field existed and is
            # left alone, so carts in flight across a deployment keep working.
            if snapshot_cart.carry_snapshot is False:
                raise CartPathMismatchException(
                    f"Cart {snapshot_cart.cart_id} was opened without carrySnapshot, so it is served from the "
                    "server-side cache and cannot be carried. Open the cart with carrySnapshot=true to carry it.",
                    logger,
                )

            # Only in-flight carts are operable; terminal-state snapshots are
            # rejected (a non-finalize op on a finalized cart is invalid).
            if snapshot_cart.status in (CartStatus.Completed.value, CartStatus.Cancelled.value):
                raise SnapshotTerminalStateException(
                    f"Snapshot of a finalized cart cannot be operated on: status={snapshot_cart.status}",
                    logger,
                )
            if snapshot_cart.status not in snapshot_service.RESTORABLE_STATUSES or not snapshot_cart.cart_id:
                raise SnapshotInvalidException(
                    f"Snapshot cart is not operable: status={snapshot_cart.status} cart_id={snapshot_cart.cart_id}",
                    logger,
                )

            # The URL path names the cart the client addressed; the snapshot must
            # agree. Below, the reconstructed cart replaces the cached one and
            # __get_cached_cart_async ignores its cart_id argument, so a mismatch
            # would silently operate on (and return) a different cart than the one
            # requested — invisible to the client and to the audit trail, which
            # records the snapshot's cart_id. Reject rather than let the snapshot
            # override the request target.
            if self.cart_id is not None and snapshot_cart.cart_id != self.cart_id:
                raise SnapshotCartIdMismatchException(
                    f"Snapshot cart_id does not match the requested cart: "
                    f"snapshot={snapshot_cart.cart_id} requested={self.cart_id}",
                    logger,
                )
        except ServiceException as e:
            await self.__add_restore_audit_async("rejected", audit_meta, reject_reason=e.error_code, api_path=api_path)
            raise

        # Arm the stateless path: reconstruct master context + state, pin the
        # cart. Subsequent __get_cached_cart_async / __cache_cart_async observe
        # _stateless and bypass the cache.
        self._stateless = True
        self._snapshot_cart = snapshot_cart
        self.cart_id = snapshot_cart.cart_id
        self.settings_master_repo.set_settings_master_documents(snapshot_cart.masters.settings)
        self.item_master_repo.set_item_master_documents(snapshot_cart.masters.items)
        self.tax_master_repo.set_tax_master_documents(snapshot_cart.masters.taxes)
        self.state_manager.set_state(snapshot_cart.status)

    async def __audit_numbering_fallback_async(self, cart_id: str, api_path: str) -> None:
        """
        Record a finalize that will be numbered from the server-side series when
        the terminal has a series of its own (issue #168).

        DUAL mode keeps two independent receipt-number sources: a carried
        finalize numbers from the terminal's running counter, a snapshot-less one
        from cart's `terminal_counter`. The branch is per *transaction*, so a
        phase 2 terminal whose snapshot signing has degraded silently falls into
        the other series and can print a receipt number it has already issued.

        An unset or malformed key no longer reaches here: the service refuses to
        start without a usable one (issue #192). What is left is a key that loads
        and then fails to sign, so the check stays - it costs one comparison, and
        the signal it carries is one nothing else would report.

        Detected, not blocked: refusing the finalize would stop a store selling
        over a key misconfiguration, and this codebase's posture for numbering
        integrity is audit detection rather than enforcement (spec 156 Q58).
        `CART_REQUEST_SNAPSHOT_MODE=REQUIRED` is what removes the window.

        Args:
            cart_id: The cart being finalized
            api_path: API path of the finalize, for the audit trail

        Returns:
            None
        """
        signing_degraded = snapshot_service.get_snapshot_signer() is None
        terminal_counter = getattr(self.terminal_info, "receipt_counter", None)
        # A counter above zero means this terminal has numbered receipts itself.
        # Zero is deliberately not enough: open seeds every terminal with zero, so
        # `is not None` would flag every phase 1 finalize as an incident.
        terminal_numbers_its_own = bool(terminal_counter)
        # A request that carried a snapshot but no finalize context is a phase 2
        # client whatever its counter says - the case a zero counter would miss.
        carried_a_snapshot = self._stateless
        if not (signing_degraded or terminal_numbers_its_own or carried_a_snapshot):
            # A phase 1 terminal with no series of its own: the server-side
            # numbering is simply how it works, and nothing can collide.
            #
            # Blind spot, stated rather than papered over: a phase 2 terminal that
            # has not numbered anything yet (counter zero), whose signing is
            # healthy, and which carries no snapshot at all is indistinguishable
            # from a phase 1 terminal here. Its first sale would not be flagged.
            return

        if signing_degraded:
            reason = "signing_degraded"
        elif carried_a_snapshot:
            reason = "snapshot_without_finalize_context"
        else:
            reason = "no_carried_context"
        logger.error(
            "Finalize numbered from the server-side series while the terminal has "
            "its own (issue #168): cart_id=%s reason=%s terminal_receipt_counter=%s "
            "stateless=%s. Receipt numbers from the two series can collide; fix the "
            "snapshot signing key, or move to CART_REQUEST_SNAPSHOT_MODE=REQUIRED.",
            cart_id,
            reason,
            terminal_counter,
            self._stateless,
        )
        await self.__add_restore_audit_async(
            result="numbering_fallback",
            audit_meta={"cart_id": cart_id},
            reject_reason=reason,
            api_path=api_path,
        )

    async def __add_restore_audit_async(
        self, result: str, audit_meta: dict, reject_reason: str = None, diverged: bool = False, api_path: str = None
    ) -> None:
        """
        Record a restore attempt in the audit trail (FR-007).

        Audit-write failure handling depends on whether server state changed:
        - "rejected" / "existing_returned" mutate nothing, so the original
          outcome wins and the failure is only logged (with the full record
          payload, so the trace survives in the app log).
        - "restored" already materialized the cart, so the failure is logged
          the same way and then raised: a state-changing restore that cannot
          be persisted to the trail must surface loudly. A client retry hits
          the existing-cart path and gets audited there.
        """
        if self.cart_restore_log_repo is None:
            logger.warning("Restore audit repository not configured; skipping audit record")
            return
        try:
            await self.cart_restore_log_repo.add_record_async(
                result=result,
                reject_reason=reject_reason,
                diverged=diverged,
                api_path=api_path,
                **audit_meta,
            )
        except Exception as e:
            # Keep the trace in the application log even when the DB write
            # failed; this is the fallback audit trail.
            logger.error(
                "Failed to write restore audit record: result=%s reject_reason=%s diverged=%s meta=%s error=%s",
                result,
                reject_reason,
                diverged,
                audit_meta,
                e,
            )
            if result == "restored":
                raise

    # Save cart document to cache
    async def __cache_cart_async(self, cart_doc: CartDocument, cart_status: CartStatus, isNew: bool = False) -> None:
        """
        Internal helper method to save cart document to cache.

        Updates the cart status if needed and saves to cache.

        Args:
            cart_doc: The cart document to save
            cart_status: New status to set (unless NoUpdate)
            isNew: Whether this is a new cart being saved for the first time

        Raises:
            CartCannotSaveException: If the cart cannot be saved to cache
        """
        # Update cart status
        if cart_status != CartStatus.NoUpdate:
            cart_doc.status = cart_status.value
            self.state_manager.set_state(cart_doc.status)

        # Save updated item master information to cache
        cart_doc.masters.items = self.item_master_repo.item_master_documents

        if self._stateless:
            # Snapshot-present path (issue #156): the response snapshot is the
            # authority; do not depend on server-side cache (FR-004). Keep the
            # pinned cart current so re-reads in this request stay consistent.
            self._snapshot_cart = cart_doc
            self.current_cart = None
            return

        try:
            await self.cart_repo.cache_cart_async(cart_doc, isNew)
        except Exception as e:
            message = f"Failed to cache cart, cart_id: {cart_doc.cart_id}"
            logger.fatal(message)

            # Send Slack notification
            context = (
                {"cart_id": cart_doc.cart_id, "terminal_id": self.terminal_info.terminal_id}
                if self.terminal_info
                else {"cart_id": cart_doc.cart_id}
            )
            await send_fatal_error_notification(message=message, error=e, service="cart", context=context)

            raise CartCannotSaveException(message, logger, e) from e

        # Clear current cart information
        self.current_cart = None

    # Get cart document from cache
    async def __get_cached_cart_async(self, cart_id: str) -> CartDocument:
        """
        Internal helper method to retrieve cart document from cache.

        Gets the cart from cache and updates repository caches with cart's master data.

        Args:
            cart_id: ID of the cart to retrieve

        Returns:
            CartDocument: The retrieved cart document
        """
        # Snapshot-present path (issue #156): serve the reconstructed cart and
        # never read the server-side cache (FR-004).
        if self._stateless:
            cart = self._snapshot_cart
            self.settings_master_repo.set_settings_master_documents(cart.masters.settings)
            self.item_master_repo.set_item_master_documents(cart.masters.items)
            self.tax_master_repo.set_tax_master_documents(cart.masters.taxes)
            self.state_manager.set_state(cart.status)
            self.current_cart = cart
            return cart

        # Get cart information from cache
        try:
            cart = await self.cart_repo.get_cached_cart_async(cart_id)
            logger.debug(f"__get_cached_cart_async: cart->{cart}")
        except Exception as e:
            message = f"Failed to get cached cart, cart_id: {cart_id}"
            logger.fatal(message)

            # Send Slack notification
            context = (
                {"cart_id": cart_id, "terminal_id": self.terminal_info.terminal_id}
                if self.terminal_info
                else {"cart_id": cart_id}
            )
            await send_fatal_error_notification(message=message, error=e, service="cart", context=context)

            raise CartNotFoundException(message, logger, e) from e

        # Update cache information in each repository
        self.settings_master_repo.set_settings_master_documents(cart.masters.settings)
        self.item_master_repo.set_item_master_documents(cart.masters.items)
        self.tax_master_repo.set_tax_master_documents(cart.masters.taxes)

        logger.debug(f"tax_master_documents: {self.tax_master_repo.tax_master_documents}")

        # Update cart state
        self.state_manager.set_state(cart.status)

        # Store current cart information
        self.current_cart = cart

        return cart

    async def __remove_cached_cart_async(self, cart_id: str) -> None:
        """
        Remove the cached cart document.

        Deletes the specified cart from the cache.

        Args:
            cart_id: ID of the cart to remove

        Raises:
            CartNotFoundException: If the cart cannot be found in the cache
        """
        if self._stateless:
            # No server-side cache entry to remove on the snapshot-present path.
            return None
        try:
            await self.cart_repo.delete_cart_async(cart_id)
        except Exception as e:
            message = f"Failed to remove cached cart, cart_id: {cart_id}"
            logger.error(message)

            # Send Slack notification — send_warning_notification has no `error`
            # kwarg, so include the exception in the context dict instead.
            context = (
                {"cart_id": cart_id, "terminal_id": self.terminal_info.terminal_id}
                if self.terminal_info
                else {"cart_id": cart_id}
            )
            context["error"] = str(e)
            await send_warning_notification(message=message, service="cart", context=context)
            return None  # Return None if failed to remove cached cart

    async def _get_setting_value_async(self, name: str) -> Any:
        """
        Get a setting value from the settings repository.

        Retrieves a setting value by name, with appropriate terminal and store context.

        Args:
            name: Name of the setting to retrieve

        Returns:
            Any: The setting value
        """
        try:
            setting_doc = await self.settings_master_repo.get_settings_value_by_name_async(name)
        except NotFoundException:
            setting_doc = None
        return get_setting_value(
            name=name,
            store_code=self.terminal_info.store_code,
            terminal_no=self.terminal_info.terminal_no,
            setting=setting_doc,
        )
