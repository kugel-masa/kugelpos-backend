# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Unit tests for ItemMasterGrpcRepository with module-level channel pooling

Tests verify that the repository correctly uses the module-level channel helper
for gRPC communication with master-data service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.repositories.item_master_grpc_repository import ItemMasterGrpcRepository
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
import app.utils.grpc_channel_helper as channel_helper


@pytest.fixture
def terminal_info():
    """Create a test terminal info document"""
    return TerminalInfoDocument(
        terminal_id="TEST001",
        store_code="STORE01",
        terminal_name="Test Terminal"
    )


@pytest.fixture
def repository(terminal_info):
    """Create a test repository instance"""
    return ItemMasterGrpcRepository(
        tenant_id="test_tenant",
        store_code="STORE01",
        terminal_info=terminal_info
    )


@pytest.fixture(autouse=True)
def clear_channel_cache():
    """Clear the channel cache before and after each test"""
    channel_helper._channels.clear()
    channel_helper._stubs.clear()
    yield
    channel_helper._channels.clear()
    channel_helper._stubs.clear()


@pytest.mark.asyncio
async def test_get_item_by_code_uses_module_level_stub(repository):
    """Test that get_item_by_code_async uses module-level channel helper"""
    with patch('app.utils.grpc_channel_helper.get_master_data_grpc_stub', new_callable=AsyncMock) as mock_get_stub:
        mock_stub = MagicMock()
        mock_response = MagicMock()
        mock_response.item_code = "ITEM001"
        mock_response.item_name = "Test Item"
        mock_response.price = 100.0
        mock_response.tax_code = "T1"
        mock_response.category_code = "CAT1"
        mock_response.is_active = True

        mock_stub.GetItemDetail = AsyncMock(return_value=mock_response)
        mock_get_stub.return_value = mock_stub

        # Call get_item_by_code_async
        item = await repository.get_item_by_code_async("ITEM001")

        # Verify module-level helper was called with correct parameters
        mock_get_stub.assert_called_once_with("test_tenant", "STORE01")

        # Verify item was created correctly
        assert item.item_code == "ITEM001"
        assert item.description == "Test Item"
        assert item.unit_price == 100.0


@pytest.mark.asyncio
async def test_get_item_by_code_multiple_calls_reuse_stub(repository):
    """
    Test that multiple get_item_by_code_async calls reuse the same stub (CORE FUNCTIONALITY)

    This verifies that the module-level channel pooling is working correctly.
    """
    with patch('app.utils.grpc_channel_helper.get_master_data_grpc_stub', new_callable=AsyncMock) as mock_get_stub:
        mock_stub = MagicMock()
        mock_response1 = MagicMock()
        mock_response1.item_code = "ITEM001"
        mock_response1.item_name = "Test Item 1"
        mock_response1.price = 100.0
        mock_response1.tax_code = "T1"
        mock_response1.category_code = "CAT1"
        mock_response1.is_active = True

        mock_response2 = MagicMock()
        mock_response2.item_code = "ITEM002"
        mock_response2.item_name = "Test Item 2"
        mock_response2.price = 200.0
        mock_response2.tax_code = "T1"
        mock_response2.category_code = "CAT2"
        mock_response2.is_active = True

        mock_stub.GetItemDetail = AsyncMock(side_effect=[mock_response1, mock_response2])
        mock_get_stub.return_value = mock_stub

        # Call twice
        item1 = await repository.get_item_by_code_async("ITEM001")
        item2 = await repository.get_item_by_code_async("ITEM002")

        # Verify items were created correctly
        assert item1.item_code == "ITEM001"
        assert item2.item_code == "ITEM002"

        # Verify get_master_data_grpc_stub was called twice
        # (The helper itself handles caching, repository just calls it)
        assert mock_get_stub.call_count == 2


@pytest.mark.asyncio
async def test_get_item_by_code_from_cache(repository):
    """Test that get_item_by_code_async returns item from cache if available"""
    # Pre-populate cache
    from app.models.documents.item_master_document import ItemMasterDocument
    cached_item = ItemMasterDocument(
        tenant_id="test_tenant",
        store_code="STORE01",
        item_code="CACHED_ITEM",
        description="Cached Item",
        unit_price=50.0,
        tax_code="T1",
        category_code="CAT1",
    )
    repository.item_master_documents = [cached_item]

    with patch('app.utils.grpc_channel_helper.get_master_data_grpc_stub', new_callable=AsyncMock) as mock_get_stub:
        # Get item from cache
        item = await repository.get_item_by_code_async("CACHED_ITEM")

        # Verify item was returned from cache
        assert item.item_code == "CACHED_ITEM"
        assert item.description == "Cached Item"

        # Verify gRPC stub was NOT called (cache hit)
        mock_get_stub.assert_not_called()


@pytest.mark.asyncio
async def test_get_item_by_code_adds_to_cache(repository):
    """Test that get_item_by_code_async adds fetched item to cache"""
    with patch('app.utils.grpc_channel_helper.get_master_data_grpc_stub', new_callable=AsyncMock) as mock_get_stub:
        mock_stub = MagicMock()
        mock_response = MagicMock()
        mock_response.item_code = "NEW_ITEM"
        mock_response.item_name = "New Item"
        mock_response.price = 150.0
        mock_response.tax_code = "T1"
        mock_response.category_code = "CAT1"
        mock_response.is_active = True

        mock_stub.GetItemDetail = AsyncMock(return_value=mock_response)
        mock_get_stub.return_value = mock_stub

        # Initially no items in cache
        assert repository.item_master_documents is None or len(repository.item_master_documents) == 0

        # Fetch item
        item = await repository.get_item_by_code_async("NEW_ITEM")

        # Verify item was added to cache
        assert len(repository.item_master_documents) == 1
        assert repository.item_master_documents[0].item_code == "NEW_ITEM"


@pytest.mark.asyncio
async def test_set_item_master_documents(repository):
    """Test that set_item_master_documents properly sets the cache"""
    from app.models.documents.item_master_document import ItemMasterDocument

    items = [
        ItemMasterDocument(
            tenant_id="test_tenant",
            store_code="STORE01",
            item_code="ITEM001",
            description="Item 1",
            unit_price=100.0,
            tax_code="T1",
            category_code="CAT1",
        ),
        ItemMasterDocument(
            tenant_id="test_tenant",
            store_code="STORE01",
            item_code="ITEM002",
            description="Item 2",
            unit_price=200.0,
            tax_code="T1",
            category_code="CAT2",
        ),
    ]

    repository.set_item_master_documents(items)

    assert len(repository.item_master_documents) == 2
    assert repository.item_master_documents[0].item_code == "ITEM001"
    assert repository.item_master_documents[1].item_code == "ITEM002"
