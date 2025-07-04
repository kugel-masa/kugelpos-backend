# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.enums import TransactionType
from kugel_common.models.documents.user_info_document import UserInfoDocument

from app.services.log_service import LogService
from app.models.documents.jornal_document import JournalDocument
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.services.journal_service import JournalService


class TestLogService:
    """Test cases for LogService class with focus on transaction type conversion logic."""

    @pytest.fixture
    def mock_repositories(self):
        """Fixture to create mock repositories."""
        tran_repo = AsyncMock(spec=TranlogRepository)
        cash_repo = AsyncMock(spec=CashInOutLogRepository)
        open_close_repo = AsyncMock(spec=OpenCloseLogRepository)
        journal_service = AsyncMock(spec=JournalService)

        # Setup journal repository mock
        journal_service.journal_repository = AsyncMock()

        return tran_repo, cash_repo, open_close_repo, journal_service

    @pytest.fixture
    def log_service(self, mock_repositories):
        """Fixture to create LogService instance with mocked dependencies."""
        tran_repo, cash_repo, open_close_repo, journal_service = mock_repositories
        return LogService(
            tran_repository=tran_repo,
            cash_in_out_log_repository=cash_repo,
            open_close_log_repository=open_close_repo,
            journal_service=journal_service,
        )

    @pytest.fixture
    def base_transaction(self):
        """Fixture to create a base transaction for testing."""
        transaction = BaseTransaction(
            tenant_id="test_tenant",
            store_code="test_store",
            store_name="Test Store",
            terminal_no=1,
            transaction_no=12345,
            transaction_type=TransactionType.NormalSales.value,
            business_date="20240101",
            open_counter=1,
            business_counter=100,
            generate_date_time="2024-01-01T10:00:00",
            receipt_no=1001,
            user=UserInfoDocument(id="user123", name="Test User"),
            sales=BaseTransaction.SalesInfo(
                total_amount=1000.0,
                total_amount_with_tax=1100.0,
                tax_amount=100.0,
                total_quantity=5,
                is_cancelled=False,
            ),
            staff=BaseTransaction.Staff(id="staff123", name="Test Staf"),
            journal_text="Journal text",
            receipt_text="Receipt text",
        )
        return transaction

    @pytest.mark.asyncio
    async def test_receive_tranlog_normal_sales_not_cancelled(self, log_service, base_transaction, mock_repositories):
        """Test that normal sales transaction type remains unchanged when not cancelled."""
        # Arrange
        tran_repo, _, _, journal_service = mock_repositories

        # Setup mock session
        mock_session = AsyncMock()
        tran_repo.start_transaction.return_value.__aenter__.return_value = mock_session
        tran_repo.create_tranlog_async.return_value = base_transaction

        # Act
        result = await log_service.receive_tranlog_async(base_transaction)

        # Assert
        # Verify that journal was created with original transaction type
        journal_service.receive_journal_async.assert_called_once()
        journal_call_args = journal_service.receive_journal_async.call_args[0][0]
        assert journal_call_args["transaction_type"] == TransactionType.NormalSales.value
        assert result == base_transaction

    @pytest.mark.asyncio
    async def test_receive_tranlog_normal_sales_cancelled(self, log_service, base_transaction, mock_repositories):
        """Test that cancelled normal sales transaction type is converted to NormalSalesCancel."""
        # Arrange
        tran_repo, _, _, journal_service = mock_repositories

        # Set the transaction as cancelled
        base_transaction.sales.is_cancelled = True

        # Setup mock session
        mock_session = AsyncMock()
        tran_repo.start_transaction.return_value.__aenter__.return_value = mock_session
        tran_repo.create_tranlog_async.return_value = base_transaction

        # Act
        result = await log_service.receive_tranlog_async(base_transaction)

        # Assert
        # Verify that journal was created with cancelled transaction type
        journal_service.receive_journal_async.assert_called_once()
        journal_call_args = journal_service.receive_journal_async.call_args[0][0]
        assert journal_call_args["transaction_type"] == TransactionType.NormalSalesCancel.value
        assert result == base_transaction

    @pytest.mark.asyncio
    async def test_receive_tranlog_other_transaction_types_unchanged(
        self, log_service, base_transaction, mock_repositories
    ):
        """Test that non-NormalSales transaction types are not affected by cancellation logic."""
        # Arrange
        tran_repo, _, _, journal_service = mock_repositories

        # Test with different transaction types
        test_cases = [
            (TransactionType.ReturnSales.value, True),
            (TransactionType.ReturnSales.value, False),
            (TransactionType.VoidSales.value, True),
            (TransactionType.VoidSales.value, False),
            (TransactionType.Open.value, False),
            (TransactionType.Close.value, False),
        ]

        for transaction_type, is_cancelled in test_cases:
            # Reset mocks
            journal_service.receive_journal_async.reset_mock()

            # Set transaction type and cancellation status
            base_transaction.transaction_type = transaction_type
            base_transaction.sales.is_cancelled = is_cancelled

            # Setup mock session
            mock_session = AsyncMock()
            tran_repo.start_transaction.return_value.__aenter__.return_value = mock_session
            tran_repo.create_tranlog_async.return_value = base_transaction

            # Act
            await log_service.receive_tranlog_async(base_transaction)

            # Assert
            journal_call_args = journal_service.receive_journal_async.call_args[0][0]
            assert (
                journal_call_args["transaction_type"] == transaction_type
            ), f"Transaction type {transaction_type} should remain unchanged regardless of cancellation status"

    @pytest.mark.asyncio
    async def test_receive_tranlog_transaction_rollback_on_error(
        self, log_service, base_transaction, mock_repositories
    ):
        """Test that transaction is rolled back when an error occurs."""
        # Arrange
        tran_repo, _, _, journal_service = mock_repositories

        # Setup mock session
        mock_session = AsyncMock()
        tran_repo.start_transaction.return_value.__aenter__.return_value = mock_session

        # Make journal service throw an exception
        journal_service.receive_journal_async.side_effect = Exception("Journal creation failed")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await log_service.receive_tranlog_async(base_transaction)

        assert str(exc_info.value) == "Journal creation failed"
        tran_repo.abort_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_tranlog_with_edge_cases(self, log_service, mock_repositories):
        """Test edge cases like missing sales info or None values."""
        # Arrange
        tran_repo, _, _, journal_service = mock_repositories

        # Test case 1: Transaction with None sales info
        transaction_no_sales = BaseTransaction(
            tenant_id="test_tenant",
            store_code="test_store",
            terminal_no=1,
            transaction_no=12345,
            transaction_type=TransactionType.NormalSales.value,
            business_date="20240101",
            open_counter=1,
            business_counter=100,
            generate_date_time="2024-01-01T10:00:00",
            sales=None,  # No sales info
            staff=BaseTransaction.Staff(id="staff123"),
            user=UserInfoDocument(id="user123"),
        )

        # Setup mock session
        mock_session = AsyncMock()
        tran_repo.start_transaction.return_value.__aenter__.return_value = mock_session
        tran_repo.create_tranlog_async.return_value = transaction_no_sales

        # This should raise an AttributeError when trying to access sales.is_cancelled
        with pytest.raises(AttributeError):
            await log_service.receive_tranlog_async(transaction_no_sales)

    @pytest.mark.parametrize(
        "is_cancelled,expected_type",
        [
            (False, TransactionType.NormalSales.value),
            (True, TransactionType.NormalSalesCancel.value),
        ],
    )
    @pytest.mark.asyncio
    async def test_transaction_type_conversion_parametrized(
        self, log_service, base_transaction, mock_repositories, is_cancelled, expected_type
    ):
        """Parametrized test for transaction type conversion logic."""
        # Arrange
        tran_repo, _, _, journal_service = mock_repositories
        base_transaction.sales.is_cancelled = is_cancelled

        # Setup mock session
        mock_session = AsyncMock()
        tran_repo.start_transaction.return_value.__aenter__.return_value = mock_session
        tran_repo.create_tranlog_async.return_value = base_transaction

        # Act
        await log_service.receive_tranlog_async(base_transaction)

        # Assert
        journal_call_args = journal_service.receive_journal_async.call_args[0][0]
        assert journal_call_args["transaction_type"] == expected_type
