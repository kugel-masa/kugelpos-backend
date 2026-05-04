# Copyright 2026 masa@kugel
"""Cross-service e2e smoke test: every service exposes a healthy /health.

This is the minimum cross-service contract — if any service is missing
its /health or returns the wrong shape, the rest of the e2e suite is
guaranteed to fail. Lives at the top-level /e2e/ instead of inside any
individual service so it's clearly a system-wide check.
"""
import os

import httpx
import pytest


SERVICES = [
    ("account", "URL_ACCOUNT"),
    ("terminal", "URL_TERMINAL"),
    ("master-data", "URL_MASTER_DATA"),
    ("cart", "URL_CART"),
    ("report", "URL_REPORT"),
    ("journal", "URL_JOURNAL"),
    ("stock", "URL_STOCK"),
]


@pytest.mark.parametrize("service_name,url_env", SERVICES)
def test_service_health_endpoint(service_name, url_env):
    """Every service responds to GET /health with a 200 and the expected
    minimal shape (status / service / version / checks)."""
    base_url = os.environ.get(url_env)
    assert base_url, f"{url_env} not set"

    response = httpx.get(f"{base_url}/health", timeout=10.0)
    assert response.status_code == 200, (
        f"{service_name} /health returned {response.status_code}: {response.text}"
    )
    data = response.json()
    assert data["service"] == service_name
    assert "status" in data
    assert "version" in data
    assert "checks" in data
    # MongoDB is the one universal dependency
    assert "mongodb" in data["checks"]
    assert data["checks"]["mongodb"]["status"] in ("healthy", "unhealthy")


def test_all_services_reachable():
    """Sanity smoke: every service URL responds at all (no DNS / port
    issues), independent of their /health implementation."""
    for service_name, url_env in SERVICES:
        base_url = os.environ.get(url_env)
        try:
            response = httpx.get(f"{base_url}/", timeout=5.0)
        except httpx.RequestError as e:
            pytest.fail(f"{service_name} ({base_url}) unreachable: {e}")
        # Any HTTP response (even 404) means the service is up
        assert response.status_code < 500, (
            f"{service_name} returned 5xx for /: {response.status_code}"
        )
