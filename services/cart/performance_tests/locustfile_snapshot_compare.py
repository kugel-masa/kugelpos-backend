# Copyright 2026 masa@kugel
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
Locust A/B comparison: snapshot-absent (legacy/cache) vs snapshot-carried
(stateless) cart path (issue #156).

A SINGLE run exercises BOTH paths at once so they share the same stack, time
window, terminal pool, and load mix — the cleanest controlled comparison:

  - LegacyCartUser     : bare request bodies → cache-authoritative path.
  - StatelessCartUser  : every mutating request carries the last response's
                         signedSnapshot in a wrapped body
                         ({signedSnapshot, payload}) → the backend reconstructs
                         the cart from it and never reads the cache.

Both run the same scenario (create → add N items → cancel). Request names are
prefixed with "[legacy]" / "[stateless]" so the stats/HTML/CSV separate the two
paths side by side.

Run (after `run_perf_test.sh setup`):
    ./scripts/run_perf_test.sh custom 40 5m --compare
or directly:
    pipenv run locust -f locustfile_snapshot_compare.py --host=http://localhost:8003 \
        --users 40 --spawn-rate 4 --run-time 5m --headless

REQUIRES: the cart service must have SNAPSHOT_HMAC_KEYS configured, otherwise
mutating responses carry no snapshot and the stateless path cannot run (the
test fails those requests loudly instead of silently degrading to legacy).
"""

from locust import HttpUser, task, between, events
import time
import logging
import random
import json
import os
from config import PerformanceTestConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global terminal configuration (loaded at test start).
TERMINALS_CONFIG = None
TERMINAL_POOL = []
# Shared terminal-assignment cursor so legacy and stateless users never collide
# on the same terminal_id (which would mix the two paths on one counter).
_TERMINAL_CURSOR = 0


def load_terminals_config():
    """Load terminals configuration from JSON file (same file as locustfile.py)."""
    global TERMINALS_CONFIG, TERMINAL_POOL

    config_path = os.path.join(os.path.dirname(__file__), "terminals_config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Terminal configuration file not found: {config_path}\n"
            "Please run setup_test_data.py (or run_perf_test.sh setup) first."
        )
    with open(config_path, "r") as f:
        TERMINALS_CONFIG = json.load(f)
    TERMINAL_POOL = TERMINALS_CONFIG["terminals"]
    logger.info(f"Loaded {len(TERMINAL_POOL)} terminals from configuration")
    return TERMINALS_CONFIG


class _BaseCartUser(HttpUser):
    """
    Shared cart scenario. Subclasses set MODE / CARRIED to pick the path.
    Marked abstract so Locust does not instantiate the base directly.
    """

    abstract = True
    wait_time = between(0, 1)

    # Overridden by subclasses.
    MODE = "legacy"
    CARRIED = False

    def on_start(self):
        global _TERMINAL_CURSOR
        config = PerformanceTestConfig.from_env()

        # Round-robin over a SHARED cursor so the two user types take distinct
        # terminals (no cross-path contention on one terminal counter).
        terminal_idx = _TERMINAL_CURSOR % len(TERMINAL_POOL)
        _TERMINAL_CURSOR += 1
        terminal_info = TERMINAL_POOL[terminal_idx]

        self.api_key = terminal_info["api_key"]
        self.tenant_id = TERMINALS_CONFIG["tenant_id"]
        self.terminal_id = terminal_info["terminal_id"]
        self.terminal_no = terminal_info["terminal_no"]

        self.items_per_cart = config.items_per_cart
        self.item_add_interval = config.item_add_interval
        self.post_cancel_wait = config.post_cancel_wait

        self.headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        logger.info(f"[{self.MODE}] user started on terminal {self.terminal_id}")

    def _n(self, label: str) -> str:
        """Request name tagged with the path so stats separate legacy/stateless."""
        return f"[{self.MODE}] {label}"

    @task
    def cart_scenario(self):
        cart_id = None
        try:
            cart_id, snapshot = self._create_cart()
            if not cart_id:
                return

            item_indices = random.sample(range(100), self.items_per_cart)
            for i, item_idx in enumerate(item_indices):
                snapshot = self._add_item(cart_id, item_idx, snapshot)
                if self.CARRIED and snapshot is None:
                    # No snapshot to carry forward — cannot continue the stateless
                    # chain. Abort this scenario (the failed request is recorded).
                    return
                if i < self.items_per_cart - 1:
                    time.sleep(self.item_add_interval)

            self._cancel_cart(cart_id, snapshot)
            time.sleep(self.post_cancel_wait)
        except Exception as e:
            logger.error(f"[{self.MODE}] scenario failed for cart {cart_id}: {e}")
            raise

    def _create_cart(self):
        """Create a cart (bare body in both modes — no inbound snapshot exists yet)."""
        create_req = {
            "transaction_type": 101,  # sales
            "user_id": f"perf_{self.MODE}_{self.terminal_no}_{int(time.time())}",
            "user_name": f"Perf {self.MODE} T{self.terminal_no}",
        }
        with self.client.post(
            f"/api/v1/carts?terminal_id={self.terminal_id}",
            json=create_req,
            headers=self.headers,
            catch_response=True,
            name=self._n("POST /api/v1/carts (Create Cart)"),
        ) as response:
            if response.status_code != 201:
                response.failure(f"Create failed: {response.status_code} - {response.text[:200]}")
                return None, None
            data = response.json()["data"]
            snapshot = data.get("signedSnapshot")
            if self.CARRIED and snapshot is None:
                response.failure("Stateless mode but create response carried no snapshot (signer disabled?)")
                return None, None
            response.success()
            return data["cartId"], snapshot

    def _add_item(self, cart_id: str, item_idx: int, snapshot):
        """Add one item. In CARRIED mode wrap the prior snapshot and return the new one."""
        item = [{"item_code": f"ITEM{item_idx:03d}", "quantity": 1, "unit_price": 100 + item_idx}]
        body = {"signedSnapshot": snapshot, "payload": item} if self.CARRIED else item

        with self.client.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={self.terminal_id}",
            json=body,
            headers=self.headers,
            catch_response=True,
            name=self._n("POST /api/v1/carts/[cart_id]/lineItems (Add Item)"),
        ) as response:
            if response.status_code != 200:
                response.failure(f"Add item failed: {response.status_code} - {response.text[:200]}")
                raise Exception("add item failed")
            new_snapshot = response.json()["data"].get("signedSnapshot")
            if self.CARRIED and new_snapshot is None:
                response.failure("Stateless mode but add-item response carried no snapshot")
            else:
                response.success()
            return new_snapshot

    def _cancel_cart(self, cart_id: str, snapshot):
        """Cancel the cart. In CARRIED mode carry the latest snapshot (body-less op)."""
        kwargs = {"headers": self.headers, "catch_response": True, "name": self._n("POST /api/v1/carts/[cart_id]/cancel (Cancel Cart)")}
        if self.CARRIED:
            # {signedSnapshot} with no payload → middleware forwards a body-less cancel.
            kwargs["json"] = {"signedSnapshot": snapshot}
        with self.client.post(
            f"/api/v1/carts/{cart_id}/cancel?terminal_id={self.terminal_id}",
            **kwargs,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Cancel failed: {response.status_code} - {response.text[:200]}")
                raise Exception("cancel failed")


class LegacyCartUser(_BaseCartUser):
    """Snapshot-absent path: bare bodies, cache-authoritative."""

    MODE = "legacy"
    CARRIED = False


class StatelessCartUser(_BaseCartUser):
    """Snapshot-carried path: wrapped bodies, reconstruct-from-snapshot."""

    MODE = "stateless"
    CARRIED = True


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    config_data = load_terminals_config()
    logger.info("=" * 80)
    logger.info("Snapshot A/B comparison: legacy (no snapshot) vs stateless (carried)")
    logger.info(f"  Tenant: {config_data['tenant_id']}  Store: {config_data['store_code']}")
    logger.info(f"  Terminals: {len(TERMINAL_POOL)}  Host: {environment.host}")
    logger.info("  Both user types run together; stats are tagged [legacy] / [stateless].")
    logger.info("=" * 80)


@events.test_stop.add_listener
def on_test_stop(environment, **_kwargs):
    logger.info("=" * 80)
    logger.info("Snapshot A/B comparison completed")
    logger.info("Compare the [legacy] vs [stateless] rows in the stats / HTML report.")
    logger.info("=" * 80)
