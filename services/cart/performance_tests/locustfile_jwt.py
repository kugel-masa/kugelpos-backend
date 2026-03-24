"""
Locust performance test for Cart Service - JWT Authentication Mode

This is the JWT equivalent of locustfile.py. It uses terminal JWT tokens
instead of API keys for authentication, eliminating the cart → terminal
HTTP call on every request.

Comparison:
  locustfile.py     - API key auth (X-API-KEY header + terminal_id query param)
  locustfile_jwt.py - JWT auth (Authorization: Bearer header, no terminal_id needed)

The key performance difference:
  API key: Each cart request triggers cart → terminal HTTP call to verify API key
  JWT:     Claims are verified locally, no inter-service HTTP call

Usage:
  locust -f locustfile_jwt.py --host=http://localhost:8003 --headless --users 20 --spawn-rate 2 --run-time 5m
"""

from locust import HttpUser, task, between, events
import time
import logging
import random
import json
import os
import httpx
from config import PerformanceTestConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TERMINALS_CONFIG = None
TERMINAL_POOL = []
# Map terminal_id -> JWT token
JWT_TOKENS = {}


def load_terminals_config():
    """Load terminals configuration from JSON file"""
    global TERMINALS_CONFIG, TERMINAL_POOL
    config_path = os.path.join(os.path.dirname(__file__), "terminals_config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Terminal configuration file not found: {config_path}\n"
            "Please run setup_test_data.py first."
        )
    with open(config_path, "r") as f:
        TERMINALS_CONFIG = json.load(f)
    TERMINAL_POOL = TERMINALS_CONFIG["terminals"]
    logger.info(f"Loaded {len(TERMINAL_POOL)} terminals from configuration")
    return TERMINALS_CONFIG


def acquire_jwt_tokens():
    """
    Pre-acquire JWT tokens for all terminals via POST /auth/token.
    This is done once at test start, not during the test itself.
    """
    global JWT_TOKENS

    # Try multiple URL patterns for terminal service
    terminal_base_url = os.environ.get("BASE_URL_TERMINAL", "http://localhost:8001/api/v1")
    terminal_root = terminal_base_url.replace("/api/v1", "")

    logger.info(f"Acquiring JWT tokens for {len(TERMINAL_POOL)} terminals from {terminal_root}...")

    with httpx.Client(timeout=60.0) as client:
        for i, terminal_info in enumerate(TERMINAL_POOL):
            api_key = terminal_info["api_key"]
            terminal_id = terminal_info["terminal_id"]

            try:
                response = client.post(
                    f"{terminal_root}/api/v1/auth/token",
                    headers={"X-API-KEY": api_key},
                    params={"terminal_id": terminal_id},
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    token = data.get("access_token") or data.get("accessToken")
                    if token:
                        JWT_TOKENS[terminal_id] = token
                    else:
                        logger.error(f"No token in response for {terminal_id}: {response.json()}")
                else:
                    logger.error(f"Failed to get JWT for {terminal_id}: {response.status_code} {response.text[:200]}")
            except Exception as e:
                logger.error(f"Exception getting JWT for {terminal_id}: {e}")

            if (i + 1) % 10 == 0:
                logger.info(f"  Acquired {i + 1}/{len(TERMINAL_POOL)} tokens")

    logger.info(f"JWT tokens acquired: {len(JWT_TOKENS)}/{len(TERMINAL_POOL)}")
    if len(JWT_TOKENS) == 0:
        raise RuntimeError(f"Failed to acquire any JWT tokens from {terminal_root}/api/v1/auth/token")


class CartPerformanceUserJWT(HttpUser):
    """
    Simulates a user performing cart operations using JWT authentication.
    No terminal_id query parameter needed - all context comes from JWT claims.
    """

    wait_time = between(0, 1)
    _user_counter = 0

    def on_start(self):
        config = PerformanceTestConfig.from_env()

        terminal_idx = self.__class__._user_counter % len(TERMINAL_POOL)
        self.__class__._user_counter += 1

        terminal_info = TERMINAL_POOL[terminal_idx]
        self.terminal_id = terminal_info["terminal_id"]
        self.tenant_id = TERMINALS_CONFIG["tenant_id"]

        self.items_per_cart = config.items_per_cart
        self.item_add_interval = config.item_add_interval
        self.post_cancel_wait = config.post_cancel_wait

        # Use JWT token instead of API key
        jwt_token = JWT_TOKENS.get(self.terminal_id)
        if not jwt_token:
            raise RuntimeError(f"No JWT token for terminal {self.terminal_id}")
        self.headers = {"Authorization": f"Bearer {jwt_token}"}

        logger.info(f"JWT User #{self.__class__._user_counter} started with terminal: {self.terminal_id}")

    @task
    def cart_scenario(self):
        cart_id = None
        scenario_start_time = time.time()

        try:
            cart_id = self._create_cart()
            if not cart_id:
                return
            self._add_items(cart_id)
            self._cancel_cart(cart_id)
            time.sleep(self.post_cancel_wait)

            scenario_duration = time.time() - scenario_start_time
            logger.debug(f"JWT Scenario completed in {scenario_duration:.2f}s for cart {cart_id}")

        except Exception as e:
            logger.error(f"JWT Scenario failed for cart {cart_id}: {str(e)}")
            raise

    def _create_cart(self) -> str:
        create_req = {
            "transaction_type": 101,
            "user_id": f"jwt_perf_{int(time.time())}",
            "user_name": "JWT Performance Test User"
        }

        # JWT auth: no terminal_id query param needed
        with self.client.post(
            "/api/v1/carts",
            json=create_req,
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/carts (Create Cart)"
        ) as response:
            if response.status_code == 201:
                cart_id = response.json()["data"]["cartId"]
                response.success()
                return cart_id
            else:
                response.failure(f"Failed: {response.status_code} - {response.text}")
                return None

    def _add_items(self, cart_id: str):
        item_indices = random.sample(range(100), self.items_per_cart)

        for i, item_idx in enumerate(item_indices):
            item_data = [{
                "item_code": f"ITEM{item_idx:03d}",
                "quantity": 1,
                "unit_price": 100 + item_idx
            }]

            # JWT auth: no terminal_id query param needed
            with self.client.post(
                f"/api/v1/carts/{cart_id}/lineItems",
                json=item_data,
                headers=self.headers,
                catch_response=True,
                name="POST /api/v1/carts/[cart_id]/lineItems (Add Item)"
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Failed: {response.status_code} - {response.text}")
                    raise Exception(f"Failed to add item {i+1}")

            if i < self.items_per_cart - 1:
                time.sleep(self.item_add_interval)

    def _cancel_cart(self, cart_id: str):
        # JWT auth: no terminal_id query param needed
        with self.client.post(
            f"/api/v1/carts/{cart_id}/cancel",
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/carts/[cart_id]/cancel (Cancel Cart)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed: {response.status_code} - {response.text}")
                raise Exception("Failed to cancel cart")


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    try:
        config_data = load_terminals_config()
        acquire_jwt_tokens()

        logger.info("=" * 80)
        logger.info("Performance Test Starting - JWT Authentication Mode")
        logger.info(f"  Tenant ID: {config_data['tenant_id']}")
        logger.info(f"  Terminals: {len(TERMINAL_POOL)}")
        logger.info(f"  JWT Tokens: {len(JWT_TOKENS)}")
        logger.info(f"  Target: {environment.host}")
        logger.info("=" * 80)
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise


@events.test_stop.add_listener
def on_test_stop(environment, **_kwargs):
    logger.info("=" * 80)
    logger.info("Performance Test Completed - JWT Authentication Mode")
    logger.info(f"Total users: {CartPerformanceUserJWT._user_counter}")
    logger.info("=" * 80)
