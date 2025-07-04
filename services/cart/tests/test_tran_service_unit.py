# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.enums import TransactionType
from app.services.tran_service import TranService
from app.models.repositories.transaction_status_repository import TransactionStatusRepository
from app.models.documents.transaction_status_document import TransactionStatusDocument
from app.exceptions import AlreadyVoidedException, AlreadyRefundedException
from app.exceptions.cart_error_codes import CartErrorCode


class TestTranServiceUnit:
    """Unit tests for TranService void/return functionality"""

    @pytest.fixture
    def mock_terminal_info(self):
        """Create mock terminal info"""
        terminal_info = MagicMock(spec=TerminalInfoDocument)
        terminal_info.tenant_id = "test_tenant"
        terminal_info.store_code = "S0001"
        terminal_info.terminal_no = 1
        return terminal_info

    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories"""
        terminal_counter_repo = AsyncMock()
        tranlog_repo = AsyncMock()
        tranlog_delivery_status_repo = AsyncMock()
        settings_master_repo = AsyncMock()
        payment_master_repo = AsyncMock()
        transaction_status_repo = AsyncMock(spec=TransactionStatusRepository)

        return (
            terminal_counter_repo,
            tranlog_repo,
            tranlog_delivery_status_repo,
            settings_master_repo,
            payment_master_repo,
            transaction_status_repo,
        )

    @pytest_asyncio.fixture
    async def tran_service(self, mock_terminal_info, mock_repositories):
        """Create TranService instance with mocked dependencies"""
        (
            terminal_counter_repo,
            tranlog_repo,
            tranlog_delivery_status_repo,
            settings_master_repo,
            payment_master_repo,
            transaction_status_repo,
        ) = mock_repositories

        service = TranService(
            terminal_info=mock_terminal_info,
            terminal_counter_repo=terminal_counter_repo,
            tranlog_repo=tranlog_repo,
            tranlog_delivery_status_repo=tranlog_delivery_status_repo,
            settings_master_repo=settings_master_repo,
            payment_master_repo=payment_master_repo,
            transaction_status_repo=transaction_status_repo,
        )

        yield service

        # Clean up the service to close HTTP clients
        await service.close()

    @pytest.mark.asyncio
    async def test_void_transaction_success(self, tran_service):
        """Test successful void operation"""
        # Create mock transaction
        mock_transaction = MagicMock(spec=BaseTransaction)
        mock_transaction.tenant_id = "test_tenant"
        mock_transaction.store_code = "S0001"
        mock_transaction.terminal_no = 1
        mock_transaction.transaction_no = 12345
        mock_transaction.transaction_type = TransactionType.NormalSales
        mock_transaction.is_voided = False
        mock_transaction.is_refunded = False
        mock_transaction.sales = MagicMock()
        mock_transaction.sales.total_amount = 1000
        mock_transaction.sales.total_tax = 100
        mock_transaction.origin = None  # No origin for normal sale
        mock_transaction.user_info = MagicMock()
        mock_transaction.user_info.id = "test_user"
        mock_transaction.payments = []
        mock_transaction.store_id = "S0001"
        mock_transaction.terminal_id = "T0001"
        mock_transaction.business_date = "20250101"
        mock_transaction.transaction_date = "2025-01-01T10:00:00"

        # Mock repository methods
        tran_service.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)
        tran_service.transaction_status_repo.mark_as_voided_async = AsyncMock(
            return_value=TransactionStatusDocument(
                tenant_id="test_tenant",
                store_code="S0001",
                terminal_no=1,
                transaction_no=12345,
                is_voided=True,
                void_transaction_no=12346,
                void_user_id="test_user",
            )
        )
        tran_service.terminal_counter_repository.get_next_transaction_no_async = AsyncMock(return_value=12346)
        tran_service.tranlog_repository.save_async = AsyncMock(return_value=True)

        # Mock payment master
        mock_payment_master = MagicMock()
        mock_payment_master.payment_code = "01"
        mock_payment_master.payment_name = "Cash"
        tran_service.payment_master_repo.find_by_payment_code_async = AsyncMock(return_value=mock_payment_master)

        # Mock tranlog delivery status
        tran_service.tranlog_delivery_status_repo.create_tranlog_delivery_status = AsyncMock(return_value=True)

        # Add payment list
        add_payment_list = [{"payment_code": "01", "amount": 1000}]

        # Call void method
        with patch("app.services.tran_service.get_app_time_str", return_value="2025-01-01T12:00:00"):
            result = await tran_service.void_async(mock_transaction, add_payment_list)

        # Verify
        assert result is not None
        tran_service.transaction_status_repo.mark_as_voided_async.assert_called_once()
        tran_service.tranlog_repo.save_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_void_already_voided_transaction(self, tran_service):
        """Test void operation on already voided transaction"""
        # Create mock transaction
        mock_transaction = MagicMock(spec=BaseTransaction)
        mock_transaction.tenant_id = "test_tenant"
        mock_transaction.store_code = "S0001"
        mock_transaction.terminal_no = 1
        mock_transaction.transaction_no = 12345

        # Mock status as already voided
        existing_status = TransactionStatusDocument(
            tenant_id="test_tenant",
            store_code="S0001",
            terminal_no=1,
            transaction_no=12345,
            is_voided=True,
            void_transaction_no=12340,
        )
        tran_service.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=existing_status)

        # Call void method and expect exception
        with pytest.raises(AlreadyVoidedException) as exc_info:
            await tran_service.void_async(mock_transaction, [])

        assert exc_info.value.error_code == CartErrorCode.ALREADY_VOIDED

    @pytest.mark.asyncio
    async def test_return_transaction_success(self, tran_service):
        """Test successful return operation"""
        # Create mock transaction
        mock_transaction = MagicMock(spec=BaseTransaction)
        mock_transaction.tenant_id = "test_tenant"
        mock_transaction.store_code = "S0001"
        mock_transaction.terminal_no = 1
        mock_transaction.transaction_no = 12345
        mock_transaction.transaction_type = TransactionType.NormalSales
        mock_transaction.is_voided = False
        mock_transaction.is_refunded = False
        mock_transaction.sales = MagicMock()
        mock_transaction.sales.total_amount = 1000
        mock_transaction.sales.total_tax = 100
        mock_transaction.origin = None  # No origin for normal sale
        mock_transaction.user_info = MagicMock()
        mock_transaction.user_info.id = "test_user"
        mock_transaction.payments = []
        mock_transaction.store_id = "S0001"
        mock_transaction.terminal_id = "T0001"
        mock_transaction.business_date = "20250101"
        mock_transaction.transaction_date = "2025-01-01T10:00:00"

        # Mock repository methods
        tran_service.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=None)
        tran_service.transaction_status_repo.mark_as_refunded_async = AsyncMock(
            return_value=TransactionStatusDocument(
                tenant_id="test_tenant",
                store_code="S0001",
                terminal_no=1,
                transaction_no=12345,
                is_refunded=True,
                return_transaction_no=12346,
                return_user_id="test_user",
            )
        )
        tran_service.terminal_counter_repository.get_next_transaction_no_async = AsyncMock(return_value=12346)
        tran_service.tranlog_repository.save_async = AsyncMock(return_value=True)

        # Mock payment master
        mock_payment_master = MagicMock()
        mock_payment_master.payment_code = "01"
        mock_payment_master.payment_name = "Cash"
        tran_service.payment_master_repo.find_by_payment_code_async = AsyncMock(return_value=mock_payment_master)

        # Mock tranlog delivery status
        tran_service.tranlog_delivery_status_repo.create_tranlog_delivery_status = AsyncMock(return_value=True)

        # Add payment list
        add_payment_list = [{"payment_code": "01", "amount": 1000}]

        # Call return method
        with patch("app.services.tran_service.get_app_time_str", return_value="2025-01-01T12:00:00"):
            result = await tran_service.return_async(mock_transaction, add_payment_list)

        # Verify
        assert result is not None
        tran_service.transaction_status_repo.mark_as_refunded_async.assert_called_once()
        tran_service.tranlog_repo.save_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_return_already_refunded_transaction(self, tran_service):
        """Test return operation on already refunded transaction"""
        # Create mock transaction
        mock_transaction = MagicMock(spec=BaseTransaction)
        mock_transaction.tenant_id = "test_tenant"
        mock_transaction.store_code = "S0001"
        mock_transaction.terminal_no = 1
        mock_transaction.transaction_no = 12345

        # Mock status as already refunded
        existing_status = TransactionStatusDocument(
            tenant_id="test_tenant",
            store_code="S0001",
            terminal_no=1,
            transaction_no=12345,
            is_refunded=True,
            return_transaction_no=12340,
        )
        tran_service.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=existing_status)

        # Call return method and expect exception
        with pytest.raises(AlreadyRefundedException) as exc_info:
            await tran_service.return_async(mock_transaction, [])

        assert exc_info.value.error_code == CartErrorCode.ALREADY_REFUNDED

    @pytest.mark.asyncio
    async def test_get_transaction_list_with_status(self, tran_service):
        """Test getting transaction list with void/return status"""
        # Create mock transactions
        mock_transactions = [
            MagicMock(
                tenant_id="test_tenant",
                store_code="S0001",
                terminal_no=1,
                transaction_no=12345,
                is_voided=False,
                is_refunded=False,
            ),
            MagicMock(
                tenant_id="test_tenant",
                store_code="S0001",
                terminal_no=1,
                transaction_no=12346,
                is_voided=False,
                is_refunded=False,
            ),
        ]

        # Mock status documents
        status_dict = {
            12345: TransactionStatusDocument(
                tenant_id="test_tenant",
                store_code="S0001",
                terminal_no=1,
                transaction_no=12345,
                is_voided=True,
                void_transaction_no=12350,
            )
        }

        tran_service.transaction_status_repo.get_status_for_transactions_async = AsyncMock(return_value=status_dict)

        # Call method
        result = await tran_service.get_transaction_list_with_status_async(mock_transactions)

        # Verify
        assert len(result) == 2
        assert result[0].is_voided is True
        assert result[1].is_voided is False  # No status for this one
