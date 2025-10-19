# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
import uuid
import aiohttp
import time
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config.settings import settings
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.user_info_document import UserInfoDocument
from kugel_common.utils.misc import get_app_time_str

from app.enums.cart_status import CartStatus
from app.models.documents.cart_document import CartDocument
from app.models.documents.settings_master_document import SettingsMasterDocument
from app.models.documents.tax_master_document import TaxMasterDocument
from app.models.documents.item_master_document import ItemMasterDocument
from app.config.settings import settings
from app.exceptions import NotFoundException, CannotCreateException, UpdateNotWorkException, CannotDeleteException
from app.utils.dapr_statestore_session_helper import get_dapr_statestore_session

logger = getLogger(__name__)


class CartRepository(AbstractRepository[CartDocument]):
    """
    name: CartRepository
    description: This class is used to interact with the database for the CartDocument collection.
    base class: AbstractRepository
    """

    def __init__(self, db: AsyncIOMotorDatabase, terminal_info: TerminalInfoDocument = None):
        """
        This is the constructor of the CartRepository class
        args:
            terminal_info: TerminalInfoDocument
        """
        super().__init__(settings.DB_COLLECTION_NAME_CACHE_CART, CartDocument, db)
        self.terminal_info = terminal_info
        # Variables for circuit breaker state management
        self._circuit_open = False
        self._failure_count = 0
        self._last_failure_time = 0
        self._failure_threshold = 3
        self._reset_timeout = 60  # Reset timeout in seconds

    base_url_cartstore = f"{settings.BASE_URL_DAPR}/state/cartstore"

    def _check_circuit_breaker(self):
        """
        Check the current state of the circuit breaker.
        If the circuit is open, check if the reset timeout has elapsed.
        If it has, close the circuit (move to half-open state).

        Returns:
            bool: True if the circuit is closed (normal state), False if open
        """
        if self._circuit_open:
            current_time = time.time()
            if (current_time - self._last_failure_time) > self._reset_timeout:
                logger.info("Circuit breaker reset timeout elapsed. Moving to half-open state.")
                self._circuit_open = False
                self._failure_count = 0
                return True
            return False
        return True

    def _open_circuit(self):
        """
        Open the circuit (set the circuit breaker to tripped state)
        """
        logger.warning("Circuit breaker tripped. Opening the circuit.")
        self._circuit_open = True
        self._last_failure_time = time.time()

    def _record_failure(self):
        """
        Record a failure and open the circuit if the threshold is exceeded
        """
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._open_circuit()

    def _record_success(self):
        """
        Record a success and reset the failure count
        """
        if self._circuit_open:
            logger.info("Circuit breaker successful request in half-open state. Closing the circuit.")
        self._circuit_open = False
        self._failure_count = 0

    async def create_cart_async(
        self,
        transaction_type: int,
        user_id: str,
        user_name: str,
        store_name: str,
        receipt_no: int,
        transaction_no: int,
        settings_master: list[SettingsMasterDocument],
        tax_master: list[TaxMasterDocument],
        item_master: list[ItemMasterDocument],
    ) -> CartDocument:
        """
        This is the create_cart_async method
        args:
            transaction_type: int,
            user_id: str,
            user_name: str,
            receipt_no: int,
            transaction_no: int,
            settings_master: list[SettingsMasterDocument]
        return:
            document if the document is created, None otherwise
        note:
            only create CartDocument object, not insert into the database
        """
        cart = CartDocument()
        cart.cart_id = str(uuid.uuid4())
        cart.tenant_id = self.terminal_info.tenant_id
        cart.store_code = self.terminal_info.store_code
        cart.store_name = store_name
        cart.terminal_no = self.terminal_info.terminal_no
        cart.status = CartStatus.Initial.value
        cart.transaction_type = transaction_type
        cart.transaction_no = transaction_no
        cart.receipt_no = receipt_no
        cart.receipt_text = ""
        cart.user = UserInfoDocument(id=user_id, name=user_name)
        cart.sales = CartDocument.SalesInfo()
        cart.sales.reference_date_time = get_app_time_str()
        cart.business_date = self.terminal_info.business_date
        cart.shard_key = self.__get_shard_key(cart)
        cart.masters.settings = settings_master
        cart.masters.taxes = tax_master
        cart.masters.items = item_master
        cart.staff = CartDocument.Staff(id=self.terminal_info.staff.id, name=self.terminal_info.staff.name)
        logger.debug(f"Cart business_date: {cart.business_date}, reference_date_tiem: {cart.sales.reference_date_time}")
        return cart

    async def cache_cart_async(self, cart: CartDocument, isNew: bool = False) -> None:
        """
        This is the cache_cart_async method
        update the cart in the cache by replacing the existing cart
        args:
            cart: CartDocument
            isNew: bool
        return:
            None
        exceptions:
            CartCannotCreateException is raised if there is an error when creating the cart
            UpdateNotWorkException is raised if there is an error when updating the cart
        """
        # Check circuit breaker
        if not self._check_circuit_breaker():
            logger.warning("Circuit is open. Bypassing cache and using database directly.")
            await self.__save_cart_to_db_async(cart)
            return

        try:
            await self.__cache_cart_async(cart, isNew)
            # Record success
            self._record_success()
        except Exception as e:
            logger.warning(f"Failed to cache cart: {e}")
            # Record failure
            self._record_failure()
            # Fallback to database
            await self.__save_cart_to_db_async(cart)

    async def get_cached_cart_async(self, cart_id: str) -> CartDocument:
        """
        This is the get_cached_cart_async method
        get the cart from the cache
        args:
            cart_id: str
        return:
            document if the document is found, raise CartNotFoundException otherwise
        exceptions:
            CartNotFoundException is raised if there is an error
        """
        # Check circuit breaker
        if not self._check_circuit_breaker():
            logger.warning("Circuit is open. Bypassing cache and using database directly.")
            return await self.__get_cart_from_db_async(cart_id)

        try:
            cart = await self.__get_cached_cart_async(cart_id)
            # Record success
            self._record_success()
            return cart
        except Exception as e:
            logger.warning(f"Failed to get cached cart: {e}")
            # Record failure
            self._record_failure()
            # Fallback to database
            return await self.__get_cart_from_db_async(cart_id)

    async def delete_cart_async(self, cart_id: str) -> None:
        """
        This is the delete_cart_async method
        args:
            cart_id: str
        return:
            None
        exceptions:
            CannnotDeleteException is raised if there is an error when deleting the cart
        """
        # Check circuit breaker
        if not self._check_circuit_breaker():
            logger.warning("Circuit is open. Bypassing cache and using database directly.")
            try:
                await self.__delete_cart_from_db_async(cart_id)
                return None
            except Exception as e:
                logger.error(f"Failed to delete cart from database: {e}")
                raise e
        try:
            await self.__delete_cached_cart_async(cart_id)
            # Record success
            self._record_success()
        except Exception as e:
            logger.error(f"Failed to delete cached cart: {e}")
            # Record failure
            self._record_failure()
            raise e

    async def __cache_cart_async(self, cart: CartDocument, isNew: bool = False) -> None:
        """
        Cache the cart to Dapr state store.
        Uses shared aiohttp session with connection pooling for performance.

        Performance: Shared session eliminates 50-100ms session creation overhead per request.

        args:
            cart: CartDocument to cache
            isNew: Whether this is a new cart (for logging purposes)
        return:
            None
        exceptions:
            CartCannotCreateException is raised if there is an error when creating the cart
            UpdateNotWorkException is raised if there is an error when updating the cart
        """
        cart_data = cart.model_dump()
        state_post_data = [{"key": cart.cart_id, "value": cart_data}]
        logger.debug(f"State post data: {state_post_data}")

        # Use shared session with connection pooling (eliminates session creation overhead)
        session = await get_dapr_statestore_session()
        async with session.post(self.base_url_cartstore, json=state_post_data) as response:
            logger.debug(f"Response status: {response.status}")
            logger.debug(f"Response text: {await response.text()}")
            if response.status != 204:
                if response.status == 400:
                    error_message = await response.json()
                    if error_message.get("errorCode") == "ERR_STATE_STORE_NOT_FOUND":
                        logger.error(f"State store not found: {error_message.get('message')}")
                message = "Failed to cache cart"
                raise UpdateNotWorkException(message, self.collection_name, cart.cart_id, logger)
            logger.debug(f"Cart cached: {cart}")

    async def __get_cached_cart_async(self, cart_id: str) -> CartDocument:
        """
        Get the cart from Dapr state store cache.
        Uses shared aiohttp session with connection pooling for performance.

        Performance: Shared session eliminates 50-100ms session creation overhead per request.

        args:
            cart_id: str - Cart ID to retrieve
        return:
            CartDocument if found in cache
        exceptions:
            NotFoundException is raised if cart not found in cache
        """
        # Use shared session with connection pooling (eliminates session creation overhead)
        session = await get_dapr_statestore_session()
        async with session.get(f"{self.base_url_cartstore}/{cart_id}") as response:
            if response.status != 200:
                message = "cart not found"
                raise NotFoundException(message, self.collection_name, cart_id, logger)
            cart_data = await response.json()
            logger.debug(f"Cart data: {cart_data}")
            cart_doc = CartDocument(**cart_data)
            cart_doc.staff = CartDocument.Staff(id=self.terminal_info.staff.id, name=self.terminal_info.staff.name)
            return cart_doc

    async def __delete_cached_cart_async(self, cart_id: str) -> None:
        """
        Delete the cart from Dapr state store cache.
        Uses shared aiohttp session with connection pooling for performance.

        Performance: Shared session eliminates 50-100ms session creation overhead per request.

        args:
            cart_id: str - Cart ID to delete
        return:
            None
        exceptions:
            CannotDeleteException is raised if deletion fails
        """
        # Use shared session with connection pooling (eliminates session creation overhead)
        session = await get_dapr_statestore_session()
        async with session.delete(f"{self.base_url_cartstore}/{cart_id}") as response:
            if response.status != 204:
                message = f"cart not found. cart_id->{cart_id}"
                raise CannotDeleteException(message, self.collection_name, cart_id, logger)
            return None

    async def __save_cart_to_db_async(self, cart: CartDocument) -> None:
        """
        This is the save_cart_async method
        args:
            cart: CartDocument
        return:
            None
        exceptions:
            CartCannotCreateException is raised if there is an error when creating the cart
            UpdateNotWorkException is raised if there is an error when updating the cart
        """
        # save cart to the database
        search_dict = {"cart_id": cart.cart_id}
        doc = await self.get_one_async(search_dict)
        if doc is not None:
            # update the cart
            cart.shard_key = self.__get_shard_key(cart)
            result = await self.update_one_async(search_dict, cart.model_dump())
            if not result:
                message = "Failed to update cart"
                raise UpdateNotWorkException(message, self.collection_name, cart.cart_id, logger)
        else:
            # create a new cart
            cart.shard_key = self.__get_shard_key(cart)
            result = await self.create_async(cart)
            if not result:
                message = "Failed to create cart"
                raise CannotCreateException(message, self.collection_name, cart.cart_id, logger)
        return None

    async def __get_cart_from_db_async(self, cart_id: str) -> CartDocument:
        """
        This is the get_cart_async method
        args:
            cart_id: str
        return:
            document if the document is found, raise CartNotFoundException otherwise
        exceptions:
            CartNotFoundException is raised if there is an error
        """
        search_dict = {"cart_id": cart_id}
        doc = await self.get_one_async(search_dict)
        if doc is None:
            message = f"cart not found. cart_id->{cart_id}"
            raise NotFoundException(message, self.collection_name, cart_id, logger)
        return doc

    async def __delete_cart_from_db_async(self, cart_id: str) -> None:
        """
        This is the delete_cart_async method
        args:
            cart_id: str
        return:
            None
        exceptions:
            CartNotFoundException is raised if there is an error
        """
        search_dict = {"cart_id": cart_id}
        try:
            result = await self.delete_async(search_dict)
            if not result:
                raise NotFoundException("Cart not found", self.collection_name, cart_id, logger)
            return None
        except Exception as e:
            message = f"Failed to delete cart: cart_id->{cart_id} err->{e}"
            raise CannotDeleteException(message, self.collection_name, cart_id, logger)

    def __get_shard_key(self, cartDocument: CartDocument):
        """
        This is the get_shard_key method
        args:
            cartDocument: CartDocument
        return:
            str which is the shard key
        """
        keys = []
        keys.append(cartDocument.tenant_id)
        keys.append(cartDocument.store_code)
        keys.append(cartDocument.business_date)
        return self.make_shard_key(keys)
