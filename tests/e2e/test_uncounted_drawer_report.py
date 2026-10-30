# Copyright 2026 masa@kugel
"""A session opened without a float and closed without counting the drawer
still has a sales report.

The terminal accepts both: `initial_amount` and `physical_amount` are
optional on the open and close requests. The report summed them as-is, so
once the close log reached the report service every sales report covering
that session failed with a 500.

The report now says the drawer was not counted (`physicalAmount` and
`differenceAmount` are null) instead of failing, and instead of printing
zero, which would read as counted and empty.
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
async def test_sales_report_survives_an_uncounted_drawer(wait_for):
    # No hyphen: terminal_id is "{tenant}-{store}-{no}" and is split on "-".
    tenant_id = "UNC" + uuid.uuid4().hex[:8].upper()
    store_code = "5001"
    terminal_no = 1

    headers = {"Authorization": f"Bearer {_admin_token(tenant_id)}"}

    _post("URL_TERMINAL", "/api/v1/tenants", headers, json={
        "tenant_id": tenant_id, "tenant_name": "Uncounted Drawer Tenant",
        "stores": [], "tags": ["e2e-uncounted-drawer"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/staff", headers, json={
        "id": "S001", "name": "Uncounted Staff", "pin": "1234", "roles": ["staff"],
    })
    _post("URL_TERMINAL", f"/api/v1/tenants/{tenant_id}/stores", headers, json={
        "store_code": store_code, "store_name": "Uncounted Store", "tags": [],
    })

    with _client("URL_TERMINAL") as c:
        resp = c.post(
            "/api/v1/terminals",
            json={"store_code": store_code, "terminal_no": terminal_no, "description": "Uncounted Terminal"},
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

        # Neither the float nor the counted amount is sent; both are optional.
        resp = c.post(f"/api/v1/terminals/{terminal_id}/open", json={}, headers={"Authorization": f"Bearer {jwt}"})
        assert resp.status_code == 200, resp.text
        jwt = resp.headers.get("x-new-token", jwt)

        resp = c.post(f"/api/v1/terminals/{terminal_id}/close", json={}, headers={"Authorization": f"Bearer {jwt}"})
        assert resp.status_code == 200, resp.text

    business_date = _app_business_date()

    def _report_after_close():
        # Until the close log arrives over pub/sub the report has no close to
        # sum and shows 0; once it arrives the drawer is uncounted (or, before
        # the fix, the report fails). Either outcome ends the wait.
        with _client("URL_REPORT") as c:
            r = c.get(
                f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
                params={
                    "report_scope": "flash",
                    "report_type": "sales",
                    "business_date": business_date,
                    "open_counter": 1,
                },
                headers=headers,
            )
        if r.status_code != 200:
            return r
        cash = (r.json().get("data") or {}).get("cash") or {}
        return r if cash.get("physicalAmount", 0) is None else None

    resp = wait_for(_report_after_close, timeout=15.0, description="the close log to reach the sales report")

    assert resp.status_code == 200, resp.text
    cash = resp.json()["data"]["cash"]
    assert cash["physicalAmount"] is None
    assert cash["differenceAmount"] is None
    assert cash["logicalAmount"] == 0
