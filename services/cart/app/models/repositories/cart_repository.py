# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
import asyncio
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
from app.models.documents.promotion_master_document import PromotionMasterDocument
from app.config.settings import settings
from app.exceptions import (
    NotFoundException,
    CannotCreateException,
    UpdateNotWorkException,
    CartStoreUnavailableException,
)
from app.utils.dapr_statestore_session_helper import get_dapr_statestore_session

logger = getLogger(__name__)

CACHE_STORE_REDIS = "redis"
CACHE_STORE_MONGODB = "mongodb"

# Short retries for a blip, not for an outage: the breaker handles outages.
REDIS_ATTEMPTS = 3
REDIS_RETRY_DELAYS = (0.05, 0.1)


class _RedisUnavailable(Exception):
    """The Dapr cart store could not answer (transport error, timeout, 5xx)."""


class _RedisRefused(_RedisUnavailable):
    """The Dapr cart store answered 4xx: not a blip, so not retried."""


class _CartStoreBreaker:
    """
    Process-wide circuit breaker over the Dapr cart store (Redis).

    It used to live on CartRepository, which is built per request, so its failure
    count started at zero every time and it never opened. Process-wide, it opens
    after FAILURE_THRESHOLD consecutive failures; while open, new carts are created
    in MongoDB and Redis is not tried. After RESET_TIMEOUT one request is let
    through to probe Redis: success closes it, failure keeps it open.

    Replicas each keep their own; that is safe because the breaker only decides
    where NEW carts go. Every cart is read from where it was created.
    """

    FAILURE_THRESHOLD = 3
    RESET_TIMEOUT = 60.0

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._probing = False

    @property
    def is_open(self) -> bool:
        return self._opened_at is not None

    def allow_redis(self) -> bool:
        if self._opened_at is None:
            return True
        if not self._probing and time.monotonic() - self._opened_at >= self.RESET_TIMEOUT:
            self._probing = True
            return True
        return False

    def record_success(self) -> None:
        if self._opened_at is not None:
            logger.info("Cart store (Redis) answered again; new carts go back to Redis")
        self.reset()

    def record_failure(self) -> None:
        self._failures += 1
        self._probing = False
        if self._opened_at is not None or self._failures >= self.FAILURE_THRESHOLD:
            if self._opened_at is None:
                logger.error(
                    f"Cart store (Redis) failed {self._failures} times in a row; new carts are created in "
                    f"MongoDB until it answers again (next probe in {self.RESET_TIMEOUT:.0f}s)"
                )
            self._opened_at = time.monotonic()


_breaker = _CartStoreBreaker()


def reset_cart_store_breaker() -> None:
    """Close the breaker (tests; a process starts closed)."""
    _breaker.reset()


def _store_of(cart: CartDocument) -> str:
    return cart.cache_store or CACHE_STORE_REDIS


def _unexpected_status(op: str, status: int, text: str) -> Exception:
    if status >= 500:
        return _RedisUnavailable(f"{op}: HTTP {status} {text[:200]}")
    # A 4xx is not a blip (a missing state store component, a bad request):
    # retrying will not help, but the cart store is still not usable.
    return _RedisRefused(f"{op}: HTTP {status} {text[:200]}")


async def _with_retry(op):
    """Run a Dapr state call, retrying transport errors, timeouts and 5xx briefly."""
    last = None
    for attempt in range(REDIS_ATTEMPTS):
        try:
            return await op()
        except (aiohttp.ClientError, TimeoutError) as e:
            last = _RedisUnavailable(f"{type(e).__name__}: {e}")
        except _RedisRefused:
            raise
        except _RedisUnavailable as e:
            last = e
        except Exception as e:  # noqa: BLE001
            # Anything else from the Dapr call (a session bound to a closed loop,
            # a body that does not parse) leaves the cart store unusable just the
            # same; the old code fell back on any exception. Not retried.
            raise _RedisRefused(f"{type(e).__name__}: {e}") from e
        if attempt < REDIS_ATTEMPTS - 1:
            await asyncio.sleep(REDIS_RETRY_DELAYS[min(attempt, len(REDIS_RETRY_DELAYS) - 1)])
    raise last


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

    base_url_cartstore = f"{settings.BASE_URL_DAPR}/state/cartstore"

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
        promotion_master: list[PromotionMasterDocument] = None,
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
        cart.masters.promotions = promotion_master or []
        cart.staff = CartDocument.Staff(id=self.terminal_info.staff.id, name=self.terminal_info.staff.name)
        logger.debug(f"Cart business_date: {cart.business_date}, reference_date_tiem: {cart.sales.reference_date_time}")
        return cart

    async def cache_cart_async(self, cart: CartDocument, isNew: bool = False) -> None:
        """
        Write the cart to the store it lives in.

        A new cart is placed here: in Redis unless the cart-store breaker is open,
        or Redis fails on this very write - a cart that exists nowhere yet can be
        put in MongoDB without anything to be stale against. An existing cart is
        written only to the store recorded on it, and is never moved: a Redis cart
        whose write fails is answered 503 and keeps its previous version.

        args:
            cart: CartDocument
            isNew: True on the first write of a cart created in this request
        return:
            None
        exceptions:
            CartStoreUnavailableException if the cart's store cannot be reached
        """
        if isNew:
            cart.cache_store = CACHE_STORE_REDIS if _breaker.allow_redis() else CACHE_STORE_MONGODB
            if cart.cache_store == CACHE_STORE_REDIS:
                try:
                    await self.__redis_save_async(cart)
                    _breaker.record_success()
                    return
                except _RedisUnavailable as e:
                    _breaker.record_failure()
                    # The write may have reached Redis with only the answer lost.
                    # Nobody knows this id yet, so the cart is re-issued under a new
                    # one: whatever landed in Redis is an orphan no request will name,
                    # and expires with the store's TTL.
                    stale_id = cart.cart_id
                    cart.cart_id = str(uuid.uuid4())
                    logger.warning(
                        f"Cart store (Redis) unavailable when creating cart {stale_id}: {e}; "
                        f"re-issued as {cart.cart_id} in MongoDB"
                    )
                    cart.cache_store = CACHE_STORE_MONGODB
            logger.warning(f"Cart {cart.cart_id} is created in MongoDB (cache_cart) and stays there until it ends")
            await self.__save_cart_to_db_async(cart)
            return

        if _store_of(cart) == CACHE_STORE_MONGODB:
            await self.__save_cart_to_db_async(cart)
            return

        if not _breaker.allow_redis():
            raise CartStoreUnavailableException(
                f"Cart store (Redis) is unavailable; cart {cart.cart_id} lives there and is not moved", logger
            )
        try:
            await self.__redis_save_async(cart)
            _breaker.record_success()
        except _RedisUnavailable as e:
            _breaker.record_failure()
            raise CartStoreUnavailableException(
                f"Cart store (Redis) is unavailable; cart {cart.cart_id} lives there and is not moved", logger, e
            ) from e

    async def get_cached_cart_async(self, cart_id: str) -> CartDocument:
        """
        Read the cart from the store it lives in.

        Redis first, as in normal operation; a cart that is not there is looked up
        in MongoDB, where only carts created while Redis was failing live. While
        the breaker is open Redis is skipped.

        args:
            cart_id: str
        return:
            CartDocument
        exceptions:
            NotFoundException if the cart is in neither store
            CartStoreUnavailableException if it is not in MongoDB and Redis could not
                be asked - it may well be there
        """
        redis_unanswered = True
        if _breaker.allow_redis():
            try:
                cart = await self.__redis_get_async(cart_id)
                _breaker.record_success()
                redis_unanswered = False
                if cart is not None and _store_of(cart) == CACHE_STORE_REDIS:
                    cart.cache_store = CACHE_STORE_REDIS
                    return self.__with_terminal_staff(cart)
                if cart is not None:
                    # A MongoDB cart found in Redis was put there by a replica that
                    # predates cache_store (a rolling update): MongoDB holds the cart.
                    logger.warning(f"Cart {cart_id} lives in MongoDB but a copy is in Redis; reading MongoDB")
            except _RedisUnavailable as e:
                _breaker.record_failure()
                logger.warning(f"Cart store (Redis) unavailable when reading cart {cart_id}: {e}")

        cart = await self.get_one_async({"cart_id": cart_id})
        if cart is not None:
            # A copy written by a version that predates cache_store lived here
            # because Redis had failed; reading it from here makes it a MongoDB cart.
            cart.cache_store = CACHE_STORE_MONGODB
            return self.__with_terminal_staff(cart)
        if redis_unanswered:
            raise CartStoreUnavailableException(
                f"Cart {cart_id} is not in MongoDB and the cart store (Redis) could not be asked", logger
            )
        raise NotFoundException("cart not found", self.collection_name, cart_id, logger)

    async def delete_cart_async(self, cart_id: str, cache_store: str | None = None) -> None:
        """
        Remove a finished cart from the store it lives in.

        Only that store is touched, so an outage of the other one cannot stop the
        removal. A caller that does not know the store (None) clears both, MongoDB
        first.

        args:
            cart_id: str
            cache_store: the cart's cache_store, when the caller has the cart
        return:
            None
        exceptions:
            CartStoreUnavailableException if Redis could not be asked for a Redis cart
            whatever MongoDB raises for a MongoDB cart
        """
        if cache_store == CACHE_STORE_MONGODB:
            await self.delete_async({"cart_id": cart_id})
            return

        removed_from_db = False
        if cache_store is None:
            removed_from_db = await self.delete_async({"cart_id": cart_id})

        if not _breaker.allow_redis():
            if removed_from_db:
                return
            raise CartStoreUnavailableException(
                f"Cart {cart_id} could not be removed: the cart store (Redis) is unavailable", logger
            )
        try:
            await self.__redis_delete_async(cart_id)
            _breaker.record_success()
        except _RedisUnavailable as e:
            _breaker.record_failure()
            if removed_from_db:
                return
            raise CartStoreUnavailableException(
                f"Cart {cart_id} could not be removed: the cart store (Redis) is unavailable", logger, e
            ) from e

    def __with_terminal_staff(self, cart: CartDocument) -> CartDocument:
        # The cart service refuses a signed-out terminal before it reads a cart, so
        # staff is set here. Should a caller ever arrive without it, keep the staff
        # the cart already has (who created it) rather than fail on None.
        staff = self.terminal_info.staff if self.terminal_info is not None else None
        if staff is not None:
            cart.staff = CartDocument.Staff(id=staff.id, name=staff.name)
        return cart

    async def __redis_save_async(self, cart: CartDocument) -> None:
        # mode="json" so datetimes (created_at, the embedded promotion periods)
        # become ISO strings aiohttp's json encoder can write (issue #141).
        state_post_data = [{"key": cart.cart_id, "value": cart.model_dump(mode="json")}]

        async def post():
            session = await get_dapr_statestore_session()
            async with session.post(self.base_url_cartstore, json=state_post_data) as response:
                if response.status == 204:
                    return
                raise _unexpected_status("save", response.status, await response.text())

        await _with_retry(post)

    async def __redis_get_async(self, cart_id: str) -> CartDocument | None:
        async def get():
            session = await get_dapr_statestore_session()
            async with session.get(f"{self.base_url_cartstore}/{cart_id}") as response:
                if response.status == 200:
                    return CartDocument(**(await response.json()))
                # Dapr answers a missing key with 204 No Content.
                if response.status in (204, 404):
                    return None
                raise _unexpected_status("get", response.status, await response.text())

        return await _with_retry(get)

    async def __redis_delete_async(self, cart_id: str) -> None:
        async def delete():
            session = await get_dapr_statestore_session()
            async with session.delete(f"{self.base_url_cartstore}/{cart_id}") as response:
                if response.status in (200, 204):
                    return
                raise _unexpected_status("delete", response.status, await response.text())

        await _with_retry(delete)

    async def __save_cart_to_db_async(self, cart: CartDocument) -> None:
        """
        Upsert the cart into cache_cart (the MongoDB cart store).

        exceptions:
            UpdateNotWorkException / CannotCreateException if MongoDB refuses the write
        """
        search_dict = {"cart_id": cart.cart_id}
        cart.shard_key = self.__get_shard_key(cart)
        doc = await self.get_one_async(search_dict)
        if doc is not None:
            if not await self.update_one_async(search_dict, cart.model_dump()):
                raise UpdateNotWorkException("Failed to update cart", self.collection_name, cart.cart_id, logger)
        elif not await self.create_async(cart):
            raise CannotCreateException("Failed to create cart", self.collection_name, cart.cart_id, logger)

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
