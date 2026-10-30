# Copyright 2026 masa@kugel
"""A report error reaches the caller with its own status and code.

The report API caught its service exceptions and re-raised them as
HTTPException(detail=<dict>). The shared handler then wrapped that dict a second
time into ApiResponse(message=<dict>), which fails validation, so every report
error - a terminal not yet closed, a report that failed to build - arrived as a
422 "Validation error" with the real code buried in its text.
"""
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest


def _app_business_date() -> str:
    # Same rule as test_pos_full_journey: the backend's timezone, not the host's (#150).
    return datetime.now(ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tokyo"))).strftime("%Y%m%d")


def _client(url_env: str) -> httpx.Client:
    return httpx.Client(base_url=os.environ[url_env], timeout=30.0)


def _admin_token(tenant_id: str) -> str:
    with _client("URL_ACCOUNT") as c:
        c.post("/api/v1/accounts/register", json={
            "username": "admin", "password": "admin", "tenant_id": tenant_id,
        })
        resp = c.post("/api/v1/accounts/token", data={
            "username": "admin", "password": "admin", "client_id": tenant_id,
        })
        resp.raise_for_status()
        return resp.json()["access_token"]


def _post(url_env: str, path: str, headers: dict, json: dict, ok=(200, 201, 400)) -> None:
    with _client(url_env) as c:
        resp = c.post(path, json=json, headers=headers)
    assert resp.status_code in ok, f"{path} -> {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_daily_report_for_an_open_terminal_says_so():
    # No hyphen: terminal_id is "{tenant}-{store}-{no}" and is split on "-".
    tenant_id = "RERR" + uuid.uuid4().hex[:8].upper()
    store_code = "5001"
    terminal_no = 1

    headers = {"Authorization": f"Bearer {_admin_token(tenant_id)}"}

    _post("URL_TERMINAL", "/api/v1/tenants", headers, json={
        "tenant_id": tenant_id, "tenant_name": "Report Error Tenant",
        "stores": [], "tags": ["e2e-report-error"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/staff", headers, json={
        "id": "S001", "name": "Report Error Staff", "pin": "1234", "roles": ["staff"],
    })
    _post("URL_TERMINAL", f"/api/v1/tenants/{tenant_id}/stores", headers, json={
        "store_code": store_code, "store_name": "Report Error Store", "tags": [],
    })

    with _client("URL_TERMINAL") as c:
        resp = c.post(
            "/api/v1/terminals",
            json={"store_code": store_code, "terminal_no": terminal_no, "description": "Report Error Terminal"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        terminal_id = resp.json()["data"]["terminalId"]
        api_key = resp.json()["data"]["apiKey"]

        resp = c.post(f"/api/v1/auth/token?terminal_id={terminal_id}", headers={"X-API-KEY": api_key})
        assert resp.status_code == 200, resp.text
        jwt = resp.json()["data"]["access_token"]

        resp = c.post(
            f"/api/v1/terminals/{terminal_id}/sign-in",
            json={"staff_id": "S001"}, headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200, resp.text
        jwt = resp.headers.get("x-new-token", jwt)

        # Opened and left open: a daily report cannot be built yet.
        resp = c.post(
            f"/api/v1/terminals/{terminal_id}/open",
            json={"initial_amount": 0.0}, headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200, resp.text

    with _client("URL_REPORT") as c:
        resp = c.get(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
            params={"report_scope": "daily", "report_type": "sales", "business_date": _app_business_date()},
            headers=headers,
        )

    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["code"] == 403
    assert body["user_error"]["code"] == "412101"
