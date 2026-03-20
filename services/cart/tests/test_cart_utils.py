"""
Unit tests for cart utility modules: settings.py and pubsub_manager.py
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.documents.settings_master_document import SettingsMasterDocument, SettingsValue


class TestGetSettingValue:
    """Tests for app.utils.settings.get_setting_value"""

    def _make_setting(self, values=None, default_value=None):
        """Helper to create a SettingsMasterDocument with given values."""
        return SettingsMasterDocument(
            name="test_setting",
            default_value=default_value,
            values=values or [],
        )

    def _make_value(self, store_code=None, terminal_no=None, value="val"):
        return SettingsValue(store_code=store_code, terminal_no=terminal_no, value=value)

    @patch("app.utils.settings.settings")
    def test_terminal_and_store_specific_match(self, mock_settings):
        """Most specific match: store_code + terminal_no both match."""
        from app.utils.settings import get_setting_value

        setting = self._make_setting(values=[
            self._make_value(store_code="S1", terminal_no=1, value="terminal_specific"),
            self._make_value(store_code="S1", terminal_no=None, value="store_level"),
            self._make_value(store_code=None, terminal_no=None, value="global"),
        ])
        result = get_setting_value("test_setting", "S1", 1, setting)
        assert result == "terminal_specific"

    @patch("app.utils.settings.settings")
    def test_store_level_fallback(self, mock_settings):
        """Falls back to store-level when no terminal-specific match."""
        from app.utils.settings import get_setting_value

        setting = self._make_setting(values=[
            self._make_value(store_code="S1", terminal_no=None, value="store_level"),
            self._make_value(store_code=None, terminal_no=None, value="global"),
        ])
        result = get_setting_value("test_setting", "S1", 99, setting)
        assert result == "store_level"

    @patch("app.utils.settings.settings")
    def test_global_fallback(self, mock_settings):
        """Falls back to global when no store-specific match."""
        from app.utils.settings import get_setting_value

        setting = self._make_setting(values=[
            self._make_value(store_code=None, terminal_no=None, value="global"),
        ])
        result = get_setting_value("test_setting", "OTHER", 1, setting)
        assert result == "global"

    @patch("app.utils.settings.settings")
    def test_default_value_fallback(self, mock_settings):
        """Falls back to default_value when no matching values entry."""
        from app.utils.settings import get_setting_value

        setting = self._make_setting(values=[], default_value="default_val")
        result = get_setting_value("test_setting", "S1", 1, setting)
        assert result == "default_val"

    @patch("app.utils.settings.settings")
    def test_no_match_returns_none(self, mock_settings):
        """Returns None when no match and no default_value."""
        from app.utils.settings import get_setting_value

        setting = self._make_setting(values=[], default_value=None)
        result = get_setting_value("test_setting", "S1", 1, setting)
        assert result is None

    @patch("app.utils.settings.settings")
    def test_setting_none_falls_back_to_settings_module(self, mock_settings):
        """When setting is None, reads from the settings module attribute."""
        from app.utils.settings import get_setting_value

        mock_settings.some_attr = "from_module"
        result = get_setting_value("some_attr", "S1", 1, setting=None)
        assert result == "from_module"

    @patch("app.utils.settings.settings")
    def test_setting_none_attr_not_found(self, mock_settings):
        """When setting is None and attr doesn't exist, returns None."""
        from app.utils.settings import get_setting_value

        # Use a spec to ensure the attribute does not exist
        mock_settings_obj = MagicMock(spec=[])
        with patch("app.utils.settings.settings", mock_settings_obj):
            result = get_setting_value("nonexistent_attr", "S1", 1, setting=None)
        assert result is None

    @patch("app.utils.settings.settings")
    def test_priority_terminal_over_store(self, mock_settings):
        """Terminal+store match takes priority over store-only match."""
        from app.utils.settings import get_setting_value

        setting = self._make_setting(values=[
            self._make_value(store_code="S1", terminal_no=None, value="store_level"),
            self._make_value(store_code="S1", terminal_no=5, value="terminal_specific"),
        ])
        result = get_setting_value("test_setting", "S1", 5, setting)
        assert result == "terminal_specific"


class TestPubsubManager:
    """Tests for app.utils.pubsub_manager.PubsubManager"""

    @pytest.fixture
    def manager(self):
        """Create a PubsubManager with a mocked DaprClientHelper."""
        with patch("app.utils.pubsub_manager.DaprClientHelper") as MockHelper:
            mock_client = AsyncMock()
            MockHelper.return_value = mock_client
            from app.utils.pubsub_manager import PubsubManager
            mgr = PubsubManager()
            mgr._dapr_client = mock_client
            yield mgr, mock_client

    @pytest.mark.asyncio
    async def test_publish_success(self, manager):
        """publish_message_async returns (True, None) on success."""
        mgr, mock_client = manager
        mock_client.publish_event = AsyncMock(return_value=True)

        success, error = await mgr.publish_message_async("pubsub", "topic", {"key": "val"})
        assert success is True
        assert error is None
        mock_client.publish_event.assert_awaited_once_with(
            pubsub_name="pubsub", topic_name="topic", event_data={"key": "val"}
        )

    @pytest.mark.asyncio
    async def test_publish_failure(self, manager):
        """publish_message_async returns (False, error_message) when publish returns False."""
        mgr, mock_client = manager
        mock_client.publish_event = AsyncMock(return_value=False)

        success, error = await mgr.publish_message_async("pubsub", "topic", {"key": "val"})
        assert success is False
        assert "Failed to publish message" in error

    @pytest.mark.asyncio
    async def test_publish_exception(self, manager):
        """publish_message_async returns (False, error_message) on exception."""
        mgr, mock_client = manager
        mock_client.publish_event = AsyncMock(side_effect=RuntimeError("connection lost"))

        success, error = await mgr.publish_message_async("pubsub", "topic", {"key": "val"})
        assert success is False
        assert "connection lost" in error

    @pytest.mark.asyncio
    async def test_close(self, manager):
        """close() delegates to the dapr client."""
        mgr, mock_client = manager
        mock_client.close = AsyncMock()

        await mgr.close()
        mock_client.close.assert_awaited_once()
