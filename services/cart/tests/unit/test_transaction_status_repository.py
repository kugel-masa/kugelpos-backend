# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.repositories.transaction_status_repository import TransactionStatusRepository
from app.models.documents.transaction_status_document import TransactionStatusDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument


class TestTransactionStatusRepository:
    """Test cases for TransactionStatusRepository"""

    @pytest.fixture
    def mock_terminal_info(self):
        """Create mock terminal info"""
        terminal_info = MagicMock(spec=TerminalInfoDocument)
        terminal_info.tenant_id = "test_tenant"
        terminal_info.store_code = "S0001"
        terminal_info.terminal_no = 1
        return terminal_info

    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        return AsyncMock()

    @pytest.fixture
    def repository(self, mock_db, mock_terminal_info):
        """Create repository instance with mocked dependencies"""
        repo = TransactionStatusRepository(mock_db, mock_terminal_info)
        # Mock the dbcollection
        repo.dbcollection = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_mark_as_voided_new_document(self, repository):
        """
        Test marking a transaction as voided when no status document exists
        """
        # Test data
        tenant_id = "test_tenant"
        store_code = "S0001"
        terminal_no = 1
        transaction_no = 12345
        void_transaction_no = 12346
        staff_id = "test_user"

        # Mock get_one_async to return None (no existing document)
        repository.get_one_async = AsyncMock(return_value=None)

        # Mock create_async
        repository.create_async = AsyncMock(return_value=True)

        # Mark as voided
        result = await repository.mark_as_voided_async(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            void_transaction_no=void_transaction_no,
            staff_id=staff_id,
        )

        # Verify
        assert result is not None
        assert result.is_voided is True
        assert result.is_refunded is False
        assert result.void_transaction_no == void_transaction_no
        assert result.void_staff_id == staff_id
        assert result.void_date_time is not None

        # Verify create_async was called
        repository.create_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_as_voided_existing_document(self, repository):
        """
        Test marking a transaction as voided when status document already exists
        """
        # Test data
        tenant_id = "test_tenant"
        store_code = "S0001"
        terminal_no = 1
        transaction_no = 12347
        void_transaction_no = 12348
        staff_id = "test_user"

        # Create an existing document
        existing_doc = TransactionStatusDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            is_voided=False,
            is_refunded=True,  # Already refunded
            return_transaction_no=12340,
            return_date_time="2024-01-01T10:00:00",
            return_staff_id="another_user",
        )

        # Create updated document to return after update
        updated_doc = TransactionStatusDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            is_voided=True,  # Now voided
            is_refunded=True,  # Still refunded
            void_transaction_no=void_transaction_no,
            void_date_time="2025-01-01T12:00:00",
            void_staff_id=staff_id,
            return_transaction_no=12340,  # Preserved
            return_date_time="2024-01-01T10:00:00",  # Preserved
            return_staff_id="another_user",  # Preserved
        )

        # Mock get_one_async to return existing document first, then updated
        repository.get_one_async = AsyncMock(return_value=existing_doc)
        repository.get_status_by_transaction_async = AsyncMock(return_value=updated_doc)

        # Mock update_one_async
        repository.update_one_async = AsyncMock(return_value=True)

        # Mark as voided
        result = await repository.mark_as_voided_async(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            void_transaction_no=void_transaction_no,
            staff_id=staff_id,
        )

        # Verify - should preserve refund info
        assert result is not None
        assert result.is_voided is True
        assert result.is_refunded is True  # Preserved
        assert result.void_transaction_no == void_transaction_no
        assert result.void_staff_id == staff_id
        assert result.return_transaction_no == 12340  # Preserved
        assert result.return_staff_id == "another_user"  # Preserved

        # Verify update_one_async was called
        repository.update_one_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_as_refunded_new_document(self, repository):
        """
        Test marking a transaction as refunded when no status document exists
        """
        # Test data
        tenant_id = "test_tenant"
        store_code = "S0001"
        terminal_no = 1
        transaction_no = 12349
        return_transaction_no = 12350
        staff_id = "test_user"

        # Mock get_one_async to return None (no existing document)
        repository.get_one_async = AsyncMock(return_value=None)

        # Mock create_async
        repository.create_async = AsyncMock(return_value=True)

        # Mark as refunded
        result = await repository.mark_as_refunded_async(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            return_transaction_no=return_transaction_no,
            staff_id=staff_id,
        )

        # Verify
        assert result is not None
        assert result.is_refunded is True
        assert result.is_voided is False
        assert result.return_transaction_no == return_transaction_no
        assert result.return_staff_id == staff_id
        assert result.return_date_time is not None

        # Verify create_async was called
        repository.create_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_for_transactions(self, repository):
        """
        Test getting status for multiple transactions
        """
        # Test data
        tenant_id = "test_tenant"
        store_code = "S0001"
        terminal_no = 1
        transaction_nos = [20001, 20002, 20003, 20004]

        # Create mock status documents
        status1 = TransactionStatusDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=20001,
            is_voided=True,
            is_refunded=False,
        )

        status2 = TransactionStatusDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=20002,
            is_voided=False,
            is_refunded=True,
        )

        # Mock get_list_async to return two status documents
        repository.get_list_async = AsyncMock(return_value=[status1, status2])

        # Get status for all
        status_dict = await repository.get_status_for_transactions_async(
            tenant_id, store_code, terminal_no, transaction_nos
        )

        # Verify
        assert len(status_dict) == 2  # Only two have status
        assert 20001 in status_dict
        assert 20002 in status_dict
        assert 20003 not in status_dict
        assert 20004 not in status_dict

        assert status_dict[20001].is_voided is True
        assert status_dict[20001].is_refunded is False

        assert status_dict[20002].is_voided is False
        assert status_dict[20002].is_refunded is True

    @pytest.mark.asyncio
    async def test_get_status_by_transaction_not_found(self, repository):
        """
        Test getting status for a transaction that doesn't exist
        """
        # Test data
        tenant_id = "test_tenant"
        store_code = "S0001"
        terminal_no = 1
        transaction_no = 99999

        # Mock get_one_async to return None
        repository.get_one_async = AsyncMock(return_value=None)

        # Get status
        status = await repository.get_status_by_transaction_async(tenant_id, store_code, terminal_no, transaction_no)

        # Should return None
        assert status is None

    @pytest.mark.asyncio
    async def test_reset_refund_status_success(self, repository):
        """
        Test successfully resetting refund status of a transaction
        """
        # Test data
        tenant_id = "test_tenant"
        store_code = "S0001"
        terminal_no = 1
        transaction_no = 1001

        # Create existing status document with refund info
        existing_status = TransactionStatusDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            is_voided=False,
            is_refunded=True,
            return_transaction_no=2001,
            return_date_time="2024-01-15 14:30:00",
            return_staff_id="STAFF002",
        )

        # Updated status after reset
        updated_status = TransactionStatusDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            is_voided=False,
            is_refunded=False,
            return_transaction_no=None,
            return_date_time=None,
            return_staff_id=None,
        )

        # Mock methods
        repository.get_status_by_transaction_async = AsyncMock(side_effect=[existing_status, updated_status])
        repository.update_one_async = AsyncMock(return_value=None)

        # Reset refund status
        result = await repository.reset_refund_status_async(tenant_id, store_code, terminal_no, transaction_no)

        # Verify result
        assert result is not None
        assert result.is_refunded is False
        assert result.return_transaction_no is None
        assert result.return_date_time is None
        assert result.return_staff_id is None

        # Verify update was called with correct values
        repository.update_one_async.assert_called_once()
        update_call_args = repository.update_one_async.call_args
        assert update_call_args[0][1]["is_refunded"] is False
        assert update_call_args[0][1]["return_transaction_no"] is None
        assert update_call_args[0][1]["return_date_time"] is None
        assert update_call_args[0][1]["return_staff_id"] is None

    @pytest.mark.asyncio
    async def test_reset_refund_status_no_existing_document(self, repository):
        """
        Test resetting refund status when no status document exists
        """
        # Test data
        tenant_id = "test_tenant"
        store_code = "S0001"
        terminal_no = 1
        transaction_no = 1001

        # Mock get_status_by_transaction_async to return None
        repository.get_status_by_transaction_async = AsyncMock(return_value=None)
        repository.update_one_async = AsyncMock()

        # Reset refund status
        result = await repository.reset_refund_status_async(tenant_id, store_code, terminal_no, transaction_no)

        # Should return None
        assert result is None

        # Verify no update was attempted
        repository.update_one_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_reset_refund_status_preserves_void_info(self, repository):
        """
        Test that resetting refund status preserves void information
        """
        # Test data
        tenant_id = "test_tenant"
        store_code = "S0001"
        terminal_no = 1
        transaction_no = 1001

        # Create existing status document with both void and refund info
        existing_status = TransactionStatusDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            is_voided=True,
            void_transaction_no=3001,
            void_date_time="2024-01-15 10:00:00",
            void_staff_id="STAFF001",
            is_refunded=True,
            return_transaction_no=2001,
            return_date_time="2024-01-15 14:30:00",
            return_staff_id="STAFF002",
        )

        # Updated status after reset (void info preserved)
        updated_status = TransactionStatusDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            is_voided=True,
            void_transaction_no=3001,
            void_date_time="2024-01-15 10:00:00",
            void_staff_id="STAFF001",
            is_refunded=False,
            return_transaction_no=None,
            return_date_time=None,
            return_staff_id=None,
        )

        # Mock methods
        repository.get_status_by_transaction_async = AsyncMock(side_effect=[existing_status, updated_status])
        repository.update_one_async = AsyncMock(return_value=None)

        # Reset refund status
        result = await repository.reset_refund_status_async(tenant_id, store_code, terminal_no, transaction_no)

        # Verify result - void info should be preserved
        assert result is not None
        assert result.is_voided is True
        assert result.void_transaction_no == 3001
        assert result.is_refunded is False
        assert result.return_transaction_no is None
