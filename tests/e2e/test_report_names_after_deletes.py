# Copyright 2026 masa@kugel
"""A past report keeps the names of masters deleted since (issue #326).

master-data deletes logically by default (issue #324) and hides deleted
records from its default reads. A report run after the sale names:
- the category from master-data, deleted ones included;
- the item from the transaction log, as it was sold;
- the payment method from master-data, else from the transaction log.
"""
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

PROVISIONING_HEADERS = {
    "X-Provisioning-Key": os.environ.get(
        "TENANT_PROVISIONING_KEY", "dev-tenant-provisioning-key-for-development-only"
    )
}
STORE = "5001"


def _app_business_date() -> str:
    return datetime.now(ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tokyo"))).strftime("%Y%m%d")


def _client(url_env: str) -> httpx.Client:
    return httpx.Client(base_url=os.environ[url_env], timeout=30.0)


def _admin_token(tenant_id: str) -> str:
    with _client("URL_ACCOUNT") as c:
        c.post("/api/v1/accounts/register", headers=PROVISIONING_HEADERS, json={
            "username": "admin", "password": "admin", "tenant_id": tenant_id,
        })
        resp = c.post("/api/v1/accounts/token", data={
            "username": "admin", "password": "admin", "client_id": tenant_id,
        })
        resp.raise_for_status()
        return resp.json()["access_token"]


def _send(method: str, url_env: str, path: str, headers: dict, json: dict | None = None, ok=(200, 201)) -> httpx.Response:
    with _client(url_env) as c:
        resp = c.request(method, path, json=json, headers=headers)
    assert resp.status_code in ok, f"{method} {path} -> {resp.status_code}: {resp.text}"
    return resp


def _sell(tenant_id: str, headers: dict) -> None:
    """Seed the masters, open a terminal and sell one item paid by method 12 (named "Gift Card")."""
    t = f"/api/v1/tenants/{tenant_id}"
    _send("POST", "URL_TERMINAL", "/api/v1/tenants", headers, {
        "tenant_id": tenant_id, "tenant_name": "Report Names", "stores": [], "tags": ["e2e-report-names"],
    })
    _send("POST", "URL_MASTER_DATA", f"{t}/staff", headers, {"id": "S001", "name": "Names Staff", "roles": ["staff"]})
    _send("POST", "URL_MASTER_DATA", f"{t}/categories", headers, {
        "categoryCode": "DC1", "description": "Deletable Category", "descriptionShort": "DC", "taxCode": "01",
    })
    _send("POST", "URL_MASTER_DATA", f"{t}/items", headers, {
        "itemCode": "DI1", "description": "Deletable Item", "unitPrice": 100.0, "unitCost": 50.0,
        "taxCode": "01", "categoryCode": "DC1", "itemDetails": [], "imageUrls": [],
    })
    _send("POST", "URL_MASTER_DATA", f"{t}/payments", headers, {
        "paymentCode": "12", "description": "Gift Card", "limitAmount": 0.0, "canRefund": True,
        "canDepositOver": False, "canChange": False, "isActive": True,
    })
    _send("POST", "URL_TERMINAL", f"{t}/stores", headers, {"store_code": STORE, "store_name": "Names Store", "tags": []})

    with _client("URL_TERMINAL") as c:
        resp = c.post("/api/v1/terminals", json={"store_code": STORE, "terminal_no": 1, "description": "Names"},
                      headers=headers)
        assert resp.status_code == 201, resp.text
        terminal_id, api_key = resp.json()["data"]["terminalId"], resp.json()["data"]["apiKey"]
        resp = c.post(f"/api/v1/auth/token?terminal_id={terminal_id}", headers={"X-API-KEY": api_key})
        assert resp.status_code == 200, resp.text
        jwt = resp.json()["data"]["access_token"]
        resp = c.post(f"/api/v1/terminals/{terminal_id}/sign-in", json={"staff_id": "S001"},
                      headers={"Authorization": f"Bearer {jwt}"})
        assert resp.status_code == 200, resp.text
        jwt = resp.headers.get("x-new-token", jwt)
        resp = c.post(f"/api/v1/terminals/{terminal_id}/open", json={"initial_amount": 0.0},
                      headers={"Authorization": f"Bearer {jwt}"})
        assert resp.status_code == 200, resp.text

    key = {"X-API-KEY": api_key}
    q = f"terminal_id={terminal_id}"
    with _client("URL_CART") as c:
        resp = c.post(f"/api/v1/carts?{q}", json={"operator_code": "S001", "operator_name": "Names Staff"}, headers=key)
        assert resp.status_code == 201, resp.text
        cart = f"/api/v1/carts/{resp.json()['data']['cartId']}"
        resp = c.post(f"{cart}/lineItems?{q}", json=[{"itemCode": "DI1", "quantity": 1}], headers=key)
        assert resp.status_code == 200, resp.text
        resp = c.post(f"{cart}/subtotal?{q}", headers=key)
        assert resp.status_code == 200, resp.text
        balance = resp.json()["data"]["balanceAmount"]
        resp = c.post(f"{cart}/payments?{q}", json=[{"paymentCode": "12", "amount": balance}], headers=key)
        assert resp.status_code == 200, resp.text
        resp = c.post(f"{cart}/bill?{q}", headers=key)
        assert resp.status_code == 200, resp.text


def _payments(report: dict) -> list:
    return [(p["paymentCode"], p["paymentName"]) for p in report.get("paymentSummary") or []]


def _report(tenant_id: str, headers: dict, report_type: str) -> dict:
    with _client("URL_REPORT") as c:
        resp = c.get(
            f"/api/v1/tenants/{tenant_id}/stores/{STORE}/reports",
            params={"report_scope": "flash", "report_type": report_type,
                    "business_date": _app_business_date(), "open_counter": 1},
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_reports_name_masters_deleted_after_the_sale(wait_for):
    tenant_id = "RNM" + uuid.uuid4().hex[:8].upper()
    headers = {"Authorization": f"Bearer {_admin_token(tenant_id)}"}
    _sell(tenant_id, headers)

    wait_for(
        lambda: _payments(_report(tenant_id, headers, "payment")),
        timeout=15.0,
        description="the sale to reach the report service",
    )
    t = f"/api/v1/tenants/{tenant_id}"
    for path in ("/categories/DC1", "/items/DI1", "/payments/12"):
        _send("DELETE", "URL_MASTER_DATA", f"{t}{path}", headers)
    # Deleted is hidden from master-data's default reads
    _send("GET", "URL_MASTER_DATA", f"{t}/categories/DC1", headers, ok=(404,))

    categories = _report(tenant_id, headers, "category")["categories"]
    assert [(c["categoryCode"], c["categoryName"]) for c in categories] == [("DC1", "Deletable Category")]

    item_categories = _report(tenant_id, headers, "item")["categories"]
    assert item_categories[0]["categoryName"] == "Deletable Category"
    assert [(i["itemCode"], i["itemName"]) for i in item_categories[0]["items"]] == [("DI1", "Deletable Item")]

    assert _payments(_report(tenant_id, headers, "payment")) == [("12", "Gift Card")]
