"""Unit tests split out from test_repositories.py.

Shared helpers / imports preserved as-is from the original
test_repositories.py — splitting by repository class group keeps
each file under ~700 lines and lets pytest-xdist parallelise faster.
"""
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
import pytest_asyncio

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.documents.user_info_document import UserInfoDocument
from kugel_common.exceptions import (
    NotFoundException,
    LoadDataNoExistException,
    CannotCreateException,
)

from app.enums.cart_status import CartStatus
from app.models.documents.cart_document import CartDocument
from app.models.documents.tax_master_document import TaxMasterDocument
from app.models.documents.settings_master_document import SettingsMasterDocument
from app.models.documents.item_master_document import ItemMasterDocument
from app.models.documents.transaction_status_document import TransactionStatusDocument
from app.models.documents.tranlog_delivery_status_document import TranlogDeliveryStatus
from app.models.documents.terminal_counter_document import TerminalCounterDocument

from app.models.repositories.cart_repository import CartRepository
from app.models.repositories.transaction_status_repository import TransactionStatusRepository
from app.models.repositories.tranlog_delivery_status_repository import TranlogDeliveryStatusRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.terminal_counter_repository import (
    TerminalCounterRepository,
    make_terminal_id,
)
from app.models.repositories.tax_master_repository import TaxMasterRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_terminal_info(**overrides) -> TerminalInfoDocument:
    """Create a TerminalInfoDocument with sensible defaults."""
    defaults = dict(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        business_date="20240601",
        open_counter=1,
        staff=StaffMasterDocument(id="staff01", name="Test Staff"),
    )
    defaults.update(overrides)
    return TerminalInfoDocument(**defaults)


def _make_mock_db():
    """Return a MagicMock that behaves like AsyncIOMotorDatabase."""
    db = MagicMock()
    db.get_collection = MagicMock(return_value=MagicMock())
    db.client = MagicMock()
    return db


# =========================================================================
# CartRepository tests
# =========================================================================

def _make_aiohttp_context_manager(mock_response):
    """Wrap a mock response to behave as an aiohttp async context manager.

    aiohttp session methods (post/get/delete) return an object that supports
    ``async with`` directly (not a coroutine returning a context manager).
    Using MagicMock ensures the return value is synchronous while still
    supporting ``__aenter__``/``__aexit__``.
    """
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm



class TestCartRepositoryShardKey:
    """Tests for shard key generation in CartRepository."""

    def test_shard_key_format(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info(
            tenant_id="T001", store_code="S001", business_date="20240601"
        )
        repo = CartRepository(db, terminal_info)
        cart = CartDocument(
            tenant_id="T001", store_code="S001", business_date="20240601"
        )
        # Access the name-mangled private method
        key = repo._CartRepository__get_shard_key(cart)
        assert key == "T001_S001_20240601"

    def test_shard_key_with_different_values(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info(
            tenant_id="TENANT_X", store_code="STORE_Y", business_date="20250101"
        )
        repo = CartRepository(db, terminal_info)
        cart = CartDocument(
            tenant_id="TENANT_X", store_code="STORE_Y", business_date="20250101"
        )
        key = repo._CartRepository__get_shard_key(cart)
        assert key == "TENANT_X_STORE_Y_20250101"


class TestCartRepositoryCreateCart:
    """Tests for create_cart_async in CartRepository."""

    @pytest.mark.asyncio
    async def test_create_cart_sets_fields(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = CartRepository(db, terminal_info)

        cart = await repo.create_cart_async(
            transaction_type=1,
            user_id="user01",
            user_name="User One",
            store_name="Test Store",
            receipt_no=100,
            transaction_no=200,
            settings_master=[],
            tax_master=[],
            item_master=[],
        )

        assert isinstance(cart, CartDocument)
        assert cart.cart_id is not None and len(cart.cart_id) > 0
        assert cart.tenant_id == "T001"
        assert cart.store_code == "S001"
        assert cart.store_name == "Test Store"
        assert cart.terminal_no == 1
        assert cart.status == CartStatus.Initial.value
        assert cart.transaction_type == 1
        assert cart.transaction_no == 200
        assert cart.receipt_no == 100
        assert cart.receipt_text == ""
        assert cart.user.id == "user01"
        assert cart.user.name == "User One"
        assert cart.sales is not None
        assert cart.sales.reference_date_time is not None
        assert cart.business_date == "20240601"
        assert cart.shard_key == "T001_S001_20240601"
        assert cart.masters.settings == []
        assert cart.masters.taxes == []
        assert cart.masters.items == []
        assert cart.staff.id == "staff01"
        assert cart.staff.name == "Test Staff"

    @pytest.mark.asyncio
    async def test_create_cart_with_master_data(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = CartRepository(db, terminal_info)

        tax = TaxMasterDocument(tax_code="TAX10", rate=0.10)
        settings_doc = SettingsMasterDocument(name="setting1", default_value="val1")
        item = ItemMasterDocument(item_code="ITEM01", description="Test Item")

        cart = await repo.create_cart_async(
            transaction_type=2,
            user_id="u2",
            user_name="U2",
            store_name="S",
            receipt_no=1,
            transaction_no=1,
            settings_master=[settings_doc],
            tax_master=[tax],
            item_master=[item],
        )

        assert len(cart.masters.taxes) == 1
        assert cart.masters.taxes[0].tax_code == "TAX10"
        assert len(cart.masters.settings) == 1
        assert len(cart.masters.items) == 1



@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    monkeypatch.setattr("app.models.repositories.cart_repository.REDIS_RETRY_DELAYS", (0, 0))


def _repo():
    return CartRepository(_make_mock_db(), _make_terminal_info())


def _cart(cart_id="cart-1", **kw):
    return CartDocument(cart_id=cart_id, tenant_id="T001", store_code="S001", business_date="20240601", **kw)


def _response(status, json_data=None, text=""):
    r = AsyncMock()
    r.status = status
    r.text = AsyncMock(return_value=text)
    r.json = AsyncMock(return_value=json_data)
    return r


class _Dapr:
    """A Dapr state store stand-in: a dict, plus a switch to make it fail."""

    def __init__(self):
        self.data = {}
        self.down = False
        self.calls = []

    def _fail(self):
        import aiohttp

        raise aiohttp.ClientConnectionError("dapr down")

    def post(self, url, json=None):
        self.calls.append("post")
        if self.down:
            self._fail()
        for item in json:
            self.data[item["key"]] = item["value"]
        return _make_aiohttp_context_manager(_response(204))

    def get(self, url):
        self.calls.append("get")
        if self.down:
            self._fail()
        key = url.rsplit("/", 1)[-1]
        if key in self.data:
            return _make_aiohttp_context_manager(_response(200, json_data=self.data[key]))
        return _make_aiohttp_context_manager(_response(204))

    def delete(self, url):
        self.calls.append("delete")
        if self.down:
            self._fail()
        self.data.pop(url.rsplit("/", 1)[-1], None)
        return _make_aiohttp_context_manager(_response(204))


class _Mongo:
    """Stands in for the cache_cart collection through the repository's own helpers."""

    def __init__(self, repo):
        self.docs = {}

        async def get_one(search):
            return self.docs.get(search["cart_id"])

        async def create(doc):
            self.docs[doc.cart_id] = doc.model_copy(deep=True)
            return True

        async def update(search, data):
            self.docs[search["cart_id"]] = CartDocument(**data)
            return True

        async def delete(search):
            return self.docs.pop(search["cart_id"], None) is not None

        repo.get_one_async = get_one
        repo.create_async = create
        repo.update_one_async = update
        repo.delete_async = delete


@pytest.fixture
def stores():
    dapr = _Dapr()
    with patch("app.models.repositories.cart_repository.get_dapr_statestore_session", AsyncMock(return_value=dapr)):
        repo = _repo()
        mongo = _Mongo(repo)
        yield repo, dapr, mongo


def _open_breaker():
    from app.models.repositories.cart_repository import _breaker

    for _ in range(_breaker.FAILURE_THRESHOLD):
        _breaker.record_failure()
    assert _breaker.is_open


class TestWhereANewCartIsCreated:
    @pytest.mark.asyncio
    async def test_in_redis_normally(self, stores):
        repo, dapr, mongo = stores
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        assert cart.cache_store == "redis"
        assert "cart-1" in dapr.data and "cart-1" not in mongo.docs

    @pytest.mark.asyncio
    async def test_in_mongodb_while_the_breaker_is_open(self, stores):
        repo, dapr, mongo = stores
        _open_breaker()
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        assert cart.cache_store == "mongodb"
        assert "cart-1" in mongo.docs and dapr.calls == []

    @pytest.mark.asyncio
    async def test_in_mongodb_when_redis_fails_on_the_first_write(self, stores):
        # Nothing exists anywhere yet, so there is nothing to be stale against.
        repo, dapr, mongo = stores
        dapr.down = True
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        assert cart.cache_store == "mongodb"
        assert mongo.docs[cart.cart_id].cache_store == "mongodb"


class TestAmbiguousFirstWrite:
    @pytest.mark.asyncio
    async def test_a_new_cart_moved_to_mongodb_gets_a_new_id(self, stores):
        # The POST may have landed with only the answer lost; reusing the id would
        # leave a copy in Redis that a later read prefers over MongoDB.
        repo, dapr, mongo = stores
        real_post = dapr.post

        def lands_then_fails(url, json=None):
            real_post(url, json=json)
            dapr._fail()

        dapr.post = lands_then_fails
        cart = _cart("first")
        await repo.cache_cart_async(cart, isNew=True)

        assert cart.cart_id != "first"
        assert cart.cache_store == "mongodb"
        assert set(mongo.docs) == {cart.cart_id}
        assert "first" in dapr.data, "precondition: the orphan landed in Redis"
        assert cart.cart_id not in dapr.data


class TestRollingUpdate:
    @pytest.mark.asyncio
    async def test_a_mongodb_cart_copied_to_redis_by_an_old_replica_is_read_from_mongodb(self, stores):
        repo, dapr, _mongo = stores
        dapr.down = True
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        dapr.down = False
        # An old replica (no cache_store logic) writes its stale view to Redis.
        dapr.data[cart.cart_id] = cart.model_dump(mode="json")
        # The real cart moves on in MongoDB.
        newer = await repo.get_cached_cart_async(cart.cart_id)
        newer.line_items = [CartDocument.CartLineItem(item_code="A")]
        await repo.cache_cart_async(newer)

        read = await repo.get_cached_cart_async(cart.cart_id)
        assert [i.item_code for i in read.line_items] == ["A"]


class TestACartNeverMoves:
    @pytest.mark.asyncio
    async def test_a_redis_cart_whose_write_fails_is_refused_not_moved(self, stores):
        from app.exceptions import CartStoreUnavailableException

        repo, dapr, mongo = stores
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        cart.line_items = [CartDocument.CartLineItem(item_code="A")]
        dapr.down = True

        with pytest.raises(CartStoreUnavailableException):
            await repo.cache_cart_async(cart)

        assert "cart-1" not in mongo.docs, "a cart in mid-transaction was copied to MongoDB"
        assert dapr.data["cart-1"]["line_items"] == [], "the previous version must be what Redis keeps"

    @pytest.mark.asyncio
    async def test_a_redis_cart_is_refused_while_the_breaker_is_open(self, stores):
        from app.exceptions import CartStoreUnavailableException

        repo, dapr, mongo = stores
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        _open_breaker()
        dapr.calls.clear()

        with pytest.raises(CartStoreUnavailableException):
            await repo.cache_cart_async(cart)
        assert dapr.calls == [] and "cart-1" not in mongo.docs

    @pytest.mark.asyncio
    async def test_a_mongodb_cart_stays_in_mongodb_after_redis_recovers(self, stores):
        repo, dapr, mongo = stores
        dapr.down = True
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        dapr.down = False

        cart = await repo.get_cached_cart_async(cart.cart_id)
        cart.line_items = [CartDocument.CartLineItem(item_code="A")]
        await repo.cache_cart_async(cart)

        assert cart.cart_id not in dapr.data, "a MongoDB cart was written to Redis"
        assert mongo.docs[cart.cart_id].line_items[0].item_code == "A"


class TestReading:
    @pytest.mark.asyncio
    async def test_a_redis_cart_is_read_from_redis_only(self, stores):
        repo, _dapr, _mongo = stores
        await repo.cache_cart_async(_cart(), isNew=True)
        repo.get_one_async = AsyncMock(side_effect=AssertionError("MongoDB must not be read"))

        cart = await repo.get_cached_cart_async("cart-1")

        assert cart.cache_store == "redis"
        assert cart.staff.id == "staff01"

    @pytest.mark.asyncio
    async def test_a_mongodb_cart_is_found_after_a_redis_miss(self, stores):
        repo, dapr, _mongo = stores
        dapr.down = True
        created = _cart()
        await repo.cache_cart_async(created, isNew=True)
        dapr.down = False

        cart = await repo.get_cached_cart_async(created.cart_id)
        assert cart.cache_store == "mongodb"

    @pytest.mark.asyncio
    async def test_a_cart_in_neither_store_is_not_found(self, stores):
        repo, _dapr, _mongo = stores
        with pytest.raises(NotFoundException):
            await repo.get_cached_cart_async("nope")

    @pytest.mark.asyncio
    async def test_unreachable_redis_and_no_mongodb_copy_is_unavailable_not_not_found(self, stores):
        # The cart may well be in Redis: answering 404 would tell the till it is gone.
        from app.exceptions import CartStoreUnavailableException

        repo, dapr, _mongo = stores
        await repo.cache_cart_async(_cart(), isNew=True)
        dapr.down = True
        with pytest.raises(CartStoreUnavailableException):
            await repo.get_cached_cart_async("cart-1")

    @pytest.mark.asyncio
    async def test_while_the_breaker_is_open_redis_is_not_asked(self, stores):
        repo, dapr, _mongo = stores
        dapr.down = True
        created = _cart()
        await repo.cache_cart_async(created, isNew=True)
        _open_breaker()
        dapr.calls.clear()

        cart = await repo.get_cached_cart_async(created.cart_id)
        assert cart.cache_store == "mongodb" and dapr.calls == []

    @pytest.mark.asyncio
    async def test_a_legacy_copy_without_cache_store_read_from_mongodb_becomes_a_mongodb_cart(self, stores):
        repo, _dapr, mongo = stores
        mongo.docs["old"] = _cart("old")
        cart = await repo.get_cached_cart_async("old")
        assert cart.cache_store == "mongodb"


class TestNoStaleRead:
    """The reason a cart never moves: Redis can never hold an older copy of a MongoDB cart."""

    @pytest.mark.asyncio
    async def test_redis_recovering_does_not_resurface_anything(self, stores):
        repo, dapr, _mongo = stores
        # Created while Redis is down -> MongoDB; several updates there.
        dapr.down = True
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        cart_id = cart.cart_id
        for code in ("A", "B", "C"):
            cart = await repo.get_cached_cart_async(cart_id)
            cart.line_items = [*cart.line_items, CartDocument.CartLineItem(item_code=code)]
            await repo.cache_cart_async(cart)
        # Redis comes back, the breaker closes; another replica reads Redis first.
        dapr.down = False
        from app.models.repositories.cart_repository import reset_cart_store_breaker

        reset_cart_store_breaker()
        other_replica = _repo()
        other_replica.get_one_async = repo.get_one_async

        cart = await other_replica.get_cached_cart_async(cart_id)
        assert [i.item_code for i in cart.line_items] == ["A", "B", "C"]


class TestDelete:
    @pytest.mark.asyncio
    async def test_a_finished_cart_is_removed_from_both(self, stores):
        repo, dapr, mongo = stores
        await repo.cache_cart_async(_cart("r"), isNew=True)
        dapr.down = True
        m = _cart("m")
        await repo.cache_cart_async(m, isNew=True)
        dapr.down = False

        await repo.delete_cart_async("r")
        await repo.delete_cart_async(m.cart_id)
        assert dapr.data == {} and mongo.docs == {}

    @pytest.mark.asyncio
    async def test_a_mongodb_cart_is_removed_while_redis_is_down(self, stores):
        repo, dapr, mongo = stores
        dapr.down = True
        m = _cart("m")
        await repo.cache_cart_async(m, isNew=True)
        await repo.delete_cart_async(m.cart_id)
        assert mongo.docs == {}

    @pytest.mark.asyncio
    async def test_a_redis_cart_cannot_be_removed_while_redis_is_down(self, stores):
        from app.exceptions import CartStoreUnavailableException

        repo, dapr, _mongo = stores
        await repo.cache_cart_async(_cart("r"), isNew=True)
        dapr.down = True
        with pytest.raises(CartStoreUnavailableException):
            await repo.delete_cart_async("r")


class TestDeleteFailure:
    @pytest.mark.asyncio
    async def test_a_mongodb_outage_does_not_stop_removing_a_redis_cart(self, stores):
        repo, dapr, _mongo = stores
        await repo.cache_cart_async(_cart(), isNew=True)
        repo.delete_async = AsyncMock(side_effect=RuntimeError("mongo down"))

        await repo.delete_cart_async("cart-1", "redis")
        assert "cart-1" not in dapr.data

    @pytest.mark.asyncio
    async def test_a_redis_outage_does_not_stop_removing_a_mongodb_cart(self, stores):
        repo, dapr, mongo = stores
        dapr.down = True
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        _open_breaker()

        await repo.delete_cart_async(cart.cart_id, "mongodb")
        assert mongo.docs == {}

    @pytest.mark.asyncio
    async def test_without_the_store_mongodb_failure_leaves_redis_untouched(self, stores):
        repo, dapr, _mongo = stores
        await repo.cache_cart_async(_cart(), isNew=True)
        repo.delete_async = AsyncMock(side_effect=RuntimeError("mongo down"))

        with pytest.raises(RuntimeError):
            await repo.delete_cart_async("cart-1")
        assert "cart-1" in dapr.data

    @pytest.mark.asyncio
    async def test_a_mongodb_delete_failure_is_not_reported_as_success(self, stores):
        repo, dapr, _mongo = stores
        dapr.down = True
        cart = _cart()
        await repo.cache_cart_async(cart, isNew=True)
        dapr.down = False
        repo.delete_async = AsyncMock(side_effect=RuntimeError("mongo down"))

        with pytest.raises(RuntimeError):
            await repo.delete_cart_async(cart.cart_id, "mongodb")


class TestRetryAndBreaker:
    @pytest.mark.asyncio
    async def test_a_blip_is_retried(self, stores):
        repo, dapr, _mongo = stores
        await repo.cache_cart_async(_cart(), isNew=True)
        real_get = dapr.get
        failures = {"n": 1}

        def flaky(url):
            if failures["n"]:
                failures["n"] -= 1
                dapr._fail()
            return real_get(url)

        dapr.get = flaky
        cart = await repo.get_cached_cart_async("cart-1")
        assert cart.cart_id == "cart-1"

    @pytest.mark.asyncio
    async def test_a_5xx_is_retried_and_a_4xx_is_not(self, stores):
        from app.models.repositories.cart_repository import _RedisRefused, _RedisUnavailable, _with_retry

        calls = {"n": 0}

        async def five():
            calls["n"] += 1
            raise _RedisUnavailable("HTTP 500")

        with pytest.raises(_RedisUnavailable):
            await _with_retry(five)
        assert calls["n"] == 3

        calls["n"] = 0

        async def four():
            calls["n"] += 1
            raise _RedisRefused("HTTP 400")

        with pytest.raises(_RedisRefused):
            await _with_retry(four)
        assert calls["n"] == 1

    @pytest.mark.asyncio
    async def test_the_breaker_is_shared_across_repositories(self, stores):
        # The old breaker lived on the per-request repository and never opened.
        _, dapr, _mongo = stores
        dapr.down = True
        for i in range(3):
            other = _repo()
            _Mongo(other)
            await other.cache_cart_async(_cart(f"c{i}"), isNew=True)
        from app.models.repositories.cart_repository import _breaker

        assert _breaker.is_open

    def test_the_breaker_probes_once_after_the_timeout(self, monkeypatch):
        from app.models.repositories import cart_repository as m

        now = {"t": 1000.0}
        monkeypatch.setattr(m.time, "monotonic", lambda: now["t"])
        _open_breaker()
        assert m._breaker.allow_redis() is False
        now["t"] += m._CartStoreBreaker.RESET_TIMEOUT
        assert m._breaker.allow_redis() is True
        assert m._breaker.allow_redis() is False, "only one probe at a time"
        m._breaker.record_failure()
        assert m._breaker.allow_redis() is False, "a failed probe keeps it open"
        now["t"] += m._CartStoreBreaker.RESET_TIMEOUT
        assert m._breaker.allow_redis() is True
        m._breaker.record_success()
        assert not m._breaker.is_open


class TestRedisPayload:
    """Issue #141: the Dapr payload must be JSON-serializable and round-trip."""

    @pytest.mark.asyncio
    async def test_payload_is_json_and_round_trips(self, stores):
        import json

        from app.models.documents.promotion_master_document import PromotionMasterDocument

        repo, dapr, _mongo = stores
        cart = _cart()
        cart.created_at = datetime(2024, 6, 1, 9, 0, 0)
        cart.masters.promotions = [
            PromotionMasterDocument(start_datetime=datetime(2024, 6, 1), end_datetime=datetime(2024, 6, 30))
        ]
        await repo.cache_cart_async(cart, isNew=True)

        json.dumps(dapr.data["cart-1"])
        rebuilt = CartDocument(**dapr.data["cart-1"])
        assert rebuilt.created_at == cart.created_at
        assert rebuilt.masters.promotions[0].start_datetime == datetime(2024, 6, 1)
        assert rebuilt.cache_store == "redis"
