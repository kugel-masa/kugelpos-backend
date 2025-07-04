# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from typing import Tuple, Optional

from kugel_common.utils.dapr_client_helper import DaprClientHelper
from app.config.settings import settings

# Get a logger instance for this module
logger = getLogger(__name__)


class StateStoreManager:
    """
    Manager for handling statestore operations with Dapr.
    Uses DaprClientHelper for unified Dapr communication with built-in circuit breaker.
    """

    def __init__(self):
        """
        Initializes DaprClientHelper with circuit breaker.
        """
        # Use DaprClientHelper with circuit breaker
        self._dapr_client = DaprClientHelper(
            circuit_breaker_threshold=3,  # Open circuit after 3 consecutive failures
            circuit_breaker_timeout=60,  # Transition to half-open state after 60 seconds
        )
        # Default state store name
        self._store_name = "statestore"

    async def save_state(self, state_id: str, state_data: dict) -> Tuple[bool, Optional[str]]:
        """
        Save a state to the Dapr statestore for idempotent message processing.
        Non-blocking implementation that returns success/failure status instead of raising exceptions.

        Args:
            state_id: The unique ID for the state (typically the message ID)
            state_data: The data to store in the state

        Returns:
            Tuple[bool, Optional[str]]: (True if successful, None) or (False, error message)
        """
        try:
            success = await self._dapr_client.save_state(store_name=self._store_name, key=state_id, value=state_data)

            if success:
                logger.info(f"State saved successfully. state_id: {state_id}, state_data: {state_data}")
                return True, None
            else:
                error_message = f"Failed to save state. state_id: {state_id}"
                return False, error_message

        except Exception as e:
            error_message = f"Exception occurred while saving state: {e}"
            logger.error(error_message)
            return False, error_message

    async def get_state(self, state_id: str) -> Tuple[Optional[dict], Optional[str]]:
        """
        Get a state from the Dapr statestore by its ID.
        Non-blocking implementation that returns success/failure status with error message.

        Args:
            state_id: The unique ID for the state (typically the message ID)

        Returns:
            Tuple[Optional[dict], Optional[str]]: (state data if found, None) or (None, error message)
        """
        try:
            state_data = await self._dapr_client.get_state(store_name=self._store_name, key=state_id)

            if state_data is None:
                logger.info(f"New state. state_id: {state_id}")
                return None, None
            else:
                logger.info(f"State retrieved successfully. state_id: {state_id}, state_data: {state_data}")
                return state_data, None

        except Exception as e:
            error_message = f"Exception occurred while retrieving state: {e}"
            logger.error(error_message)
            return None, error_message

    async def close(self):
        """
        Close the Dapr client connection.
        """
        await self._dapr_client.close()


# Create a singleton instance of StateStoreManager
state_store_manager = StateStoreManager()
