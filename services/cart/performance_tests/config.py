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
Configuration for Cart Service Performance Tests
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class PerformanceTestConfig:
    """
    Configuration for performance tests

    All parameters can be overridden via environment variables.
    """

    # Authentication
    api_key: str
    tenant_id: str

    # Test scenario parameters
    items_per_cart: int = 20
    item_add_interval: int = 5  # seconds between item additions
    post_cancel_wait: int = 5   # seconds to wait after cart cancellation

    # Test execution parameters
    num_users: int = 20
    spawn_rate: int = 2  # users spawned per second
    run_time: str = "5m"  # test duration

    # Target URL
    base_url: str = "http://localhost:8003"

    @classmethod
    def from_env(cls, env_prefix: str = "PERF_TEST_") -> "PerformanceTestConfig":
        """
        Load configuration from environment variables

        Args:
            env_prefix: Prefix for environment variable names

        Returns:
            PerformanceTestConfig instance

        Environment variables:
            - API_KEY: API key for authentication (required)
            - TENANT_ID: Tenant ID (required)
            - PERF_TEST_ITEMS_PER_CART: Number of items to add per cart (default: 20)
            - PERF_TEST_ITEM_ADD_INTERVAL: Seconds between item additions (default: 5)
            - PERF_TEST_POST_CANCEL_WAIT: Seconds to wait after cart cancel (default: 5)
            - PERF_TEST_NUM_USERS: Number of concurrent users (default: 20)
            - PERF_TEST_SPAWN_RATE: Users spawned per second (default: 2)
            - PERF_TEST_RUN_TIME: Test duration (default: 5m)
            - BASE_URL_CART: Target URL (default: http://localhost:8003)
        """

        # Required parameters
        api_key = os.environ.get("API_KEY")
        if not api_key:
            raise ValueError("API_KEY environment variable is required")

        tenant_id = os.environ.get("TENANT_ID")
        if not tenant_id:
            raise ValueError("TENANT_ID environment variable is required")

        # Optional parameters with defaults
        items_per_cart = int(os.environ.get(f"{env_prefix}ITEMS_PER_CART", "20"))
        item_add_interval = int(os.environ.get(f"{env_prefix}ITEM_ADD_INTERVAL", "5"))
        post_cancel_wait = int(os.environ.get(f"{env_prefix}POST_CANCEL_WAIT", "5"))
        num_users = int(os.environ.get(f"{env_prefix}NUM_USERS", "20"))
        spawn_rate = int(os.environ.get(f"{env_prefix}SPAWN_RATE", "2"))
        run_time = os.environ.get(f"{env_prefix}RUN_TIME", "5m")
        base_url = os.environ.get("BASE_URL_CART", "http://localhost:8003")

        return cls(
            api_key=api_key,
            tenant_id=tenant_id,
            items_per_cart=items_per_cart,
            item_add_interval=item_add_interval,
            post_cancel_wait=post_cancel_wait,
            num_users=num_users,
            spawn_rate=spawn_rate,
            run_time=run_time,
            base_url=base_url,
        )

    def to_locust_args(self) -> list[str]:
        """
        Convert configuration to Locust command line arguments

        Returns:
            List of command line arguments for Locust
        """
        return [
            "--host", self.base_url,
            "--users", str(self.num_users),
            "--spawn-rate", str(self.spawn_rate),
            "--run-time", self.run_time,
            "--headless",
            "--only-summary",
        ]


# Predefined test patterns
TEST_PATTERNS = {
    "pattern1": {
        "PERF_TEST_NUM_USERS": "20",
        "PERF_TEST_SPAWN_RATE": "2",
        "PERF_TEST_RUN_TIME": "5m",
        "description": "20 concurrent users for 5 minutes"
    },
    "pattern2": {
        "PERF_TEST_NUM_USERS": "40",
        "PERF_TEST_SPAWN_RATE": "4",
        "PERF_TEST_RUN_TIME": "5m",
        "description": "40 concurrent users for 5 minutes"
    }
}
