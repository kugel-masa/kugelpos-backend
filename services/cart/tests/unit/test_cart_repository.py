"""Unit tests split out from test_repositories.py.

Shared helpers / imports preserved as-is from the original
test_repositories.py — splitting by repository class group keeps
each file under ~700 lines and lets pytest-xdist parallelise faster.
"""
import time
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



class TestCartRepositoryCircuitBreaker:
    """Tests for the circuit breaker logic inside CartRepository."""

    def _make_repo(self, db=None):
        db = db or _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = CartRepository(db, terminal_info)
        return repo

    # -- _check_circuit_breaker --

    def test_circuit_closed_by_default(self):
        repo = self._make_repo()
        assert repo._check_circuit_breaker() is True

    def test_circuit_open_returns_false(self):
        repo = self._make_repo()
        repo._circuit_open = True
        repo._last_failure_time = time.time()
        assert repo._check_circuit_breaker() is False

    def test_circuit_resets_after_timeout(self):
        repo = self._make_repo()
        repo._circuit_open = True
        # Set failure time well beyond reset timeout
        repo._last_failure_time = time.time() - (repo._reset_timeout + 10)
        assert repo._check_circuit_breaker() is True
        assert repo._circuit_open is False
        assert repo._failure_count == 0

    # -- _record_failure / _open_circuit --

    def test_record_failure_increments_count(self):
        repo = self._make_repo()
        repo._record_failure()
        assert repo._failure_count == 1
        assert repo._circuit_open is False

    def test_record_failure_opens_circuit_at_threshold(self):
        repo = self._make_repo()
        for _ in range(repo._failure_threshold):
            repo._record_failure()
        assert repo._circuit_open is True
        assert repo._failure_count == repo._failure_threshold

    def test_record_failure_does_not_open_circuit_below_threshold(self):
        repo = self._make_repo()
        for _ in range(repo._failure_threshold - 1):
            repo._record_failure()
        assert repo._circuit_open is False

    # -- _record_success --

    def test_record_success_resets_failure_count(self):
        repo = self._make_repo()
        repo._failure_count = 2
        repo._record_success()
        assert repo._failure_count == 0
        assert repo._circuit_open is False

    def test_record_success_closes_open_circuit(self):
        repo = self._make_repo()
        repo._circuit_open = True
        repo._failure_count = 3
        repo._record_success()
        assert repo._circuit_open is False
        assert repo._failure_count == 0

    # -- _open_circuit --

    def test_open_circuit_sets_state(self):
        repo = self._make_repo()
        before = time.time()
        repo._open_circuit()
        after = time.time()
        assert repo._circuit_open is True
        assert before <= repo._last_failure_time <= after


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


class TestCartRepositoryCacheCartAsync:
    """Tests for cache_cart_async / get_cached_cart_async / delete_cart_async with circuit breaker integration."""

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = CartRepository(db, terminal_info)
        return repo

    @pytest.mark.asyncio
    async def test_cache_cart_falls_back_to_db_when_circuit_open(self):
        repo = self._make_repo()
        repo._circuit_open = True
        repo._last_failure_time = time.time()

        cart = CartDocument(cart_id="cart-123", tenant_id="T001", store_code="S001", business_date="20240601")

        # Mock the private __save_cart_to_db_async method
        repo._CartRepository__save_cart_to_db_async = AsyncMock()

        await repo.cache_cart_async(cart)

        repo._CartRepository__save_cart_to_db_async.assert_awaited_once_with(cart)

    @pytest.mark.asyncio
    async def test_cache_cart_records_success_on_dapr_success(self):
        repo = self._make_repo()
        repo._failure_count = 2

        cart = CartDocument(cart_id="cart-456", tenant_id="T001", store_code="S001", business_date="20240601")

        # Mock the private __cache_cart_async to succeed
        repo._CartRepository__cache_cart_async = AsyncMock()

        await repo.cache_cart_async(cart)

        assert repo._failure_count == 0
        assert repo._circuit_open is False

    @pytest.mark.asyncio
    async def test_cache_cart_records_failure_and_falls_back_on_exception(self):
        repo = self._make_repo()

        cart = CartDocument(cart_id="cart-789", tenant_id="T001", store_code="S001", business_date="20240601")

        # Mock Dapr cache to fail
        repo._CartRepository__cache_cart_async = AsyncMock(side_effect=Exception("Dapr down"))
        repo._CartRepository__save_cart_to_db_async = AsyncMock()

        await repo.cache_cart_async(cart)

        assert repo._failure_count == 1
        repo._CartRepository__save_cart_to_db_async.assert_awaited_once_with(cart)

    @pytest.mark.asyncio
    async def test_get_cached_cart_falls_back_to_db_when_circuit_open(self):
        repo = self._make_repo()
        repo._circuit_open = True
        repo._last_failure_time = time.time()

        expected_cart = CartDocument(cart_id="cart-abc")
        repo._CartRepository__get_cart_from_db_async = AsyncMock(return_value=expected_cart)

        result = await repo.get_cached_cart_async("cart-abc")

        assert result == expected_cart

    @pytest.mark.asyncio
    async def test_get_cached_cart_falls_back_on_exception(self):
        repo = self._make_repo()

        expected_cart = CartDocument(cart_id="cart-def")
        repo._CartRepository__get_cached_cart_async = AsyncMock(side_effect=Exception("cache error"))
        repo._CartRepository__get_cart_from_db_async = AsyncMock(return_value=expected_cart)

        result = await repo.get_cached_cart_async("cart-def")

        assert result == expected_cart
        assert repo._failure_count == 1

    @pytest.mark.asyncio
    async def test_delete_cart_falls_back_to_db_when_circuit_open(self):
        repo = self._make_repo()
        repo._circuit_open = True
        repo._last_failure_time = time.time()

        repo._CartRepository__delete_cart_from_db_async = AsyncMock()

        await repo.delete_cart_async("cart-xyz")

        repo._CartRepository__delete_cart_from_db_async.assert_awaited_once_with("cart-xyz")


# =========================================================================
# TransactionStatusRepository tests
# =========================================================================



class TestCartRepositoryDaprCacheAsync:
    """Tests for the private __cache_cart_async method (Dapr state store POST)."""

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        return CartRepository(db, terminal_info)

    def _make_mock_response(self, status_code, json_data=None, text=""):
        mock_response = AsyncMock()
        mock_response.status = status_code
        mock_response.text = AsyncMock(return_value=text)
        if json_data is not None:
            mock_response.json = AsyncMock(return_value=json_data)
        return mock_response

    @pytest.mark.asyncio
    async def test_cache_cart_success(self):
        repo = self._make_repo()
        cart = CartDocument(cart_id="cart-dapr-01", tenant_id="T001", store_code="S001", business_date="20240601")

        mock_response = self._make_mock_response(204)
        mock_session = MagicMock()
        mock_session.post.return_value = _make_aiohttp_context_manager(mock_response)

        with patch(
            "app.models.repositories.cart_repository.get_dapr_statestore_session",
            return_value=mock_session,
        ):
            await repo._CartRepository__cache_cart_async(cart)

        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_cart_non_204_raises_update_not_work(self):
        from app.exceptions import UpdateNotWorkException

        repo = self._make_repo()
        cart = CartDocument(cart_id="cart-dapr-02", tenant_id="T001", store_code="S001", business_date="20240601")

        mock_response = self._make_mock_response(500, text="Internal error")
        mock_session = MagicMock()
        mock_session.post.return_value = _make_aiohttp_context_manager(mock_response)

        with patch(
            "app.models.repositories.cart_repository.get_dapr_statestore_session",
            return_value=mock_session,
        ):
            with pytest.raises(UpdateNotWorkException):
                await repo._CartRepository__cache_cart_async(cart)

    @pytest.mark.asyncio
    async def test_cache_cart_400_state_store_not_found(self):
        from app.exceptions import UpdateNotWorkException

        repo = self._make_repo()
        cart = CartDocument(cart_id="cart-dapr-03", tenant_id="T001", store_code="S001", business_date="20240601")

        mock_response = self._make_mock_response(
            400,
            json_data={"errorCode": "ERR_STATE_STORE_NOT_FOUND", "message": "state store not found"},
            text="",
        )
        mock_session = MagicMock()
        mock_session.post.return_value = _make_aiohttp_context_manager(mock_response)

        with patch(
            "app.models.repositories.cart_repository.get_dapr_statestore_session",
            return_value=mock_session,
        ):
            with pytest.raises(UpdateNotWorkException):
                await repo._CartRepository__cache_cart_async(cart)


class TestCartRepositoryCacheJsonSerialization:
    """Regression tests for issue #141: the Dapr/Redis cache payload must be JSON-serializable.

    Before the fix, __cache_cart_async called cart.model_dump() (no mode="json"), leaving
    datetime objects in the payload. aiohttp's stdlib json encoder then raised
    "Object of type datetime is not JSON serializable" on every write, silently falling
    back to MongoDB. These tests assert the posted payload survives json.dumps.
    """

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        return CartRepository(db, terminal_info)

    def _make_cart_with_datetimes(self) -> CartDocument:
        from app.models.documents.promotion_master_document import PromotionMasterDocument

        cart = CartDocument(cart_id="cart-dt-01", tenant_id="T001", store_code="S001", business_date="20240601")
        # Base document datetimes (always present in practice).
        cart.created_at = datetime(2024, 6, 1, 9, 0, 0)
        cart.updated_at = datetime(2024, 6, 1, 9, 5, 0)
        # Embedded master snapshot also carries datetimes.
        cart.masters.promotions = [
            PromotionMasterDocument(
                start_datetime=datetime(2024, 6, 1, 0, 0, 0),
                end_datetime=datetime(2024, 6, 30, 23, 59, 59),
            )
        ]
        return cart

    @pytest.mark.asyncio
    async def test_cache_payload_is_json_serializable(self):
        import json

        repo = self._make_repo()
        cart = self._make_cart_with_datetimes()

        captured = {}

        def _capture_post(url, json=None):
            captured["json"] = json
            return _make_aiohttp_context_manager(AsyncMock(status=204, text=AsyncMock(return_value="")))

        mock_session = MagicMock()
        mock_session.post.side_effect = _capture_post

        with patch(
            "app.models.repositories.cart_repository.get_dapr_statestore_session",
            return_value=mock_session,
        ):
            await repo._CartRepository__cache_cart_async(cart)

        # The core assertion: the payload aiohttp would encode must not raise.
        # (With the pre-fix model_dump(), this raises TypeError on the datetime fields.)
        json.dumps(captured["json"])
        value = captured["json"][0]["value"]
        assert isinstance(value["created_at"], str)
        assert isinstance(value["masters"]["promotions"][0]["start_datetime"], str)

    @pytest.mark.asyncio
    async def test_cache_payload_round_trips_back_to_datetime(self):
        repo = self._make_repo()
        cart = self._make_cart_with_datetimes()

        captured = {}

        def _capture_post(url, json=None):
            captured["json"] = json
            return _make_aiohttp_context_manager(AsyncMock(status=204, text=AsyncMock(return_value="")))

        mock_session = MagicMock()
        mock_session.post.side_effect = _capture_post

        with patch(
            "app.models.repositories.cart_repository.get_dapr_statestore_session",
            return_value=mock_session,
        ):
            await repo._CartRepository__cache_cart_async(cart)

        # __get_cached_cart_async rebuilds via CartDocument(**cart_data); pydantic must
        # parse the ISO strings back into datetimes, preserving the original values.
        rebuilt = CartDocument(**captured["json"][0]["value"])
        assert rebuilt.created_at == cart.created_at
        assert rebuilt.masters.promotions[0].start_datetime == cart.masters.promotions[0].start_datetime


class TestCartRepositoryDeleteFallbackCleanup:
    """Tests for issue #141 secondary fix: delete must also remove the MongoDB fallback copy."""

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        return CartRepository(db, terminal_info)

    @pytest.mark.asyncio
    async def test_delete_removes_redis_and_db_fallback_copy(self):
        repo = self._make_repo()
        repo._CartRepository__delete_cached_cart_async = AsyncMock()
        repo.delete_async = AsyncMock(return_value=True)

        await repo.delete_cart_async("cart-cleanup-01")

        repo._CartRepository__delete_cached_cart_async.assert_awaited_once_with("cart-cleanup-01")
        repo.delete_async.assert_awaited_once_with({"cart_id": "cart-cleanup-01"})

    @pytest.mark.asyncio
    async def test_db_fallback_cleanup_failure_does_not_break_delete(self):
        repo = self._make_repo()
        repo._CartRepository__delete_cached_cart_async = AsyncMock()
        repo.delete_async = AsyncMock(side_effect=Exception("db down"))

        # Cleanup failure must be swallowed: the cache delete already succeeded.
        await repo.delete_cart_async("cart-cleanup-02")

        repo._CartRepository__delete_cached_cart_async.assert_awaited_once_with("cart-cleanup-02")
        assert repo._circuit_open is False

    @pytest.mark.asyncio
    async def test_delete_does_not_clean_db_when_circuit_open(self):
        repo = self._make_repo()
        repo._circuit_open = True
        repo._last_failure_time = time.time()
        repo._CartRepository__delete_cart_from_db_async = AsyncMock()
        repo.delete_async = AsyncMock()

        await repo.delete_cart_async("cart-cleanup-03")

        # Circuit-open path deletes directly from DB; the extra best-effort cleanup
        # is only for the cache-success path and must not run here.
        repo._CartRepository__delete_cart_from_db_async.assert_awaited_once_with("cart-cleanup-03")
        repo.delete_async.assert_not_awaited()


class TestCartRepositoryDaprGetCachedAsync:
    """Tests for the private __get_cached_cart_async method (Dapr state store GET)."""

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        return CartRepository(db, terminal_info)

    def _make_mock_response(self, status_code, json_data=None):
        mock_response = AsyncMock()
        mock_response.status = status_code
        if json_data is not None:
            mock_response.json = AsyncMock(return_value=json_data)
        return mock_response

    @pytest.mark.asyncio
    async def test_get_cached_cart_success(self):
        repo = self._make_repo()

        cart_data = CartDocument(
            cart_id="cart-get-01", tenant_id="T001", store_code="S001", business_date="20240601"
        ).model_dump()

        mock_response = self._make_mock_response(200, json_data=cart_data)
        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_context_manager(mock_response)

        with patch(
            "app.models.repositories.cart_repository.get_dapr_statestore_session",
            return_value=mock_session,
        ):
            result = await repo._CartRepository__get_cached_cart_async("cart-get-01")

        assert isinstance(result, CartDocument)
        assert result.cart_id == "cart-get-01"
        # Staff should be overwritten from terminal_info
        assert result.staff.id == "staff01"
        assert result.staff.name == "Test Staff"

    @pytest.mark.asyncio
    async def test_get_cached_cart_not_found_raises(self):
        repo = self._make_repo()

        mock_response = self._make_mock_response(404)
        mock_session = MagicMock()
        mock_session.get.return_value = _make_aiohttp_context_manager(mock_response)

        with patch(
            "app.models.repositories.cart_repository.get_dapr_statestore_session",
            return_value=mock_session,
        ):
            with pytest.raises(NotFoundException):
                await repo._CartRepository__get_cached_cart_async("nonexistent")


class TestCartRepositoryDaprDeleteCachedAsync:
    """Tests for the private __delete_cached_cart_async method (Dapr state store DELETE)."""

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        return CartRepository(db, terminal_info)

    def _make_mock_response(self, status_code):
        mock_response = AsyncMock()
        mock_response.status = status_code
        return mock_response

    @pytest.mark.asyncio
    async def test_delete_cached_cart_success(self):
        repo = self._make_repo()

        mock_response = self._make_mock_response(204)
        mock_session = MagicMock()
        mock_session.delete.return_value = _make_aiohttp_context_manager(mock_response)

        with patch(
            "app.models.repositories.cart_repository.get_dapr_statestore_session",
            return_value=mock_session,
        ):
            result = await repo._CartRepository__delete_cached_cart_async("cart-del-01")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_cached_cart_not_found_raises(self):
        from app.exceptions import CannotDeleteException

        repo = self._make_repo()

        mock_response = self._make_mock_response(404)
        mock_session = MagicMock()
        mock_session.delete.return_value = _make_aiohttp_context_manager(mock_response)

        with patch(
            "app.models.repositories.cart_repository.get_dapr_statestore_session",
            return_value=mock_session,
        ):
            with pytest.raises(CannotDeleteException):
                await repo._CartRepository__delete_cached_cart_async("cart-del-02")


class TestCartRepositoryDBFallbackSave:
    """Tests for the private __save_cart_to_db_async method."""

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        return CartRepository(db, terminal_info)

    @pytest.mark.asyncio
    async def test_save_cart_creates_new_when_not_exists(self):
        repo = self._make_repo()
        repo.get_one_async = AsyncMock(return_value=None)
        repo.create_async = AsyncMock(return_value=True)

        cart = CartDocument(cart_id="cart-db-01", tenant_id="T001", store_code="S001", business_date="20240601")
        await repo._CartRepository__save_cart_to_db_async(cart)

        repo.create_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_cart_updates_when_exists(self):
        repo = self._make_repo()
        existing = CartDocument(cart_id="cart-db-02")
        repo.get_one_async = AsyncMock(return_value=existing)
        repo.update_one_async = AsyncMock(return_value=True)

        cart = CartDocument(cart_id="cart-db-02", tenant_id="T001", store_code="S001", business_date="20240601")
        await repo._CartRepository__save_cart_to_db_async(cart)

        repo.update_one_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_cart_update_failure_raises(self):
        from app.exceptions import UpdateNotWorkException

        repo = self._make_repo()
        existing = CartDocument(cart_id="cart-db-03")
        repo.get_one_async = AsyncMock(return_value=existing)
        repo.update_one_async = AsyncMock(return_value=False)

        cart = CartDocument(cart_id="cart-db-03", tenant_id="T001", store_code="S001", business_date="20240601")

        with pytest.raises(UpdateNotWorkException):
            await repo._CartRepository__save_cart_to_db_async(cart)

    @pytest.mark.asyncio
    async def test_save_cart_create_failure_raises(self):
        from app.exceptions import CannotCreateException

        repo = self._make_repo()
        repo.get_one_async = AsyncMock(return_value=None)
        repo.create_async = AsyncMock(return_value=False)

        cart = CartDocument(cart_id="cart-db-04", tenant_id="T001", store_code="S001", business_date="20240601")

        with pytest.raises(CannotCreateException):
            await repo._CartRepository__save_cart_to_db_async(cart)


class TestCartRepositoryDBFallbackGet:
    """Tests for the private __get_cart_from_db_async method."""

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        return CartRepository(db, terminal_info)

    @pytest.mark.asyncio
    async def test_get_cart_from_db_success(self):
        repo = self._make_repo()
        expected = CartDocument(cart_id="cart-dbget-01")
        repo.get_one_async = AsyncMock(return_value=expected)

        result = await repo._CartRepository__get_cart_from_db_async("cart-dbget-01")

        assert result.cart_id == "cart-dbget-01"
        repo.get_one_async.assert_awaited_once_with({"cart_id": "cart-dbget-01"})

    @pytest.mark.asyncio
    async def test_get_cart_from_db_not_found_raises(self):
        repo = self._make_repo()
        repo.get_one_async = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await repo._CartRepository__get_cart_from_db_async("nonexistent")


class TestCartRepositoryDBFallbackDelete:
    """Tests for the private __delete_cart_from_db_async method."""

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        return CartRepository(db, terminal_info)

    @pytest.mark.asyncio
    async def test_delete_cart_from_db_success(self):
        repo = self._make_repo()
        repo.delete_async = AsyncMock(return_value=True)

        result = await repo._CartRepository__delete_cart_from_db_async("cart-dbdel-01")

        assert result is None
        repo.delete_async.assert_awaited_once_with({"cart_id": "cart-dbdel-01"})

    @pytest.mark.asyncio
    async def test_delete_cart_from_db_not_found_raises(self):
        from app.exceptions import CannotDeleteException

        repo = self._make_repo()
        repo.delete_async = AsyncMock(return_value=False)

        with pytest.raises(CannotDeleteException):
            await repo._CartRepository__delete_cart_from_db_async("nonexistent")

    @pytest.mark.asyncio
    async def test_delete_cart_from_db_exception_raises_cannot_delete(self):
        from app.exceptions import CannotDeleteException

        repo = self._make_repo()
        repo.delete_async = AsyncMock(side_effect=Exception("DB error"))

        with pytest.raises(CannotDeleteException):
            await repo._CartRepository__delete_cart_from_db_async("cart-dbdel-err")


class TestCartRepositoryDeleteCartAsync:
    """Tests for delete_cart_async with circuit breaker and Dapr/DB interaction."""

    def _make_repo(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        return CartRepository(db, terminal_info)

    @pytest.mark.asyncio
    async def test_delete_cart_success_records_success(self):
        repo = self._make_repo()
        repo._failure_count = 2
        repo._CartRepository__delete_cached_cart_async = AsyncMock()
        repo.delete_async = AsyncMock()  # best-effort MongoDB fallback cleanup

        await repo.delete_cart_async("cart-del-ok")

        assert repo._failure_count == 0
        assert repo._circuit_open is False

    @pytest.mark.asyncio
    async def test_delete_cart_dapr_failure_records_failure_and_raises(self):
        repo = self._make_repo()
        repo._CartRepository__delete_cached_cart_async = AsyncMock(side_effect=Exception("Dapr error"))

        with pytest.raises(Exception, match="Dapr error"):
            await repo.delete_cart_async("cart-del-fail")

        assert repo._failure_count == 1

    @pytest.mark.asyncio
    async def test_delete_cart_circuit_open_db_failure_raises(self):
        repo = self._make_repo()
        repo._circuit_open = True
        repo._last_failure_time = time.time()
        repo._CartRepository__delete_cart_from_db_async = AsyncMock(side_effect=Exception("DB error"))

        with pytest.raises(Exception, match="DB error"):
            await repo.delete_cart_async("cart-del-dbfail")
