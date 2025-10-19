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
Unit tests for ItemMasterGrpcRepository gRPC channel pooling

Tests verify that gRPC channels and stubs are properly created, reused, and closed.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.repositories.item_master_grpc_repository import ItemMasterGrpcRepository
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.exceptions import RepositoryException


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


@pytest.mark.asyncio
async def test_get_stub_creates_channel_on_first_call(repository):
    """Test that _get_stub creates channel on first call"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel = MagicMock()
        mock_get_channel.return_value = mock_channel

        # First call should create channel
        stub = await repository._get_stub()

        assert repository._channel == mock_channel
        assert repository._stub is not None
        mock_get_channel.assert_called_once()


@pytest.mark.asyncio
async def test_get_stub_reuses_existing_channel(repository):
    """
    Test that _get_stub reuses existing channel (CORE FUNCTIONALITY)

    This is the key test that verifies channel pooling is working correctly.
    The second call should NOT create a new channel, but reuse the existing one.
    """
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel = MagicMock()
        mock_get_channel.return_value = mock_channel

        # First call creates channel
        stub1 = await repository._get_stub()

        # Second call should reuse channel
        stub2 = await repository._get_stub()

        # Verify same stub instance is returned
        assert stub1 is stub2
        assert repository._channel == mock_channel

        # Verify get_channel was called only once
        mock_get_channel.assert_called_once()


@pytest.mark.asyncio
async def test_close_closes_channel(repository):
    """Test that close() properly closes the channel"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock()
        mock_get_channel.return_value = mock_channel

        # Create channel
        await repository._get_stub()
        assert repository._channel is not None

        # Close
        await repository.close()

        # Verify channel was closed
        mock_channel.close.assert_called_once()
        assert repository._channel is None
        assert repository._stub is None


@pytest.mark.asyncio
async def test_get_stub_after_close_creates_new_channel(repository):
    """Test that _get_stub creates new channel after close"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel1 = MagicMock()
        mock_channel1.close = AsyncMock()
        mock_channel2 = MagicMock()
        mock_get_channel.side_effect = [mock_channel1, mock_channel2]

        # Create and close
        await repository._get_stub()
        await repository.close()

        # Create again - should create new channel
        await repository._get_stub()

        assert repository._channel == mock_channel2
        assert mock_get_channel.call_count == 2


@pytest.mark.asyncio
async def test_get_item_by_code_uses_shared_stub(repository):
    """Test that get_item_by_code_async uses shared stub"""
    with patch.object(repository, '_get_stub', new_callable=AsyncMock) as mock_get_stub:
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

        # Call twice with different items
        item1 = await repository.get_item_by_code_async("ITEM001")

        # Mock different response for second call
        mock_response2 = MagicMock()
        mock_response2.item_code = "ITEM002"
        mock_response2.item_name = "Test Item 2"
        mock_response2.price = 200.0
        mock_response2.tax_code = "T1"
        mock_response2.category_code = "CAT2"
        mock_response2.is_active = True
        mock_stub.GetItemDetail = AsyncMock(return_value=mock_response2)

        item2 = await repository.get_item_by_code_async("ITEM002")

        # Verify _get_stub was called for both requests
        assert mock_get_stub.call_count == 2

        # Verify items were created correctly
        assert item1.item_code == "ITEM001"
        assert item2.item_code == "ITEM002"


@pytest.mark.asyncio
async def test_close_handles_errors_gracefully(repository):
    """Test that close() handles errors gracefully"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock(side_effect=Exception("Close failed"))
        mock_get_channel.return_value = mock_channel

        # Create channel
        await repository._get_stub()

        # Close should not raise exception even if channel.close() fails
        await repository.close()

        # Should still reset state despite error
        assert repository._channel is None
        assert repository._stub is None


@pytest.mark.asyncio
async def test_close_without_channel_is_safe(repository):
    """Test that calling close() without creating channel is safe"""
    # Close without creating channel should not raise exception
    await repository.close()

    assert repository._channel is None
    assert repository._stub is None


@pytest.mark.asyncio
async def test_multiple_close_calls_are_safe(repository):
    """Test that calling close() multiple times is safe"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock()
        mock_get_channel.return_value = mock_channel

        # Create channel
        await repository._get_stub()

        # Close multiple times
        await repository.close()
        await repository.close()
        await repository.close()

        # channel.close() should only be called once (first close)
        assert mock_channel.close.call_count == 1
        assert repository._channel is None
        assert repository._stub is None


@pytest.mark.asyncio
async def test_get_stub_handles_channel_creation_error(repository):
    """Test that _get_stub properly handles channel creation errors"""
    with patch.object(repository.grpc_helper, 'get_channel', new_callable=AsyncMock) as mock_get_channel:
        # Simulate channel creation failure
        mock_get_channel.side_effect = Exception("Channel creation failed")

        # Should raise RepositoryException
        with pytest.raises(RepositoryException) as exc_info:
            await repository._get_stub()

        assert "Failed to create gRPC channel" in str(exc_info.value)
        assert repository._channel is None
        assert repository._stub is None
