"""
Unit tests for the repository layer of the cart service.

Tests cover:
- CartRepository: circuit breaker state transitions, shard key generation, cart creation
- TransactionStatusRepository: void/refund state preservation, bulk queries
- TranlogDeliveryStatusRepository: status creation, pending delivery queries, service status updates
- TranlogRepository: dynamic query building, shard key generation
- TerminalCounterRepository: atomic counter numbering
- TaxMasterRepository: cache loading, tax lookup by code
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


class TestTransactionStatusRepository:
    """Tests for TransactionStatusRepository business logic."""

    def _make_repo(self, db=None):
        db = db or _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TransactionStatusRepository(db, terminal_info)
        return repo

    @pytest.mark.asyncio
    async def test_mark_as_voided_creates_new_when_no_existing(self):
        repo = self._make_repo()
        repo.get_one_async = AsyncMock(return_value=None)
        repo.create_async = AsyncMock(return_value=True)

        result = await repo.mark_as_voided_async(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            void_transaction_no=101,
            staff_id="staff01",
        )

        assert result.is_voided is True
        assert result.void_transaction_no == 101
        assert result.void_staff_id == "staff01"
        assert result.tenant_id == "T001"
        assert result.transaction_no == 100
        repo.create_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_as_voided_preserves_refund_info_on_existing(self):
        repo = self._make_repo()

        existing = TransactionStatusDocument(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            is_refunded=True,
            return_transaction_no=50,
            return_date_time="2024-06-01T10:00:00",
            return_staff_id="staff_ret",
        )

        # First call returns existing, second call (after update) returns updated
        updated = TransactionStatusDocument(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            is_voided=True,
            is_refunded=True,
            void_transaction_no=101,
            return_transaction_no=50,
        )
        repo.get_one_async = AsyncMock(side_effect=[existing, updated])
        repo.update_one_async = AsyncMock(return_value=True)

        result = await repo.mark_as_voided_async(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            void_transaction_no=101,
            staff_id="staff01",
        )

        # Verify update was called with preserved refund fields
        update_call_args = repo.update_one_async.call_args
        update_values = update_call_args[0][1]
        assert update_values["is_voided"] is True
        assert update_values["is_refunded"] is True
        assert update_values["return_transaction_no"] == 50
        assert update_values["return_date_time"] == "2024-06-01T10:00:00"
        assert update_values["return_staff_id"] == "staff_ret"

    @pytest.mark.asyncio
    async def test_mark_as_refunded_creates_new_when_no_existing(self):
        repo = self._make_repo()
        repo.get_one_async = AsyncMock(return_value=None)
        repo.create_async = AsyncMock(return_value=True)

        result = await repo.mark_as_refunded_async(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            return_transaction_no=102,
            staff_id="staff02",
        )

        assert result.is_refunded is True
        assert result.return_transaction_no == 102
        assert result.return_staff_id == "staff02"
        repo.create_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_as_refunded_preserves_void_info_on_existing(self):
        repo = self._make_repo()

        existing = TransactionStatusDocument(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            is_voided=True,
            void_transaction_no=90,
            void_date_time="2024-05-01T09:00:00",
            void_staff_id="staff_void",
        )

        updated = TransactionStatusDocument(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            is_voided=True,
            is_refunded=True,
        )
        repo.get_one_async = AsyncMock(side_effect=[existing, updated])
        repo.update_one_async = AsyncMock(return_value=True)

        result = await repo.mark_as_refunded_async(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            return_transaction_no=102,
            staff_id="staff02",
        )

        update_call_args = repo.update_one_async.call_args
        update_values = update_call_args[0][1]
        assert update_values["is_refunded"] is True
        assert update_values["is_voided"] is True
        assert update_values["void_transaction_no"] == 90
        assert update_values["void_date_time"] == "2024-05-01T09:00:00"
        assert update_values["void_staff_id"] == "staff_void"

    @pytest.mark.asyncio
    async def test_get_status_for_transactions_builds_in_query(self):
        repo = self._make_repo()

        status1 = TransactionStatusDocument(
            tenant_id="T001", store_code="S001", terminal_no=1, transaction_no=10
        )
        status2 = TransactionStatusDocument(
            tenant_id="T001", store_code="S001", terminal_no=1, transaction_no=20
        )
        repo.get_list_async = AsyncMock(return_value=[status1, status2])

        result = await repo.get_status_for_transactions_async(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_nos=[10, 20, 30],
        )

        # Verify query contains $in operator
        query = repo.get_list_async.call_args[0][0]
        assert query["transaction_no"] == {"$in": [10, 20, 30]}
        assert query["tenant_id"] == "T001"
        assert query["store_code"] == "S001"
        assert query["terminal_no"] == 1

        # Verify result is a dictionary keyed by transaction_no
        assert isinstance(result, dict)
        assert 10 in result
        assert 20 in result
        assert 30 not in result

    @pytest.mark.asyncio
    async def test_get_status_for_transactions_returns_empty_dict_when_none_found(self):
        repo = self._make_repo()
        repo.get_list_async = AsyncMock(return_value=[])

        result = await repo.get_status_for_transactions_async(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_nos=[99],
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_reset_refund_status_clears_refund_fields(self):
        repo = self._make_repo()

        existing = TransactionStatusDocument(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            is_refunded=True,
            return_transaction_no=50,
        )
        updated = TransactionStatusDocument(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            is_refunded=False,
        )
        repo.get_one_async = AsyncMock(side_effect=[existing, updated])
        repo.update_one_async = AsyncMock(return_value=True)

        result = await repo.reset_refund_status_async(
            tenant_id="T001", store_code="S001", terminal_no=1, transaction_no=100
        )

        update_call_args = repo.update_one_async.call_args
        update_values = update_call_args[0][1]
        assert update_values["is_refunded"] is False
        assert update_values["return_transaction_no"] is None
        assert update_values["return_date_time"] is None
        assert update_values["return_staff_id"] is None

    @pytest.mark.asyncio
    async def test_reset_refund_status_returns_none_when_no_existing(self):
        repo = self._make_repo()
        repo.get_one_async = AsyncMock(return_value=None)

        result = await repo.reset_refund_status_async(
            tenant_id="T001", store_code="S001", terminal_no=1, transaction_no=999
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_status_by_transaction_builds_correct_query(self):
        repo = self._make_repo()
        repo.get_one_async = AsyncMock(return_value=None)

        await repo.get_status_by_transaction_async("T001", "S001", 1, 100)

        query = repo.get_one_async.call_args[0][0]
        assert query == {
            "tenant_id": "T001",
            "store_code": "S001",
            "terminal_no": 1,
            "transaction_no": 100,
        }


# =========================================================================
# TranlogDeliveryStatusRepository tests
# =========================================================================


class TestTranlogDeliveryStatusRepository:
    """Tests for TranlogDeliveryStatusRepository."""

    def _make_repo(self, db=None):
        db = db or _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TranlogDeliveryStatusRepository(db, terminal_info)
        return repo

    @pytest.mark.asyncio
    async def test_create_status_constructs_service_status_list(self):
        repo = self._make_repo()
        repo.create_async = AsyncMock(return_value=True)

        services = [
            {"service_name": "report", "status": "pending"},
            {"service_name": "journal", "status": "pending"},
        ]

        result = await repo.create_status_async(
            event_id="evt-001",
            transaction_no=100,
            payload={"data": "test"},
            services=services,
        )

        assert result is True
        created_doc = repo.create_async.call_args[0][0]
        assert isinstance(created_doc, TranlogDeliveryStatus)
        assert created_doc.event_id == "evt-001"
        assert created_doc.transaction_no == 100
        assert created_doc.tenant_id == "T001"
        assert created_doc.store_code == "S001"
        assert created_doc.terminal_no == 1
        assert created_doc.business_date == "20240601"
        assert created_doc.open_counter == 1
        assert created_doc.status == "published"
        assert len(created_doc.services) == 2
        assert created_doc.services[0].service_name == "report"
        assert created_doc.services[1].service_name == "journal"

    @pytest.mark.asyncio
    async def test_create_status_with_no_services(self):
        repo = self._make_repo()
        repo.create_async = AsyncMock(return_value=True)

        await repo.create_status_async(
            event_id="evt-002",
            transaction_no=200,
            payload={},
            services=None,
        )

        created_doc = repo.create_async.call_args[0][0]
        assert created_doc.services == []

    @pytest.mark.asyncio
    async def test_find_pending_deliveries_builds_correct_query(self):
        repo = self._make_repo()
        repo.get_list_async = AsyncMock(return_value=[])

        await repo.find_pending_deliveries(hours_ago=12)

        query = repo.get_list_async.call_args[0][0]
        assert "published_at" in query
        assert "$gte" in query["published_at"]
        assert query["status"] == {"$nin": ["delivered"]}

    @pytest.mark.asyncio
    async def test_find_pending_deliveries_default_hours(self):
        repo = self._make_repo()
        repo.get_list_async = AsyncMock(return_value=[])

        await repo.find_pending_deliveries()

        query = repo.get_list_async.call_args[0][0]
        threshold = query["published_at"]["$gte"]
        assert isinstance(threshold, datetime)

    @pytest.mark.asyncio
    async def test_find_by_event_id_uses_correct_filter(self):
        repo = self._make_repo()
        repo.get_one_async = AsyncMock(return_value=None)

        await repo.find_by_event_id("evt-xyz")

        repo.get_one_async.assert_awaited_once_with({"event_id": "evt-xyz"})

    @pytest.mark.asyncio
    async def test_find_by_transaction_info_uses_correct_filter(self):
        repo = self._make_repo()
        repo.get_list_async = AsyncMock(return_value=[])

        await repo.find_by_transaction_info("T001", "S001", 1, 100)

        expected_filter = {
            "tenant_id": "T001",
            "store_code": "S001",
            "terminal_no": 1,
            "transaction_no": 100,
        }
        repo.get_list_async.assert_awaited_once_with(expected_filter)

    @pytest.mark.asyncio
    async def test_find_by_business_date_uses_correct_filter(self):
        repo = self._make_repo()
        repo.get_list_async = AsyncMock(return_value=[])

        await repo.find_by_business_date("T001", "S001", "20240601")

        expected_filter = {
            "tenant_id": "T001",
            "store_code": "S001",
            "business_date": "20240601",
        }
        repo.get_list_async.assert_awaited_once_with(expected_filter)

    @pytest.mark.asyncio
    async def test_update_service_status_builds_array_filter(self):
        repo = self._make_repo()

        # Set up mock collection
        mock_collection = MagicMock()
        mock_update_result = MagicMock()
        mock_update_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        repo.dbcollection = mock_collection

        # Mock find_by_event_id to return a doc with all services delivered
        delivered_doc = TranlogDeliveryStatus(
            event_id="evt-001",
            published_at=datetime.now(),
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            business_date="20240601",
            open_counter=1,
            payload={},
            services=[
                TranlogDeliveryStatus.ServiceStatus(service_name="report", status="delivered"),
                TranlogDeliveryStatus.ServiceStatus(service_name="journal", status="delivered"),
            ],
            last_updated_at=datetime.now(),
        )
        repo.find_by_event_id = AsyncMock(return_value=delivered_doc)
        repo.update_delivery_status = AsyncMock(return_value=True)

        result = await repo.update_service_status(
            event_id="evt-001",
            service_name="report",
            status="delivered",
        )

        assert result is True
        # Verify array filter was passed
        update_call = mock_collection.update_one.call_args
        assert update_call.kwargs["array_filters"] == [{"elem.service_name": "report"}]
        # Overall status should be set to delivered since all services are delivered
        repo.update_delivery_status.assert_awaited_once_with("evt-001", "delivered")

    @pytest.mark.asyncio
    async def test_update_service_status_sets_partially_delivered_on_failure(self):
        repo = self._make_repo()

        mock_collection = MagicMock()
        mock_update_result = MagicMock()
        mock_update_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        repo.dbcollection = mock_collection

        failed_doc = TranlogDeliveryStatus(
            event_id="evt-002",
            published_at=datetime.now(),
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            business_date="20240601",
            open_counter=1,
            payload={},
            services=[
                TranlogDeliveryStatus.ServiceStatus(service_name="report", status="delivered"),
                TranlogDeliveryStatus.ServiceStatus(service_name="journal", status="failed"),
            ],
            last_updated_at=datetime.now(),
        )
        repo.find_by_event_id = AsyncMock(return_value=failed_doc)
        repo.update_delivery_status = AsyncMock(return_value=True)

        await repo.update_service_status(
            event_id="evt-002",
            service_name="journal",
            status="failed",
        )

        repo.update_delivery_status.assert_awaited_once_with("evt-002", "partially_delivered")

    @pytest.mark.asyncio
    async def test_update_service_status_sets_published_when_pending_exists(self):
        repo = self._make_repo()

        mock_collection = MagicMock()
        mock_update_result = MagicMock()
        mock_update_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        repo.dbcollection = mock_collection

        pending_doc = TranlogDeliveryStatus(
            event_id="evt-003",
            published_at=datetime.now(),
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=100,
            business_date="20240601",
            open_counter=1,
            payload={},
            services=[
                TranlogDeliveryStatus.ServiceStatus(service_name="report", status="delivered"),
                TranlogDeliveryStatus.ServiceStatus(service_name="journal", status="pending"),
            ],
            last_updated_at=datetime.now(),
        )
        repo.find_by_event_id = AsyncMock(return_value=pending_doc)
        repo.update_delivery_status = AsyncMock(return_value=True)

        await repo.update_service_status(
            event_id="evt-003",
            service_name="report",
            status="delivered",
        )

        repo.update_delivery_status.assert_awaited_once_with("evt-003", "published")

    @pytest.mark.asyncio
    async def test_update_service_status_with_message(self):
        repo = self._make_repo()

        mock_collection = MagicMock()
        mock_update_result = MagicMock()
        mock_update_result.modified_count = 0
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        repo.dbcollection = mock_collection

        result = await repo.update_service_status(
            event_id="evt-004",
            service_name="journal",
            status="failed",
            message="Connection timeout",
        )

        assert result is False
        # Verify that message was included in update dict
        update_call = mock_collection.update_one.call_args
        update_dict = update_call[0][1]
        assert "services.$[elem].message" in update_dict["$set"]
        assert update_dict["$set"]["services.$[elem].message"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_update_service_status_returns_false_on_exception(self):
        repo = self._make_repo()

        mock_collection = MagicMock()
        mock_collection.update_one = AsyncMock(side_effect=Exception("DB error"))
        repo.dbcollection = mock_collection

        result = await repo.update_service_status(
            event_id="evt-005",
            service_name="report",
            status="delivered",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_delivery_status_uses_correct_filter_and_retries(self):
        repo = self._make_repo()
        repo.update_one_async = AsyncMock(return_value=True)

        result = await repo.update_delivery_status("evt-001", "delivered")

        assert result is True
        call_args = repo.update_one_async.call_args
        assert call_args[0][0] == {"event_id": "evt-001"}
        assert call_args[0][1]["status"] == "delivered"
        assert call_args[1]["max_retries"] == 10


# =========================================================================
# TranlogRepository tests
# =========================================================================


class TestTranlogRepository:
    """Tests for TranlogRepository query building and shard key generation."""

    def _make_repo(self, db=None):
        db = db or _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TranlogRepository(db, terminal_info)
        return repo

    @pytest.mark.asyncio
    async def test_query_with_all_optional_params(self):
        repo = self._make_repo()
        repo.get_paginated_list_async = AsyncMock(return_value=MagicMock())

        await repo.get_tranlog_list_by_query_async(
            store_code="S001",
            terminal_no=1,
            business_date="20240601",
            open_counter=5,
            transaction_type=[1, 2],
            receipt_no=100,
            limit=50,
            page=2,
            sort=[("transaction_no", -1)],
            include_cancelled=True,
        )

        call_args = repo.get_paginated_list_async.call_args
        query = call_args[1]["filter"]
        assert query["tenant_id"] == "T001"
        assert query["store_code"] == "S001"
        assert query["terminal_no"] == 1
        assert query["business_date"] == "20240601"
        assert query["open_counter"] == 5
        assert query["transaction_type"] == {"$in": [1, 2]}
        assert query["receipt_no"] == 100
        assert "sales.is_cancelled" not in query  # include_cancelled=True
        assert call_args[1]["limit"] == 50
        assert call_args[1]["page"] == 2
        assert call_args[1]["sort"] == [("transaction_no", -1)]

    @pytest.mark.asyncio
    async def test_query_with_no_optional_params(self):
        repo = self._make_repo()
        repo.get_paginated_list_async = AsyncMock(return_value=MagicMock())

        await repo.get_tranlog_list_by_query_async(
            store_code="S001",
            terminal_no=1,
        )

        call_args = repo.get_paginated_list_async.call_args
        query = call_args[1]["filter"]
        assert query == {
            "tenant_id": "T001",
            "store_code": "S001",
            "terminal_no": 1,
            "sales.is_cancelled": False,
        }

    @pytest.mark.asyncio
    async def test_query_excludes_cancelled_by_default(self):
        repo = self._make_repo()
        repo.get_paginated_list_async = AsyncMock(return_value=MagicMock())

        await repo.get_tranlog_list_by_query_async(
            store_code="S001",
            terminal_no=1,
        )

        call_args = repo.get_paginated_list_async.call_args
        query = call_args[1]["filter"]
        assert query["sales.is_cancelled"] is False

    @pytest.mark.asyncio
    async def test_query_includes_cancelled_when_flag_set(self):
        repo = self._make_repo()
        repo.get_paginated_list_async = AsyncMock(return_value=MagicMock())

        await repo.get_tranlog_list_by_query_async(
            store_code="S001",
            terminal_no=1,
            include_cancelled=True,
        )

        call_args = repo.get_paginated_list_async.call_args
        query = call_args[1]["filter"]
        assert "sales.is_cancelled" not in query

    def test_shard_key_generation(self):
        repo = self._make_repo()
        from kugel_common.models.documents.base_tranlog import BaseTransaction

        tranlog = BaseTransaction(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            generate_date_time="2024-06-01T10:30:00Z",
        )
        key = repo._TranlogRepository__get_shard_key(tranlog)
        assert key == "T001_S001_1_2024-06-01"

    def test_shard_key_with_different_datetime_format(self):
        repo = self._make_repo()
        from kugel_common.models.documents.base_tranlog import BaseTransaction

        tranlog = BaseTransaction(
            tenant_id="TENX",
            store_code="STR2",
            terminal_no=99,
            generate_date_time="2025-12-31T23:59:59Z",
        )
        key = repo._TranlogRepository__get_shard_key(tranlog)
        assert key == "TENX_STR2_99_2025-12-31"

    @pytest.mark.asyncio
    async def test_create_tranlog_sets_shard_key_and_calls_create(self):
        repo = self._make_repo()
        repo.create_async = AsyncMock(return_value=True)

        from kugel_common.models.documents.base_tranlog import BaseTransaction

        tranlog = BaseTransaction(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=500,
            transaction_type=1,
            generate_date_time="2024-06-01T12:00:00Z",
        )

        result = await repo.create_tranlog_async(tranlog)

        assert result.shard_key == "T001_S001_1_2024-06-01"
        repo.create_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_tranlog_raises_on_failure(self):
        repo = self._make_repo()
        repo.create_async = AsyncMock(return_value=False)

        from kugel_common.models.documents.base_tranlog import BaseTransaction

        tranlog = BaseTransaction(
            tenant_id="T001",
            store_code="S001",
            terminal_no=1,
            transaction_no=500,
            transaction_type=1,
            generate_date_time="2024-06-01T12:00:00Z",
        )

        with pytest.raises(CannotCreateException):
            await repo.create_tranlog_async(tranlog)

    @pytest.mark.asyncio
    async def test_get_tranlog_by_transaction_no_builds_correct_query(self):
        repo = self._make_repo()
        repo.get_one_async = AsyncMock(return_value=None)

        await repo.get_tranlog_by_transaction_no_async("S001", 1, 100)

        query = repo.get_one_async.call_args[0][0]
        assert query == {
            "tenant_id": "T001",
            "store_code": "S001",
            "terminal_no": 1,
            "transaction_no": 100,
        }


# =========================================================================
# TerminalCounterRepository tests
# =========================================================================


class TestTerminalCounterRepository:
    """Tests for TerminalCounterRepository."""

    def test_make_terminal_id(self):
        tid = make_terminal_id("T001", "S001", 1)
        assert tid == "T001-S001-1"

    def test_make_terminal_id_different_values(self):
        tid = make_terminal_id("TENX", "STRY", 99)
        assert tid == "TENX-STRY-99"

    @pytest.mark.asyncio
    async def test_numbering_count_success(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TerminalCounterRepository(db, terminal_info)

        mock_collection = MagicMock()
        mock_collection.find_one_and_update = AsyncMock(
            return_value={"count_dic": {"receipt": 42}}
        )
        repo.dbcollection = mock_collection

        result = await repo.numbering_count("receipt")

        assert result == 42
        # Verify the filter used correct terminal_id
        call_args = mock_collection.find_one_and_update.call_args
        assert call_args[1]["filter"] == {"terminal_id": "T001-S001-1"}
        assert call_args[1]["upsert"] is True

    @pytest.mark.asyncio
    async def test_numbering_count_raises_on_none_result(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TerminalCounterRepository(db, terminal_info)

        mock_collection = MagicMock()
        mock_collection.find_one_and_update = AsyncMock(return_value=None)
        repo.dbcollection = mock_collection

        from app.exceptions import UpdateNotWorkException

        with pytest.raises(UpdateNotWorkException):
            await repo.numbering_count("receipt")

    @pytest.mark.asyncio
    async def test_numbering_count_raises_when_count_type_missing(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TerminalCounterRepository(db, terminal_info)

        mock_collection = MagicMock()
        mock_collection.find_one_and_update = AsyncMock(
            return_value={"count_dic": {"other_type": 5}}
        )
        repo.dbcollection = mock_collection

        from app.exceptions import UpdateNotWorkException

        with pytest.raises(UpdateNotWorkException):
            await repo.numbering_count("receipt")

    @pytest.mark.asyncio
    async def test_numbering_count_custom_start_and_end(self):
        db = _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TerminalCounterRepository(db, terminal_info)

        mock_collection = MagicMock()
        mock_collection.find_one_and_update = AsyncMock(
            return_value={"count_dic": {"transaction": 10}}
        )
        repo.dbcollection = mock_collection

        result = await repo.numbering_count("transaction", start_value=10, end_value=9999)

        assert result == 10
        # Verify the pipeline was passed (list of dicts = aggregation pipeline)
        call_args = mock_collection.find_one_and_update.call_args
        update = call_args[1]["update"]
        assert isinstance(update, list)  # aggregation pipeline
        assert len(update) == 2


# =========================================================================
# TaxMasterRepository tests
# =========================================================================


class TestTaxMasterRepository:
    """Tests for TaxMasterRepository cache and lookup logic."""

    def _make_repo(self, db=None, tax_docs=None):
        db = db or _make_mock_db()
        terminal_info = _make_terminal_info()
        repo = TaxMasterRepository(db, terminal_info, tax_docs)
        return repo

    @pytest.mark.asyncio
    async def test_load_all_taxes_from_settings(self):
        repo = self._make_repo()

        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = [
                {"tax_code": "TAX10", "rate": 0.10, "tax_name": "Sales Tax"},
                {"tax_code": "TAX08", "rate": 0.08, "tax_name": "Reduced Tax"},
            ]
            result = await repo.load_all_taxes()

        assert len(result) == 2
        assert result[0].tax_code == "TAX10"
        assert result[1].tax_code == "TAX08"
        assert repo.tax_master_documents is result

    @pytest.mark.asyncio
    async def test_load_all_taxes_clears_existing(self):
        existing_taxes = [TaxMasterDocument(tax_code="OLD")]
        repo = self._make_repo(tax_docs=existing_taxes)

        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = [
                {"tax_code": "NEW", "rate": 0.05},
            ]
            result = await repo.load_all_taxes()

        assert len(result) == 1
        assert result[0].tax_code == "NEW"

    @pytest.mark.asyncio
    async def test_load_all_taxes_with_none_settings(self):
        repo = self._make_repo()

        with patch("app.models.repositories.tax_master_repository.settings") as mock_settings:
            mock_settings.TAX_MASTER = None
            result = await repo.load_all_taxes()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_tax_by_code_found(self):
        taxes = [
            TaxMasterDocument(tax_code="TAX10", rate=0.10),
            TaxMasterDocument(tax_code="TAX08", rate=0.08),
        ]
        repo = self._make_repo(tax_docs=taxes)

        result = await repo.get_tax_by_code("TAX08")

        assert result.tax_code == "TAX08"
        assert result.rate == 0.08

    @pytest.mark.asyncio
    async def test_get_tax_by_code_not_found_raises(self):
        taxes = [TaxMasterDocument(tax_code="TAX10")]
        repo = self._make_repo(tax_docs=taxes)

        with pytest.raises(NotFoundException):
            await repo.get_tax_by_code("NONEXISTENT")

    @pytest.mark.asyncio
    async def test_get_tax_by_code_raises_when_not_loaded(self):
        repo = self._make_repo(tax_docs=None)

        with pytest.raises(LoadDataNoExistException):
            await repo.get_tax_by_code("TAX10")

    def test_set_tax_master_documents(self):
        repo = self._make_repo()
        taxes = [TaxMasterDocument(tax_code="T1")]
        repo.set_tax_master_documents(taxes)
        assert repo.tax_master_documents == taxes

    def test_shard_key_returns_no_need(self):
        repo = self._make_repo()
        tax = TaxMasterDocument(tax_code="T1")
        key = repo._TaxMasterRepository__get_shard_key(tax)
        assert key == "no_need"


# =========================================================================
# CartRepository Dapr cache + DB fallback tests
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
