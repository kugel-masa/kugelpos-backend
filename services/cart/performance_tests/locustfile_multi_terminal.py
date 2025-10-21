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
Locust performance test for Cart Service - Multi Terminal Version

This test simulates the following scenario:
1. Create a cart
2. Add 20 items (with 5 second intervals)
3. Cancel the cart
4. Wait 5 seconds before repeating

IMPORTANT: Each simulated user uses a DIFFERENT terminal_id to avoid lock contention
on the terminal counter (transaction_no generation).

Test can be run in two modes:
- Web UI mode: locust -f locustfile_multi_terminal.py --host=http://localhost:8003
- Headless mode: locust -f locustfile_multi_terminal.py --host=http://localhost:8003 --users 20 --spawn-rate 2 --run-time 5m --headless
"""

from locust import HttpUser, task, between, events
import time
import logging
import random
import json
import os
from config import PerformanceTestConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global terminal configuration
TERMINALS_CONFIG = None
TERMINAL_POOL = []


def load_terminals_config():
    """Load terminals configuration from JSON file"""
    global TERMINALS_CONFIG, TERMINAL_POOL

    config_path = os.path.join(os.path.dirname(__file__), "terminals_config.json")

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Terminal configuration file not found: {config_path}\n"
            "Please run setup_test_data_multi_terminal.py first to create test terminals."
        )

    with open(config_path, "r") as f:
        TERMINALS_CONFIG = json.load(f)

    TERMINAL_POOL = TERMINALS_CONFIG["terminals"]
    logger.info(f"Loaded {len(TERMINAL_POOL)} terminals from configuration")

    return TERMINALS_CONFIG


class CartPerformanceUserMultiTerminal(HttpUser):
    """
    Simulates a user performing cart operations using a unique terminal
    """

    # Wait time between tasks (0-1 seconds)
    wait_time = between(0, 1)

    # Class-level counter for terminal assignment
    _user_counter = 0

    def on_start(self):
        """
        Called when a simulated user starts executing tasks.
        Sets up authentication and assigns a unique terminal to this user.
        """
        # Load configuration
        config = PerformanceTestConfig.from_env()

        # Assign a unique terminal to this user using round-robin
        terminal_idx = self.__class__._user_counter % len(TERMINAL_POOL)
        self.__class__._user_counter += 1

        terminal_info = TERMINAL_POOL[terminal_idx]

        # Set user configuration
        self.api_key = terminal_info["api_key"]
        self.tenant_id = TERMINALS_CONFIG["tenant_id"]
        self.terminal_id = terminal_info["terminal_id"]
        self.terminal_no = terminal_info["terminal_no"]

        self.items_per_cart = config.items_per_cart
        self.item_add_interval = config.item_add_interval
        self.post_cancel_wait = config.post_cancel_wait

        self.headers = {"X-API-KEY": self.api_key}

        logger.info(f"User #{self.__class__._user_counter} started with terminal: {self.terminal_id}")

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
            logger.debug(f"Scenario completed in {scenario_duration:.2f}s for cart {cart_id} on {self.terminal_id}")

        except Exception as e:
            logger.error(f"Scenario failed for cart {cart_id} on {self.terminal_id}: {str(e)}")
            raise

    def _create_cart(self) -> str:
        """
        Create a new cart

        Returns:
            cart_id if successful, None otherwise
        """
        create_req = {
            "transaction_type": 101,  # 101 = sales
            "user_id": f"perf_user_{self.terminal_no}_{int(time.time())}",
            "user_name": f"Performance Test User T{self.terminal_no}"
        }

        with self.client.post(
            f"/api/v1/carts?terminal_id={self.terminal_id}",
            json=create_req,
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/carts (Create Cart)"
        ) as response:
            if response.status_code == 201:
                cart_id = response.json()["data"]["cartId"]
                response.success()
                logger.debug(f"Cart created: {cart_id} on {self.terminal_id}")
                return cart_id
            else:
                response.failure(f"Failed to create cart: {response.status_code} - {response.text}")
                logger.error(f"Cart creation failed on {self.terminal_id}: {response.status_code}")
                return None

    def _add_items(self, cart_id: str):
        """
        Add items to the cart with random unique items

        Args:
            cart_id: The cart ID to add items to
        """
        # Generate random unique item indices for this cart (avoid duplicates)
        # We have 100 items (ITEM000-ITEM099), so sample randomly without replacement
        item_indices = random.sample(range(100), self.items_per_cart)

        for i, item_idx in enumerate(item_indices):
            item_data = [{
                "item_code": f"ITEM{item_idx:03d}",
                "quantity": 1,
                "unit_price": 100 + item_idx  # Varying price for diversity
            }]

            with self.client.post(
                f"/api/v1/carts/{cart_id}/lineItems?terminal_id={self.terminal_id}",
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
            f"/api/v1/carts/{cart_id}/cancel?terminal_id={self.terminal_id}",
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/carts/[cart_id]/cancel (Cancel Cart)"
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug(f"Cart cancelled: {cart_id} on {self.terminal_id}")
            else:
                response.failure(f"Failed to cancel cart: {response.status_code} - {response.text}")
                logger.error(f"Cart cancel failed for {cart_id}: {response.status_code}")
                raise Exception("Failed to cancel cart")


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    """
    Called when the test starts
    """
    # Load terminals configuration
    try:
        config_data = load_terminals_config()
        logger.info("=" * 80)
        logger.info("Performance Test Starting - Multi Terminal Mode")
        logger.info(f"Configuration:")
        logger.info(f"  - Tenant ID: {config_data['tenant_id']}")
        logger.info(f"  - Store Code: {config_data['store_code']}")
        logger.info(f"  - Available Terminals: {len(TERMINAL_POOL)}")
        logger.info(f"  - Target host: {environment.host}")
        logger.info("=" * 80)
        logger.info("NOTE: Each user will be assigned a unique terminal ID")
        logger.info("      to avoid lock contention on transaction number generation")
        logger.info("=" * 80)
    except Exception as e:
        logger.error(f"Failed to load terminal configuration: {e}")
        raise


@events.test_stop.add_listener
def on_test_stop(environment, **_kwargs):
    """
    Called when the test stops
    """
    logger.info("=" * 80)
    logger.info("Performance Test Completed - Multi Terminal Mode")
    logger.info(f"Total terminals used: {min(len(TERMINAL_POOL), CartPerformanceUserMultiTerminal._user_counter)}")
    logger.info("=" * 80)
