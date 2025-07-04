# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
import pytest_asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.services.tran_service import TranService
from app.models.documents.transaction_status_document import TransactionStatusDocument
from app.exceptions import AlreadyVoidedException, AlreadyRefundedException


@pytest.fixture
def mock_terminal_info():
    """Create mock terminal info"""
    terminal_info = MagicMock(spec=TerminalInfoDocument)
    terminal_info.tenant_id = "test_tenant"
    terminal_info.store_code = "S0001"
    terminal_info.terminal_no = 1
    terminal_info.business_date = "20240101"
    terminal_info.business_counter = 1
    terminal_info.open_counter = 1
    return terminal_info


@pytest.fixture
def mock_repositories():
    """Create mock repositories"""
    return {
        "terminal_counter_repo": AsyncMock(),
        "tranlog_repo": AsyncMock(),
        "tranlog_delivery_status_repo": AsyncMock(),
        "settings_master_repo": AsyncMock(),
        "payment_master_repo": AsyncMock(),
        "transaction_status_repo": AsyncMock(),
    }


@pytest_asyncio.fixture
async def tran_service(mock_terminal_info, mock_repositories):
    """Create TranService instance with mocks and proper cleanup"""
    service = TranService(terminal_info=mock_terminal_info, **mock_repositories)

    yield service

    # Clean up the service to close HTTP clients
    await service.close()


@pytest.mark.asyncio
async def test_get_transaction_list_with_status_empty_list(tran_service):
    """Test getting transaction list with status when list is empty"""
    result = await tran_service.get_transaction_list_with_status_async([])
    assert result == []


@pytest.mark.asyncio
async def test_get_transaction_list_with_status_merges_correctly(tran_service, mock_repositories):
    """Test that transaction status is correctly merged from history"""
    # Create test transactions - using MagicMock to avoid validation issues
    tran1 = MagicMock(spec=BaseTransaction)
    tran1.tenant_id = "test_tenant"
    tran1.store_code = "S0001"
    tran1.terminal_no = 1
    tran1.transaction_no = 1001
    tran1.is_voided = False
    tran1.is_refunded = False

    tran2 = MagicMock(spec=BaseTransaction)
    tran2.tenant_id = "test_tenant"
    tran2.store_code = "S0001"
    tran2.terminal_no = 1
    tran2.transaction_no = 1002
    tran2.is_voided = False
    tran2.is_refunded = False

    tran3 = MagicMock(spec=BaseTransaction)
    tran3.tenant_id = "test_tenant"
    tran3.store_code = "S0001"
    tran3.terminal_no = 1
    tran3.transaction_no = 1003
    tran3.is_voided = False
    tran3.is_refunded = False

    transaction_list = [tran1, tran2, tran3]

    # Mock status repository response
    status_dict = {
        1001: TransactionStatusDocument(
            tenant_id="test_tenant",
            store_code="S0001",
            terminal_no=1,
            transaction_no=1001,
            is_voided=True,
            is_refunded=False,
            void_transaction_no=2001,
        ),
        1002: TransactionStatusDocument(
            tenant_id="test_tenant",
            store_code="S0001",
            terminal_no=1,
            transaction_no=1002,
            is_voided=False,
            is_refunded=True,
            return_transaction_no=2002,
        ),
        # 1003 has no status document
    }

    mock_repositories["transaction_status_repo"].get_status_for_transactions_async.return_value = status_dict

    # Call the method
    result = await tran_service.get_transaction_list_with_status_async(transaction_list)

    # Verify
    assert len(result) == 3

    # Transaction 1 should be marked as voided
    assert result[0].is_voided is True
    assert result[0].is_refunded is False

    # Transaction 2 should be marked as refunded
    assert result[1].is_voided is False
    assert result[1].is_refunded is True

    # Transaction 3 should remain unchanged
    assert result[2].is_voided is False
    assert result[2].is_refunded is False

    # Verify the repository was called correctly
    mock_repositories["transaction_status_repo"].get_status_for_transactions_async.assert_called_once_with(
        tenant_id="test_tenant", store_code="S0001", terminal_no=1, transaction_nos=[1001, 1002, 1003]
    )


@pytest.mark.asyncio
async def test_void_async_checks_status_history(tran_service, mock_repositories):
    """Test that void_async checks transaction status history"""
    # Create a transaction
    tran = BaseTransaction(
        tenant_id="test_tenant",
        store_code="S0001",
        terminal_no=1,
        transaction_no=1001,
        transaction_type=101,
        sales=BaseTransaction.SalesInfo(),
    )

    # Mock status repository to return already voided
    status = TransactionStatusDocument(
        tenant_id="test_tenant",
        store_code="S0001",
        terminal_no=1,
        transaction_no=1001,
        is_voided=True,
        void_transaction_no=2001,
    )
    mock_repositories["transaction_status_repo"].get_status_by_transaction_async.return_value = status

    # Attempt to void - should raise exception
    with pytest.raises(AlreadyVoidedException) as exc_info:
        await tran_service.void_async(tran, [{"payment_code": "01", "amount": 100}])

    assert "already been voided" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_return_async_checks_refund_status(tran_service, mock_repositories):
    """Test that return_async checks if transaction is already refunded"""
    # Create a transaction
    tran = BaseTransaction(
        tenant_id="test_tenant",
        store_code="S0001",
        terminal_no=1,
        transaction_no=1001,
        transaction_type=101,
        sales=BaseTransaction.SalesInfo(),
    )

    # Mock status repository to return already refunded
    status = TransactionStatusDocument(
        tenant_id="test_tenant",
        store_code="S0001",
        terminal_no=1,
        transaction_no=1001,
        is_refunded=True,
        return_transaction_no=2002,
    )
    mock_repositories["transaction_status_repo"].get_status_by_transaction_async.return_value = status

    # Attempt to return - should raise exception
    with pytest.raises(AlreadyRefundedException) as exc_info:
        await tran_service.return_async(tran, [{"payment_code": "01", "amount": 100}])

    assert "already been refunded" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_return_async_checks_void_status(tran_service, mock_repositories):
    """Test that return_async checks if transaction is already voided"""
    # Create a transaction
    tran = BaseTransaction(
        tenant_id="test_tenant",
        store_code="S0001",
        terminal_no=1,
        transaction_no=1001,
        transaction_type=101,
        sales=BaseTransaction.SalesInfo(),
    )

    # Mock status repository to return already voided
    status = TransactionStatusDocument(
        tenant_id="test_tenant",
        store_code="S0001",
        terminal_no=1,
        transaction_no=1001,
        is_voided=True,
        void_transaction_no=2001,
    )
    mock_repositories["transaction_status_repo"].get_status_by_transaction_async.return_value = status

    # Attempt to return - should raise exception
    with pytest.raises(AlreadyVoidedException) as exc_info:
        await tran_service.return_async(tran, [{"payment_code": "01", "amount": 100}])

    assert "already been voided" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_tranlog_by_query_merges_status(tran_service, mock_repositories):
    """Test that get_tranlog_by_query_async merges status from history"""
    # Mock tranlog repository response
    from kugel_common.schemas.pagination import PaginatedResult
    from kugel_common.schemas.base_schemas import Metadata

    tran1 = MagicMock(spec=BaseTransaction)
    tran1.transaction_no = 1001
    tran1.is_voided = False
    tran1.is_refunded = False

    tran2 = MagicMock(spec=BaseTransaction)
    tran2.transaction_no = 1002
    tran2.is_voided = False
    tran2.is_refunded = False

    paginated_result = PaginatedResult(
        data=[tran1, tran2], metadata=Metadata(total=2, page=1, limit=10, sort=None, filter=None)
    )

    mock_repositories["tranlog_repo"].get_tranlog_list_by_query_async.return_value = paginated_result

    # Mock status repository
    status_dict = {
        1001: TransactionStatusDocument(
            tenant_id="test_tenant",
            store_code="S0001",
            terminal_no=1,
            transaction_no=1001,
            is_voided=True,
            is_refunded=False,
        )
    }
    mock_repositories["transaction_status_repo"].get_status_for_transactions_async.return_value = status_dict

    # Call the method
    result = await tran_service.get_tranlog_by_query_async(store_code="S0001", terminal_no=1, limit=10, page=1)

    # Verify status was merged
    assert result.data[0].is_voided is True
    assert result.data[0].is_refunded is False
    assert result.data[1].is_voided is False
    assert result.data[1].is_refunded is False
