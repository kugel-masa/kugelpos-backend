# Copyright 2026 masa@kugel
"""Pub/sub idempotency e2e — verify that the Dapr subscriber endpoints
on the downstream services (journal, report, stock) reject malformed
or duplicate messages and the event_id is required.

Strict end-to-end idempotency proof (same event_id → processed once)
needs a real cart bill to seed Dapr state and is best validated by the
full POS journey test re-running without producing extra journal/report
entries. Here we cover the auth-boundary / shape contracts directly.
"""
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest


def _app_business_date() -> str:
    """Business date in the backend's app timezone. Services compute it via
    settings.TIMEZONE (default Asia/Tokyo), not host-local time, so a UTC
    host must not use datetime.now() here (#150)."""
    return datetime.now(ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tokyo"))).strftime("%Y%m%d")


# What each subscriber's Dapr sidecar sends on every delivery; the routes refuse
# a request without it (issue #134). The development compose default.
APP_API_TOKEN = os.environ.get("APP_API_TOKEN", "dev-app-api-token-for-development-only")


def _client(url_env: str, token: str | None = APP_API_TOKEN) -> httpx.Client:
    headers = {"dapr-api-token": token} if token is not None else {}
    return httpx.Client(base_url=os.environ[url_env], timeout=30.0, headers=headers)


@pytest.mark.parametrize(
    "url_env, path",
    [
        ("URL_JOURNAL", "/api/v1/tranlog"),
        ("URL_JOURNAL", "/api/v1/cashlog"),
        ("URL_JOURNAL", "/api/v1/opencloselog"),
        ("URL_REPORT", "/api/v1/tranlog"),
        ("URL_REPORT", "/api/v1/cashlog"),
        ("URL_REPORT", "/api/v1/opencloselog"),
        ("URL_STOCK", "/api/v1/tranlog"),
    ],
)
def test_dapr_subscriber_health_check(url_env, path):
    """Dapr health-check messages are accepted on every subscriber endpoint
    and short-circuited with status=SUCCESS."""
    with _client(url_env) as c:
        resp = c.post(path, json={"data": {"test": "health-check"}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("status") == "SUCCESS", body


@pytest.mark.parametrize(
    "url_env, path",
    [
        ("URL_JOURNAL", "/api/v1/tranlog"),
        ("URL_JOURNAL", "/api/v1/cashlog"),
        ("URL_JOURNAL", "/api/v1/opencloselog"),
        ("URL_REPORT", "/api/v1/tranlog"),
        ("URL_STOCK", "/api/v1/tranlog"),
    ],
)
def test_dapr_subscriber_drops_missing_event_id(url_env, path):
    """A pubsub message without event_id is dropped (status=DROP). This is
    the contract that prevents Dapr's at-least-once delivery from getting
    stuck on un-processable messages."""
    payload_data = {
        # event_id intentionally omitted
        "tenant_id": "DUMMY",
        "store_code": "5001",
        "terminal_no": 1,
        "transaction_no": 1,
        "transaction_type": 101,
        "business_date": _app_business_date(),
        "open_counter": 1,
        "business_counter": 1,
        "generate_date_time": datetime.now().isoformat(),
    }
    with _client(url_env) as c:
        resp = c.post(path, json={"data": payload_data})
    # Dapr honours DROP only on a 2xx; any non-2xx is retried, so a 400
    # would redeliver a message that can never succeed (#135).
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("status") == "DROP", body


@pytest.mark.parametrize(
    "url_env,path",
    [
        ("URL_JOURNAL", "/api/v1/tranlog"),
        ("URL_JOURNAL", "/api/v1/cashlog"),
        ("URL_JOURNAL", "/api/v1/opencloselog"),
        ("URL_REPORT", "/api/v1/tranlog"),
        ("URL_REPORT", "/api/v1/cashlog"),
        ("URL_REPORT", "/api/v1/opencloselog"),
        ("URL_STOCK", "/api/v1/tranlog"),
    ],
)
@pytest.mark.parametrize("token", [None, "a-token-someone-guessed"], ids=["no token", "wrong token"])
def test_dapr_subscriber_refuses_a_request_not_from_its_sidecar(url_env, path, token):
    # The app port is published; before #134 this event would have been stored
    # in whichever tenant it named. The sales the other e2e tests make still
    # arrive, through the sidecars, which carry the token.
    with _client(url_env, token=token) as c:
        resp = c.post(path, json={"data": {"event_id": f"evt-forged-{uuid.uuid4()}", "tenant_id": "T-FORGED"}})
    assert resp.status_code == 401, resp.text
