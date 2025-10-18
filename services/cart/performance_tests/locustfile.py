# Copyright 2025 masa@kugel
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
Locust performance test for Cart Service

This test simulates the following scenario:
1. Create a cart
2. Add 20 items (with 5 second intervals)
3. Cancel the cart
4. Wait 5 seconds before repeating

Test can be run in two modes:
- Web UI mode: locust -f locustfile.py --host=http://localhost:8003
- Headless mode: locust -f locustfile.py --host=http://localhost:8003 --users 20 --spawn-rate 2 --run-time 5m --headless
"""

from locust import HttpUser, task, between, events
import os
import time
import logging
from config import PerformanceTestConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CartPerformanceUser(HttpUser):
    """
    Simulates a user performing cart operations
    """

    # Wait time between tasks (0-1 seconds)
    wait_time = between(0, 1)

    def on_start(self):
        """
        Called when a simulated user starts executing tasks.
        Sets up authentication and configuration.
        """
        # Load configuration
        config = PerformanceTestConfig.from_env()

        self.api_key = config.api_key
        self.tenant_id = config.tenant_id
        self.items_per_cart = config.items_per_cart
        self.item_add_interval = config.item_add_interval
        self.post_cancel_wait = config.post_cancel_wait

        self.headers = {"X-API-KEY": self.api_key}

        logger.info(f"User started with config: items={self.items_per_cart}, "
                   f"interval={self.item_add_interval}s, wait={self.post_cancel_wait}s")

    @task
    def cart_scenario(self):
        """
        Main test scenario:
        1. Create cart
        2. Add items (configurable count with configurable intervals)
        3. Cancel cart
        4. Wait before repeating
        """
        cart_id = None
        scenario_start_time = time.time()

        try:
            # Step 1: Create cart
            cart_id = self._create_cart()
            if not cart_id:
                return

            # Step 2: Add items
            self._add_items(cart_id)

            # Step 3: Cancel cart
            self._cancel_cart(cart_id)

            # Step 4: Post-cancel wait
            time.sleep(self.post_cancel_wait)

            scenario_duration = time.time() - scenario_start_time
            logger.info(f"Scenario completed in {scenario_duration:.2f}s for cart {cart_id}")

        except Exception as e:
            logger.error(f"Scenario failed for cart {cart_id}: {str(e)}")
            raise

    def _create_cart(self) -> str:
        """
        Create a new cart

        Returns:
            cart_id if successful, None otherwise
        """
        create_req = {
            "transaction_type": "sales",
            "user_id": f"perf_user_{int(time.time())}",
            "user_name": "Performance Test User"
        }

        with self.client.post(
            "/api/v1/carts",
            json=create_req,
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/carts (Create Cart)"
        ) as response:
            if response.status_code == 201:
                cart_id = response.json()["data"]["cart_id"]
                response.success()
                logger.debug(f"Cart created: {cart_id}")
                return cart_id
            else:
                response.failure(f"Failed to create cart: {response.status_code} - {response.text}")
                logger.error(f"Cart creation failed: {response.status_code}")
                return None

    def _add_items(self, cart_id: str):
        """
        Add items to the cart

        Args:
            cart_id: The cart ID to add items to
        """
        for i in range(self.items_per_cart):
            item_data = [{
                "item_code": f"ITEM{i:03d}",
                "quantity": 1,
                "unit_price": 100 + i  # Varying price for diversity
            }]

            with self.client.post(
                f"/api/v1/carts/{cart_id}/lineItems",
                json=item_data,
                headers=self.headers,
                catch_response=True,
                name="POST /api/v1/carts/[cart_id]/lineItems (Add Item)"
            ) as response:
                if response.status_code == 200:
                    response.success()
                    logger.debug(f"Item {i+1}/{self.items_per_cart} added to cart {cart_id}")
                else:
                    response.failure(f"Failed to add item: {response.status_code} - {response.text}")
                    logger.error(f"Item add failed for cart {cart_id}: {response.status_code}")
                    raise Exception(f"Failed to add item {i+1}")

            # Wait between item additions (except after the last item)
            if i < self.items_per_cart - 1:
                time.sleep(self.item_add_interval)

    def _cancel_cart(self, cart_id: str):
        """
        Cancel the cart

        Args:
            cart_id: The cart ID to cancel
        """
        with self.client.post(
            f"/api/v1/carts/{cart_id}/cancel",
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/carts/[cart_id]/cancel (Cancel Cart)"
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug(f"Cart cancelled: {cart_id}")
            else:
                response.failure(f"Failed to cancel cart: {response.status_code} - {response.text}")
                logger.error(f"Cart cancel failed: {response.status_code}")
                raise Exception("Failed to cancel cart")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Called when the test starts
    """
    config = PerformanceTestConfig.from_env()
    logger.info("=" * 80)
    logger.info("Performance Test Starting")
    logger.info(f"Configuration:")
    logger.info(f"  - Items per cart: {config.items_per_cart}")
    logger.info(f"  - Item add interval: {config.item_add_interval}s")
    logger.info(f"  - Post-cancel wait: {config.post_cancel_wait}s")
    logger.info(f"  - Target host: {environment.host}")
    logger.info("=" * 80)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Called when the test stops
    """
    logger.info("=" * 80)
    logger.info("Performance Test Completed")
    logger.info("=" * 80)
