# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.tran_service import TranService
from app.models.documents.transaction_status_document import TransactionStatusDocument
from app.exceptions import AlreadyVoidedException, AlreadyRefundedException
from app.exceptions.cart_error_codes import CartErrorCode


class TestTranServiceValidation:
    """Simple unit tests for TranService validation logic"""

    @pytest_asyncio.fixture
    async def service(self):
        """Create TranService instance with mocked dependencies and proper cleanup"""
        service = TranService(
            terminal_info=MagicMock(),
            terminal_counter_repo=MagicMock(),
            tranlog_repo=MagicMock(),
            tranlog_delivery_status_repo=MagicMock(),
            settings_master_repo=MagicMock(),
            payment_master_repo=MagicMock(),
            transaction_status_repo=MagicMock(),
        )

        yield service

        # Clean up the service to close HTTP clients
        await service.close()

    @pytest.mark.asyncio
    async def test_void_already_voided_transaction_raises_exception(self, service):
        """Test that void operation on already voided transaction raises exception"""

        # Mock transaction
        mock_transaction = MagicMock()
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
        service.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=existing_status)

        # Call void method and expect exception
        with pytest.raises(AlreadyVoidedException) as exc_info:
            await service.void_async(mock_transaction, [])

        assert exc_info.value.error_code == CartErrorCode.ALREADY_VOIDED

    @pytest.mark.asyncio
    async def test_return_already_refunded_transaction_raises_exception(self, service):
        """Test that return operation on already refunded transaction raises exception"""

        # Mock transaction
        mock_transaction = MagicMock()
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
        service.transaction_status_repo.get_status_by_transaction_async = AsyncMock(return_value=existing_status)

        # Call return method and expect exception
        with pytest.raises(AlreadyRefundedException) as exc_info:
            await service.return_async(mock_transaction, [])

        assert exc_info.value.error_code == CartErrorCode.ALREADY_REFUNDED

    @pytest.mark.asyncio
    async def test_get_transaction_list_with_status_merges_correctly(self, service):
        """Test that transaction list correctly merges void/return status"""

        # Create mock transactions
        mock_trans1 = MagicMock()
        mock_trans1.tenant_id = "test_tenant"
        mock_trans1.store_code = "S0001"
        mock_trans1.terminal_no = 1
        mock_trans1.transaction_no = 12345
        mock_trans1.is_voided = False
        mock_trans1.is_refunded = False

        mock_trans2 = MagicMock()
        mock_trans2.tenant_id = "test_tenant"
        mock_trans2.store_code = "S0001"
        mock_trans2.terminal_no = 1
        mock_trans2.transaction_no = 12346
        mock_trans2.is_voided = False
        mock_trans2.is_refunded = False

        transactions = [mock_trans1, mock_trans2]

        # Mock status documents
        status_dict = {
            12345: TransactionStatusDocument(
                tenant_id="test_tenant",
                store_code="S0001",
                terminal_no=1,
                transaction_no=12345,
                is_voided=True,
                is_refunded=False,
                void_transaction_no=12350,
            )
        }

        service.transaction_status_repo.get_status_for_transactions_async = AsyncMock(return_value=status_dict)

        # Call method
        result = await service.get_transaction_list_with_status_async(transactions)

        # Verify
        assert len(result) == 2
        assert result[0].is_voided is True  # Status applied
        assert result[1].is_voided is False  # No status, remains false
