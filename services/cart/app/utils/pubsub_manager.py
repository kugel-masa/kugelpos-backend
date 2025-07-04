#!/usr/bin/env python  # -*- coding: utf-8 -*-  # Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from typing import Any, Dict, Optional, Tuple

from kugel_common.utils.dapr_client_helper import DaprClientHelper
from app.config.settings import settings
from app.exceptions import ExternalServiceException

logger = getLogger(__name__)


class PubsubManager:
    """
    Manager for handling pubsub message publishing to Dapr.
    Uses DaprClientHelper for unified Dapr communication with built-in circuit breaker.
    Non-blocking implementation that allows application to continue even when publishing fails.
    """

    def __init__(self):
        """
        Constructor for PubsubManager.
        Initializes DaprClientHelper with circuit breaker.
        """
        # Use DaprClientHelper with circuit breaker
        self._dapr_client = DaprClientHelper(
            circuit_breaker_threshold=3,  # Open circuit after 3 consecutive failures
            circuit_breaker_timeout=60,  # Transition to half-open state after 60 seconds
        )

    async def publish_message_async(
        self, pubsub_name: str, topic_name: str, message: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Publish a message to a Dapr pubsub component.
        Non-blocking implementation that returns success/failure status instead of raising exceptions.

        Args:
            pubsub_name: The name of the pubsub component in Dapr
            topic_name: The name of the topic to publish to
            message: The message to publish

        Returns:
            Tuple[bool, Optional[str]]: (True if successful, None) or (False, error message)
        """
        logger.debug(f"Publishing message to {pubsub_name}/{topic_name}: {message}")

        try:
            success = await self._dapr_client.publish_event(
                pubsub_name=pubsub_name, topic_name=topic_name, event_data=message
            )

            if success:
                return True, None
            else:
                error_message = f"Failed to publish message to {pubsub_name}/{topic_name}"
                return False, error_message

        except Exception as e:
            error_message = f"Failed to publish message: {e}"
            logger.error(error_message)
            return False, error_message

    async def close(self):
        """
        Close the Dapr client connection.
        """
        await self._dapr_client.close()
