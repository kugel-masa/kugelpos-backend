# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any, Union
from logging import getLogger

# Get logger instance
logger = getLogger(__name__)

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
)

from app.models.repositories.cart_repository import CartRepository
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
from app.models.documents.cart_document import CartDocument
from app.enums.terminal_status import TerminalStatus
from app.services.cart_service_interface import ICartService
from app.services.cart_state_manager import CartStateManager
from app.services.cart_strategy_manager import CartStrategyManager
from app.services.logics import calc_tax_logic
from app.services.logics import add_discount_to_cart_logic
from app.services.logics import calc_line_item_logic
from app.services.logics import calc_subtotal_logic
from app.services.strategies.payments.abstract_payment import AbstractPayment
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

        self.cart_id = cart_id
        self.current_cart = None

        self.state_manager = CartStateManager()
        self.strategy_manager = CartStrategyManager()

        try:
            # Load sales promotion strategy plugins
            self.sales_promo_strategies = self.strategy_manager.load_strategies("sales_promo_strategies")
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
    async def create_cart_async(
        self,
        terminal_id: str,
        transaction_type: int,
        user_id: str,
        user_name: str,
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
            )
            if cart is None:
                raise Exception("failed to create cart, cart is None")
        except Exception as e:
            message = f"Failed to create cart, transaction_type: {transaction_type}, user_id: {user_id}, user_name: {user_name}"
            raise CartCannotCreateException(message, logger, e) from e

        # Save to cache
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
    async def cancel_transaction_async(self) -> CartDocument:
        """
        Cancel the current transaction.

        Marks the cart as cancelled and creates a transaction log entry.

        Returns:
            CartDocument: The updated cart document with cancelled status
        """
        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Process cancellation
        cart_doc.sales.is_cancelled = True

        # Create transaction log
        tranlog = await self.tran_service.create_tranlog_async(cart_doc)
        logger.debug(f"CancelTransaction-> tranlog: {tranlog}")

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.Cancelled)

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

        # Calculate subtotal
        cart_doc = await self.__subtotal_async(cart_doc)

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.EnteringItem)

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
        Internal helper method to calculate all cart totals.

        Delegates the calculation logic to calc_subtotal_logic module.

        Args:
            cart_doc: The cart document to calculate totals for

        Returns:
            CartDocument: The cart document with updated totals
        """
        return await calc_subtotal_logic.calc_subtotal_async(cart_doc, self.tax_master_repo)

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
    async def bill_async(self) -> CartDocument:
        """
        Complete the transaction and finalize the cart.

        Verifies that the balance is zero, creates a transaction log entry,
        and marks the cart as completed.

        Returns:
            CartDocument: The final cart document with completed status

        Raises:
            BalanceGreaterThanZeroException: If the cart balance is not zero
        """
        logger.debug(f"Bill-> cart_id: {self.cart_id}")

        # Get cart information
        cart_doc = await self.__get_cached_cart_async(self.cart_id)
        logger.debug(f"Bill-> cart_doc: {cart_doc}")

        # Check if the event can be accepted in the current state
        self.state_manager.check_event_sequence(self)

        # Calculate subtotal (as a precaution)
        cart_doc = await self.__subtotal_async(cart_doc)

        # Verify balance is zero
        if cart_doc.balance_amount > 0:
            message = f"The balance is greater than 0, cart_id: {self.cart_id}, balance: {cart_doc.balance_amount}"
            raise BalanceGreaterThanZeroException(message, logger)

        logger.debug(f"Bill-> balance: {cart_doc.balance_amount}")

        # Create transaction log
        tranlog = await self.tran_service.create_tranlog_async(cart_doc)
        logger.debug(f"Bill-> tranlog: {tranlog}")

        # Save to cache
        await self.__cache_cart_async(cart_doc=cart_doc, cart_status=CartStatus.Completed)

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
        try:
            await self.cart_repo.delete_cart_async(cart_id)
        except Exception as e:
            message = f"Failed to remove cached cart, cart_id: {cart_id}"
            logger.error(message)

            # Send Slack notification
            context = (
                {"cart_id": cart_id, "terminal_id": self.terminal_info.terminal_id}
                if self.terminal_info
                else {"cart_id": cart_id}
            )
            await send_warning_notification(message=message, error=e, service="cart", context=context)
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
