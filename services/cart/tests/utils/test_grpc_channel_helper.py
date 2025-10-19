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
Unit tests for gRPC Channel Helper

Tests verify that gRPC channels are properly created, reused, and closed
at the module level (shared across all requests).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import app.utils.grpc_channel_helper as channel_helper


@pytest.fixture(autouse=True)
def clear_channel_cache():
    """Clear the channel cache before and after each test"""
    # Clear before test
    channel_helper._channels.clear()
    channel_helper._stubs.clear()

    yield

    # Clear after test
    channel_helper._channels.clear()
    channel_helper._stubs.clear()


@pytest.mark.asyncio
async def test_get_stub_creates_channel_on_first_call():
    """Test that get_master_data_grpc_stub creates channel on first call"""
    with patch('app.utils.grpc_channel_helper.GrpcClientHelper') as mock_helper_class:
        mock_helper = MagicMock()
        mock_channel = MagicMock()
        mock_helper.get_channel = AsyncMock(return_value=mock_channel)
        mock_helper_class.return_value = mock_helper

        # First call should create channel
        stub = await channel_helper.get_master_data_grpc_stub("test_tenant", "STORE01")

        assert stub is not None
        assert ("test_tenant", "STORE01") in channel_helper._channels
        assert ("test_tenant", "STORE01") in channel_helper._stubs
        mock_helper.get_channel.assert_called_once()


@pytest.mark.asyncio
async def test_get_stub_reuses_existing_channel():
    """
    Test that get_master_data_grpc_stub reuses existing channel (CORE FUNCTIONALITY)

    This is the critical test that verifies channel pooling is working correctly.
    The second call should NOT create a new channel, but reuse the existing one.
    """
    with patch('app.utils.grpc_channel_helper.GrpcClientHelper') as mock_helper_class:
        mock_helper = MagicMock()
        mock_channel = MagicMock()
        mock_helper.get_channel = AsyncMock(return_value=mock_channel)
        mock_helper_class.return_value = mock_helper

        # First call creates channel
        stub1 = await channel_helper.get_master_data_grpc_stub("test_tenant", "STORE01")

        # Second call should reuse channel
        stub2 = await channel_helper.get_master_data_grpc_stub("test_tenant", "STORE01")

        # Verify same stub instance is returned
        assert stub1 is stub2

        # Verify get_channel was called only once (channel reused)
        mock_helper.get_channel.assert_called_once()


@pytest.mark.asyncio
async def test_get_stub_creates_separate_channels_for_different_tenants():
    """Test that different tenant/store combinations get separate channels"""
    with patch('app.utils.grpc_channel_helper.GrpcClientHelper') as mock_helper_class:
        mock_helper = MagicMock()
        mock_channel1 = MagicMock()
        mock_channel2 = MagicMock()
        mock_helper.get_channel = AsyncMock(side_effect=[mock_channel1, mock_channel2])
        mock_helper_class.return_value = mock_helper

        # Create stubs for different tenant/store combinations
        stub1 = await channel_helper.get_master_data_grpc_stub("tenant1", "STORE01")
        stub2 = await channel_helper.get_master_data_grpc_stub("tenant2", "STORE02")

        # Verify different stubs
        assert stub1 is not stub2

        # Verify two channels were created
        assert len(channel_helper._channels) == 2
        assert len(channel_helper._stubs) == 2
        assert mock_helper.get_channel.call_count == 2


@pytest.mark.asyncio
async def test_close_all_channels():
    """Test that close_master_data_grpc_channels properly closes all channels"""
    with patch('app.utils.grpc_channel_helper.GrpcClientHelper') as mock_helper_class:
        mock_helper = MagicMock()
        mock_channel1 = MagicMock()
        mock_channel1.close = AsyncMock()
        mock_channel2 = MagicMock()
        mock_channel2.close = AsyncMock()
        mock_helper.get_channel = AsyncMock(side_effect=[mock_channel1, mock_channel2])
        mock_helper_class.return_value = mock_helper

        # Create two channels
        await channel_helper.get_master_data_grpc_stub("tenant1", "STORE01")
        await channel_helper.get_master_data_grpc_stub("tenant2", "STORE02")

        # Close all channels
        await channel_helper.close_master_data_grpc_channels()

        # Verify both channels were closed
        mock_channel1.close.assert_called_once()
        mock_channel2.close.assert_called_once()

        # Verify caches were cleared
        assert len(channel_helper._channels) == 0
        assert len(channel_helper._stubs) == 0


@pytest.mark.asyncio
async def test_get_stub_after_close_creates_new_channel():
    """Test that get_master_data_grpc_stub creates new channel after close"""
    with patch('app.utils.grpc_channel_helper.GrpcClientHelper') as mock_helper_class:
        mock_helper = MagicMock()
        mock_channel1 = MagicMock()
        mock_channel1.close = AsyncMock()
        mock_channel2 = MagicMock()
        mock_helper.get_channel = AsyncMock(side_effect=[mock_channel1, mock_channel2])
        mock_helper_class.return_value = mock_helper

        # Create and close
        await channel_helper.get_master_data_grpc_stub("test_tenant", "STORE01")
        await channel_helper.close_master_data_grpc_channels()

        # Create again - should create new channel
        await channel_helper.get_master_data_grpc_stub("test_tenant", "STORE01")

        # Verify get_channel was called twice
        assert mock_helper.get_channel.call_count == 2


@pytest.mark.asyncio
async def test_close_handles_errors_gracefully():
    """Test that close_master_data_grpc_channels handles errors gracefully"""
    with patch('app.utils.grpc_channel_helper.GrpcClientHelper') as mock_helper_class:
        mock_helper = MagicMock()
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock(side_effect=Exception("Close failed"))
        mock_helper.get_channel = AsyncMock(return_value=mock_channel)
        mock_helper_class.return_value = mock_helper

        # Create channel
        await channel_helper.get_master_data_grpc_stub("test_tenant", "STORE01")

        # Close should not raise exception even if channel.close() fails
        await channel_helper.close_master_data_grpc_channels()

        # Should still clear caches despite error
        assert len(channel_helper._channels) == 0
        assert len(channel_helper._stubs) == 0


@pytest.mark.asyncio
async def test_close_without_channels_is_safe():
    """Test that calling close without creating channels is safe"""
    # Close without creating channels should not raise exception
    await channel_helper.close_master_data_grpc_channels()

    assert len(channel_helper._channels) == 0
    assert len(channel_helper._stubs) == 0


@pytest.mark.asyncio
async def test_multiple_close_calls_are_safe():
    """Test that calling close multiple times is safe"""
    with patch('app.utils.grpc_channel_helper.GrpcClientHelper') as mock_helper_class:
        mock_helper = MagicMock()
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock()
        mock_helper.get_channel = AsyncMock(return_value=mock_channel)
        mock_helper_class.return_value = mock_helper

        # Create channel
        await channel_helper.get_master_data_grpc_stub("test_tenant", "STORE01")

        # Close multiple times
        await channel_helper.close_master_data_grpc_channels()
        await channel_helper.close_master_data_grpc_channels()
        await channel_helper.close_master_data_grpc_channels()

        # channel.close() should only be called once (first close, cache was cleared)
        assert mock_channel.close.call_count == 1


def test_get_channel_cache_stats():
    """Test that get_channel_cache_stats returns correct statistics"""
    # Clear cache first
    channel_helper._channels.clear()
    channel_helper._stubs.clear()

    # Empty cache
    stats = channel_helper.get_channel_cache_stats()
    assert stats['total_channels'] == 0
    assert stats['total_stubs'] == 0

    # Add mock entries
    channel_helper._channels[("tenant1", "store1")] = MagicMock()
    channel_helper._stubs[("tenant1", "store1")] = MagicMock()
    channel_helper._channels[("tenant2", "store2")] = MagicMock()
    channel_helper._stubs[("tenant2", "store2")] = MagicMock()

    # Check stats
    stats = channel_helper.get_channel_cache_stats()
    assert stats['total_channels'] == 2
    assert stats['total_stubs'] == 2
