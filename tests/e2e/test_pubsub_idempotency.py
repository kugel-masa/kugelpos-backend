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

import httpx
import pytest


def _client(url_env: str) -> httpx.Client:
    return httpx.Client(base_url=os.environ[url_env], timeout=30.0)


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
        "business_date": datetime.now().strftime("%Y%m%d"),
        "open_counter": 1,
        "business_counter": 1,
        "generate_date_time": datetime.now().isoformat(),
    }
    with _client(url_env) as c:
        resp = c.post(path, json={"data": payload_data})
    # Endpoint may return 200 (with status:"DROP") or 400 depending on
    # error path; both prove the contract is enforced.
    assert resp.status_code in (200, 400), resp.text
    body = resp.json()
    if isinstance(body, list):
        body = body[0]
    text = (body.get("message") or "").lower() + (body.get("status") or "").lower()
    assert "drop" in text or "event_id" in text or "required" in text, body
