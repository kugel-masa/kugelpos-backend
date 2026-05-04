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
import pytest
from unittest.mock import AsyncMock, patch

from app.utils.pubsub_manager import PubsubManager


class TestPubsubManagerPublish:
    """Tests for PubsubManager.publish_message_async"""

    @pytest.fixture
    def manager(self):
        with patch(
            "app.utils.pubsub_manager.DaprClientHelper"
        ) as MockHelper:
            mock_client = AsyncMock()
            MockHelper.return_value = mock_client
            mgr = PubsubManager()
            mgr._dapr_client = mock_client
            yield mgr, mock_client

    @pytest.mark.asyncio
    async def test_publish_success(self, manager):
        """publish_event returns True -> (True, None)"""
        mgr, mock_client = manager
        mock_client.publish_event.return_value = True

        success, error = await mgr.publish_message_async(
            "pubsub", "topic", {"key": "value"}
        )

        assert success is True
        assert error is None
        mock_client.publish_event.assert_called_once_with(
            pubsub_name="pubsub", topic_name="topic", event_data={"key": "value"}
        )

    @pytest.mark.asyncio
    async def test_publish_failure(self, manager):
        """publish_event returns False -> (False, error_message)"""
        mgr, mock_client = manager
        mock_client.publish_event.return_value = False

        success, error = await mgr.publish_message_async(
            "pubsub", "topic", {"key": "value"}
        )

        assert success is False
        assert "Failed to publish message" in error
        assert "pubsub/topic" in error

    @pytest.mark.asyncio
    async def test_publish_exception(self, manager):
        """publish_event raises exception -> (False, error_message)"""
        mgr, mock_client = manager
        mock_client.publish_event.side_effect = RuntimeError("connection failed")

        success, error = await mgr.publish_message_async(
            "pubsub", "topic", {"key": "value"}
        )

        assert success is False
        assert "Failed to publish message" in error
        assert "connection failed" in error


class TestPubsubManagerClose:
    """Tests for PubsubManager.close"""

    @pytest.mark.asyncio
    async def test_close(self):
        """close delegates to DaprClientHelper.close"""
        with patch(
            "app.utils.pubsub_manager.DaprClientHelper"
        ) as MockHelper:
            mock_client = AsyncMock()
            MockHelper.return_value = mock_client
            mgr = PubsubManager()
            mgr._dapr_client = mock_client

            await mgr.close()

            mock_client.close.assert_called_once()
