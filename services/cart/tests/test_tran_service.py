"""
Unit tests for TranService.
Extends the existing test_tran_service_unit_simple.py with more method coverage.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.tran_service import TranService
from app.models.documents.transaction_status_document import TransactionStatusDocument
from app.exceptions import (
    DocumentNotFoundException,
    BadRequestBodyException,
    InternalErrorException,
    AlreadyVoidedException,
    AlreadyRefundedException,
)
from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction


def _make_tran_service():
    """Create a TranService with all dependencies mocked."""
    terminal_info = MagicMock()
    terminal_info.tenant_id = "test_tenant"
    terminal_info.store_code = "S0001"
    terminal_info.terminal_no = 1
    terminal_info.business_date = "2025-01-01"
    terminal_info.business_counter = 1
    terminal_info.open_counter = 1
    terminal_info.staff = MagicMock()
    terminal_info.staff.id = "staff1"
    terminal_info.staff.name = "Staff One"

    with patch("app.services.tran_service.CartStrategyManager") as MockStrategyMgr, \
         patch("app.services.tran_service.PubsubManager") as MockPubsub:
        mock_strategy = MagicMock()
        mock_receipt_strategy = MagicMock()
        mock_receipt_strategy.name = "default"
        mock_strategy.load_strategies.return_value = [mock_receipt_strategy]
        MockStrategyMgr.return_value = mock_strategy

        mock_pubsub = MagicMock()
        mock_pubsub.publish_message_async = AsyncMock(return_value=(True, None))
        mock_pubsub.close = AsyncMock()
        MockPubsub.return_value = mock_pubsub

        svc = TranService(
            terminal_info=terminal_info,
            terminal_counter_repo=MagicMock(),
            tranlog_repo=MagicMock(),
            tranlog_delivery_status_repo=MagicMock(),
            settings_master_repo=MagicMock(),
            payment_master_repo=MagicMock(),
            transaction_status_repo=MagicMock(),
        )
    return svc


def _make_base_transaction(
    transaction_type=TransactionType.NormalSales.value,
    transaction_no=100,
    total_amount=1000.0,
):
    """Create a BaseTransaction for testing."""
    tran = BaseTransaction()
    tran.tenant_id = "test_tenant"
    tran.store_code = "S0001"
    tran.terminal_no = 1
    tran.transaction_no = transaction_no
    tran.transaction_type = transaction_type
    tran.receipt_no = 200
    tran.generate_date_time = "2025-01-01T12:00:00"
    tran.store_name = "Test Store"
    tran.origin = None
    tran.staff = BaseTransaction.Staff()
    tran.staff.id = "staff1"
    tran.staff.name = "Staff One"

    tran.sales = BaseTransaction.SalesInfo()
    tran.sales.total_amount_with_tax = total_amount
    tran.sales.is_cancelled = False
    tran.sales.is_stamp_duty_applied = False
    tran.sales.stamp_duty_target_amount = 0
    tran.sales.stamp_duty_amount = 0.0
    tran.sales.change_amount = 0
    tran.sales.reference_date_time = None

    payment = BaseTransaction.Payment()
    payment.payment_no = 1
    payment.payment_code = "01"
    payment.description = "Cash"
    payment.amount = total_amount
    payment.deposit_amount = 0
    payment.detail = None
    tran.payments = [payment]

    tran.line_items = []
    tran.taxes = []
    tran.subtotal_discounts = []
    tran.user = MagicMock()
    tran.business_date = "2025-01-01"
    tran.business_counter = 1
    tran.open_counter = 1
    return tran


class TestConvertDatetime:
    """Tests for convert_datetime helper."""

    def test_converts_dict_with_datetime(self):
        svc = _make_tran_service()
        dt = datetime(2025, 1, 1, 12, 0, 0)
        result = svc.convert_datetime({"date": dt, "name": "test"})
        assert result["date"] == "2025-01-01T12:00:00"
        assert result["name"] == "test"

    def test_converts_list_with_datetime(self):
        svc = _make_tran_service()
        dt = datetime(2025, 6, 15)
        result = svc.convert_datetime([dt, "hello"])
        assert result[0] == "2025-06-15T00:00:00"
        assert result[1] == "hello"

    def test_passes_through_other_types(self):
        svc = _make_tran_service()
        assert svc.convert_datetime(42) == 42
        assert svc.convert_datetime("str") == "str"


class TestGetTranlogByTransactionNo:
    """Tests for get_tranlog_by_transaction_no_async."""

    @pytest.mark.asyncio
    async def test_get_tranlog_success(self):
        svc = _make_tran_service()
        mock_tran = MagicMock()
        mock_tran.transaction_no = 100
        svc.tranlog_repository.get_tranlog_by_transaction_no_async = AsyncMock(return_value=mock_tran)
        svc.transaction_status_repo.get_status_for_transactions_async = AsyncMock(return_value={})

        result = await svc.get_tranlog_by_transaction_no_async("S0001", 1, 100)
        assert result.transaction_no == 100

    @pytest.mark.asyncio
    async def test_get_tranlog_not_found(self):
        svc = _make_tran_service()
        svc.tranlog_repository.get_tranlog_by_transaction_no_async = AsyncMock(return_value=None)

        with pytest.raises(DocumentNotFoundException):
            await svc.get_tranlog_by_transaction_no_async("S0001", 1, 999)


class TestGetTranlogByQuery:
    """Tests for get_tranlog_by_query_async."""

    @pytest.mark.asyncio
    async def test_get_tranlog_by_query_with_data(self):
        svc = _make_tran_service()
        mock_result = MagicMock()
        mock_tran = MagicMock()
        mock_tran.transaction_no = 100
        mock_result.data = [mock_tran]
        svc.tranlog_repository.get_tranlog_list_by_query_async = AsyncMock(return_value=mock_result)
        svc.transaction_status_repo.get_status_for_transactions_async = AsyncMock(return_value={})

        result = await svc.get_tranlog_by_query_async("S0001", 1)
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_get_tranlog_by_query_empty(self):
        svc = _make_tran_service()
        mock_result = MagicMock()
        mock_result.data = []
        svc.tranlog_repository.get_tranlog_list_by_query_async = AsyncMock(return_value=mock_result)

        result = await svc.get_tranlog_by_query_async("S0001", 1)
        assert result.data == []


class TestVoidAsync:
    """Tests for void_async."""

    @pytest.mark.asyncio
    async def test_void_already_voided(self):
        """Voiding an already-voided transaction should raise AlreadyVoidedException."""
        svc = _make_tran_service()
        tran = _make_base_transaction()

        status = TransactionStatusDocument(
            tenant_id="test_tenant", store_code="S0001", terminal_no=1,
            transaction_no=100, is_voided=True, void_transaction_no=99,
        )
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=status)

        with pytest.raises(AlreadyVoidedException):
            await svc.void_async(tran, [])

    @pytest.mark.asyncio
    async def test_void_already_refunded_normal_sales(self):
        """Voiding a refunded normal sale should raise AlreadyRefundedException."""
        svc = _make_tran_service()
        tran = _make_base_transaction(transaction_type=TransactionType.NormalSales.value)

        status = TransactionStatusDocument(
            tenant_id="test_tenant", store_code="S0001", terminal_no=1,
            transaction_no=100, is_refunded=True, return_transaction_no=99,
        )
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=status)

        with pytest.raises(AlreadyRefundedException):
            await svc.void_async(tran, [])

    @pytest.mark.asyncio
    async def test_void_payment_code_not_in_original(self):
        """Void with payment not in original should raise BadRequestBodyException."""
        svc = _make_tran_service()
        tran = _make_base_transaction()
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)

        with pytest.raises(BadRequestBodyException):
            await svc.void_async(tran, [{"payment_code": "99", "amount": 1000}])

    @pytest.mark.asyncio
    async def test_void_payment_amount_mismatch(self):
        """Void with wrong payment amount should raise BadRequestBodyException."""
        svc = _make_tran_service()
        tran = _make_base_transaction()
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)

        with pytest.raises(BadRequestBodyException):
            await svc.void_async(tran, [{"payment_code": "01", "amount": 500}])

    @pytest.mark.asyncio
    async def test_void_invalid_transaction_type(self):
        """Voiding a non-sale/non-return transaction should raise BadRequestBodyException."""
        svc = _make_tran_service()
        tran = _make_base_transaction(transaction_type=99)
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)

        pay_doc = MagicMock()
        pay_doc.payment_code = "01"
        pay_doc.description = "Cash"
        pay_doc.can_deposit_over = False
        pay_doc.can_change = False
        svc.payment_master_repo.get_payment_by_code_async = AsyncMock(return_value=pay_doc)

        with pytest.raises(BadRequestBodyException):
            await svc.void_async(tran, [{"payment_code": "01", "amount": 1000, "detail": None}])

    @pytest.mark.asyncio
    async def test_void_no_payments_raises_bad_request(self):
        """Void with None payment list should raise BadRequestBodyException."""
        svc = _make_tran_service()
        tran = _make_base_transaction()
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)

        with pytest.raises(BadRequestBodyException):
            await svc.void_async(tran, None)


class TestReturnAsync:
    """Tests for return_async."""

    @pytest.mark.asyncio
    async def test_return_already_refunded(self):
        """Returning an already-refunded transaction should raise AlreadyRefundedException."""
        svc = _make_tran_service()
        tran = _make_base_transaction()

        status = TransactionStatusDocument(
            tenant_id="test_tenant", store_code="S0001", terminal_no=1,
            transaction_no=100, is_refunded=True, return_transaction_no=99,
        )
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=status)

        with pytest.raises(AlreadyRefundedException):
            await svc.return_async(tran, [])

    @pytest.mark.asyncio
    async def test_return_already_voided(self):
        """Returning an already-voided transaction should raise AlreadyVoidedException."""
        svc = _make_tran_service()
        tran = _make_base_transaction()

        status = TransactionStatusDocument(
            tenant_id="test_tenant", store_code="S0001", terminal_no=1,
            transaction_no=100, is_voided=True, void_transaction_no=99,
        )
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=status)

        with pytest.raises(AlreadyVoidedException):
            await svc.return_async(tran, [])

    @pytest.mark.asyncio
    async def test_return_invalid_transaction_type(self):
        """Returning a non-NormalSales transaction should raise BadRequestBodyException."""
        svc = _make_tran_service()
        tran = _make_base_transaction(transaction_type=TransactionType.VoidSales.value)
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)

        with pytest.raises(BadRequestBodyException):
            await svc.return_async(tran, [{"payment_code": "01", "amount": 1000}])

    @pytest.mark.asyncio
    async def test_return_no_payments_raises_bad_request(self):
        """Return with None payment list should raise BadRequestBodyException."""
        svc = _make_tran_service()
        tran = _make_base_transaction()
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)

        with pytest.raises(BadRequestBodyException):
            await svc.return_async(tran, None)

    @pytest.mark.asyncio
    async def test_return_payment_not_found(self):
        """Return with unknown payment code should raise DocumentNotFoundException."""
        svc = _make_tran_service()
        tran = _make_base_transaction()
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)
        svc.payment_master_repo.get_payment_by_code_async = AsyncMock(return_value=None)

        with pytest.raises(DocumentNotFoundException):
            await svc.return_async(tran, [{"payment_code": "01", "amount": 1000, "detail": None}])

    @pytest.mark.asyncio
    async def test_return_payment_amount_mismatch(self):
        """Return with wrong total payment amount should raise BadRequestBodyException."""
        svc = _make_tran_service()
        tran = _make_base_transaction(total_amount=1000.0)
        svc.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)

        pay_doc = MagicMock()
        pay_doc.payment_code = "01"
        pay_doc.description = "Cash"
        pay_doc.can_deposit_over = False
        pay_doc.can_change = False
        svc.payment_master_repo.get_payment_by_code_async = AsyncMock(return_value=pay_doc)

        with pytest.raises(BadRequestBodyException):
            await svc.return_async(tran, [{"payment_code": "01", "amount": 500, "detail": None}])


class TestParseJsonOrLiteral:
    """Tests for _parse_json_or_literal_async."""

    @pytest.mark.asyncio
    async def test_already_list(self):
        svc = _make_tran_service()
        result = await svc._parse_json_or_literal_async([1, 2], "TEST")
        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_already_dict(self):
        svc = _make_tran_service()
        result = await svc._parse_json_or_literal_async({"a": 1}, "TEST")
        assert result == {"a": 1}

    @pytest.mark.asyncio
    async def test_json_string(self):
        svc = _make_tran_service()
        result = await svc._parse_json_or_literal_async('[{"text": "hi"}]', "TEST")
        assert result == [{"text": "hi"}]

    @pytest.mark.asyncio
    async def test_python_literal_string(self):
        svc = _make_tran_service()
        result = await svc._parse_json_or_literal_async("[{'text': 'hi'}]", "TEST")
        assert result == [{"text": "hi"}]

    @pytest.mark.asyncio
    async def test_non_string_returns_none(self):
        svc = _make_tran_service()
        result = await svc._parse_json_or_literal_async(12345, "TEST")
        assert result is None

    @pytest.mark.asyncio
    async def test_unparseable_string_returns_none(self):
        svc = _make_tran_service()
        result = await svc._parse_json_or_literal_async("not valid json or python", "TEST")
        assert result is None


class TestGetTransactionListWithStatus:
    """Tests for get_transaction_list_with_status_async."""

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self):
        svc = _make_tran_service()
        result = await svc.get_transaction_list_with_status_async([])
        assert result == []

    @pytest.mark.asyncio
    async def test_merges_status_correctly(self):
        svc = _make_tran_service()
        tran1 = MagicMock()
        tran1.transaction_no = 100
        tran1.is_voided = False
        tran1.is_refunded = False

        tran2 = MagicMock()
        tran2.transaction_no = 101
        tran2.is_voided = False
        tran2.is_refunded = False

        status_dict = {
            100: TransactionStatusDocument(
                tenant_id="t", store_code="S", terminal_no=1,
                transaction_no=100, is_voided=True, void_transaction_no=999,
            ),
        }
        svc.transaction_status_repo.get_status_for_transactions_async = AsyncMock(return_value=status_dict)

        result = await svc.get_transaction_list_with_status_async([tran1, tran2])
        assert len(result) == 2
        assert result[0].is_voided is True
        assert result[1].is_voided is False


class TestUpdateDeliveryStatus:
    """Tests for update_delivery_status_async."""

    @pytest.mark.asyncio
    async def test_all_services_received(self):
        """When all services received, overall status should be 'delivered'."""
        svc = _make_tran_service()

        svc.tranlog_delivery_status_repo.update_service_status = AsyncMock(return_value=True)
        mock_status = MagicMock()
        svc1 = MagicMock()
        svc1.status = "received"
        svc2 = MagicMock()
        svc2.status = "received"
        mock_status.services = [svc1, svc2]
        svc.tranlog_delivery_status_repo.find_by_event_id = AsyncMock(return_value=mock_status)
        svc.tranlog_delivery_status_repo.update_delivery_status = AsyncMock(return_value=True)

        await svc.update_delivery_status_async(
            event_id="ev1", status="received", service_name="report", message=None
        )

        # Should update overall status to "delivered"
        svc.tranlog_delivery_status_repo.update_delivery_status.assert_awaited()

    @pytest.mark.asyncio
    async def test_delivery_status_not_found_raises(self):
        """When delivery status not found, should raise InternalErrorException."""
        svc = _make_tran_service()
        svc.tranlog_delivery_status_repo.update_service_status = AsyncMock(return_value=True)
        svc.tranlog_delivery_status_repo.find_by_event_id = AsyncMock(return_value=None)

        with pytest.raises(InternalErrorException):
            await svc.update_delivery_status_async(
                event_id="ev1", status="received", service_name="report", message=None
            )


class TestTranServiceClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_close_calls_pubsub_close(self):
        svc = _make_tran_service()
        svc.pubsub_manager.close = AsyncMock()
        await svc.close()
        svc.pubsub_manager.close.assert_awaited_once()
