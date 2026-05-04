# Copyright 2026 masa@kugel
"""Top-level e2e test conftest.

Drives the full docker-compose stack via raw httpx clients pointed at
the published service ports. Loads .env.test from the project root so
TENANT_ID / MONGODB_URI / etc. line up with the per-service e2e tier.

`wait_for` is exposed as a session-scoped fixture so test files can poll
for Dapr-mediated fan-out instead of using fixed `time.sleep` calls.
"""
import os
import time
from pathlib import Path
from typing import Callable, TypeVar

import pytest
from dotenv import load_dotenv


T = TypeVar("T")


@pytest.fixture(scope="session", autouse=True)
def _load_env():
    # tests/e2e/conftest.py -> tests/e2e -> tests -> repo root
    root = Path(__file__).parent.parent.parent
    load_dotenv(root / ".env.test", override=True)
    # Default service URLs for local docker-compose
    os.environ.setdefault("URL_ACCOUNT", "http://localhost:8000")
    os.environ.setdefault("URL_TERMINAL", "http://localhost:8001")
    os.environ.setdefault("URL_MASTER_DATA", "http://localhost:8002")
    os.environ.setdefault("URL_CART", "http://localhost:8003")
    os.environ.setdefault("URL_REPORT", "http://localhost:8004")
    os.environ.setdefault("URL_JOURNAL", "http://localhost:8005")
    os.environ.setdefault("URL_STOCK", "http://localhost:8006")
    yield


def pytest_collection_modifyitems(config, items):
    """Auto-mark every test in this directory with `e2e`."""
    for item in items:
        item.add_marker(pytest.mark.e2e)


def _wait_for(
    predicate: Callable[[], T],
    *,
    timeout: float = 15.0,
    interval: float = 0.25,
    description: str = "condition",
) -> T:
    """Poll `predicate` until it returns truthy; raise on timeout.

    Replaces fixed-duration `time.sleep` after Dapr-mediated fan-out
    (cart -> journal/report/stock). Polling cuts the steady-state wait
    when the event arrives early and surfaces a meaningful error if it
    never arrives, instead of silently passing on a stale assertion
    that the sleep happened to outlast.
    """
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(
        f"timed out after {timeout}s waiting for {description} (last={last!r})"
    )


@pytest.fixture(scope="session")
def wait_for():
    """Polling helper — see `_wait_for` for semantics."""
    return _wait_for
