"""Unit tests for StateStoreManager (stock service)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_save_state_success():
    """save_state should return (True, None) when Dapr succeeds."""
    with patch("app.utils.state_store_manager.DaprClientHelper") as MockHelper:
        mock_client = AsyncMock()
        mock_client.save_state.return_value = True
        MockHelper.return_value = mock_client

        from app.utils.state_store_manager import StateStoreManager
        mgr = StateStoreManager()

        result = await mgr.save_state("id1", {"key": "value"})
        assert result == (True, None)
        mock_client.save_state.assert_called_once_with(
            store_name="statestore", key="id1", value={"key": "value"}
        )


@pytest.mark.asyncio
async def test_save_state_failure():
    """save_state should return (False, error_message) when Dapr returns False."""
    with patch("app.utils.state_store_manager.DaprClientHelper") as MockHelper:
        mock_client = AsyncMock()
        mock_client.save_state.return_value = False
        MockHelper.return_value = mock_client

        from app.utils.state_store_manager import StateStoreManager
        mgr = StateStoreManager()

        success, error = await mgr.save_state("id1", {"key": "value"})
        assert success is False
        assert "Failed to save state" in error


@pytest.mark.asyncio
async def test_save_state_exception():
    """save_state should return (False, error_message) on exception."""
    with patch("app.utils.state_store_manager.DaprClientHelper") as MockHelper:
        mock_client = AsyncMock()
        mock_client.save_state.side_effect = Exception("connection error")
        MockHelper.return_value = mock_client

        from app.utils.state_store_manager import StateStoreManager
        mgr = StateStoreManager()

        success, error = await mgr.save_state("id1", {})
        assert success is False
        assert "Exception occurred while saving state" in error


@pytest.mark.asyncio
async def test_get_state_success():
    """get_state should return (data, None) when state exists."""
    with patch("app.utils.state_store_manager.DaprClientHelper") as MockHelper:
        mock_client = AsyncMock()
        mock_client.get_state.return_value = {"status": "processed"}
        MockHelper.return_value = mock_client

        from app.utils.state_store_manager import StateStoreManager
        mgr = StateStoreManager()

        data, error = await mgr.get_state("id1")
        assert data == {"status": "processed"}
        assert error is None


@pytest.mark.asyncio
async def test_get_state_not_found():
    """get_state should return (None, None) when state does not exist."""
    with patch("app.utils.state_store_manager.DaprClientHelper") as MockHelper:
        mock_client = AsyncMock()
        mock_client.get_state.return_value = None
        MockHelper.return_value = mock_client

        from app.utils.state_store_manager import StateStoreManager
        mgr = StateStoreManager()

        data, error = await mgr.get_state("nonexistent")
        assert data is None
        assert error is None


@pytest.mark.asyncio
async def test_get_state_exception():
    """get_state should return (None, error_message) on exception."""
    with patch("app.utils.state_store_manager.DaprClientHelper") as MockHelper:
        mock_client = AsyncMock()
        mock_client.get_state.side_effect = Exception("timeout")
        MockHelper.return_value = mock_client

        from app.utils.state_store_manager import StateStoreManager
        mgr = StateStoreManager()

        data, error = await mgr.get_state("id1")
        assert data is None
        assert "Exception occurred while retrieving state" in error


@pytest.mark.asyncio
async def test_close():
    """close should delegate to DaprClientHelper.close."""
    with patch("app.utils.state_store_manager.DaprClientHelper") as MockHelper:
        mock_client = AsyncMock()
        MockHelper.return_value = mock_client

        from app.utils.state_store_manager import StateStoreManager
        mgr = StateStoreManager()

        await mgr.close()
        mock_client.close.assert_called_once()
